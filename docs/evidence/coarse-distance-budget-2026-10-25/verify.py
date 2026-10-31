"""Read-only saved-distance evidence/source/asset bindings; no producer/search."""
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
    prior = load(base / 'sha256.json')
    assert len(prior) == record['files']
    verify_files(prior, base)
local = '--local-assets' in sys.argv
for name in ['plan.json', 'analysis-plan.json', 'next-timing-plan.json']:
    for path, expected in load(folder / name)['inputs'].items():
        if local or not path.startswith('data/'):
            assert digest(repo / path) == expected, (name, path)
report, analysis = load(folder / 'report.json'), load(folder / 'analysis.json')
assert report['planSha256'] == digest(folder / 'plan.json')
assert analysis['analysisPlanSha256'] == digest(folder / 'analysis-plan.json')
assert report['cases'] == analysis['cases'] == len(report['rows']) == len(report['ledger']) == 83
assert report['sensitivities'] == analysis['sensitivities'] == sum(r['valhallaMinutes'] is not None for r in report['rows']) == 35
assert len(report['cohorts']) == analysis['cohorts'] == 20
assert len(json.loads(gzip.decompress((folder / 'edge-audit.json.gz').read_bytes()))) == 83
assert report['allRecordedCostsSourcesAndOccurrencesReconciled']
assert analysis['independentCostsOccurrencesDistanceBoundsAndCohortsAudit']
assert analysis['transitionsChecked'] == 29247 and analysis['sourceOccurrences'] == 22316 and analysis['baseOccurrences'] == 6576
assert analysis['bounded'] == 83 and analysis['unboundedOrMissing'] == 0
assert report['cohorts']['all']['statusCounts'] == analysis['statusCounts']
assert analysis['statusCounts'] == {'recorded_model_shorter': 57, 'recorded_model_longer': 5, 'recorded_length_intervals_overlap': 21}
assert analysis['newMissStatusCounts']['recorded_model_shorter'] == 6
assert analysis['persistentMissStatusCounts']['recorded_model_shorter'] == 2
assert report['routingQueries'] == report['providerRequests'] == 0 and not report['runtimeChanged']
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
                  'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True,
                  'localAssetsChecked': local, 'cases': 83, 'sensitivities': 35, 'cohorts': 20,
                  'bounded': 83, 'unboundedOrMissing': 0, 'v9Unchanged': True,
                  'routingQueries': 0, 'providerRequests': 0}, indent=2))
