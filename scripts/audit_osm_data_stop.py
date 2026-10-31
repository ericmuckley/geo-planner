"""Read-only partial-download/driver-stop reconciliation; no network or native scans."""
import datetime
import hashlib
import json
from pathlib import Path
import stat
import struct
import sys
import zlib

from coarse_osm_bulk_pbf import fields, singular


def audit(root):
    root = Path(root); load = lambda p: json.loads(p.read_text())
    plan = load(root / 'execution-plan.json'); ledger = load(root / 'download/http/http-ledger.json'); failure = load(root / 'download/driver-failure.json')
    assert len(ledger['events']) == 1; event = ledger['events'][0]; body = root / 'download/http/001.bin'
    assert event['status'] == 200 and event['method'] == 'GET' and event['kind'] == 'pbf' and event['url'] == plan['sourceSpec']['url']
    assert int(event['headers']['content-length']) == plan['sourceSpec']['exactBytes'] == 12229320016
    assert event['outcome'] == 'started' and 'bodySha256' not in event and not ledger['stopped']
    assert body.stat().st_size == event['bodyBytes'] == ledger['receivedBodyBytes'] == 34603008
    assert ledger['bodyBytesByKind'] == {'pbf': 34603008, 'metadata': 0, 'wheel': 0}
    assert failure['error'] == 'Special data output' and failure['hardStopCountersMayBePartial'] and not failure['sourceFeasibilityQualified']
    assert [w['id'] for w in failure['windows']] == [w['id'] for w in plan['extractConfig']['windows']]
    assert all(w['status'] == 'unqualified_after_driver_stop' for w in failure['windows'])
    assert not (root / 'extract').exists() and not (root / 'download/source-receipt.json').exists() and not (root / 'run-summary.json').exists()
    assert not (root / 'download/container-result.json').exists()
    roster = {}; total = 0
    for path in sorted(root.rglob('*')):
        info = path.lstat(); assert stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode), path
        if stat.S_ISREG(info.st_mode):
            with path.open('rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            roster[str(path.relative_to(root))] = {'bytes': info.st_size, 'sha256': digest}; total += info.st_size
    with body.open('rb') as stream:
        size = struct.unpack('!I', stream.read(4))[0]; assert 0 < size < 65536
        header = singular(stream.read(size)); assert header[1] == (2, b'OSMHeader'); length = header[3][1]; assert 0 < length < 1048576
        blob = singular(stream.read(length)); header_bytes = 4 + size + length
        if 1 in blob: payload = blob[1][1]
        else:
            assert 0 < blob[2][1] < 1048576
            decoder = zlib.decompressobj(); payload = decoder.decompress(blob[3][1], blob[2][1] + 1)
            assert decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail and len(payload) == blob[2][1]
    header_fields = list(fields(payload)); stamps = [v for k, w, v in header_fields if k == 32]; assert len(stamps) == 1
    stamp = datetime.datetime.fromtimestamp(stamps[0], datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    assert stamp == plan['extractConfig']['source']['proposedPublisherReplicationStateUtc']
    features = sorted(v.decode() for k, w, v in header_fields if k == 4); assert features == ['DenseNodes', 'OsmSchema-V0.6']
    guards = load(root / 'download/resource-guards.json'); cleanup = load(root / 'download/cleanup.json')
    assert guards['memory'] == {'memoryMaxBytes': 4294967296, 'swapMaxBytes': 0} and guards['tmpBytes'] == 268435456
    assert cleanup['removed'] and cleanup['independentInspectAbsent']
    return {'status': 'preserved_driver_stop_verified', 'sourceAttempts': 1, 'httpStatus': 200, 'declaredSourceBytes': 12229320016,
        'journaledBodyBytes': 34603008, 'retainedPartialBodyBytes': body.stat().st_size,
        'prefixSha256': roster['download/http/001.bin']['sha256'], 'fullSourceChecksumQualified': False,
        'lastMeterCheckpointElapsedSeconds': ledger['elapsedSeconds'], 'meterFinalized': False,
        'counterScope': 'Journal and retained spool agree at this checkpoint; hard-stop delivered/wire totals may be partial. No complete-source digest or full driver timing.',
        'observedHeaderBytes': header_bytes, 'observedPublisherStateUtc': stamp, 'requiredFeatures': features, 'headerMatchesRecipe': True,
        'headerAuditSharedPrimitive': 'Frozen protobuf fields/singular; independent byte/hash/ledger/stop reconciliation.',
        'nativeObjectScansStarted': False, 'nativeProjectedRecords': 0, 'rawEntityCounts': 'unmeasured', 'allWindowsUnqualified': 21,
        'workerExitAndOomStateCaptured': False, 'finalWorkerExitCode': None, 'oomKilled': None,
        'observedWorkerMemory': guards['memory'], 'observedTmpBytes': guards['tmpBytes'], 'ownedCleanupConfirmed': True,
        'allRetainedEntriesRegularOrDirectories': True, 'outputFiles': len(roster), 'outputFileBytes': total, 'roster': roster,
        'sourceModelQualified': False, 'v9Changed': False}


if __name__ == '__main__': print(json.dumps(audit(sys.argv[1]), indent=2))
