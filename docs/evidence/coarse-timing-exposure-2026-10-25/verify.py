"""Read-only evidence/source/asset bindings; no model, producer or query execution."""
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
for name in ['plan.json', 'analysis-plan.json', 'next-diagnostic-plan.json']:
    for path, expected in load(folder / name)['inputs'].items():
        if local or not path.startswith('data/'):
            assert digest(repo / path) == expected, (name, path)
report, analysis = load(folder / 'report.json'), load(folder / 'analysis.json')
assert report['planSha256'] == digest(folder / 'plan.json')
assert analysis['analysisPlanSha256'] == digest(folder / 'analysis-plan.json')
assert report['cases'] == analysis['cases'] == len(report['rows']) == len(report['coverageLedger']) == 83
assert report['sensitivities'] == analysis['sensitivities'] == sum(r['valhallaMinutes'] is not None for r in report['rows']) == 35
assert len(report['cohorts']) == analysis['cohorts'] == 20
assert sum(r['coverageStatus'] == 'no_full_census' for r in report['rows']) == analysis['noFullCensus'] == 3
assert analysis['coverageAvailable'] == 80
assert report['allIdentifiersComponentsClassesAndCoverageReconciled']
assert analysis['independentIdentifiersSourceComponentsAndCohortsAudit']
assert report['routingQueries'] == report['providerRequests'] == 0 and not report['runtimeChanged']
assert load(folder / 'decision.json')['status'] == 'insufficient_evidence_for_selective_timing_rule'
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
                  'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True,
                  'localAssetsChecked': local, 'cases': 83, 'sensitivities': 35, 'cohorts': 20,
                  'coverageAvailable': 80, 'noFullCensus': 3,
                  'v9Unchanged': True, 'routingQueries': 0, 'providerRequests': 0}, indent=2))
