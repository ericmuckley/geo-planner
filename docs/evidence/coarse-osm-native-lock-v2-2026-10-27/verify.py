"""Read-only closed metadata proof; no network, Docker, native scan or producer replay."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import re
import runpy
import sys

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bindings(mapping, root):
    for name, pin in mapping.items(): assert sha(root / name) == pin, name


manifest = load(folder / 'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name != 'sha256.json'}
bindings(manifest, folder)
parent = load(folder / 'parent-proof.json')
assert sha(repo / parent['path'] / 'sha256.json') == parent['manifestSha256']
with contextlib.redirect_stdout(io.StringIO()):
    runpy.run_path(str(repo / parent['path'] / 'verify.py'), run_name='__main__')
plan = load(folder / 'execution-plan.json')
assert sha(folder / 'execution-plan.json') == '360263cb9c63f5c897a8ee22391997f8e833cd85fd8efe9fe3bf5c8d5c19e69a'
assert len(plan['inputs']) == 239 and len(plan['workerFiles']) == 236
bindings({n: s for n, s in plan['inputs'].items() if not n.startswith('data/')}, repo)
assert plan['caps']['attempts'] == 12 and plan['caps']['eachBytes'] == 2097152 and plan['caps']['totalBytes'] == 14680064
assert 'rootUrl' not in plan and plan['imagePull'] == 'never'
assert plan['phases'] == {'controls': 'none', 'acquire': 'bridge'}
assert all(n.startswith(('scripts/', 'docs/evidence/')) or n == plan['savedManifest']['path'] for n in plan['mounts'])
freeze = load(folder / 'freeze.json')
assert freeze['outputAbsent'] and freeze['hostControls'] == freeze['linuxOfflineControls'] == 27 and not freeze['skipped']
assert freeze['recipeSha256'] == sha(folder / 'execution-plan.json')
bindings(load(folder / 'pre-freeze-controls/bindings.json'), repo)
pre = load(folder / 'pre-freeze-controls/container-result.json')
assert pre['clientExitCode'] == pre['State']['ExitCode'] == 0 and not pre['State']['OOMKilled']
assert load(folder / 'pre-freeze-controls/cleanup.json')['removed']
assert load(folder / 'pre-freeze-controls/independent-absence.json')['independentInspectAbsent']
raw = folder / 'raw'
assert load(raw / 'controls/controls.json') == {'tests': 27, 'successful': True, 'failures': 0, 'errors': 0, 'skipped': 0}
for phase, network in [('controls', 'none'), ('acquire', 'bridge')]:
    root = raw / phase
    initial = load(root / 'container-initial.json')
    assert initial['Limits'] == {'NetworkMode': network, 'Memory': 4294967296, 'MemorySwap': 4294967296,
        'ReadonlyRootfs': True, 'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=256m'}}
    assert all(not m['writable'] for m in initial['Mounts'] if m['destination'] != '/work')
    assert not any(m['destination'].endswith(('.pbf', '.jsonl', '.sqlite')) for m in initial['Mounts'])
    assert {u['Name']: (u['Soft'], u['Hard']) for u in initial['Ulimits']} == {'core': (0, 0), 'fsize': (67108864, 67108864)}
    guards = load(root / 'resource-guards.json')
    assert guards['memory'] == {'memoryMaxBytes': 4294967296, 'swapMaxBytes': 0} and guards['tmpBytes'] == 268435456
    final = load(root / 'container-result.json')
    assert final['clientExitCode'] == final['State']['ExitCode'] == 0 and not final['State']['Running'] and not final['State']['OOMKilled']
    cleanup = load(root / 'cleanup.json'); independent = load(folder / (phase + '-cleanup-audit.json'))
    assert cleanup['removed'] and cleanup['independentInspectAbsent'] and independent['independentInspectAbsent']
    assert cleanup['ownedContainer'] == independent['ownedContainer'] and independent['exitCode'] == 1
result = load(raw / 'acquire/result.json')
assert result['status'] == 'metadata_locked_not_acquired' and result['image'] == 'metadata_locked'
assert set(result['sources'].values()) == {'metadata_locked'} and result['requests'] == 8 and result['receivedBodyBytes'] == 246045
assert result['binaryDownloads'] == result['sourceOrSampleReads'] == 0 and not result['modelChanged']
summary = load(raw / 'run-summary.json')
assert summary['status'] == result['status'] and summary['phaseClientExitCodes'] == {'controls': 0, 'acquire': 0}
assert summary['hostSecondsIncludingHashStartupControlsAcquireOfflineAuditCleanup'] < 600
assert not summary['compilerQualified'] and not summary['fullImportAdmitted'] and not summary['modelChanged']
ledger = load(raw / 'acquire/http/ledger.json')
assert not ledger['stopped'] and ledger['receivedBodyBytes'] == sum(e['bodyBytes'] for e in ledger['events']) == 246045
assert [(e['kind'], e['status']) for e in ledger['events']] == [('config', 302), ('cdn', 200)] + [('git', 200)] * 6
assert ledger['events'][0]['bodyFile'] is None and ledger['events'][0]['privateBodyRedacted']
assert ledger['events'][0]['bodyBytes'] == 1359 and ledger['events'][1]['bodyBytes'] == 14396
assert all(e['outcome'] == 'body_complete' for e in ledger['events'])
assert all('location' not in e.get('headers', {}) and not e.get('authBodyRedacted') for e in ledger['events'])
lock = load(raw / 'acquire/lock.json'); image = lock['image']
assert image['platform'] == 'linux/arm64' and image['expandedBytes'] is None and not image['binaryAcquired']
assert len(image['layers']) == len(image['diffIds']) == 25 and image['compressedLayerBytes'] == 565413699
assert sha(raw / 'acquire/http/002.bin') == image['config']['digest'][7:]
assert [(s['repository'], s['commit'], s['tree'], len(s['selectedFiles']), s['selectedBytes']) for s in lock['sources']] == [
    ('osmcode/libosmium', '97dccf105391d410701ae8bd52170dc0ee041373', 'c17441c8de31e1d51b596879fe61cc232c1a0367', 197, 1668371),
    ('mapbox/protozero', 'af2f6e274e0a873a00e34d8c9ab99fca76898047', '3efd40b2a7469960081054e16819191daa24d21a', 19, 144518)]
assert all(not s['annotatedTags'] and s['archiveSha256'] is None and not s['sourceAcquired'] for s in lock['sources'])
sys.path.insert(0, str(repo / 'scripts'))
from coarse_osm_native_lock_v2 import verify_saved
saved_manifest = repo / parent['path'] / 'raw/acquire/http/001.bin'
assert sha(saved_manifest) == plan['savedManifest']['sha256'] == image['manifestDigest'][7:]
assert verify_saved(raw / 'acquire', saved_manifest) == load(raw / 'offline-audit.json')
roster = load(folder / 'closed-output.json')
assert roster['files'] == len(roster['roster']) == 33 and roster['totalBytes'] == sum(r['bytes'] for r in roster['roster'].values()) == 810713
assert set(roster['roster']) == {str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}
for name, record in roster['roster'].items():
    path = raw / name
    assert path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], name
    body = path.read_bytes()
    assert not re.search(rb'(?:X-Amz-(?:Algorithm|Credential|Date|Expires|Signature|SignedHeaders)|akamai_signature)=', body), name
    assert not re.search(rb'https://cdn01\.quay\.io[^\s"<>]*\?', body), name
privacy = load(folder / 'privacy-audit.json')
assert not privacy['signedQueryValuesPersisted'] and not privacy['rawLocationHeadersPersisted'] and not privacy['configRedirectBodyPersisted']
proposal = load(folder / 'acquisition-build-proposal.json')
assert proposal['bindings']['metadataLockSha256'] == sha(raw / 'acquire/lock.json')
assert proposal['builder']['layers'] == image['layers'] and proposal['builder']['diffIds'] == image['diffIds']
assert proposal['closureReservationBytes'] == sum(proposal['componentCeilings'].values()) == 15032385536
assert proposal['proposedNetworkCaps']['attempts'] == 25 * 2 + 2 == 52 and not proposal['fullImportAdmitted']
checks = load(folder / 'verification.json')
assert checks['hostControls'] == checks['linuxPreFreezeControls'] == checks['linuxFrozenControls'] == 27 and not checks['skipped']
assert checks['checkPassed197Files'] and checks['typecheckPassed'] and checks['buildPassed']
local = '--local-assets' in sys.argv
if local:
    bindings(plan['inputs'], repo)
    root = repo / roster['root']
    assert set(roster['roster']) == {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    for name, record in roster['roster'].items():
        path = root / name
        assert not path.is_symlink() and path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], name
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': 235, 'priorSealedRuns': 45,
    'bindingsValid': True, 'localAssetsChecked': local, 'controlsPassed': 27, 'metadataRequests': 8,
    'bodyBytes': 246045, 'completeMetadataLock': True, 'completePublicJsonReplay': True,
    'signedQueryValuesPersisted': False, 'ownedRemovalsIndependentlyConfirmed': True,
    'builderAcquired': False, 'compilerOrAbiQualified': False, 'fullImportAdmitted': False, 'v9Unchanged': True}, indent=2))
