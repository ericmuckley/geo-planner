"""Read-only schema/design/source bindings; no download, producer or routing query."""
import hashlib
import json
from pathlib import Path
import sys

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda path: json.loads(path.read_text())
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def verify_files(files, root):
    for name, expected in files.items():
        assert digest(root / name) == expected, name

manifest = load(folder / 'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*')
                         if p.is_file() and p.name != 'sha256.json'}
verify_files(manifest, folder)
checks = load(folder / 'checks.json')
verify_files(checks['producerFiles'], repo)
verify_files(checks['preservedFiles'], repo)
for name, record in checks['priorSealedEvidence'].items():
    base = repo / 'docs/evidence' / name
    assert digest(base / 'sha256.json') == record['manifestSha256']
    prior = load(base / 'sha256.json')
    assert len(prior) == record['files']
    verify_files(prior, base)
local = '--local-assets' in sys.argv
for name in ['inventory-plan.json', 'schema-check-plan.json', 'data-input-proposal.json']:
    for path, expected in load(folder / name)['inputs'].items():
        if local or not path.startswith('data/'):
            assert digest(repo / path) == expected, (name, path)
inventory = load(folder / 'inventory.json')
assert inventory['planSha256'] == digest(folder / 'inventory-plan.json')
assert len(inventory['censusPartitions']) == 49 and inventory['censusSchemasUniform']
assert {tuple(r['fieldNames']) for r in inventory['censusPartitions']} == {('LINEARID', 'FULLNAME', 'RTTYP', 'MTFCC')}
assert len(inventory['ors']) == inventory['orsNoInstructionSteps'] == inventory['orsInstructionsDisabled'] == 83
assert len(inventory['valhalla']) == 35 and len(inventory['backboneGraphFields']) == 17
assert len(inventory['naturalEarthPropertyNames']) == 31
provider = load(repo / load(folder / 'inventory-plan.json')['providerReport'])['providerInventory']
extras = [load(repo / r['ors']['responsePath'])['features'][0]['properties'].get('extras') for r in provider]
notes = load(folder / 'reference-schema-notes.json')
assert notes['emptyExtras'] == sum(not value for value in extras) == 70
assert notes['extraFieldNames'] == sorted({k for value in extras if isinstance(value, dict) for k in value}) == ['roadaccessrestrictions']
assert load(folder / 'schema-check.json')['all49HeadersIndependentlyConfirmed']
assert load(folder / 'schema-check.json')['inventorySha256'] == digest(folder / 'inventory.json')
decision = load(folder / 'decision.json')
assert decision['status'] == 'bounded_missing_timing_input_proposal'
assert not decision['dataAcquired'] and not decision['candidateProduced'] and decision['selectedPolicy'] is None
proposal = load(folder / 'data-input-proposal.json')
assert proposal['selection']['windowCount'] == len(proposal['selection']['windows']) == 21
assert len({case for window in proposal['selection']['windows'] for case in window['validationCaseIds']}) == 83
assert sum(len(window['validationCaseIds']) for window in proposal['selection']['windows']) == 83
assert len({(w['origin']['lon'], w['origin']['lat']) for w in proposal['selection']['windows']}) == 21
for window in proposal['selection']['windows']:
    lon, lat = window['origin']['lon'], window['origin']['lat']
    assert window['bbox'] == [lon - .05, lat - .05, lon + .05, lat + .05]
assert proposal['hardCaps']['receivedHttpBodyBytes'] == 512 * 1024 ** 2
assert proposal['hardCaps']['routingProviderRequests'] == proposal['hardCaps']['paidSpend'] == proposal['hardCaps']['retries'] == 0
assert inventory['routingQueries'] == inventory['sourceBuilds'] == inventory['sourceDownloads'] == 0
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
                  'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True,
                  'localAssetsChecked': local, 'censusSchemas': 49, 'orsSchemas': 83, 'valhallaSchemas': 35,
                  'proposalWindows': 21, 'pilotDataAcquired': False, 'v9Unchanged': True}, indent=2))
