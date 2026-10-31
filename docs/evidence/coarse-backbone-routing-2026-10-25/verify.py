"""Read-only bindings and stored decisions; no model load/search or service calls."""
import gzip
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
    base = repo / 'docs/evidence' / name
    assert digest(base / 'sha256.json') == record['manifestSha256'], name
    saved = load(base / 'sha256.json')
    assert len(saved) == record['files']
    verify_files(saved, base)
comparison = load(folder / 'comparison.json')
analysis = load(folder / 'analysis.json')
assert not comparison['accuracyGatesPassed'] and not analysis['accuracyGatesPassed']
assert comparison['gates'] == analysis['gates']
assert sum(not value for value in analysis['gates'].values()) == 14
assert len(comparison['rows']) == len(analysis['normalizedRows']) == 83
assert analysis['independentGateAnd166ComponentSumAudit'] and analysis['all83And35Retained']
assert not comparison['runtimeChanged'] and comparison['outboundCalls'] == 0
assert digest(folder / 'paths.json.gz') == comparison['pathSha256']
assert len(json.loads(gzip.decompress((folder / 'paths.json.gz').read_bytes()))) == 83
plan = load(folder / 'execution-plan.json')
assert digest(folder / 'execution-plan.json') == comparison['planSha256']
for path, expected in plan['inputs'].items():
    if not path.startswith(('data/', 'node_modules/')):
        assert digest(repo / path) == expected, path
local = '--local-assets' in sys.argv
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    output = repo / checks['candidateOutputRoot']
    assert set(checks['candidateOutputFiles']) == {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
                  'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True,
                  'localAssetsChecked': local, 'candidateRejected': True, 'failedGates': 14,
                  'all83CasesAnd35SensitivitiesAnd166ComponentSumsRetained': True,
                  'v9Unchanged': True, 'providerRequests': 0}, indent=2))
