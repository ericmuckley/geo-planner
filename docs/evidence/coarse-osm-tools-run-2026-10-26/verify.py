"""Read-only preserved tool-v1 proof; no downloads, Docker or producer replay."""
import hashlib
import json
from pathlib import Path
import sys


folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda path: json.loads(path.read_text())


def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_files(files, root):
    for name, digest in files.items(): assert sha(root / name) == digest, name


manifest = load(folder / 'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name != 'sha256.json'}
verify_files(manifest, folder)
checks = load(folder / 'checks.json')
verify_files(checks['producerFiles'], repo); verify_files(checks['preservedFiles'], repo)
for name, record in checks['priorSealedEvidence'].items():
    base = repo / 'docs/evidence' / name
    assert sha(base / 'sha256.json') == record['manifestSha256']
    previous = load(base / 'sha256.json'); assert len(previous) == record['files']
    verify_files(previous, base)
plan = load(folder / 'execution-plan.json')
assert sha(folder / 'execution-plan.json') == 'f01f06dda71c7b24e6de2c43d0ead5f391673645676bea242bf40bdc172e194b'
verify_files(plan['inputs'], repo)
lock = load(repo / plan['lock']); ledger = load(folder / 'acquire/http/http-ledger.json')
receipt = load(folder / 'acquire/acquisition.json'); summary = load(folder / 'run-summary.json'); audit = load(folder / 'tool-audit.json')
assert len(ledger['events']) == len(lock['packages']) == len(receipt['packages']) == 6 and not ledger['stopped']
assert ledger['receivedBodyBytes'] == lock['toolArchiveBytes'] == audit['wheelBodyBytes'] == receipt['archiveBytes'] == 2387936
assert ledger['bodyBytesByKind'] == {'metadata': 0, 'wheel': 2387936, 'pbf': 0}
for i, (event, pin, spec, saved) in enumerate(zip(ledger['events'], lock['packages'], plan['wheelSpecs'], receipt['packages']), 1):
    assert event['number'] == i and event['method'] == 'GET' and event['status'] == 200 and event['outcome'] == 'complete' and event['kind'] == 'wheel'
    assert event['url'] == pin['url'] == spec['url']
    assert event['bodyBytes'] == int(event['headers']['content-length']) == pin['size'] == spec['exactBytes']
    assert event['bodySha256'] == pin['sha256'] == spec['sha256'] == saved['sha256']
assert receipt['validationBytes'] == sum(p['installedBytes'] for p in receipt['packages']) == audit['validationBytes'] == 8236978
installed = load(folder / 'offline/installed-inventory.json')
assert installed['bytes'] == sum(p['bytes'] for p in installed['files'].values()) == audit['installedBytes'] == 8241646
assert len(installed['files']) == audit['installedFiles'] == 182
assert audit['installedMetadataVersions'] == {p['name']: p['version'] for p in lock['packages']}
assert load(folder / 'offline/proof-failure.json')['error'] == 'libexpat.so.1: cannot open shared object file: No such file or directory'
assert summary['status'] == 'stopped' and summary['phases'] == [{'phase': 'acquire', 'exitCode': 0}, {'phase': 'offline', 'exitCode': 2}]
for phase, network, code in [('acquire', 'bridge', 0), ('offline', 'none', 2)]:
    container = load(folder / phase / 'container-result.json'); cleanup = load(folder / phase / 'cleanup.json')
    assert container['Image'] == plan['imageId'] and container['State']['ExitCode'] == code and not container['State']['OOMKilled']
    assert container['Limits'] == {'NetworkMode': network, 'Memory': 1073741824, 'MemorySwap': 1073741824,
        'ReadonlyRootfs': True, 'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=64m'}}
    assert cleanup['removed'] and cleanup['independentInspectAbsent']
    assert load(folder / phase / 'resource-guards.json')['memory'] == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0}
cleanup_audit = load(folder / 'cleanup-audit.json'); assert len(cleanup_audit['workers']) == 2
assert all(p['independentInspectAbsent'] for p in cleanup_audit['workers'])
assert load(folder / 'runtime-diagnostic.json')['missingLibraries'] == audit['missingSharedLibraries'] == ['libexpat.so.1']
assert not audit['nativeImportSucceeded'] and not audit['tinyPbfTestsExecuted'] and not audit['tinyNativeDecoderQualified'] and not audit['nationalSourceFeasibilityQualified']
assert audit['outputFiles'] == 368 and audit['outputFileBytes'] == 18921586
assert audit['outputFileBytes'] + 67108864 < plan['caps']['workingBytesIncludingTmp']
assert audit['driverSecondsIncludingCleanupBeforeSummary'] == summary['driverSecondsIncludingCleanupBeforeSummary'] < 600
assert audit['meterElapsedSeconds'] == ledger['elapsedSeconds']
next_plan = load(folder / 'next-runtime-plan.json')
assert len(next_plan['savedWheels']) == 6 and sum(p['bytes'] for p in next_plan['savedWheels']) == 2387936
for p, pin in zip(next_plan['savedWheels'], lock['packages']): assert p['sha256'] == pin['sha256'] and p['filename'] == pin['filename']
local = '--local-assets' in sys.argv
if local:
    verify_files(checks['assetFiles'], repo); verify_files(checks['toolFiles'], repo)
    for path, roster in checks['completedOutputs'].items():
        assert set(roster) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
    root = repo / plan['output']
    for name in checks['mirroredOutputReports']: assert sha(root / name) == sha(folder / name)
    sys.path.insert(0, str(repo / 'scripts'))
    from audit_osm_tools import audit as reconcile
    assert reconcile(root, repo / plan['lock'], folder / 'runtime-diagnostic.json') == audit
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']), 'priorSealedRuns': len(checks['priorSealedEvidence']),
    'allBindingsValid': True, 'localAssetsChecked': local, 'assetFiles': len(checks['assetFiles']), 'tools': len(checks['toolFiles']),
    'completedOutputs': len(checks['completedOutputs']), 'wheelGets': 6, 'wheelBodyBytes': 2387936, 'offlineInstallCompleted': True,
    'nativeAbiGatePassed': False, 'missingLibrary': 'libexpat.so.1', 'tinyPbfTestsExecuted': False, 'nationalPbfRequests': 0, 'v9Unchanged': True}, indent=2))
