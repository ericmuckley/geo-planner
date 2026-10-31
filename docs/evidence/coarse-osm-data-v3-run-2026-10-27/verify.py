"""Read-only closed V3 source/deadline proof; no network, Docker or native replay."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

manifest = load(folder / 'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name != 'sha256.json'}
for name, digest in manifest.items():
    assert sha(folder / name) == digest, name
parent = repo / 'docs/evidence/coarse-osm-data-run-2026-10-26'
assert sha(parent / 'sha256.json') == load(folder / 'parent-proof.json')['manifestSha256']
# The parent verifies all 204 unchanged producers, 38 earlier sealed runs and saved assets.
with contextlib.redirect_stdout(io.StringIO()):
    runpy.run_path(str(parent / 'verify.py'), run_name='__main__')
root = folder / 'v3'
plan = load(root / 'execution-plan.json')
assert sha(root / 'execution-plan.json') == 'a7155c25e61516c9cd61bb3b32f5bd96e5ef8811c265a93f4b845c69f448857e'
receipt = load(root / 'download/source-receipt.json')
ledger = load(root / 'download/http/http-ledger.json')
assert len(ledger['events']) == 1 and not ledger['stopped']
event = ledger['events'][0]
assert event['status'] == 200 and event['outcome'] == 'complete' and event['method'] == 'GET'
assert event['url'] == plan['sourceSpec']['url'] and event['kind'] == 'pbf'
assert receipt['bodyBytes'] == event['bodyBytes'] == ledger['receivedBodyBytes'] == int(event['headers']['content-length']) == 12229320016
assert ledger['bodyBytesByKind'] == {'metadata': 0, 'wheel': 0, 'pbf': 12229320016}
state = load(root / 'extract/extract/state.json')
identity = state['sourceIdentity']
assert receipt['sha256'] == event['bodySha256'] == identity['sourceSha256'] == '1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff'
assert receipt['publisherMd5'] == event['bodyMd5'] == identity['sourceMd5'] == plan['sourceSpec']['md5'] == 'c5abaec55e724255277f22fb97941e5a'
assert identity['publisherStateUtc'] == plan['extractConfig']['source']['proposedPublisherReplicationStateUtc'] == '2026-10-25T21:21:21Z'
assert identity['requiredFeatures'] == ['DenseNodes', 'OsmSchema-V0.6'] and identity['frames'] == 221321
assert identity['framingBytesRead'] == state['hashFramingBytesRead'] == receipt['bodyBytes']
assert state['status'] == 'running' and state['stage'] == 'primary-index-selection'
assert state['passes'] == [{'label': 'primary-index-selection', 'status': 'running', 'counts': {'node': 320881664}}]
assert state['scanObjectVisits'] == 320881664 and state['retainedElements'] == state['extractBytes'] == state['windowOccurrences'] == 0
failure = load(root / 'extract/driver-failure.json')
assert failure['errorType'] == 'PilotError' and failure['error'] == 'Data shared host deadline'
assert failure['hardStopCountersMayBePartial'] and not failure['derivedIndexesTrusted'] and not failure['sourceFeasibilityQualified']
assert [w['id'] for w in failure['windows']] == [w['id'] for w in plan['extractConfig']['windows']]
assert len(failure['windows']) == 21 and all(w['status'] == 'unqualified_after_driver_stop' for w in failure['windows'])
cleanup = load(folder / 'cleanup-audit.json')
for phase in ('download', 'extract'):
    guards = load(root / phase / 'resource-guards.json')
    assert guards['memory'] == {'memoryMaxBytes': 4294967296, 'swapMaxBytes': 0} and guards['tmpBytes'] == 268435456
    initial = load(root / phase / 'container-initial.json')
    assert initial['Limits']['NetworkMode'] == ('bridge' if phase == 'download' else 'none')
    assert initial['Limits']['NanoCpus'] == 2000000000 and initial['Limits']['PidsLimit'] == 64 and initial['Limits']['ReadonlyRootfs']
    assert all(not m['writable'] for m in initial['Mounts'] if m['destination'] != '/work')
    removed = load(root / phase / 'cleanup.json')
    assert removed['removed'] and removed['independentInspectAbsent']
    assert any(c['phase'] == phase and c['ownedContainer'] == removed['ownedContainer'] and c['independentInspectAbsent'] for c in cleanup['containers'])
assert load(root / 'download/container-result.json')['State']['ExitCode'] == 0
assert not load(root / 'download/container-result.json')['State']['OOMKilled']
assert load(root / 'extract/container-before-removal.json')['State']['Running']
result = load(folder / 'execution-result.json')
assert result['observedHostExitCode'] == 1 and result['nativeEofPasses'] == 0 and result['windowsUnqualified'] == 21
assert result['extractWorkerFinalExitCode'] is None and result['extractWorkerFinalOomKilled'] is None
assert not any(result[k] for k in ('sourceFeasibilityQualified', 'publisherBoundaryQualified', 'usableAttributesQualified', 'modelChanged'))
inventory = load(folder / 'retained-output.json')
assert inventory['files'] == len(inventory['roster']) == 21
assert sum(v['bytes'] for v in inventory['roster'].values()) == inventory['totalFileBytes']
assert inventory['roster']['download/http/001.bin']['bytes'] == receipt['bodyBytes']
assert inventory['roster']['download/http/001.bin']['sha256'] == receipt['sha256']
assert inventory['roster']['extract/extract/primary-nodes.sqlite']['bytes'] == 8783028224
assert all(n not in inventory['roster'] for n in ('run-summary.json', 'extract/container-result.json', 'extract/extract/elements.jsonl', 'completion-check.json'))
local = '--local-assets' in sys.argv
if local:
    source = repo / inventory['root']
    assert set(inventory['roster']) == {str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()}
    for name, binding in inventory['roster'].items():
        path = source / name
        assert not path.is_symlink() and path.stat().st_size == binding['bytes'] and sha(path) == binding['sha256'], name
        if (root / name).is_file():
            assert sha(root / name) == binding['sha256'], name
print(json.dumps({'recordFiles': len(manifest), 'unchangedProducerFiles': 204, 'priorSealedRuns': 39, 'parentBindingsValid': True,
    'localAssetsChecked': local, 'closedV3Files': inventory['files'], 'closedV3Bytes': inventory['totalFileBytes'],
    'sourceAttempts': 1, 'fullSourceBytes': receipt['bodyBytes'], 'acquisitionFramingAndClosedSourceHashMatch': True,
    'nativeObjectVisitsAtLastCheckpoint': state['scanObjectVisits'], 'nativeEofPasses': 0, 'allWindowsUnqualified': 21,
    'ownedRemovalsIndependentlyConfirmed': True, 'extractWorkerFinalExitAndOomKnown': False, 'v9Unchanged': True}, indent=2))
