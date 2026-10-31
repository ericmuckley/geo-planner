"""Read-only frozen-fragment readiness; no test/producer replay or Docker."""
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
assert digest(folder / 'execution-plan.json') == '509e98e071d67659698a550e6672766bad5e820a4f8d82c20688199669913fdd'
assert digest(repo / plan['rules']) == plan['rulesSha256']
local = '--local-assets' in sys.argv
for path, sha in plan['inputs'].items():
    if local or not path.startswith('data/'):
        assert digest(repo / path) == sha, path
for target, sha in plan['workerFiles'].items():
    source = 'scripts/' + Path(target).name if target.startswith('/code/') else next(k for k, v in plan['mounts'].items() if v == target)
    assert plan['inputs'][source] == sha, source
assert plan['entryModule'] == 'coarse_timing_fragments' and '/code/coarse_timing_fragments.py' in plan['workerFiles']
assert plan['network'] == 'none' and plan['imagePull'] == 'never'
assert plan['memoryBytes'] == 1073741824 and plan['swapBytes'] == 0 and plan['wallSeconds'] == 3600
assert plan['outputBytes'] == 134217728 and plan['tmpBytes'] == 67108864
assert plan['maximumRowsPerChain'] == 64 and plan['maximumExpandedStatesPerArc'] == 4096
assert (plan['expectedRows'], plan['expectedMatches'], plan['expectedSamples'], plan['expectedWindows']) == (55120, 2469, 85629, 21)
ready = load(folder / 'readiness.json')
assert ready['hostTests'] == ready['networkDisabledLinuxTests'] == 18
assert ready['biomeFiles'] == 197 and ready['typecheckPassed'] and ready['ordinaryBuildPassed']
assert ready['actualLinuxMemoryGuard'] == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0} and ready['actualLinuxNetworkGuardPassed']
assert ready['syntheticAssertions']['endToEndArcRecords'] == 2 and ready['syntheticAssertions']['endToEndOriginalSourceKm'] == 112
assert ready['syntheticAssertions']['endToEndNewUncappedClippedRecords'] == 1
assert all(ready['syntheticAssertions'][k] for k in ['emptyCacheRecordRetained', 'everyOriginalFieldAndInputBytesPreserved', 'independentProjectionIntervalUnionEnumerationAgrees', 'tamperedFractionsProjectionsWeightsOriginalStatusAndAccessClaimsRejected', 'oldMatcherReplayProhibitedInNewPipeline'])
assert ready['newCachedGeometryEnumerations'] == ready['newRealProducerExecutions'] == ready['newSourceToolProviderRequests'] == ready['newRoutingQueries'] == 0
assert not ready['graphArraysLoaded'] and not ready['originalFeasibilityQualified'] and not ready['productionChanged']
failure = (folder / 'linux-preflight-rejection.txt').read_text()
assert 'Worker requires an init supervisor for hard timeout' in failure and 'Ran 18 tests' not in failure
assert 'Ran 18 tests' in (folder / 'unit-tests.txt').read_text() and 'Ran 18 tests' in (folder / 'linux-tests.txt').read_text()
assert checks['realOutputAbsentAtFreeze'] and not checks['realProducerExecuted']
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
    'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True, 'localAssetsChecked': local,
    'syntheticHostTests': 18, 'syntheticLinuxTests': 18, 'frozenInputs': len(plan['inputs']), 'frozenWorkerFiles': len(plan['workerFiles']),
    'newRealProducerExecutionsAtCheckpoint': 0, 'newCachedGeometryEnumerationsAtCheckpoint': 0,
    'plannedOutputCurrentlyExists': (repo / plan['output']).exists(), 'newNetworkRequests': 0, 'v9Unchanged': True}, indent=2))
