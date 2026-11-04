"""Independent captured cost facts against sealed source SQLite and old lineage.

No native library, producer, cost codec, PBF reader or graph search is imported.
"""
from array import array
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import struct
import time

from import_roads import distance_m
from coarse_osm_car_policy_v2 import POLICY, node_policy, restriction_policy, way_policy
from graph_capture_query_oracle_v2 import query_checks

REASONS = [None, 'outside-major-profile', 'vehicle-ferry', 'access', 'area-ford-driveway-parking',
           'conditional-or-way-restriction', 'lane-access', 'unsupported-oneway', 'unsupported-speed', 'directional-access']
TURNS = ['no_left_turn', 'no_right_turn', 'no_straight_on', 'no_u_turn', 'no_entry', 'no_exit',
         'only_left_turn', 'only_right_turn', 'only_straight_on', 'only_u_turn']
WAY = struct.Struct('<QddII');ARC = struct.Struct('<IIIIIb3xQ');TURN = struct.Struct('<QQQQB7x')


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream, 'sha256').hexdigest()


def audit():
    began = time.monotonic();repo = Path('/repo')
    root = repo/'data/coarse-quality/us-osm-car-cost-graph-captured-v5'
    result = json.loads((root/'audit.json').read_bytes());facts = root/'cost-facts';counts = result['facts']
    assert result['receipt']['nativeEof'] and result['receipt']['pythonProjectionFrames'] == 0
    assert result['receipt']['semanticSha256'] == result['conversion']['semanticSha256']
    def load(prefix, code=None):
        paths = sorted(facts.glob(prefix+'-*.bin'))
        assert all(p.is_file() and not p.is_symlink() and p.stat().st_size <= 16*1048576 for p in paths)
        raw = b''.join(p.read_bytes() for p in paths)
        if code is None:return raw
        out = array(code);out.frombytes(raw);return out
    def original(name, code):
        out = array(code);out.frombytes((repo/'data/coarse-quality/us-osm-lineage-run-v1'/name).read_bytes());return out
    path = repo/'data/coarse-quality/us-osm-disk-capture-run-v1/extract/audit-selected.sqlite'
    closed = json.loads((repo/'docs/evidence/coarse-osm-extraction-2026-10-30/disk-capture-closed-run-v1.json').read_bytes())
    pin = closed['roster']['extract/audit-selected.sqlite'];assert path.stat().st_size == pin['bytes'] and sha(path) == pin['sha256']
    db = sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1', uri=True);db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-16384')
    all_ids = array('Q', (row[0] for row in db.execute("SELECT id FROM objects WHERE kind='node' ORDER BY id")))
    selected = original('provenance/selected-nodes.u32', 'I');source_vertices = original('provenance/vertices.u32', 'I')
    ids = load('ids', 'Q');xy = load('xy', 'i');anchors = load('anchors', 'I');geometry = load('geometry', 'I')
    assert len(all_ids) == 1123919 and ids == array('Q', (all_ids[i] for i in selected)) and len(ids) == 143560
    assert xy == original('geometry/xy.i32', 'i') and len(xy) == 2*len(ids)
    source_position = {source: i for i, source in enumerate(selected)}
    old_flags = (repo/'data/coarse-quality/us-osm-car-run-v1/routing/node-flags.u8').read_bytes()
    assert len(old_flags) == len(source_vertices) == 53672 and all(flag == 0 for flag in old_flags if not flag & 4)
    assert anchors == array('I', (source_position[source] for source,flag in zip(source_vertices,old_flags) if flag & 4)) and len(anchors) == 46881
    positions = {identity: i for i, identity in enumerate(ids)};vertex = {ids[node]: i for i, node in enumerate(anchors)}
    closures = set();closed_nodes = set();turns = [];source_rules = [];relations = invalid = unsupported = member_occurrences = 0
    for raw, in db.execute("SELECT raw FROM objects WHERE kind='relation' ORDER BY id"):
        row = json.loads(raw);relations += 1;decision = restriction_policy(row)
        if decision['status'] == 'closed-unsupported':
            unsupported += 1;closures.update(decision['memberWays']);member_occurrences += sum(m['type'] == 'way' for m in row['members'])
            if not decision['memberWays']:closed_nodes.update(decision['memberNodes'])
        elif decision['status'] == 'via-node':
            source_rules.append(decision);turns.append((row['id'], decision['fromWay'], decision['via'], decision['toWay'], TURNS.index(decision['kind'])))
        elif decision['status'] == 'invalid-unlocatable':invalid += 1
    assert relations == 4900 and invalid == counts['invalidUnlocatableRestrictions'] == 0 and load('invalid') == b''
    assert list(TURN.iter_unpack(load('turns'))) == turns and load('closures', 'Q') == array('Q', sorted(closures))
    assert counts['supportedViaNodeRules'] == len(turns) and counts['unsupportedRelations'] == unsupported
    assert counts['unsupportedWayMemberOccurrences'] == member_occurrences and counts['uniqueUnsupportedMemberWays'] == len(closures)
    flags = load('flags');assert len(flags) == len(anchors)
    for ordinal, node in enumerate(anchors):
        raw = db.execute("SELECT raw FROM objects WHERE kind='node' AND id=?", (ids[node],)).fetchone()[0]
        decision = node_policy(json.loads(raw)['tags'])
        assert flags[ordinal] == 4 | int(decision['blocked'] or ids[node] in closed_nodes) | 2*int(decision['signal'])
    way_rows = iter(WAY.iter_unpack(load('ways')));arc_rows = iter(ARC.iter_unpack(load('arcs')))
    cursor = examined = major = physical = pre = post = pre_overflow = post_overflow = 0
    all_arcs = [];way_ids = [];fragments = {}
    pre_roles = Counter();post_roles = Counter();reasons = Counter()
    for raw, in db.execute("SELECT raw FROM objects WHERE kind='way' ORDER BY id"):
        row = json.loads(raw);examined += 1;policy = way_policy(row['tags']);reasons[str(policy.reason or 'eligible')] += 1
        if row['tags'].get('highway') not in POLICY['roles']:continue
        way_ids.append(row['id'])
        stored = next(way_rows);refs = row['nodes'];indices = [positions[n] for n in refs]
        assert stored[0] == row['id'] and stored[-1] == cursor+len(refs)
        assert geometry[cursor:stored[-1]] == array('I', indices);cursor = stored[-1]
        role = POLICY['roles'].index(row['tags']['highway'])
        expected_flags = int(policy.forward is not None) | 2*int(policy.backward is not None) | 4*int(policy.forward_default) | 8*int(policy.backward_default) | role << 4 | REASONS.index(policy.reason) << 8
        assert stored[3] == expected_flags
        for slot, speed in enumerate((policy.forward, policy.backward), 1):
            if speed is not None:assert stored[slot] == speed
        cuts = [i for i, node in enumerate(refs) if node in vertex]
        assert cuts[0] == 0 and cuts[-1] == len(refs)-1
        for first, last in zip(cuts, cuts[1:]):
            if all(node == refs[first] for node in refs[first:last+1]):continue
            physical += 1
            span = (major,first,last);fragment = {'chain':tuple(refs[first:last+1]),'prefix':{}};fragments[span] = fragment
            for direction, speed in ((1, policy.forward), (-1, policy.backward)):
                if speed is None:continue
                milliseconds = 0;prefix = [0]
                for i in range(first, last):
                    a, b = indices[i], indices[i+1]
                    p, q = [xy[2*a]/1e7, xy[2*a+1]/1e7], [xy[2*b]/1e7, xy[2*b+1]/1e7]
                    milliseconds += 0 if refs[i] == refs[i+1] else max(1, math.ceil(distance_m(p, q)*3600/speed))
                    prefix.append(milliseconds)
                tail, head = (refs[first], refs[last]) if direction == 1 else (refs[last], refs[first])
                stored_arc = next(arc_rows)
                assert stored_arc == (vertex[tail], vertex[head], major, first, last, direction, milliseconds)
                all_arcs.append(stored_arc);fragment['prefix'][direction] = prefix
                overflow = (milliseconds+124)//125 >= 65535
                pre += 1;pre_overflow += overflow;pre_roles[role] += 1
                if row['id'] not in closures:post += 1;post_overflow += overflow;post_roles[role] += 1
        major += 1
    assert next(way_rows, None) is None and next(arc_rows, None) is None and cursor == len(geometry) == 177956
    assert (examined, major, physical, post) == (239253, 28995, 52282, 75137)
    for key, expected in (('preClosureArcs', pre), ('postClosureArcs', post), ('preClosureCostOverflows', pre_overflow), ('postClosureCostOverflows', post_overflow)):
        assert counts[key] == expected
    assert counts['wayReasons'] == {str(reason or 'eligible'): reasons[str(reason or 'eligible')] for reason in REASONS}
    assert counts['preClosureArcsByRole'] == {role: pre_roles[i] for i, role in enumerate(POLICY['roles'])}
    assert counts['postClosureArcsByRole'] == {role: post_roles[i] for i, role in enumerate(POLICY['roles'])}
    assert counts['outputBytes'] == sum(p.stat().st_size for p in facts.iterdir())
    db.close()
    original_cases = json.loads((repo/'docs/evidence/coarse-osm-car-prototype-2026-11-01/car-raw/run-v1/report.json').read_bytes())['queries']
    queries = query_checks(ids,xy,anchors,flags,way_ids,all_arcs,fragments,closures,source_rules,original_cases)
    assert queries['originalDirectionalCases'] == 82 and queries['unreachableCasesPreserved'] == 14
    return {'status': 'independent_complete_captured_native_cost_fact_audit_passed', 'selectedNativeCoordinatesChecked': len(ids),
            'anchorsAndFlagsChecked': len(anchors), 'sourceWaysExamined': examined, 'majorWayGeometryMetadataChecked': major,
            'sourceGeometryReferencesChecked': cursor, 'physicalSegmentsChecked': physical, 'preClosureArcCostsChecked': pre,
            'postClosureArcCostsChecked': post, 'supportedSourceTurnsChecked': len(turns), 'relationsExamined': relations,
            'queries': queries, 'secondsIncludingSourceHashesAllFieldsAndOriginalQueries': time.monotonic()-began, 'sourcePbfReads': 0, 'nativeLibraryExecutions': 0,
            'networkRequests': 0, 'applicationDbReads': 0, 'countryArtifactBuilt': False, 'modelChanged': False}
