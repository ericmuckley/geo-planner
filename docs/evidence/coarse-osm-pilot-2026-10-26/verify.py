"""Read-only executable-capture readiness; no HTTP, Docker or producer replay."""
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
    previous = load(base / 'sha256.json')
    assert len(previous) == record['files']
    verify_files(previous, base)
plan = load(folder / 'execution-plan.json')
assert digest(folder / 'execution-plan.json') == 'c8dd8d24f91a9fa679cd22ebd48bc06d38728a3605b8c29494c29d1d6e53fd48'
verify_files(plan['inputs'], repo)
assert digest(repo / plan['controls']) == plan['controlsSha256']
assert len(plan['inputs']) == 41 and len(plan['workerFiles']) == 29 and len(plan['queryPaths']) == 21
for path, sha in plan['workerFiles'].items():
    source = next(k for k, v in plan['mounts'].items() if v == path)
    assert plan['inputs'][source] == sha
assert plan['network'] == 'bridge' and plan['imagePull'] == 'never'
assert plan['memoryBytes'] == 1073741824 and plan['swapBytes'] == 0 and plan['wallSeconds'] == 3600
assert plan['workingBytes'] == 2147483648 and plan['tmpBytes'] == 67108864
assert plan['maximumHttpAttempts'] == 42 and plan['maximumHttpBodyBytes'] == 536870912
ready, proof = load(folder / 'readiness.json'), load(folder / 'resource-proof.json')
assert ready['hostTests'] == ready['networkDisabledLinuxTests'] == 28
assert ready['biomeFiles'] == 197 and ready['typecheckPassed'] and ready['ordinaryBuildPassed']
assert proof['memoryGuard'] == ready['actualLinuxMemoryGuard'] == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0}
assert proof['tmpCapacityBytes'] == 67108864
assert all(proof[k] for k in ['overLimitChildKilledByCgroup', 'independentWatchdogKilledStalledChild', 'absoluteDeadlineInterruptedBlockingCall'])
assert not (folder / 'resource-proof-errors.txt').read_text()
assert 'Ran 28 tests' in (folder / 'unit-tests.txt').read_text() and 'Ran 28 tests' in (folder / 'linux-tests.txt').read_text()
assert all(ready[k] == 0 for k in ['newRoadStatusInterpreterRequests', 'newToolBinaryDownloads', 'newRoutingProviderQueries', 'newMatcherRuns'])
assert not ready['sourceAdapterImplemented'] and not ready['originalFeasibilityQualified'] and not ready['runtimeChanged']
local = '--local-assets' in sys.argv
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
    'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True, 'localAssetsChecked': local,
    'hostTests': 28, 'linuxTests': 28, 'hardMemorySwapTmpWatchdogAndTimerProof': True,
    'frozenInputs': 41, 'workerFiles': 29, 'unchangedQueries': 21,
    'newLiveRequestsAtCheckpoint': 0, 'plannedOutputCurrentlyExists': (repo / plan['output']).exists(),
    'sourceFeasibilityQualified': False, 'v9Unchanged': True}, indent=2))
