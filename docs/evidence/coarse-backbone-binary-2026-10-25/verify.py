"""Read-only saved bindings; never rebuilds, loads the model or calls a provider."""
import hashlib
import json
import sys
from pathlib import Path

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
    previous = repo / 'docs/evidence' / name
    assert digest(previous / 'sha256.json') == record['manifestSha256'], name
    saved = load(previous / 'sha256.json')
    assert len(saved) == record['files']
    verify_files(saved, previous)
report = load(folder / 'report.json')
pack = load(folder / 'measurements-v3/packaging-v2.json')
result = load(folder / 'measurements-v3/result-v2.json')
assert pack['passed'] and pack['functionBytes'] == sum(v['bytes'] for v in pack['files'].values())
assert pack['functionBytes'] + 4194304 == pack['totalWithReserve'] <= 70000000
assert result['processes'] == 3 and result['allLoadsPassed']
for index in range(1, 4):
    worker = load(folder / f'measurements-v3/load-v2-{index}.json')
    assert worker['passed'] and all(worker['gates'].values())
    assert worker['firstLocalHandlerMs'] <= 3000
    assert worker['summary']['loadDecodeValidateMs'] <= 3000
    assert worker['retainedDecodedBytes'] == (worker['after']['heapUsed'] - worker['baseline']['heapUsed']
                                             + worker['after']['arrayBuffers'] - worker['baseline']['arrayBuffers'])
    assert worker['retainedDecodedBytes'] <= 162238546
    assert worker['outboundCalls'] == 0
assert report['allValuesAndHashesEqual'] and report['independentPythonAudit']
assert not report['runtimeChanged'] and not report['routingAvailable']
local = '--local-assets' in sys.argv
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    generated = repo / checks['generatedFunctionRoot']
    assert set(pack['files']) == {str(p.relative_to(generated)) for p in generated.rglob('*') if p.is_file()}
    for name, info in pack['files'].items():
        assert (generated / name).stat().st_size == info['bytes']
        assert digest(generated / name) == info['sha256'], name
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
                  'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True,
                  'localAssetsChecked': local, 'binaryPackageAndLocalLoadQualified': True,
                  'routingQualified': False, 'v9Unchanged': True, 'providerRequests': 0}, indent=2))
