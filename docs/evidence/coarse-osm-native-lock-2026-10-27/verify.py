"""Read-only stopped-lock proof; never follows signed URLs or exposes query values."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys
from urllib.parse import parse_qsl, urlsplit

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bindings(mapping, root):
    for name, pin in mapping.items():
        assert sha(root / name) == pin, name


manifest = load(folder / 'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name != 'sha256.json'}
bindings(manifest, folder)
parent = load(folder / 'parent-proof.json')
assert sha(repo / parent['path'] / 'sha256.json') == parent['manifestSha256']
with contextlib.redirect_stdout(io.StringIO()):
    runpy.run_path(str(repo / parent['path'] / 'verify.py'), run_name='__main__')
plan = load(folder / 'execution-plan.json')
assert sha(folder / 'execution-plan.json') == '698a0269066901147b60c60b72b074ddb29e1c24c975f46db11b04c38ca38348'
assert len(plan['inputs']) == 233 and len(plan['workerFiles']) == 232
bindings({n: s for n, s in plan['inputs'].items() if not n.startswith('data/')}, repo)
assert plan['caps']['attempts'] == 16 and plan['caps']['eachBytes'] == 2097152 and plan['caps']['totalBytes'] == 16777216
assert plan['phases'] == {'controls': 'none', 'acquire': 'bridge'} and plan['imagePull'] == 'never'
assert all(n.startswith(('scripts/', 'docs/evidence/')) for n in plan['mounts'])
raw = folder / 'raw'
assert load(raw / 'controls/controls.json') == {'tests': 19, 'successful': True, 'failures': 0, 'errors': 0, 'skipped': 0}
for phase, code, network in [('controls', 0, 'none'), ('acquire', 2, 'bridge')]:
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
    assert final['clientExitCode'] == final['State']['ExitCode'] == code and not final['State']['Running'] and not final['State']['OOMKilled']
    cleanup = load(root / 'cleanup.json')
    independent = load(folder / (phase + '-cleanup-audit.json'))
    assert cleanup['removed'] and cleanup['independentInspectAbsent'] and independent['independentInspectAbsent']
    assert cleanup['ownedContainer'] == independent['ownedContainer'] and independent['exitCode'] == 1
result = load(raw / 'acquire/result.json')
assert result['status'] == 'stopped' and result['error'] == 'Config status/size/digest'
assert result['image'] == 'unmeasured' and set(result['sources'].values()) == {'unmeasured'}
assert result['requests'] == 2 and result['receivedBodyBytes'] == 6901
assert result['binaryDownloads'] == result['sourceOrSampleReads'] == 0 and not result['modelChanged']
summary = load(raw / 'run-summary.json')
assert summary['status'] == 'stopped' and summary['phaseClientExitCodes'] == {'controls': 0, 'acquire': 2}
assert summary['hostSecondsIncludingHashStartupControlsAcquireOfflineAuditCleanup'] < 600
assert not summary['compilerQualified'] and not summary['fullImportAdmitted'] and not summary['modelChanged']
assert load(raw / 'offline-audit.json')['ledgerVerified'] and not load(raw / 'offline-audit.json')['completeLockReplayed']
ledger = load(folder / 'public-http-ledger.json')
assert ledger['receivedBodyBytes'] == sum(e['bodyBytes'] for e in ledger['events']) == 6901
assert [(e['kind'], e['status'], e['bodyBytes']) for e in ledger['events']] == [('registry', 200, 5542), ('config', 302, 1359)]
assert all(e['outcome'] == 'body_complete' and not e['authBodyRedacted'] for e in ledger['events'])
assert 'location' not in ledger['events'][1]['headers']
review = load(folder / 'partial-manifest-review.json')
root_digest = 'sha256:' + sha(raw / 'acquire/http/001.bin')
assert root_digest == ledger['events'][0]['headers']['docker-content-digest'] == review['rootManifestDigest']
assert root_digest == 'sha256:a3e02308c822fb6ce0d12248b0c941817ba5e1a1bc9e7bb5929f29c50eaa40a9'
image = load(raw / 'acquire/http/001.bin')
assert review['configDescriptor'] == image['config'] and image['config']['size'] == 14396
assert len(image['layers']) == review['layerCount'] == 25
assert sum(r['size'] for r in image['layers']) == review['compressedLayerBytes'] == 565413699
assert not review['configAcquired'] and not review['arm64ConfigVerified'] and not review['completeImageLock']
redirect = ledger['events'][1]['redactedLocation']
assert redirect == review['redirectMetadata'] and redirect['host'] == 'cdn01.quay.io' and redirect['scheme'] == 'https'
assert redirect['path'].endswith(image['config']['digest'][7:]) and redirect['queryValuesRedacted']
redaction = load(folder / 'redactions.json')
omitted = {'acquire/http/ledger.json', 'acquire/http/002.bin'}
assert set(redaction['rawFilesOmittedFromReport']) == omitted and not redaction['rawProducerRecordsAltered']
roster = load(folder / 'closed-output.json')
assert roster['files'] == len(roster['roster']) == 24 and roster['totalBytes'] == sum(r['bytes'] for r in roster['roster'].values()) == 91013
for name, record in roster['roster'].items():
    path = raw / name
    if name in omitted:
        assert not path.exists() and record == redaction['rawFilesOmittedFromReport'][name]
    else:
        assert path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], name
proposal = load(folder / 'redirect-correction-proposal.json')
assert proposal['reuse']['manifestDigest'] == root_digest and proposal['reuse']['configDescriptor'] == image['config']
assert proposal['redirectPolicy']['maximumHops'] == 1 and proposal['redirectPolicy']['host'] == redirect['host']
assert proposal['newStandaloneCaps'] == {'attempts': 12, 'eachBytes': 2097152, 'totalBytes': 14680064, 'hostSeconds': 600, 'retries': 0}
assert 12 + 2 <= 16 and 14680064 + 6901 < 16777216 and not proposal['fullImportAdmitted']
checks = load(folder / 'verification.json')
assert checks['hostControls'] == checks['linuxPreFreezeControls'] == checks['linuxFrozenControls'] == 19 and not checks['skipped']
assert checks['checkPassed197Files'] and checks['typecheckPassed'] and checks['buildPassed']
local = '--local-assets' in sys.argv
if local:
    bindings(plan['inputs'], repo)
    root = repo / roster['root']
    assert set(roster['roster']) == {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    for name, record in roster['roster'].items():
        path = root / name
        assert not path.is_symlink() and path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], name
    original = load(root / 'acquire/http/ledger.json')
    event = original['events'][1]
    location = event['headers'].pop('location')
    parsed = urlsplit(location)
    event['redactedLocation'] = {'scheme': parsed.scheme, 'host': parsed.hostname, 'path': parsed.path,
        'queryParameterNames': [k for k, v in parse_qsl(parsed.query)], 'urlSha256': hashlib.sha256(location.encode()).hexdigest(), 'queryValuesRedacted': True}
    assert original == ledger
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': 232, 'priorSealedRuns': 44,
    'bindingsValid': True, 'localAssetsChecked': local, 'controlsPassed': 19, 'metadataRequests': 2,
    'bodyBytes': 6901, 'configRedirectFollowed': False, 'completeBuildLock': False,
    'signedQueryValuesExcludedFromReport': True, 'ownedRemovalsIndependentlyConfirmed': True,
    'fullImportAdmitted': False, 'v9Unchanged': True}, indent=2))
