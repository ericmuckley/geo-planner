"""Read-only stopped-pilot proof; never rerun capture, install tools or query."""
import hashlib
import json
from pathlib import Path
import sys

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def verify_files(files, root):
    for name, sha in files.items():
        assert digest(root / name) == sha, name

manifest = load(folder / 'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name != 'sha256.json'}
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
for name in ['execution-plan.json', 'analysis-plan.json', 'recovery-plan.json']:
    for path, sha in load(folder / name)['inputs'].items():
        if local or not path.startswith('data/'):
            assert digest(repo / path) == sha, (name, path)
state, audit = load(folder / 'state.json'), load(folder / 'analysis.json')
assert state['status'] == 'stopped' and state['errorType'] == 'URLError'
assert state['budget']['receivedHttpBodyBytes'] == audit['receivedHttpBodyBytes'] == 123155489
assert state['budget']['toolBodyBytes'] == audit['toolBodyBytes'] == 41148539
assert state['budget']['httpRequests'] == audit['httpRequests'] == 1115
assert state['budget']['uniqueRows'] == audit['retainedUniqueRoadRows'] == 55120
assert audit['completedWindows'] == 0 and audit['plannedWindows'] == 21
assert all(w['status'] == 'unmeasured_after_stop' for w in state['windows'])
assert not audit['feasibilityQualified'] and not audit['coverageMatchingAndReviewPerformed']
assert audit['independentCaptureBudgetIdentityAndPartialRowAudit']
assert load(folder / 'resource-proof.json')['hardMemoryGuardProven']
assert load(folder / 'parquet-selftest.json')['realRangedReadPassed']
assert not load(folder / 'container-result.json')['State']['OOMKilled']
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
                  'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True,
                  'localAssetsChecked': local, 'retainedRoadRows': 55120, 'completedWindows': 0,
                  'plannedWindows': 21, 'stoppedWithoutRetry': True, 'feasibilityQualified': False,
                  'v9Unchanged': True}, indent=2))
