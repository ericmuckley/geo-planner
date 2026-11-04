"""Pure native cost equivalence on all saved captured major-road geometries."""
from array import array
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from import_roads import distance_m
from coarse_osm_car_codec_v1 import ticks
from coarse_osm_car_policy_v2 import POLICY, restriction_policy, way_policy
from coarse_timing_input import require


def run(native, repo, check=lambda: None):
    path = repo/'data/coarse-quality/us-osm-disk-capture-run-v1/extract/audit-selected.sqlite'
    closed = json.loads((repo/'docs/evidence/coarse-osm-extraction-2026-10-30/disk-capture-closed-run-v1.json').read_bytes())
    pin = closed['roster']['extract/audit-selected.sqlite']
    require(path.stat().st_size == pin['bytes'], 'Cost equivalence sealed SQLite size')
    with path.open('rb') as stream:
        require(hashlib.file_digest(stream, 'sha256').hexdigest() == pin['sha256'], 'Cost equivalence sealed SQLite hash')
    db = sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1', uri=True)
    db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-16384')
    def load(name, code):
        out = array(code);out.frombytes((repo/'data/coarse-quality/us-osm-lineage-run-v1'/name).read_bytes());return out
    selected = load('provenance/selected-nodes.u32', 'I');xy = load('geometry/xy.i32', 'i')
    source_anchors = set(load('provenance/vertices.u32', 'I'))
    all_ids = array('q', (row[0] for row in db.execute("SELECT id FROM objects WHERE kind='node' ORDER BY id")))
    require(len(all_ids) == 1123919 and len(selected) == 143560 and len(xy) == 2*len(selected) and len(source_anchors) == 53672, 'Cost equivalence source denominators')
    positions = {all_ids[source]: i for i, source in enumerate(selected)}
    anchors = {all_ids[source] for source in source_anchors}
    closures = set();relations = 0
    for raw, in db.execute("SELECT raw FROM objects WHERE kind='relation' ORDER BY id"):
        decision = restriction_policy(json.loads(raw));relations += 1
        if decision['status'] == 'closed-unsupported':closures.update(decision['memberWays'])
        require(decision['status'] != 'invalid-unlocatable', 'Original captured source decisions unchanged')
    examined = major = primitives = directed = macros = 0
    for raw, in db.execute("SELECT raw FROM objects WHERE kind='way' ORDER BY id"):
        examined += 1
        if examined%1024 == 0:check()
        way = json.loads(raw)
        if way['tags'].get('highway') not in POLICY['roles']:continue
        major += 1;refs = way['nodes'];primitives += len(refs)-1
        policy = way_policy(way['tags'])
        if policy.reason or way['id'] in closures:continue
        cuts = [i for i, identity in enumerate(refs) if identity in anchors]
        require(cuts[0] == 0 and cuts[-1] == len(refs)-1, 'Cost equivalence source-way end protection')
        coordinates = array('i');same = bytearray()
        for a, b in zip(refs, refs[1:]):
            i, j = positions[a], positions[b]
            coordinates.extend((xy[2*i], xy[2*i+1], xy[2*j], xy[2*j+1]));same.append(a == b)
        for speed in (policy.forward, policy.backward):
            if speed is None:continue
            actual = native.costs(coordinates, array('d', [speed])*len(same), same)
            expected = array('Q')
            for i, equal in enumerate(same):
                points = coordinates[4*i:4*i+4]
                expected.append(0 if equal else max(1, math.ceil(distance_m([points[0]/1e7, points[1]/1e7], [points[2]/1e7, points[3]/1e7])*3600/speed)))
            require(actual == expected, 'Native primitive integer-ms exact source equivalence')
            directed += sum(not equal for equal in same)
            for first, last in zip(cuts, cuts[1:]):
                if all(refs[i] == refs[first] for i in range(first, last+1)):continue
                milliseconds = sum(expected[first:last])
                require(native.sum(actual[first:last]) == (milliseconds, ticks(milliseconds)), 'Native full-geometry contraction and upward ticks exact')
                macros += 1
    db.close()
    require((examined, major, primitives, relations, directed, macros) == (239253, 28995, 148961, 4900, 218666, 86517), 'Cost equivalence unchanged complete graph denominators')
    return {'status': 'passed_complete_captured_native_primitive_and_contracted_cost_equivalence',
            'sourceWaysExamined': examined, 'majorWays': major, 'sourcePrimitiveEdges': primitives,
            'directedPrimitiveCostsChecked': directed, 'contractedArcSumsAndTicksChecked': macros,
            'sourcePbfReads': 0, 'networkRequests': 0, 'applicationDbReads': 0,
            'countryCostsBuilt': False, 'modelChanged': False, 'etaQualified': False, 'vercelQualified': False}
