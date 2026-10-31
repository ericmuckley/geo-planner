"""Independent stdlib-only value/byte audit; no source producer or route search."""
import base64
import gzip
import hashlib
import json
import struct
import sys
from pathlib import Path

digest = lambda value: hashlib.sha256(value).hexdigest()
root = Path(sys.argv[1])
record = json.loads((root / 'probe.json').read_text())
binary = (root / '.vercel/output/functions/__server.func/server-data/backbone.bin').read_bytes()
assert len(binary) == record['container']['bytes']
assert digest(binary) == record['container']['sha256']
assert binary[:8] == b'GEOBBP01'
size, = struct.unpack_from('<I', binary, 8)
assert 0 < size <= 1048576
descriptor = json.loads(binary[12:12 + size])
payload = memoryview(binary)[12 + size:]
assert len(payload) == descriptor['payloadBytes']
report = json.loads(Path('docs/evidence/coarse-backbone-geometry-2026-10-25/report.json').read_text())
entries = descriptor['entries']
assert entries == record['entries']
offset = graph = kept_count = 0
for entry in entries:
    assert entry['offset'] == offset
    blob = payload[offset:offset + entry['bytes']]
    assert digest(blob) == entry['gzipSha256']
    raw = gzip.decompress(blob)
    assert len(raw) == entry['rawBytes']
    assert digest(raw) == entry['rawSha256']
    offset += entry['bytes']
    if entry['kind'] == 'graph':
        expected = report['packedArrays'][entry['name']]
        assert digest(blob) == expected['sha256']
        assert digest(raw) == expected['rawSha256']
        assert blob == Path(expected['path']).read_bytes()
        assert entry['elements'] == expected['elements']
        assert entry['typecode'] == expected['typecode']
        graph += 1
    else:
        kept_count += 1
assert offset == len(payload)
assert graph == 17 and kept_count == 12
used = set()
def restore(value):
    if isinstance(value, dict) and '$binary' in value:
        assert set(value) == {'$binary'}
        index = value['$binary']
        assert index not in used
        used.add(index)
        entry = entries[index]
        assert entry['kind'] == 'kept'
        blob = payload[entry['offset']:entry['offset'] + entry['bytes']]
        return 'gzip:' + base64.b64encode(blob).decode('ascii')
    if isinstance(value, dict):
        return {key: restore(item) for key, item in value.items()}
    if isinstance(value, list):
        return [restore(item) for item in value]
    return value
original = json.loads(Path('src/server/data/coarse-grid-v9.json').read_text())
del original['roadLayer'], original['supplementalRoadVisits']
assert restore(descriptor['kept']) == original
assert len(used) == 12
print(json.dumps({'independentPythonAudit': True, 'graphArrays': graph, 'keptBlobs': kept_count,
                  'allGzipBytesAndRawHashesEqual': True, 'keptV9ValuesEqual': True,
                  'binaryBytes': len(binary), 'binarySha256': digest(binary),
                  'scope': 'Full container byte/value comparison, no source audit or routing.'}, indent=2))
