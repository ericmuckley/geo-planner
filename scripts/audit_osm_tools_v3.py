"""Read-only archive/install/native-output reconciliation; no setup or native reader replay."""
import ctypes
from email.parser import BytesParser
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tarfile
import xml.etree.ElementTree as ET
import zipfile


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def tree(root):
    result = {}; total = 0
    for path in sorted(Path(root).rglob('*')):
        assert not path.is_symlink(), path
        if path.is_dir(): continue
        assert path.is_file(), path
        result[str(path.relative_to(root))] = {'bytes': path.stat().st_size, 'sha256': sha(path)}; total += path.stat().st_size
    return {'bytes': total, 'files': result}


def audit(repo, *, inspect_archive=False):
    repo = Path(repo).resolve(); load = lambda p: json.loads(p.read_text())
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    v2 = repo / 'data/coarse-quality/us-osm-tools-v2'; v3 = repo / 'data/coarse-quality/us-osm-tools-v3'
    plan2 = load(v2 / 'execution-plan.json'); plan3 = load(v3 / 'execution-plan.json')
    pin = plan2['package']; archive = v2 / 'acquire/http/001.bin'; ledger = load(v2 / 'acquire/http/http-ledger.json')
    assert len(ledger['events']) == 1 and not ledger['stopped']; event = ledger['events'][0]
    assert event['method'] == 'GET' and event['kind'] == 'runtime' and event['status'] == 200 and event['outcome'] == 'complete' and event['url'] == pin['url']
    assert archive.stat().st_size == event['bodyBytes'] == int(event['headers']['content-length']) == pin['exactBytes'] == 83528
    assert sha(archive) == event['bodySha256'] == pin['sha256'] == plan3['package']['sha256']
    assert hashlib.md5(archive.read_bytes()).hexdigest() == event['bodyMd5']
    assert ledger['receivedBodyBytes'] == 83528 and ledger['bodyBytesByKind'] == {'runtime': 83528, 'metadata': 0, 'wheel': 0, 'pbf': 0}
    assert load(v2 / 'acquire/failure.json')['error'] == 'Unexpected runtime symlink'
    assert not (v2 / 'offline').exists() and not (v2 / 'acquire/runtime').exists()
    assert load(v2 / 'run-summary.json')['status'] == 'stopped'
    summary = load(v3 / 'run-summary.json'); assert summary['status'] == 'passed' and summary['phases'] == [{'phase': 'prepare', 'exitCode': 0}, {'phase': 'offline', 'exitCode': 0}]
    assert plan3['networks'] == ['none', 'none'] and summary['runtimePackageRequests'] == 0 and all(summary[k] == 0 for k in ('metadataRequests', 'wheelRequests', 'nationalPbfRequests', 'providerRequests'))
    receipt = load(v3 / 'prepare/runtime-receipt.json'); runtime = v3 / 'prepare/runtime'
    assert receipt['archiveSha256'] == pin['sha256'] and not receipt['packageScriptsExecuted']
    for name, record in [('libexpat.so.1', receipt['library']), ('copyright', receipt['copyright'])]:
        assert (runtime / name).stat().st_size == record['bytes'] and sha(runtime / name) == record['sha256']
    assert receipt['library']['bytes'] == 174168 and receipt['library']['sha256'] == '96c872449f41ac16cf6c974ea93e053713b41ea103165cb2c99bb0ebdc2e94be'
    assert receipt['copyright']['bytes'] == 1756
    archive_shared = 'Independent ar/tar/member selection; same immutable-image Zstandard decoder as producer.'
    if inspect_archive:
        # Separate minimal ar/tar reconstruction; no producer extraction function imported.
        assert sha('/usr/lib64/libzstd.so.1.5.5') == plan3['zstd']['sha256']
        api = ctypes.CDLL('/usr/lib64/libzstd.so.1.5.5')
        api.ZSTD_decompress.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]; api.ZSTD_decompress.restype = ctypes.c_size_t
        raw = archive.read_bytes(); assert raw[:8] == b'!<arch>\n'; position = 8; members = []
        while position < len(raw):
            header = raw[position:position + 60]; assert len(header) == 60 and header[-2:] == b'`\n'
            size = int(header[48:58]); position += 60; payload = raw[position:position + size]; assert len(payload) == size
            members.append((header[:16].decode().strip().rstrip('/'), payload)); position += size + size % 2
        assert len(members) == 3 and members[0] == ('debian-binary', b'2.0\n')
        reconstructed = {}; expanded = 0
        for group, (name, compressed) in zip(('control', 'data'), members[1:]):
            assert name == group + '.tar.zst'
            output = ctypes.create_string_buffer(8388608); length = api.ZSTD_decompress(output, len(output), compressed, len(compressed)); assert 0 < length <= 8388608
            expanded += length; values = {}
            with tarfile.open(fileobj=io.BytesIO(output.raw[:length]), mode='r:') as tar:
                for entry in tar:
                    path = entry.name.removeprefix('./').rstrip('/')
                    if path in ('', '.') and entry.isdir(): continue
                    assert path not in values
                    body = tar.extractfile(entry).read() if entry.isfile() else None
                    values[path] = {'kind': 'directory' if entry.isdir() else 'file' if entry.isfile() else 'symlink', 'link': entry.linkname,
                        'bytes': len(body) if body is not None else 0, 'sha256': hashlib.sha256(body).hexdigest() if body is not None else None}
            reconstructed[group] = values
        assert reconstructed == receipt['members'] and expanded == receipt['expandedTarBytes'] < 8388608
        assert len([e for e in reconstructed['data'].values() if e['kind'] == 'symlink']) == 2
    offline = v3 / 'offline'; installed = tree(offline / 'site'); assert installed == load(offline / 'installed-inventory.json')
    assert installed['bytes'] == 8241646 and len(installed['files']) == 182
    lock = load(repo / 'docs/evidence/coarse-osm-tool-lock-v3-run-2026-10-26/lock.json')
    validation_bytes = 0
    for cached, pin in zip(plan3['wheels'], lock['packages']):
        wheel = repo / cached['path']; assert sha(wheel) == pin['sha256'] and wheel.stat().st_size == pin['size']
        expanded = tree(offline / 'validation' / pin['name']); validation_bytes += expanded['bytes']
        with zipfile.ZipFile(wheel) as zipped:
            for member in zipped.infolist():
                if member.is_dir(): continue
                body = zipped.read(member); assert expanded['files'][member.filename] == {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
    assert validation_bytes == 8236978
    versions = {}
    for path in (offline / 'site').glob('*.dist-info/METADATA'):
        metadata = BytesParser().parsebytes(path.read_bytes()); versions[metadata['Name'].lower().replace('_', '-')] = metadata['Version']
    assert versions == {p['name']: p['version'] for p in lock['packages']} == load(offline / 'installation.json')['versions']
    assert load(offline / 'expat-version.json') == {'version': 'expat_2.4.7', 'librarySha256': receipt['library']['sha256']}
    assert load(offline / 'runtime-preflight.json')['runtimeClosurePassed'] and load(offline / 'native-proof.json')['tinyNativeDecoderQualified']
    native = offline / 'native'; smoke = load(native / 'smoke-result.json'); state = load(native / 'extract/state.json'); selection = load(native / 'extract/audit.json')
    assert smoke['status'] == 'passed' and smoke['tinyNativeDecoderQualified'] and smoke['inputRecords'] == 9 and smoke['retainedRecords'] == 4 and smoke['fourPassVisits'] == 36
    projected = load(native / 'projected.json'); assert len(projected) == 9
    # Independently reconstruct the copied native fields from the saved XML input.
    xml_rows = []
    for obj in ET.parse(native / 'fixture.osm').getroot():
        row = {'type': obj.tag, 'id': int(obj.attrib['id']), 'version': int(obj.attrib['version']), 'timestamp': obj.attrib['timestamp'],
            'visible': obj.attrib['visible'] == 'true', 'tags': {e.attrib['k']: e.attrib['v'] for e in obj if e.tag == 'tag'}}
        if obj.tag == 'node': row.update(lon=float(obj.attrib['lon']), lat=float(obj.attrib['lat']))
        if obj.tag == 'way': row['nodes'] = [int(e.attrib['ref']) for e in obj if e.tag == 'nd']
        if obj.tag == 'relation': row['members'] = [{'type': e.attrib['type'], 'ref': int(e.attrib['ref']), 'role': e.attrib['role']} for e in obj if e.tag == 'member']
        xml_rows.append(row)
    assert projected == xml_rows
    output = native / 'extract/elements.jsonl'; rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert {(r['element']['type'], r['element']['id']) for r in rows} == {('node', 1), ('node', 2), ('way', 1), ('relation', 1)}
    expected = {(r['type'], r['id']): r for r in projected}
    for row in rows:
        element = row['element']; assert element == expected[element['type'], element['id']]
        assert row['elementSha256'] == hashlib.sha256(canonical(element)).hexdigest() and row['windowIds'] == ['a', 'b']
        assert row['publisherStateUtc'] == '2026-10-25T21:21:21Z'
        if element['type'] == 'way': assert row['geometryDependencySha256'] == hashlib.sha256(canonical([row['publisherStateUtc'], [expected['node', i] for i in element['nodes']]])).hexdigest()
    assert state['scanObjectVisits'] == 36 and len(state['passes']) == 4 and all(p['status'] == 'eof' and p['counts'] == {'node': 4, 'way': 3, 'relation': 2} for p in state['passes'])
    assert selection['independentSelectionNativeIdentityAndOutputAudit'] and selection['retainedElements'] == 4 and selection['windowOccurrences'] == 8
    assert sha(output) == smoke['outputSha256'] == state['outputSha256'] == selection['outputSha256']
    for db_path in (native / 'extract').glob('*.sqlite'):
        db = sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True)
        try:
            assert db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
            assert db.execute('SELECT id,lon,lat FROM nodes ORDER BY id').fetchall() == [(r['id'], r['lon'], r['lat']) for r in projected if r['type'] == 'node']
        finally: db.close()
    fixture = native / 'fixture.osm.pbf'; assert fixture.stat().st_size == smoke['pbfBytes'] == 564 and sha(fixture) == smoke['sourceIdentity']['sourceSha256']
    for negative in smoke['negativeFramingChecks']:
        path = native / (negative['name'] + '.pbf'); assert negative['rejected'] and path.stat().st_size == negative['bytes'] and sha(path) == negative['sha256']
    assert len(smoke['negativeFramingChecks']) == 7 and smoke['nativeTruncatedCheck']['rejected']
    for root, phase, network, code in [(v2, 'acquire', 'bridge', 2), (v3, 'prepare', 'none', 0), (v3, 'offline', 'none', 0)]:
        stage = root / phase; container = load(stage / 'container-result.json'); cleanup = load(stage / 'cleanup.json')
        assert container['State']['ExitCode'] == code and not container['State']['OOMKilled']
        assert container['Limits'] == {'NetworkMode': network, 'Memory': 1073741824, 'MemorySwap': 1073741824, 'ReadonlyRootfs': True,
            'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=64m'}}
        assert cleanup['removed'] and cleanup['independentInspectAbsent']
        assert all(not m['writable'] for m in container['Mounts'] if m['destination'] != '/work')
    inventories = {name: tree(root) for name, root in [('v2', v2), ('v3', v3)]}
    for name, root in [('v2', v2), ('v3', v3)]:
        local_summary = load(root / 'run-summary.json'); assert local_summary['driverSecondsIncludingCleanupBeforeSummary'] < 600
        assert inventories[name]['bytes'] + local_summary['reservedReadOnlyInputsBytes'] + 67108864 < 536870912
    return {'status': 'passed', 'independentArchiveReconstructionExecuted': inspect_archive, 'archiveAuditSharedPrimitive': archive_shared,
        'packageGetsAcrossV2V3': 1, 'packageBodyBytes': 83528, 'additionalV3NetworkRequests': 0, 'libraryBytes': 174168, 'librarySha256': receipt['library']['sha256'],
        'validationBytes': validation_bytes, 'installedBytes': installed['bytes'], 'installedFiles': len(installed['files']), 'versions': versions,
        'nativePbfBytes': 564, 'nativeProjectedRecords': 9, 'retainedRecords': 4, 'fourPassVisits': 36, 'negativeFramingChecks': 7, 'nativeTruncatedRejected': True,
        'tinyNativeDecoderQualified': True, 'nationalSourceFeasibilityQualified': False, 'independentOwnedCleanupReceiptsValid': True,
        'outputFiles': {name: len(value['files']) for name, value in inventories.items()}, 'outputFileBytes': {name: value['bytes'] for name, value in inventories.items()}}


if __name__ == '__main__': print(json.dumps(audit(sys.argv[1], inspect_archive='--archive' in sys.argv), indent=2))
