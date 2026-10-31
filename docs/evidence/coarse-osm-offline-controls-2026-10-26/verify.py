"""Read-only synthetic-controls and metadata-recipe readiness; no execution."""
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
plan = load(folder / 'metadata-plan.json')
assert digest(folder / 'metadata-plan.json') == '1f802ec11e3491a375ca80327a9968a482bd1db6a0d162448c793842400a1fa2'
verify_files(plan['inputs'], repo)
assert len(plan['inputs']) == 12 and len(plan['workerFiles']) == len(plan['mounts']) == 7
for source, target in plan['mounts'].items():
    assert plan['workerFiles'][target] == plan['inputs'][source]
assert plan['phase'] == 'metadata_only_dependency_lock' and plan['network'] == 'bridge' and plan['imagePull'] == 'never'
assert plan['memoryBytes'] == 1073741824 and plan['tmpBytes'] == 67108864
assert plan['caps'] == {'attempts': 5, 'totalBytes': 16777216, 'kindBytes': {'metadata': 16777216, 'wheel': 0, 'pbf': 0},
    'wallSeconds': 300, 'idleSeconds': 20, 'workingBytes': 536870912, 'errorBytes': 65536}
assert plan['specs'] == [{'url': f'https://pypi.org/pypi/{n}/json', 'kind': 'metadata', 'maxBytes': 2097152, 'seconds': 20}
    for n in ['requests', 'charset-normalizer', 'idna', 'urllib3', 'certifi']]
ready, proof = load(folder / 'readiness.json'), load(folder / 'resource-proof.json')
assert ready['hostSyntheticTests'] == ready['networkDisabledLinuxSyntheticTests'] == 39
assert ready['biomeFiles'] == 197 and ready['typecheckPassed'] and ready['ordinaryBuildPassed']
assert 'Ran 39 tests' in (folder / 'unit-tests.txt').read_text() and 'Ran 39 tests' in (folder / 'linux-tests.txt').read_text()
assert 'FAILED (failures=1)' in (folder / 'development-cap-test-failure.txt').read_text()
assert proof['memoryGuard'] == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0} and proof['tmpCapacityBytes'] == 67108864
assert all(proof[k] for k in ['overLimitChildKilledByCgroup', 'independentWatchdogKilledStalledChild', 'absoluteDeadlineInterruptedBlockingCall', 'sqlitePageCapStoppedWrites'])
assert proof['sqliteCapBytes'] == 16384 and not (folder / 'resource-proof-errors.txt').read_text()
assert all(ready[k] == 0 for k in ['newMetadataRoadToolProviderRequests', 'newMatcherRuns', 'appDatabaseReadsWrites', 'newToolBinariesInstalled'])
assert not ready['actualPbfDecoderQualified'] and not ready['fullDependencyLockReady'] and not ready['largerDataLimitsOrSnapshotActivated'] and not ready['productionRuntimeChanged']
local = '--local-assets' in sys.argv
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
    'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True, 'localAssetsChecked': local,
    'hostSyntheticTests': 39, 'linuxSyntheticTests': 39, 'safeResourceAndSqliteCapProof': True,
    'frozenMetadataInputs': 12, 'workerFiles': 7, 'metadataGetsPlanned': 5,
    'newLiveRequestsAtCheckpoint': 0, 'actualPbfDecoderQualified': False,
    'metadataOutputCurrentlyExists': (repo / plan['output']).exists(), 'v9Unchanged': True}, indent=2))
