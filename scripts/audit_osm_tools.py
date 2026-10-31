"""Read-only reconciliation of the preserved tool-v1 ABI failure; no producer imports."""
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import sys
import zipfile


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def tree(root):
    result = {}; total = 0
    for path in sorted(Path(root).rglob('*')):
        assert not path.is_symlink(), path
        if path.is_dir(): continue
        assert path.is_file(), path
        size = path.stat().st_size; total += size
        result[str(path.relative_to(root))] = {'bytes': size, 'sha256': sha(path)}
    return {'bytes': total, 'files': result}


def audit(root, lock_path, diagnostic_path):
    root = Path(root).resolve(); load = lambda path: json.loads(Path(path).read_text())
    lock = load(lock_path); plan = load(root / 'execution-plan.json'); acq = root / 'acquire'; offline = root / 'offline'
    ledger = load(acq / 'http/http-ledger.json'); receipt = load(acq / 'acquisition.json')
    assert len(ledger['events']) == len(lock['packages']) == 6 and not ledger['stopped']
    body_bytes = validation_bytes = 0
    for i, (event, pin, record, spec) in enumerate(zip(ledger['events'], lock['packages'], receipt['packages'], plan['wheelSpecs']), 1):
        archive = acq / 'http' / f'{i:03d}.bin'
        assert event['number'] == i and event['method'] == 'GET' and event['status'] == 200 and event['outcome'] == 'complete'
        assert event['url'] == pin['url'] == spec['url'] and event['kind'] == 'wheel'
        assert archive.stat().st_size == event['bodyBytes'] == int(event['headers']['content-length']) == pin['size'] == spec['exactBytes']
        assert sha(archive) == event['bodySha256'] == pin['sha256'] == spec['sha256'] == record['sha256']
        assert event['bodyMd5'] == hashlib.md5(archive.read_bytes()).hexdigest()
        assert 0 <= event['finishedElapsed'] - event['startedElapsed'] < event['absoluteSeconds']
        body_bytes += archive.stat().st_size
        validation = tree(acq / 'validation' / pin['name']); validation_bytes += validation['bytes']
        assert validation['bytes'] == record['installedBytes'] and len(validation['files']) == record['files']
        with zipfile.ZipFile(archive) as zipped:
            members = [m for m in zipped.infolist() if not m.is_dir()]
            assert {m.filename for m in members} == set(validation['files'])
            for member in members:
                raw = zipped.read(member)
                assert len(raw) == validation['files'][member.filename]['bytes']
                assert hashlib.sha256(raw).hexdigest() == validation['files'][member.filename]['sha256']
    assert body_bytes == ledger['receivedBodyBytes'] == receipt['archiveBytes'] == lock['toolArchiveBytes'] == 2387936
    assert ledger['bodyBytesByKind'] == {'metadata': 0, 'wheel': body_bytes, 'pbf': 0}
    assert validation_bytes == receipt['validationBytes'] == 8236978 < plan['caps']['unpackedValidationBytes']
    installed = tree(offline / 'site'); assert installed == load(offline / 'installed-inventory.json')
    assert installed['bytes'] == 8241646 < plan['caps']['installedTreeBytes'] and len(installed['files']) == 182
    versions = {}
    for path in (offline / 'site').glob('*.dist-info/METADATA'):
        metadata = BytesParser().parsebytes(path.read_bytes()); name = metadata['Name'].lower().replace('_', '-')
        assert name not in versions; versions[name] = metadata['Version']
    assert versions == {p['name']: p['version'] for p in lock['packages']}
    assert 'Successfully installed' in (offline / 'pip.log').read_text()
    failure = load(offline / 'proof-failure.json')
    assert failure['phase'] == 'proof' and failure['errorType'] == 'ImportError' and 'libexpat.so.1' in failure['error']
    assert not (offline / 'native').exists() and not (offline / 'native-proof.json').exists() and not (offline / 'installation.json').exists()
    summary = load(root / 'run-summary.json')
    assert summary['status'] == 'stopped' and summary['phases'] == [{'phase': 'acquire', 'exitCode': 0}, {'phase': 'offline', 'exitCode': 2}]
    for name, network, code in [('acquire', 'bridge', 0), ('offline', 'none', 2)]:
        stage = root / name; container = load(stage / 'container-result.json'); cleanup = load(stage / 'cleanup.json'); guard = load(stage / 'resource-guards.json')
        assert container['State']['ExitCode'] == code and not container['State']['OOMKilled'] and container['Image'] == plan['imageId']
        assert container['Limits'] == {'NetworkMode': network, 'Memory': 1073741824, 'MemorySwap': 1073741824,
            'ReadonlyRootfs': True, 'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=64m'}}
        assert all(not m['writable'] for m in container['Mounts'] if m['destination'] != '/work')
        assert guard['memory'] == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0} and guard['watchdogSeconds'] == 600
        assert cleanup['removed'] and cleanup['independentInspectAbsent']
    proof_guard = load(offline / 'proof-resource-guards.json'); assert proof_guard['watchdogSeconds'] == 60
    diagnostic = load(diagnostic_path)
    assert len(diagnostic['extensions']) == 10 and diagnostic['missingLibraries'] == ['libexpat.so.1']
    assert sum(e['missing'] == ['libexpat.so.1'] for e in diagnostic['extensions']) == 8
    files = tree(root)
    assert files['bytes'] + 67108864 < plan['caps']['workingBytesIncludingTmp']
    assert summary['driverSecondsIncludingCleanupBeforeSummary'] < 600
    assert files['bytes'] - (root / 'run-summary.json').stat().st_size == summary['outputBytesBeforeSummary']
    return {'status': 'preserved_native_ABI_failure_verified', 'independentArchiveLedgerAndInstalledTreeReconciliation': True,
        'wheelGetAttempts': 6, 'wheelBodyBytes': body_bytes, 'metadataRequests': 0, 'nationalPbfRequests': 0, 'providerRequests': 0,
        'validationBytes': validation_bytes, 'installedBytes': installed['bytes'], 'installedFiles': len(installed['files']), 'installedMetadataVersions': versions,
        'missingSharedLibraries': diagnostic['missingLibraries'], 'nativeImportSucceeded': False, 'tinyPbfTestsExecuted': False,
        'tinyNativeDecoderQualified': False, 'nationalSourceFeasibilityQualified': False, 'ownedCleanupIndependentlyConfirmed': True,
        'outputFiles': len(files['files']), 'outputFileBytes': files['bytes'], 'driverSecondsIncludingCleanupBeforeSummary': summary['driverSecondsIncludingCleanupBeforeSummary'],
        'meterElapsedSeconds': ledger['elapsedSeconds'], 'timingScope': 'Meter ends after final wheel fetch/ledger; driver includes owned worker startup/download/validation/install/failed import/cleanup before final summary. Neither is routing latency or measured peak memory.'}


if __name__ == '__main__': print(json.dumps(audit(*sys.argv[1:]), indent=2))
