"""Read cached source/reference schemas only; no routing, source build or download."""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import zipfile

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

raw = (folder / 'inventory-plan.json').read_bytes()
assert digest(folder / 'inventory-plan.json') == sys.argv[1]
plan = json.loads(raw)
for name, expected in plan['inputs'].items():
    assert digest(repo / name) == expected, name
for name, expected in plan['toolFiles'].items():
    assert digest(Path(name)) == expected, name
assert not (folder / 'inventory.json').exists()
census = []
for source in load(repo / plan['censusCatalog'])['sources']:
    path = repo / source['path']
    assert digest(path) == source['sha256'] and path.stat().st_size == source['bytes']
    with zipfile.ZipFile(path) as archive:
        name, = [n for n in archive.namelist() if n.endswith('.dbf')]
        with archive.open(name) as stream:
            header = stream.read(32)
            length = struct.unpack_from('<H', header, 8)[0]
            fields = stream.read(length - 32)
        assert fields[-1] == 13 and (length - 33) % 32 == 0
        descriptors = [fields[i:i+32] for i in range(0, length - 33, 32)]
        census.append({'path': source['path'], 'fieldNames': [d[:11].split(b'\0')[0].decode('ascii') for d in descriptors]})
assert len(census) == 49
roads = load(repo / plan['naturalEarth'])['features']
ne_keys = sorted({key for feature in roads for key in feature['properties']})
provider = load(repo / plan['providerReport'])['providerInventory']
ors = []
for row in provider:
    record = row['ors']
    response = load(repo / record['responsePath'])
    properties = response['features'][0]['properties']
    segments = properties.get('segments', [])
    ors.append({'id': row['id'], 'instructionsRequested': record['request'].get('instructions'),
                'propertyNames': sorted(properties),
                'segmentFieldNames': sorted({k for segment in segments for k in segment}),
                'stepCount': sum(len(segment.get('steps', [])) for segment in segments)})
old_plan = load(repo / plan['providerPlan'])
original = load(repo / old_plan['valhallaOriginal'])
valhalla = {'original/' + s['name']: s['reference'] for s in original['samples']}
regional = load(repo / old_plan['valhallaRegionalSummary'])
for sample in regional['samples']:
    path = repo / old_plan['valhallaRegionalDirectory'] / (sample['id'] + '.json')
    record = load(path)
    assert record['status'] == 200
    valhalla['regional/' + sample['id']] = record['body']
v_schemas = [{'id': key, 'tripFieldNames': sorted(body['trip']),
              'legFieldNames': sorted({k for leg in body['trip']['legs'] for k in leg}),
              'maneuverFieldNames': sorted({k for leg in body['trip']['legs'] for m in leg.get('maneuvers', []) for k in m})}
             for key, body in valhalla.items()]
assert len(ors) == 83 and len(v_schemas) == 35
assert len({r['id'] for r in ors}) == 83
assert set(valhalla) == {r['id'] for r in provider if r['valhalla']['status'] == 'available'}
graph = (repo / 'src/server/backbone-geometry.ts').read_text().split('export type BackboneGraph = {', 1)[1].split('};', 1)[0]
graph_fields = re.findall(r'^\s*(\w+):\s*(\w+);', graph, re.M)
report = {'planSha256': hashlib.sha256(raw).hexdigest(), 'censusPartitions': census,
          'naturalEarthPropertyNames': ne_keys, 'ors': ors, 'valhalla': v_schemas,
          'backboneGraphFields': dict(graph_fields),
          'censusSchemasUniform': len({tuple(r['fieldNames']) for r in census}) == 1,
          'orsNoInstructionSteps': sum(r['stepCount'] == 0 for r in ors),
          'orsInstructionsDisabled': sum(r['instructionsRequested'] is False for r in ors),
          'routingQueries': 0, 'sourceBuilds': 0, 'sourceDownloads': 0, 'runtimeChanged': False,
          'scope': 'Schema availability only, not timing values, source truth, junction-delay measurements or a new 83-case feature/model experiment.'}
with (folder / 'inventory.json').open('x') as stream:
    stream.write(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k not in ['censusPartitions', 'ors', 'valhalla']}, indent=2))
