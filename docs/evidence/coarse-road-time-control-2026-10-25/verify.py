"""Verify saved control bindings; never load a model, rerun an audit or search."""
import gzip
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
    old = load(base / 'sha256.json')
    assert len(old) == record['files']
    verify_files(old, base)
local = '--local-assets' in sys.argv
for name in ['plan.json', 'analysis-plan.json', 'next-diagnostic-plan.json']:
    for path, expected in load(folder / name)['inputs'].items():
        if local or not path.startswith('data/'):
            assert digest(repo / path) == expected, (name, path)
report = load(folder / 'report.json')
analysis = load(folder / 'analysis.json')
assert report['planSha256'] == digest(folder / 'plan.json')
assert analysis['analysisPlanSha256'] == digest(folder / 'analysis-plan.json')
assert report['summary'] == analysis['summary']
assert report['routeSearches'] == report['outboundCalls'] == 0
assert not report['runtimeChanged']
assert len(report['rows']) == len(report['ledger']) == analysis['cases'] == 83
assert len(json.loads(gzip.decompress((folder / 'edge-audit.json.gz').read_bytes()))) == 83
assert sum(r['valhallaMinutes'] is not None for r in report['rows']) == 35
comparison = {r['set'] + '/' + r['id']: r for r in
              load(repo / 'docs/evidence/coarse-road-time-allowance-2026-10-25/comparison.json')['rows']}
assert all(r['valhallaMinutes'] == comparison[r['id']]['valhallaMinutes'] for r in report['rows'])
assert analysis['componentTotalsChecked'] == 249
assert report['boundVerified'] == analysis['boundVerified'] == 83
assert report['capLimited'] == analysis['capLimited'] == 0
assert report['allOldAndCurrentCapturedPricesReproduced']
assert report['allHeldTransitionsEligible'] and report['allComponentEquationsReconcile']
assert analysis['independentArithmeticAndCapturedIdentityAudit']
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
                  'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True,
                  'localAssetsChecked': local, 'cases': 83, 'sensitivities': 35,
                  'componentTotals': 249, 'eligibleBoundsVerified': 83, 'capLimited': 0,
                  'v9Unchanged': True, 'routingSearches': 0, 'providerRequests': 0}, indent=2))
