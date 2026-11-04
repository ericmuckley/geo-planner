"""Draft full captured-data qualification of the native cost-fact constructor."""
from array import array
from collections import Counter
import gc
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import time

from coarse_osm_attributes_v1 import validate_record
from coarse_osm_bulk_pbf import stat_key
from coarse_osm_car_cost_graph_v1 import CostGraph
from coarse_osm_car_partition_v1_test import splits
from coarse_osm_car_policy_v2 import POLICY
from coarse_osm_country_wire_v4 import SEAL_PREFIX, field_frame
from coarse_osm_native_smoke import STATE
from coarse_timing_input import require

CAPS = {'singleNormalizedElementBytes': 4194304, 'scanNodesPerPass': 1123919, 'scanWaysPerPass': 239253,
        'scanRelationsPerPass': 4900, 'scanObjectVisitsTotal': 1368072,
        'pbfHeaderBytesExclusiveMaximum': 65536, 'pbfUncompressedBlobBytesExclusiveMaximum': 33554432}


def add(writer, element):
    from osmium.osm import mutable
    common = {name: element[name] for name in ('id', 'version', 'timestamp', 'visible', 'tags')}
    common.update(uid=0, changeset=0, user='')
    if element['type'] == 'node':
        writer.add_node(mutable.Node(location=(element['lon'], element['lat']), **common))
    elif element['type'] == 'way':
        writer.add_way(mutable.Way(nodes=element['nodes'], **common))
    else:
        members = [(m['type'][0], m['ref'], m['role']) for m in element['members']]
        writer.add_relation(mutable.Relation(members=members, **common))


def writer(path):
    import osmium
    header = osmium.io.Header();header.set('osmosis_replication_timestamp', STATE)
    return osmium.SimpleWriter(osmium.io.File(str(path), 'pbf'), bufsz=1048576, header=header)


def prepare(db, root, check=lambda: None):
    ways = {};examined = 0
    for raw, in db.execute("SELECT raw FROM objects WHERE kind='way' ORDER BY id"):
        examined += 1
        if examined%4096 == 0:check()
        row = json.loads(raw)
        if row['tags'].get('highway') in POLICY['roles']:ways[row['id']] = row['nodes']
    require(examined == 239253 and len(ways) == 28995, 'Captured constructor complete way denominators')
    tagged = array('Q', (row[0] for row in db.execute("SELECT id FROM objects WHERE kind='node' AND json_extract(raw,'$.tags') != '{}' ORDER BY id")))
    relations = array('Q')
    for raw, in db.execute("SELECT raw FROM objects WHERE kind='relation' ORDER BY id"):
        relations.extend(m['ref'] for m in json.loads(raw)['members'] if m['type'] == 'node')
    relations = array('Q', sorted(relations))
    anchors = splits(ways, tagged, relations)[1]
    rows = [(node, way, 1 if i in (0, len(refs)-1) else 2, int(i in (0, len(refs)-1)))
            for way, refs in ways.items() for i, node in enumerate(refs)]
    rows.sort(key=lambda r: (r[0], r[1], r[3], r[2]))
    selected = len({r[0] for r in rows})
    require((len(rows), selected, len(anchors)) == (177956, 143560, 53672), 'Captured constructor unchanged references/native points/anchors')
    refs = root/'refs.bin';tags = root/'tags.bin'
    with refs.open('xb') as stream:
        for row in rows:stream.write(struct.pack('<QQII', *row))
    with tags.open('xb') as stream:tagged.tofile(stream)
    maximum = db.execute("SELECT max(id) FROM objects WHERE kind='node'").fetchone()[0]
    return [refs], [tags], relations, {'reference_count': len(rows), 'way_count': len(ways), 'tag_count': len(tagged),
                                      'maximum': maximum, 'selected': selected, 'anchors': len(anchors)}


def convert(source, destination, expected, check=lambda: None):
    require(source.stat().st_size == expected['bytes'] == 477852579, 'Captured constructor exact input bytes')
    before = stat_key(source);digest = hashlib.sha256();semantic = hashlib.sha256(SEAL_PREFIX)
    types = Counter();rows = memberships = size = 0;previous = None
    with source.open('rb') as stream, writer(destination) as output:
        while line := stream.readline(8388609):
            require(len(line) <= 8388608 and line.endswith(b'\n'), 'Captured constructor bounded source row')
            record = json.loads(line);element = validate_record(record, STATE)
            key = (('node', 'way', 'relation').index(element['type']), element['id'])
            require(previous is None or previous < key, 'Captured constructor source typed ID order');previous = key
            size += len(line);rows += 1;memberships += len(record['windowIds']);types[element['type']] += 1
            require(rows <= 1368072 and size <= expected['bytes'], 'Captured constructor complete input caps')
            digest.update(line);body = field_frame(element);semantic.update(struct.pack('<I', len(body)));semantic.update(body)
            add(output, element)
            if rows%4096 == 0:
                check();require(destination.stat().st_size <= 67108864, 'Captured constructor generated PBF bound')
    actual = {'rows': rows, 'bytes': size, 'sha256': digest.hexdigest(), 'types': dict(types), 'memberships': memberships}
    require(actual == expected and before == stat_key(source), 'Captured constructor unchanged complete capture receipt')
    require(destination.stat().st_size <= 67108864, 'Captured constructor closed generated PBF bound')
    return actual | {'semanticSha256': semantic.hexdigest(), 'generatedPbfBytes': destination.stat().st_size}


def run(repo, work, artifact, check=lambda: None):
    began = time.monotonic()
    report_path = repo/'docs/evidence/coarse-osm-car-prototype-2026-11-01/car-raw/run-v1/report.json'
    original = json.loads(report_path.read_bytes())
    source = repo/'data/coarse-quality/us-osm-disk-capture-run-v1/extract'
    database = source/'audit-selected.sqlite'
    closed = json.loads((repo/'docs/evidence/coarse-osm-extraction-2026-10-30/disk-capture-closed-run-v1.json').read_bytes())
    pin = closed['roster']['extract/audit-selected.sqlite']
    require(database.stat().st_size == pin['bytes'], 'Captured constructor sealed SQLite size')
    with database.open('rb') as stream:require(hashlib.file_digest(stream, 'sha256').hexdigest() == pin['sha256'], 'Captured constructor sealed SQLite hash')
    db = sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1', uri=True)
    db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-16384')
    refs, tags, relation_nodes, expected = prepare(db, work, check);db.close();gc.collect()
    pbf = work/'captured.osm.pbf'
    conversion = convert(source/'elements.jsonl', pbf, original['captureReceipt'], check)
    output = work/'cost-facts';output.mkdir()
    engine = CostGraph(*artifact, aggregate_visits=1368072)
    try:
        engine.begin(refs, tags, relation_nodes, output, **expected)
        receipt = engine.scan(pbf, STATE, CAPS, check=check, fallback=False)
        require(receipt['nativeEof'] and receipt['pythonProjectionFrames'] == 0 and receipt['semanticSha256'] == conversion['semanticSha256'], 'Captured constructor exact generated-source semantic seal and zero native projections')
        require(receipt['counts'] == original['captureReceipt']['types'], 'Captured constructor complete source type counts')
        result = engine.finish()
    finally:engine.release()
    require((result['majorWays'], result['selectedNodes'], result['anchors'], result['nonzeroLineageSegments'], result['postClosureArcs']) == (28995, 143560, 53672, 59073, 86517), 'Captured constructor original profile and post-closure graph preserved')
    return {'status': 'passed_complete_captured_native_cost_fact_constructor', 'conversion': conversion,
            'receipt': receipt, 'facts': result, 'secondsIncludingAllInputBindingsPreparationConversionAndConstruction': time.monotonic()-began,
            'countrySourcePbfReads': 0, 'generatedCapturedPbfReads': 1, 'networkRequests': 0, 'applicationDbReads': 0,
            'nationalCostsBuilt': False, 'appGraphBuilt': False, 'etaQualified': False, 'vercelQualified': False, 'modelChanged': False}
