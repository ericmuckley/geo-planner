"""Independent typed national identity/anchor/geometry/cost-fact audit.

No PBF, native library, producer or national node dictionary. Raw coordinate/tag
ingestion still relies on the qualified source/consumer and original full seals;
this is an independent derived-artifact audit, not a second raw-source decoder.
"""
from array import array
import heapq
import json
import math
from pathlib import Path
import struct
import time

from import_roads import distance_m
from coarse_osm_car_policy_v2 import POLICY
from coarse_osm_country_wire_v4 import decode_frame

REF = struct.Struct('<QQII');Q = struct.Struct('<Q');I = struct.Struct('<I')
WAY = struct.Struct('<QddII');PARENT = struct.Struct('<QQQII')
ARC = struct.Struct('<IIIIIb3sQ');TURN = struct.Struct('<QQQQB7s')
MAXIMUM_MS = (2**32-1)*125


def rows(paths, shape):
    for path in paths:
        before = path.stat()
        assert path.is_file() and not path.is_symlink() and before.st_size <= 67108864 and before.st_size%shape.size == 0
        with path.open('rb') as stream:
            while raw := stream.read(shape.size*32768):
                assert len(raw)%shape.size == 0
                yield from shape.iter_unpack(raw)
        after = path.stat()
        assert (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)


def audit_identities(reference_paths, tag_paths, relations, emitted_ids, emitted_anchors, expected):
    assert len(relations) <= 67108864 and all(a <= b for a, b in zip(relations, relations[1:]))
    def ordered(path):
        previous = None
        for row in rows([path], REF):
            node, way, degree, end = row;key = node, way, end, degree
            assert node > 0 and way > 0 and end in (0, 1) and degree == (1 if end else 2)
            assert previous is None or previous <= key;previous = key
            yield row
    source = heapq.merge(*(ordered(path) for path in reference_paths), key=lambda r: (r[0], r[1], r[3], r[2]))
    tagged = (value for value, in rows(tag_paths, Q));tag = next(tagged, None);prior_tag = 0;tag_rows = int(tag is not None)
    ordinal = anchors = references = total_degree = ends = relation_cursor = 0
    identity = degree = 0;endpoint = False
    def finish():
        nonlocal tag, prior_tag, tag_rows, ordinal, anchors, relation_cursor
        if not identity:return
        while tag is not None and tag < identity:
            assert tag > prior_tag;prior_tag = tag;tag = next(tagged, None);tag_rows += tag is not None
        while relation_cursor < len(relations) and relations[relation_cursor] < identity:relation_cursor += 1
        explicit = relation_cursor < len(relations) and relations[relation_cursor] == identity
        anchor = endpoint or degree != 2 or tag == identity or explicit
        assert next(emitted_ids) == (identity,)
        if anchor:assert next(emitted_anchors) == (ordinal,);anchors += 1
        ordinal += 1
    for node, way, d, end in source:
        if node != identity:finish();identity = node;degree = 0;endpoint = False
        references += 1;assert references <= expected[0]
        degree += d;total_degree += d;ends += end;endpoint |= bool(end)
    finish()
    while tag is not None:
        assert tag > prior_tag;prior_tag = tag;tag = next(tagged, None);tag_rows += tag is not None
    assert (references, ordinal, anchors, total_degree, ends, tag_rows) == expected
    assert next(emitted_ids, None) is None and next(emitted_anchors, None) is None
    return {'references': references, 'selectedNativeIds': ordinal, 'sourceDefinedAnchors': anchors}


def identities_and_anchors(facts):
    references = [Path(f'/inputs/topology/refs-{i:04}.bin') for i in range(25)]
    tags = [Path(f'/inputs/topology/tagged-{i:04}.bin') for i in range(6)]
    relations = array('Q');relations.frombytes(Path('/inputs/topology/sorted-relation-nodes-0000.bin').read_bytes())
    assert len(relations) == 1201443
    return audit_identities(references,tags,relations,rows(sorted(facts.glob('ids-*.bin')),Q),
                            rows(sorted(facts.glob('anchors-*.bin')),I),
                            (48163649,42993567,5731903,87872822,8454476,48142518))


def way_speeds(mask, forward, backward):
    role = (mask >> 4) & 15;directions = mask & 3
    assert role < 10 and math.isfinite(forward) and math.isfinite(backward) and 0 <= forward <= 160 and 0 <= backward <= 160
    default = POLICY['defaultSpeedsKph'][POLICY['roles'][role]]
    for enabled, absent, value in ((directions & 1, mask & 4, forward), (directions & 2, mask & 8, backward)):
        if enabled:
            assert value > 0
            if absent:assert value == default
        else:assert value == 0
    return role,directions


def audit():
    began = time.monotonic();repo = Path('/repo')
    root = repo/'data/coarse-quality/us-osm-car-cost-country-run-v1';facts = root/'cost-facts'
    producer = json.loads((root/'audit.json').read_bytes());counts = producer['facts']
    receipt = json.loads((root/'receipt.json').read_bytes())
    parent_root = repo/'data/coarse-quality/us-osm-car-capacity-run-v3'
    parent_receipt = json.loads((parent_root/'receipt.json').read_bytes())
    assert receipt['nativeEof'] and receipt['pythonProjectionFrames'] == 0
    for key in ('semanticSha256', 'sourceIdentity', 'metadata', 'histogram'):assert receipt[key] == parent_receipt[key]
    topology_started = time.monotonic();topology = identities_and_anchors(facts)
    topology_seconds = time.monotonic()-topology_started
    def load(prefix, code):
        out = array(code)
        for path in sorted(facts.glob(prefix+'-*.bin')):
            assert path.stat().st_size <= 16*1048576
            out.frombytes(path.read_bytes())
        return out
    ids = load('ids', 'Q');xy = load('xy', 'i');anchors = load('anchors', 'I');flags = load('flags', 'B')
    assert len(ids) == 42993567 and len(xy) == 2*len(ids) and len(anchors) == len(flags) == 5731903
    assert all(-1800000000 <= xy[i] <= 1800000000 and -900000000 <= xy[i+1] <= 900000000 for i in range(0, len(xy), 2))
    assert all(flag & 4 and flag < 8 for flag in flags)
    vertex = array('I', [0xffffffff])*len(ids)
    for ordinal, node in enumerate(anchors):vertex[node] = ordinal
    closures = load('closures', 'Q');parent_closures = array('Q');parent_closures.frombytes((parent_root/'way-facts/unsupported-member-ways.u64').read_bytes())
    assert closures == parent_closures and len(closures) == 149699 and all(a < b for a, b in zip(closures, closures[1:]))
    closed = set(closures)
    geometry = iter(value for value, in rows(sorted(facts.glob('geometry-*.bin')), I))
    arc_rows = rows(sorted(facts.glob('arcs-*.bin')), ARC)
    parent_ways = rows(sorted((parent_root/'way-facts').glob('ways-*.bin')), PARENT)
    cursor = ways = physical = pre = post = pre_overflow = post_overflow = zero_links = 0
    max_primitive = max_macro = 0;pre_roles = [0]*10;post_roles = [0]*10
    for identity, forward_speed, backward_speed, mask, end in rows(sorted(facts.glob('ways-*.bin')), WAY):
        original = next(parent_ways);assert original[0] == identity and original[4] == mask
        role,directions = way_speeds(mask,forward_speed,backward_speed)
        length = end-cursor;assert 2 <= length <= 2000
        previous = start_vertex = first_native = last_native = None
        first = segments = 0;forward = backward = 0;distinct = False
        for position in range(length):
            node = next(geometry);assert 0 <= node < len(ids)
            anchor = vertex[node];last_native = ids[node]
            if previous is None:
                assert anchor != 0xffffffff;start_vertex = anchor;first_native = last_native
            else:
                same = node == previous;zero_links += same;distinct |= not same
                if directions:
                    meters = 0. if same else distance_m([xy[2*previous]/1e7, xy[2*previous+1]/1e7], [xy[2*node]/1e7, xy[2*node+1]/1e7])
                    if directions & 1:
                        cost = 0 if same else max(1, math.ceil(meters*3600/forward_speed));forward += cost;max_primitive = max(max_primitive, cost)
                    if directions & 2:
                        cost = 0 if same else max(1, math.ceil(meters*3600/backward_speed));backward += cost;max_primitive = max(max_primitive, cost)
                assert forward <= MAXIMUM_MS and backward <= MAXIMUM_MS
                if anchor != 0xffffffff:
                    if distinct:
                        segments += 1;physical += 1
                        for direction, enabled, cost in ((1, directions & 1, forward), (-1, directions & 2, backward)):
                            if not enabled:continue
                            tail, head = (start_vertex, anchor) if direction == 1 else (anchor, start_vertex)
                            assert next(arc_rows) == (tail, head, ways, first, position, direction, bytes(3), cost)
                            overflow = (cost+124)//125 >= 65535
                            pre += 1;pre_overflow += overflow;pre_roles[role] += 1;max_macro = max(max_macro, cost)
                            if identity not in closed:post += 1;post_overflow += overflow;post_roles[role] += 1
                    first = position;start_vertex = anchor;forward = backward = 0;distinct = False
            previous = node
        assert first == length-1 and segments == original[3] and (first_native, last_native) == original[1:3]
        cursor = end;ways += 1
    assert next(parent_ways, None) is next(arc_rows, None) is next(geometry, None) is None
    assert (ways, cursor, physical, pre, post, zero_links) == (4227238, 48163649, 6674747, 9837326, 9620680, 0)
    assert counts['preClosureCostOverflows'] == pre_overflow and counts['postClosureCostOverflows'] == post_overflow
    assert counts['maximumPrimitiveMs'] == max_primitive and counts['maximumMacroMs'] == max_macro
    assert counts['preClosureArcsByRole'] == dict(zip(POLICY['roles'], pre_roles)) and counts['postClosureArcsByRole'] == dict(zip(POLICY['roles'], post_roles))
    turn_count = previous_relation = 0
    for identity, source_way, via, target_way, kind, reserved in rows(sorted(facts.glob('turns-*.bin')), TURN):
        assert identity > previous_relation and all(0 < value < 2**63 for value in (source_way, via, target_way)) and kind < 10 and reserved == bytes(7)
        previous_relation = identity;turn_count += 1
    assert turn_count == counts['supportedViaNodeRules'] == 409178
    invalid = b''.join(path.read_bytes() for path in sorted(facts.glob('invalid-*.bin')));records = [];offset = 0
    while offset < len(invalid):
        size = int.from_bytes(invalid[offset:offset+4], 'little');offset += 4
        assert 0 < size <= 8388608 and size <= len(invalid)-offset
        records.append(decode_frame(invalid[offset:offset+size]));offset += size
    diagnosed = json.loads((repo/'docs/evidence/coarse-osm-car-capacity-2026-11-01/capacity-raw/relation-inspect-v4/audit.json').read_bytes())['records']
    assert records == diagnosed and len(records) == counts['invalidUnlocatableRestrictions'] == 2
    assert counts['outputBytes'] == sum(path.stat().st_size for path in facts.iterdir())
    return {'status': 'independent_complete_national_derived_cost_fact_audit_passed', 'topology': topology,
            'secondsIndependentTypedIdentityAnchorMerge': topology_seconds, 'waysChecked': ways, 'sourceGeometryReferencesChecked': cursor,
            'physicalSpansChecked': physical, 'preClosureArcCostsChecked': pre, 'postClosureArcCostsChecked': post,
            'preClosureCostOverflows': pre_overflow, 'postClosureCostOverflows': post_overflow,
            'supportedSourceTurnRecordsChecked': turn_count, 'invalidSourceRecordsExactlyMatched': len(records),
            'secondsIncludingAllDerivedFieldsAndCostMath': time.monotonic()-began,
            'sourcePbfReads': 0, 'nativeLibraryExecutions': 0, 'networkRequests': 0, 'applicationDbReads': 0,
            'scope': 'Independent original typed incidences/native IDs/anchors, every geometry/index/way-capacity mask/span/integer-ms cost/closure, bounds/source-turn and invalid-record data. Raw coordinate/tag ingestion and source permissions still rely on the qualified source/policy/consumer and original full source seals; this is not a second raw-source decoder or nationwide ETA/app qualification.',
            'modelChanged': False, 'etaQualified': False, 'vercelQualified': False}
