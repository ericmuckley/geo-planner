"""Read-only stored cost/gate/source bindings; no model load/search or provider."""
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
        assert digest(root/name) == expected, name

manifest = load(folder/'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*')
                         if p.is_file() and p.name != 'sha256.json'}
verify_files(manifest, folder)
checks = load(folder/'checks.json')
verify_files(checks['producerFiles'], repo)
verify_files(checks['preservedFiles'], repo)
for name, record in checks['priorSealedEvidence'].items():
    base = repo/'docs/evidence'/name
    assert digest(base/'sha256.json') == record['manifestSha256']
    old = load(base/'sha256.json')
    assert len(old) == record['files']
    verify_files(old, base)
for name in ['policy.json', 'preparation-plan.json', 'execution-plan.json', 'analysis-plan.json', 'next-diagnostic-plan.json']:
    for path, expected in load(folder/name)['inputs'].items():
        if not path.startswith('data/'):
            assert digest(repo/path) == expected, (name, path)
comparison = load(folder/'comparison.json')
analysis = load(folder/'analysis.json')
report = load(folder/'report.json')
assert comparison['gates'] == analysis['gates']
assert sum(not value for value in analysis['gates'].values()) == 6
assert not comparison['accuracyGatesPassed'] and not analysis['accuracyGatesPassed']
assert len(comparison['rows']) == len(analysis['normalizedRows']) == 83
assert analysis['independentGateAnd166ComponentSumAudit'] and analysis['all83And35Retained']
assert not report['runtimeChanged'] and comparison['outboundCalls'] == 0
assert report['allPointTimesNoFasterThanUnbufferedBackbone']
assert digest(folder/'paths.json.gz') == comparison['pathSha256']
assert len(json.loads(gzip.decompress((folder/'paths.json.gz').read_bytes()))) == 83
assert digest(folder/'execution-plan.json') == comparison['planSha256']
costs = load(folder/'independent-cost-audit.json')
assert costs['independentComponentAndPayloadAudit'] and costs['other27PayloadsExact']
assert costs['graphArcs'] == 1234223 and costs['baseLinks'] == 378515
assert costs['endpointStatesReproduced'] == 166 and costs['maximumArcMinutesDifference'] < 1e-12
assert costs['binarySha256'] == load(folder/'artifact-manifest.json')['sha256']
local = '--local-assets' in sys.argv
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo/path)) for p in (repo/path).rglob('*') if p.is_file()}
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
                  'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True,
                  'localAssetsChecked': local, 'candidateRejected': True, 'failedGates': 6,
                  'all83Cases35Sensitivities166SumsRetained': True,
                  'allCostAndPayloadControlsPassed': True, 'v9Unchanged': True, 'providerRequests': 0}, indent=2))
