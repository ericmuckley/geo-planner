"""Saved V2-stop/V3-correction proof. No request, worker or producer replay."""
import hashlib
import json
from pathlib import Path
import sys


folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())


def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def files(mapping, root):
    for name, digest in mapping.items(): assert sha(root / name) == digest, name


manifest = load(folder / 'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name != 'sha256.json'}
files(manifest, folder)
checks = load(folder / 'checks.json'); files(checks['producerFiles'], repo); files(checks['preservedFiles'], repo)
for name, record in checks['priorSealedEvidence'].items():
    prior = repo / 'docs/evidence' / name; assert sha(prior / 'sha256.json') == record['manifestSha256']
    previous = load(prior / 'sha256.json'); assert len(previous) == record['files']; files(previous, prior)
v2 = folder / 'v2'; audit = load(folder / 'stop-audit.json'); ledger = load(v2 / 'download/http/http-ledger.json')
assert len(ledger['events']) == 1 and ledger['receivedBodyBytes'] == 34603008 and not ledger['stopped']
event = ledger['events'][0]
assert event['status'] == 200 and event['outcome'] == 'started' and event['kind'] == 'pbf' and event['bodyBytes'] == 34603008
assert int(event['headers']['content-length']) == 12229320016 and 'bodySha256' not in event
failure = load(v2 / 'download/driver-failure.json')
assert failure['error'] == 'Special data output' and failure['hardStopCountersMayBePartial'] and len(failure['windows']) == 21
assert all(w['status'] == 'unqualified_after_driver_stop' for w in failure['windows'])
assert audit['status'] == 'preserved_driver_stop_verified' and audit['sourceAttempts'] == 1 and not audit['meterFinalized']
assert audit['retainedPartialBodyBytes'] == 34603008 and audit['prefixSha256'] == '35d5005766e6a2a4e0f76723586b3b232dc0e493055420f0841797c85a12175a'
assert not audit['fullSourceChecksumQualified'] and not audit['nativeObjectScansStarted'] and audit['nativeProjectedRecords'] == 0
assert not audit['workerExitAndOomStateCaptured'] and audit['oomKilled'] is None and audit['finalWorkerExitCode'] is None
assert audit['observedWorkerMemory'] == {'memoryMaxBytes': 4294967296, 'swapMaxBytes': 0} and audit['observedTmpBytes'] == 268435456
assert audit['outputFiles'] == 9 and audit['outputFileBytes'] == 34670122
assert audit['observedHeaderBytes'] == 191 and audit['observedPublisherStateUtc'] == '2026-10-25T21:21:21Z' and audit['headerMatchesRecipe']
assert load(folder / 'partial-header-audit.json')['stateMatchesRecipe'] and load(folder / 'cleanup-audit.json')['independentInspectAbsent']
plan = load(folder / 'correction-plan.json'); expected = 'a7155c25e61516c9cd61bb3b32f5bd96e5ef8811c265a93f4b845c69f448857e'
assert sha(folder / 'correction-plan.json') == expected and plan['phase'] == 'national_input_v3' and plan['output'] == 'data/coarse-quality/us-osm-input-v3'
files({p: s for p, s in plan['inputs'].items() if not p.startswith('data/')}, repo)
original = load(v2 / 'execution-plan.json')
assert plan['extractConfig'] == original['extractConfig'] and plan['sourceSpec'] == original['sourceSpec'] and plan['networks'] == ['bridge', 'none']
assert plan['runtime'] == original['runtime'] and plan['site'] == original['site'] and plan['imageId'] == original['imageId']
assert len(plan['inputs']) == 212 and len(plan['workerFiles']) == 201 and len(plan['mounts']) == 17
assert plan['correction']['newSourceRequestsBeforeFreeze'] == 0 and not plan['correction']['partialBodyReuseOrRangeResume']
checked = load(folder / 'correction-readonly-check.json')
assert checked['status'] == 'checked_not_executed' and checked['httpRequestsMade'] == 0 and not checked['outputCreated']
capacity = checked['capacity']; assert capacity['hostDiskAvailableBytes'] >= 85899345920 and capacity['dockerMemoryBytes'] >= 6442450944 and capacity['hostMemoryBytes'] >= 8589934592
commands = load(folder / 'correction-commands.json'); base = ['python3', '-B', 'scripts/prepare_osm_input_v3.py', str((folder / 'correction-plan.json').relative_to(repo)), expected, plan['output']]
assert commands['executeLaterOnce'] == base and commands['readOnlyCheck'] == base + ['--check'] and not commands['executedNow']
controls = load(folder / 'correction-checks.json'); assert controls['hostRegressionTests'] == controls['linuxRegressionTests'] == 11 and controls['newSourceRequests'] == 0
local = '--local-assets' in sys.argv
if local:
    files(checks['assetFiles'], repo); files(checks['toolFiles'], repo); files(plan['inputs'], repo)
    for path, roster in checks['completedOutputs'].items(): assert set(roster) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
    for name in checks['mirroredOutputReports']: assert sha(repo / 'data/coarse-quality/us-osm-input-v2' / name) == sha(v2 / name)
    sys.path.insert(0, str(repo / 'scripts')); from audit_osm_data_stop import audit as reconcile
    assert reconcile(repo / 'data/coarse-quality/us-osm-input-v2') == audit
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']), 'priorSealedRuns': len(checks['priorSealedEvidence']),
    'allBindingsValid': True, 'localAssetsChecked': local, 'assetFiles': len(checks['assetFiles']), 'tools': len(checks['toolFiles']), 'completedOutputs': len(checks['completedOutputs']),
    'sourceAttempts': 1, 'journaledAndRetainedPrefixBytes': 34603008, 'headerMatchesRecipe': True, 'fullSourceAcquired': False,
    'nativeExtractionStarted': False, 'workerFinalExitAndOomKnown': False, 'ownedRemovalConfirmed': True, 'v3ReadOnlyCheckPassed': True, 'v3SourceRequests': 0, 'v9Unchanged': True}, indent=2))
