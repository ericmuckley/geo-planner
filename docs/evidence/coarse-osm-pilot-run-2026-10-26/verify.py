"""Read-only stopped-capture proof; no HTTP, Docker, audit or producer replay."""
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
assert digest(folder / 'execution-plan.json') == digest(repo / 'docs/evidence/coarse-osm-pilot-2026-10-26/execution-plan.json')
verify_files(plan['inputs'], repo)
verify_files(load(folder / 'next-input-design-plan.json')['inputs'], repo)
state, audit, summary = (load(folder / name) for name in ['state.json', 'audit.json', 'run-summary.json'])
assert state['status'] == 'stopped' and state['stage'] == 'status' and state['error'] == 'HTTP refusal/status 502'
assert state['snapshotUtc'] == '2026-10-21T00:00:00Z' and state['sourceGenerator'] is None
assert [w['id'] for w in state['windows']] == [q['id'] for q in load(repo / 'docs/evidence/coarse-input-redesign-2026-10-26/queries.json')['queries']]
assert [w['status'] for w in state['windows']] == ['incomplete_after_stop'] + ['unmeasured_after_stop'] * 20
assert len(state['http']) == 1
event = state['http'][0]
assert (event['number'], event['kind'], event['method'], event['url'], event['windowId']) == (1, 'status', 'GET', 'https://overpass-api.de/api/status', 'origin-00')
assert event['status'] == 502 and event['outcome'] == 'failed' and event['formBodySha256'] is None
assert event['bodyFile'] == 'http/00001.bin' and event['headers'] == {'content-type': 'text/plain', 'content-length': '534'}
assert event['receivedBodyBytes'] == (folder / event['bodyFile']).stat().st_size == 534
assert event['bodySha256'] == digest(folder / event['bodyFile']) == summary['responseBodySha256']
assert {p.name for p in (folder / 'http').iterdir()} == {'00001.bin'}
budget = state['budget']
assert budget['httpAttempts'] == 1 and budget['receivedHttpBodyBytes'] == 534 and budget['stopped']
assert budget['uniqueNormalizedElements'] == budget['validatedElementOccurrences'] == budget['normalizedExtractBytes'] == 0
assert budget['accountedWorkingBytes'] == budget['initialWorkingBytes'] + 534
assert (folder / 'elements.jsonl').stat().st_size == 0
assert audit['independentRawBodiesCountsClosureTypedIdentityAndLedgerAudit'] and not audit['captureComplete']
assert audit['httpAttempts'] == 1 and audit['receivedHttpBodyBytes'] == 534 and audit['windows'] == 21 and audit['completedWindows'] == 0
assert audit['uniqueNormalizedElements'] == audit['validatedElementOccurrences'] == 0
assert not audit['sourceAdapterImplemented'] and not audit['originalFeasibilityQualified']
assert summary['captureElapsedSeconds'] == budget['elapsedSeconds']
assert summary['statusRequestElapsedSeconds'] == event['finishedElapsedSeconds'] - event['startedElapsedSeconds']
assert 0 < summary['statusRequestElapsedSeconds'] < event['absoluteTimeoutSeconds'] == 10
assert 0 < summary['captureElapsedSeconds'] < plan['wallSeconds']
guards, container, stop, cleanup = (load(folder / name) for name in ['resource-guards.json', 'container-result.json', 'driver-stop.json', 'cleanup.json'])
assert guards['memoryGuard'] == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0} and guards['independentWatchdogSeconds'] == 3600
assert container['Image'] == plan['containerImageId'] and container['Limits'] == {'NetworkMode': 'bridge', 'Memory': 1073741824, 'MemorySwap': 1073741824, 'ReadonlyRootfs': True}
assert container['State']['Status'] == 'exited' and container['State']['ExitCode'] == 2 and not container['State']['OOMKilled']
assert stop == {'workerExitCode': 2, 'captureAdmitted': False, 'lastStateRetained': True, 'hardStopCountersMayBePartial': False}
assert cleanup['removed'] and summary['removalIndependentlyConfirmed']
assert not (folder / 'worker.log').read_bytes()
assert summary['attemptedRuns'] == summary['httpAttempts'] == summary['statusGets'] == 1
assert all(summary[k] == 0 for k in ['interpreterPosts', 'retries', 'redirectsFollowed', 'mirrorSwitches', 'toolDownloads', 'routingProviderRequests', 'databaseReadsWrites', 'newMatcherRuns'])
assert not summary['implementationChanged'] and not summary['runtimeChanged'] and not summary['originalFeasibilityQualified']
output_names = checks['completedOutputs'][plan['output']]
assert len(output_names) == summary['outputFiles'] == 11
assert sum((folder / name).stat().st_size for name in output_names) == summary['outputFileBytes'] == 19429
assert summary['outputFileBytes'] + plan['tmpBytes'] < plan['workingBytes']
local = '--local-assets' in sys.argv
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
    for name in output_names:
        assert digest(repo / plan['output'] / name) == digest(folder / name), name
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
    'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True, 'localAssetsChecked': local,
    'httpAttempts': 1, 'receivedHttpBodyBytes': 534, 'interpreterPosts': 0, 'completedWindows': 0,
    'independentStoppedAuditPassed': True, 'captureComplete': False, 'ownedContainerRemoved': True,
    'sourceFeasibilityQualified': False, 'v9Unchanged': True}, indent=2))
