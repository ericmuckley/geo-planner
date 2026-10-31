"""Read-only v2-stop and v3-readiness proof; no metadata/producer replay."""
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
old = load(folder / 'execution-plan.json')
assert digest(folder / 'execution-plan.json') == '1f802ec11e3491a375ca80327a9968a482bd1db6a0d162448c793842400a1fa2'
verify_files(old['inputs'], repo)
ledger, state, summary, audit = (load(folder / n) for n in ['http/http-ledger.json', 'setup-state.json', 'run-summary.json', 'audit.json'])
assert len(ledger['events']) == 2 and ledger['stopped']
assert [e['url'] for e in ledger['events']] == [s['url'] for s in old['specs'][:2]]
for i, event in enumerate(ledger['events'], 1):
    body = folder / 'http' / event['bodyFile']
    assert event['number'] == i and event['method'] == 'GET' and event['kind'] == 'metadata' and event['status'] == 200
    assert body.stat().st_size == event['bodyBytes'] and digest(body) == event['bodySha256']
    assert hashlib.md5(body.read_bytes()).hexdigest() == event['bodyMd5']
    assert 0 <= event['finishedElapsed'] - event['startedElapsed'] < event['absoluteSeconds'] == 20
first, second = ledger['events']
assert first['outcome'] == 'complete' and first['bodyBytes'] == int(first['headers']['content-length']) == 192973
assert second['outcome'] == 'failed' and second['error'] == 'Declared body oversize' and second['bodyBytes'] == 0
assert int(second['headers']['content-length']) == 2390209 > old['specs'][1]['maxBytes'] == 2097152
assert int(second['headers']['content-length']) - old['specs'][1]['maxBytes'] == summary['declaredExcessBytes'] == 293057
assert ledger['receivedBodyBytes'] == sum(e['bodyBytes'] for e in ledger['events']) == 192973
assert ledger['bodyBytesByKind'] == {'metadata': 192973, 'wheel': 0, 'pbf': 0}
assert state['status'] == 'stopped' and state['error'] == 'Declared body oversize'
assert [s['status'] for s in state['plannedRequests']] == ['complete', 'failed'] + ['unmeasured_after_stop'] * 3
assert [s['url'] for s in state['plannedRequests']] == [s['url'] for s in old['specs']]
assert not state['actualDecoderQualified'] and not state['sourceFeasibilityQualified'] and state['toolBinaryDownloads'] == state['pbfRequests'] == 0
assert not (folder / 'lock.json').exists()
assert summary['meterElapsedSeconds'] == ledger['elapsedSeconds'] and not summary['dependencyLockComplete']
assert load(folder / 'http/001.bin')['info']['version'] == summary['savedRequestsVersion'] == '2.34.2'
assert summary['savedRequestsMetadataSha256'] == digest(folder / 'http/001.bin')
assert audit['independentStoppedMetadataAccountingAudit'] and not audit['completeDependencyLock']
guards, container, stop, cleanup = (load(folder / n) for n in ['resource-guards.json', 'container-result.json', 'driver-stop.json', 'cleanup.json'])
assert guards['memory'] == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0} and guards['independentWatchdogSeconds'] == 300
assert container['Image'] == old['imageId'] and container['Limits'] == {'NetworkMode': 'bridge', 'Memory': 1073741824, 'MemorySwap': 1073741824, 'ReadonlyRootfs': True}
assert container['State']['ExitCode'] == 2 and not container['State']['OOMKilled'] and cleanup['removed']
assert stop == {'workerExitCode': 2, 'admitted': False, 'lastSetupStateRetained': True, 'hardStopCountersMayBePartial': False}
assert not (folder / 'worker.log').read_bytes()
names = checks['completedOutputs']['data/coarse-quality/us-osm-tool-lock-v2']
assert len(names) == summary['outputFiles'] == 11 and sum((folder / n).stat().st_size for n in names) == summary['outputFileBytes'] == 200572
assert summary['outputFileBytes'] + old['tmpBytes'] < old['caps']['workingBytes']
plan, ready = load(folder / 'metadata-v3-plan.json'), load(folder / 'correction-readiness.json')
assert digest(folder / 'metadata-v3-plan.json') == ready['recipeSha256'] == 'bd5bb8358cbbe41005f762578de83aae8ad34b8549008efd7b772da1a3b69044'
verify_files(plan['inputs'], repo)
verify_files(load(folder / 'decision.json')['inputs'], repo)
assert len(plan['inputs']) == 15 and len(plan['workerFiles']) == len(plan['mounts']) == 8
for source, target in plan['mounts'].items(): assert plan['workerFiles'][target] == plan['inputs'][source]
assert plan['phase'] == 'metadata_only_dependency_lock_v3' and plan['output'] == 'data/coarse-quality/us-osm-tool-lock-v3'
assert plan['caps'] == {**old['caps'], 'attempts': 4} and plan['memoryBytes'] == old['memoryBytes'] and plan['tmpBytes'] == old['tmpBytes']
assert plan['specs'] == [{'url': f'https://pypi.org/pypi/{n}/json', 'kind': 'metadata', 'maxBytes': 3145728, 'seconds': 20}
    for n in ['charset-normalizer', 'idna', 'urllib3', 'certifi']]
assert sum(s['maxBytes'] + 1 for s in plan['specs']) == ready['plannedMaximumBodyReadsBytes'] == 12582916 < plan['caps']['totalBytes']
assert ready['hostTests'] == ready['networkDisabledLinuxTests'] == 6 and ready['biomeFiles'] == 197 and ready['typecheckPassed'] and ready['ordinaryBuildPassed']
assert 'Ran 6 tests' in (folder / 'v3-unit-tests.txt').read_text() and 'Ran 6 tests' in (folder / 'v3-linux-tests.txt').read_text()
assert ready['newRequestsForCorrection'] == ready['toolBinariesDownloadedOrInstalled'] == ready['pbfRequests'] == 0
local = '--local-assets' in sys.argv
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, roster in checks['completedOutputs'].items():
        assert set(roster) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
    for name in names: assert digest(repo / old['output'] / name) == digest(folder / name)
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
    'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True, 'localAssetsChecked': local,
    'v2HttpAttempts': 2, 'v2MetadataBodyBytes': 192973, 'dependencyLockComplete': False,
    'v3HostAndLinuxTests': 6, 'v3PlannedGets': 4, 'newV3RequestsAtCheckpoint': 0,
    'v3OutputCurrentlyExists': (repo / plan['output']).exists(), 'v9Unchanged': True}, indent=2))
