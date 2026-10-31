"""Independent byte/component audit of the new artifact; never routes or reprices sources."""
from array import array
import gzip
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

root = Path(sys.argv[1])
destination = Path(sys.argv[2])
load = lambda path: json.loads(Path(path).read_text())
sha = lambda data: hashlib.sha256(data).hexdigest()
plan = load(root/'preparation-plan.json')
for path, expected in plan['inputs'].items():
    assert sha(Path(path).read_bytes()) == expected, path

def read_container(path, expected):
    raw = path.read_bytes()
    assert sha(raw) == expected and raw[:8] == b'GEOBBP01'
    size, = struct.unpack_from('<I', raw, 8)
    assert 0 < size <= 1048576
    descriptor = json.loads(raw[12:12+size])
    payload = memoryview(raw)[12+size:]
    result = {}
    offset = 0
    for entry in descriptor['entries']:
        assert entry['offset'] == offset
        blob = payload[offset:offset+entry['bytes']]
        assert sha(blob) == entry['gzipSha256']
        result[f"{entry['kind']}/{entry['name']}"] = (entry, blob)
        offset += entry['bytes']
    assert offset == len(payload) == descriptor['payloadBytes']
    return descriptor, result

manifest = load(root/'manifest.json')
old, before = read_container(Path(plan['binary']), plan['binarySha256'])
new, after = read_container(root/'backbone.bin', manifest['sha256'])
assert len(before) == len(after) == 29 and set(before) == set(after)
changed = [name for name in before if before[name][0]['gzipSha256'] != after[name][0]['gzipSha256']]
assert changed == ['kept/roadDeciseconds', 'graph/arcMinutes']
assert old['kept'] == new['kept']
assert {key: value for key, value in new['stats'].items() if key != 'costPolicy'} == old['stats']
assert new['stats']['costPolicy']['factor'] == manifest['sourceRoadTimeFactor'] == 1.1

def values(entries, name, code):
    entry, blob = entries[name]
    raw = gzip.decompress(blob)
    assert len(raw) == entry['rawBytes'] and sha(raw) == entry['rawSha256']
    result = array(code)
    result.frombytes(raw)
    if sys.byteorder != 'little':
        result.byteswap()
    return result

km = values(before, 'graph/arcRoadKm', 'd')
speed = values(before, 'graph/arcSpeedKph', 'B')
old_time = values(before, 'graph/arcMinutes', 'd')
new_time = values(after, 'graph/arcMinutes', 'd')
assert len(km) == len(speed) == len(old_time) == len(new_time) == 1234223
maximum_error = 0.
for length, kph, original, candidate in zip(km, speed, old_time, new_time):
    road = length/kph*60
    rounding = original-road
    assert road > 0 and -1e-8 <= rounding <= 1/600+1e-8
    expected = original + .1*road
    maximum_error = max(maximum_error, abs(candidate-expected))
    assert candidate >= original and math.isclose(candidate, expected, rel_tol=1e-13, abs_tol=1e-12)
old_base = values(before, 'kept/roadDeciseconds', 'H')
new_base = values(after, 'kept/roadDeciseconds', 'H')
proofs = json.loads(gzip.decompress(Path(plan['baseProofs']).read_bytes()))
assert len(proofs) == sum(bool(value) for value in old_base) == sum(bool(value) for value in new_base) == 378515
keys = set()
for proof in proofs:
    key = proof['key']
    assert key not in keys
    keys.add(key)
    assert proof['connectorSpeedKph'] == (55 if proof['kind'] == 'natural-earth' else 25)
    source = proof['roadKm']/proof['speedKph']
    connector = proof['localKm']/proof['connectorSpeedKph']
    original = max(1, math.ceil((source+connector)*36000))
    candidate = max(1, math.ceil((1.1*proof['roadKm']/proof['speedKph']+connector)*36000))
    assert original == proof['deciseconds'] == old_base[key]
    assert candidate == new_base[key] <= 65535 and candidate >= original
for i, value in enumerate(old_base):
    if i not in keys:
        assert value == new_base[i] == 0
control = load(root/'control.json')
paths = {path['id']: path for path in json.loads(gzip.decompress(Path(plan['savedPaths']).read_bytes()))}
assert len(control['endpointReproduction']) == 166
for row in control['endpointReproduction']:
    path = paths[row['id']]
    role = row['role']
    assert row['node'] == (path['edges'][0]['from'] if role == 'origin' else path['edges'][-1]['target'])
    assert row['expectedMinutes'] == path['components'][role]
    assert abs(row['reproducedMinutes']-row['expectedMinutes']) < 1e-8
report = {'independentComponentAndPayloadAudit': True, 'graphArcs': len(km), 'baseLinks': len(proofs),
          'endpointStatesReproduced': 166, 'changedPayloads': changed, 'other27PayloadsExact': True,
          'maximumArcMinutesDifference': maximum_error, 'binaryBytes': (root/'backbone.bin').stat().st_size,
          'binarySha256': manifest['sha256'], 'sourceRoadTimeFactor': 1.1,
          'routingQueries': 0, 'runtimeChanged': False,
          'scope': 'Full changed-cost/unchanged-payload audit plus saved baseline endpoint reproduction. No query, physical source producer, packaging/cloud qualification or new references.'}
with destination.open('x') as stream:
    stream.write(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
