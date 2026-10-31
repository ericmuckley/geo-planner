"""Tiny native ABI/format proof, never a road-data or national feasibility test."""
from copy import deepcopy
import datetime
import hashlib
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zlib

from coarse_osm_bulk import extract
from coarse_osm_bulk_pbf import framing, native_records, stat_key
from coarse_osm_records import canonical, normalize
from coarse_timing_input import digest, json_bytes, require


STATE = '2026-10-25T21:21:21Z'


def fixture_records():
    common = {'version': 1, 'timestamp': '2026-10-20T00:00:00Z', 'visible': True, 'tags': {}}
    rows = [
        {'type': 'node', 'id': 1, 'lon': -1., 'lat': .5, 'tags': {'barrier': 'gate'}},
        {'type': 'node', 'id': 2, 'lon': 2., 'lat': .5},
        {'type': 'node', 'id': 3, 'lon': -2., 'lat': 2.},
        {'type': 'node', 'id': 4, 'lon': -1., 'lat': 2.},
        {'type': 'way', 'id': 1, 'nodes': [1, 2], 'tags': {'highway': 'primary', 'maxspeed': '55 mph', 'access': 'private', 'maxspeed:conditional': '35 @ wet'}},
        {'type': 'way', 'id': 3, 'nodes': [3, 4], 'tags': {'highway': 'secondary'}},
        {'type': 'way', 'id': 4, 'nodes': [3, 4], 'tags': {'waterway': 'stream'}},
        {'type': 'relation', 'id': 1, 'tags': {'type': 'restriction', 'restriction:conditional': 'no_left_turn @ wet'},
         'members': [{'type': 'way', 'ref': 1, 'role': 'from'}, {'type': 'node', 'ref': 2, 'role': 'via'}, {'type': 'way', 'ref': 999, 'role': 'to'}]},
        {'type': 'relation', 'id': 2, 'tags': {'type': 'restriction'}, 'members': [{'type': 'way', 'ref': 3, 'role': 'from'}]},
    ]
    return [deepcopy(common | row) for row in rows]


def write_xml(path, rows):
    document = ET.Element('osm', version='0.6', generator='geo-planner-synthetic-tool-smoke')
    for row in rows:
        attrs = {k: str(row[k]).lower() if k == 'visible' else str(row[k]) for k in ('id', 'version', 'timestamp', 'visible')}
        if row['type'] == 'node': attrs.update({k: str(row[k]) for k in ('lon', 'lat')})
        element = ET.SubElement(document, row['type'], attrs)
        for ref in row.get('nodes', []): ET.SubElement(element, 'nd', ref=str(ref))
        for member in row.get('members', []): ET.SubElement(element, 'member', {k: str(v) for k, v in member.items()})
        for key, value in row['tags'].items(): ET.SubElement(element, 'tag', k=key, v=value)
    with Path(path).open('xb') as stream: ET.ElementTree(document).write(stream, encoding='utf-8', xml_declaration=True)


def varint(value):
    out = bytearray()
    while value > 127: out.append((value & 127) | 128); value >>= 7
    out.append(value); return bytes(out)


def field(number, value):
    return varint(number * 8) + varint(value) if isinstance(value, int) else varint(number * 8 + 2) + varint(len(value)) + value


def frame(kind, payload, *, blob=None):
    blob = field(1, payload) if blob is None else blob
    header = field(1, kind) + field(3, len(blob))
    return struct.pack('!I', len(header)) + header + blob


def negative_fixtures(valid):
    timestamp = int(datetime.datetime.fromisoformat(STATE.replace('Z', '+00:00')).timestamp())
    header = frame(b'OSMHeader', field(4, b'OsmSchema-V0.6') + field(32, timestamp))
    return {
        'truncated': (valid[:-1], 'Truncated PBF'),
        'malformed-header': (b'\x00\x00\x00\x00', 'PBF header bound'),
        'sub-coordinate': (header + frame(b'OSMData', field(17, 1)), 'coordinate precision'),
        'subsecond': (header + frame(b'OSMData', field(18, 1)), 'subsecond'),
        'offset-precision': (header + frame(b'OSMData', field(19, 1)), 'offset precision'),
        'decompression-overflow': (header + frame(b'OSMData', b'', blob=field(2, 8) + field(3, zlib.compress(b'x' * 10000))), 'decompression'),
        'unsupported-compression': (header + frame(b'OSMData', b'', blob=field(4, b'not-lzma')), 'compression'),
    }


def smoke(root, proposal):
    import osmium
    root = Path(root); root.mkdir()
    rows = fixture_records(); xml = root / 'fixture.osm'; pbf = root / 'fixture.osm.pbf'
    write_xml(xml, rows)
    header = osmium.io.Header(); header.set('osmosis_replication_timestamp', STATE)
    with osmium.SimpleWriter(str(pbf), bufsz=65536, header=header) as writer:
        for obj in osmium.FileProcessor(str(xml)): writer.add(obj)
    p = deepcopy(proposal); caps = p['proposedCaps']
    caps.update(sqliteIndexBytesEach=1048576, sqliteMaxPagesEach=256, sqliteCacheBytesEach=8192,
        workingBytesIncludingTmp=33554432, tmpBytes=65536, pythonSelectionStateBytes=4194304, retainedNativeObjectBytes=1048576,
        normalizedExtractBytes=1048576, scanNodesPerPass=100, scanWaysPerPass=100, scanRelationsPerPass=100, scanObjectVisitsTotal=1200,
        wallSeconds=30)
    p['windows'] = [{'id': 'a', 'bbox': [0, 0, 1, 1]}, {'id': 'b', 'bbox': [.25, .25, .75, .75]}]
    p['source']['proposedPublisherReplicationStateUtc'] = STATE
    identity = framing(pbf, caps, STATE); before = stat_key(pbf)
    projected = list(native_records(pbf, caps['singleNormalizedElementBytes']))
    require(projected == rows, 'Actual native projection differs from exact fixture records')
    (root / 'projected.json').write_bytes(json_bytes(projected))
    def reader():
        require(stat_key(pbf) == before, 'Tiny PBF identity changed')
        yield from native_records(pbf, caps['singleNormalizedElementBytes'])
        require(stat_key(pbf) == before, 'Tiny PBF identity changed')
    output = root / 'extract'; output.mkdir()
    state = extract(reader, p, output, source_identity=identity, reserved_input_bytes=pbf.stat().st_size)
    require(state['status'] == 'extracted_publisher_file_analysis_pending' and state['independentAuditComplete'], 'Native extraction/audit failed: ' + json.dumps(state))
    actual = [json.loads(line) for line in (output / 'elements.jsonl').read_text().splitlines()]
    expected = [normalize(rows[i], STATE, caps['singleNormalizedElementBytes']) for i in (0, 1, 4, 7)]
    require({(r['element']['type'], r['element']['id']) for r in actual} == {('node', 1), ('node', 2), ('way', 1), ('relation', 1)}, 'Native selected typed identity')
    for record in actual:
        element = next(r for r in expected if (r['type'], r['id']) == (record['element']['type'], record['element']['id']))
        require(record['element'] == element and record['windowIds'] == ['a', 'b'] and record['publisherStateUtc'] == STATE, 'Native output fields/windows/state')
        require(record['elementSha256'] == hashlib.sha256(canonical(element)).hexdigest(), 'Native output hash')
        if element['type'] == 'way': require(record['geometryDependencySha256'] == hashlib.sha256(canonical([STATE, expected[:2]])).hexdigest(), 'Native geometry dependency hash')
    require(state['scanObjectVisits'] == 36 and len(state['passes']) == 4 and all(r['status'] == 'eof' and r['counts'] == {'node': 4, 'way': 3, 'relation': 2} for r in state['passes']), 'Native four-pass EOF/counts')
    negatives = []
    for name, (raw, message) in negative_fixtures(pbf.read_bytes()).items():
        path = root / (name + '.pbf'); path.write_bytes(raw)
        try: framing(path, caps, STATE)
        except Exception as error:
            require(message in str(error), 'Unexpected negative fixture failure: ' + str(error))
            negatives.append({'name': name, 'rejected': True, 'error': str(error), 'bytes': len(raw), 'sha256': digest(path)})
        else: raise ValueError('Invalid PBF accepted: ' + name)
    # The native decoder is additionally tested directly on a truncated real PBF.
    try: list(native_records(root / 'truncated.pbf', caps['singleNormalizedElementBytes']))
    except Exception as error: native_truncated = {'rejected': True, 'errorType': type(error).__name__, 'error': str(error)[:1000]}
    else: raise ValueError('Native decoder accepted truncated PBF')
    result = {'status': 'passed', 'scope': 'Tiny synthetic native fixture only; normalization/hash/decoder are shared with extractor audit.',
        'tinyNativeDecoderQualified': True, 'nationalSourceFeasibilityQualified': False, 'publisherBoundaryQualified': False,
        'sourceIdentity': identity, 'inputRecords': len(rows), 'retainedRecords': len(actual), 'fourPassVisits': 36,
        'negativeFramingChecks': negatives, 'nativeTruncatedCheck': native_truncated,
        'sqliteVersion': __import__('sqlite3').sqlite_version, 'pbfBytes': pbf.stat().st_size, 'outputSha256': digest(output / 'elements.jsonl')}
    (root / 'smoke-result.json').write_bytes(json_bytes(result)); return result
