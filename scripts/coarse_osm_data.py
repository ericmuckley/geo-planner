"""Data-phase guards around the frozen native extractor; no I/O on import."""
from copy import deepcopy
import json
import os
from pathlib import Path
import resource
import sqlite3
import subprocess
import sys
import tempfile
import time

from coarse_osm_bulk import Coordinates, extract_pbf
from coarse_osm_bulk_transport import Https, Meter
from coarse_timing_input import digest, json_bytes, require


def memory_guard(root=Path('/sys/fs/cgroup')):
    require(sys.platform == 'linux', 'Data phase requires Linux cgroup')
    values = {'memoryMaxBytes': int((root / 'memory.max').read_text()), 'swapMaxBytes': int((root / 'memory.swap.max').read_text())}
    require(values == {'memoryMaxBytes': 4294967296, 'swapMaxBytes': 0}, 'Data memory/swap drift'); return values


def tree_bytes(root):
    total = 0
    for path in Path(root).rglob('*'):
        try:
            require(not path.is_symlink(), 'Symlink in data output')
            if path.is_dir(): continue
            require(path.is_file(), 'Special data output'); total += path.stat().st_size
        except FileNotFoundError: pass  # Atomic checkpoint replacement; report reserves cover transient copies.
    return total


def resource_arithmetic(config, read_only_bytes):
    c = config['proposedCaps']; components = config['resourceArithmetic']['storageComponents']
    require(sum(components.values()) <= c['workingBytesIncludingTmp'], 'Data working arithmetic')
    require(read_only_bytes <= components['toolArchivesAndInstalledTree'] + components['metadata'], 'Read-only tools/input reservation')
    require(c['sqliteMaxPagesEach'] * c['sqlitePageBytes'] == c['sqliteIndexBytesEach'], 'Data SQLite arithmetic')
    require(config['source']['listedBodyBytes'] + 1 < c['totalHttpBodyBytes'], 'Data source/sentinel arithmetic')
    return {'workingComponents': components, 'assignedWorkingBytes': sum(components.values()), 'workingSlackBytes': c['workingBytesIncludingTmp'] - sum(components.values()),
        'maximumSourceBodyReadBytes': config['source']['listedBodyBytes'] + 1, 'bodySlackBytes': c['totalHttpBodyBytes'] - config['source']['listedBodyBytes'] - 1,
        'actualReadOnlyInputReservationBytes': read_only_bytes}


def validate_plan(plan, proposal):
    require(plan['phase'] == 'national_input_v2' and plan['output'] == proposal['futureOutput'], 'National phase/output drift')
    config = plan['extractConfig']; caps = deepcopy(proposal['proposedCaps'])
    caps.update(httpAttempts=1, wheelGets=0, metadataGets=0, toolArchiveBodyBytesWithinTotal=0, metadataBodyBytesWithinTotal=0)
    require(config['source'] == proposal['source'] and config['windows'] == proposal['windows'] and config['proposedCaps'] == caps, 'National source/windows/caps drift')
    require(config['resourceArithmetic']['storageComponents'] == proposal['resourceArithmetic']['storageComponents'], 'National storage assignment drift')
    require(plan['imageId'] == proposal['tools']['cachedImageId'] and plan['networks'] == ['bridge', 'none'] and plan['imagePull'] == 'never', 'National image/network drift')
    require(plan['activation'] == {'largerDataLimits': True, 'publisherState': proposal['source']['proposedPublisherReplicationStateUtc'], 'onlyWhenExactHostCommandExecutes': True}, 'Explicit data activation missing')
    require(plan['sourceSpec'] == {'url': proposal['source']['url'], 'kind': 'pbf', 'maxBytes': proposal['source']['listedBodyBytes'],
        'exactBytes': proposal['source']['listedBodyBytes'], 'md5': proposal['source']['publisherMd5'], 'seconds': 5400}, 'Single source GET spec drift')
    resource_arithmetic(config, plan['reservedReadOnlyInputsBytes'])


def verify_worker_inputs(plan):
    for path, sha in plan['workerFiles'].items(): require(digest(path) == sha, 'Data worker binding: ' + path)
    site = Path('/tools/site')
    expected = {name.removeprefix('/tools/site/') for name in plan['workerFiles'] if name.startswith('/tools/site/')}
    require({str(p.relative_to(site)) for p in site.rglob('*') if p.is_file()} == expected, 'Qualified site file roster drift')
    require(not any(p.is_symlink() for p in site.rglob('*')), 'Qualified site symlink')


class SourceHttps(Https):
    def __init__(self, url): self.url = url
    def open(self, url, seconds, idle):
        require(url == self.url, 'Only frozen source URL allowed'); return super().open(url, seconds, idle)


def download_source(root, plan, remaining, *, transport=None):
    root = Path(root); http = root / 'http'; http.mkdir(); c = plan['extractConfig']['proposedCaps']
    caps = {'attempts': 1, 'totalBytes': c['totalHttpBodyBytes'], 'kindBytes': {'pbf': c['totalHttpBodyBytes'], 'wheel': 0, 'metadata': 0},
        'wallSeconds': remaining, 'idleSeconds': 30, 'workingBytes': c['workingBytesIncludingTmp'] - c['tmpBytes'] - plan['reservedReadOnlyInputsBytes'], 'errorBytes': 65536}
    meter = Meter(http, [plan['sourceSpec']], caps, transport=transport or SourceHttps(plan['sourceSpec']['url']))
    path = meter.fetch(0); event = meter.events[0]
    receipt = {'status': 'download_complete_analysis_pending', 'bodyBytes': path.stat().st_size, 'sha256': event['bodySha256'], 'publisherMd5': event['bodyMd5'],
        'meterElapsedSeconds': time.monotonic() - meter.started, 'sourceFeasibilityQualified': False}
    (root / 'source-receipt.json').write_bytes(json_bytes(receipt)); return receipt


def extract_source(source, root, plan, remaining, receipt):
    config = deepcopy(plan['extractConfig']); config['proposedCaps']['wallSeconds'] = remaining
    root = Path(root); output = root / 'extract'; output.mkdir()
    state = extract_pbf(source, config, output)
    if state['status'] == 'extracted_publisher_file_analysis_pending':
        require(state['sourceIdentity']['sourceSha256'] == receipt['sha256'] and state['sourceIdentity']['sourceMd5'] == receipt['publisherMd5'], 'Acquisition/framing source identity mismatch')
        require(len(state['passes']) == 4 and all(p['status'] == 'eof' for p in state['passes']) and state['independentAuditComplete'], 'Full four-pass data completion')
        require(all(p['status'] == 'complete_from_acquired_file_only' for p in state['windows']), 'All-window acquired-file completion')
    (root / 'analysis-result.json').write_bytes(json_bytes({'status': state['status'], 'fourPassesComplete': state.get('independentAuditComplete', False),
        'sourceFeasibilityQualified': False, 'publisherBoundaryQualified': False, 'usableAttributesQualified': False, 'modelChanged': False}))
    return state


def verify_completed_data(root, plan):
    root = Path(root); load = lambda p: json.loads(p.read_text()); spec = plan['sourceSpec']
    receipt = load(root / 'download/source-receipt.json'); ledger = load(root / 'download/http/http-ledger.json')
    require(len(ledger['events']) == 1 and not ledger['stopped'], 'Data single completed GET')
    event = ledger['events'][0]
    require(event['url'] == spec['url'] and event['status'] == 200 and event['outcome'] == 'complete' and event['bodyBytes'] == spec['exactBytes'], 'Data complete transfer accounting')
    require(event['bodySha256'] == receipt['sha256'] and event['bodyMd5'] == receipt['publisherMd5'] == spec['md5'], 'Data transfer digest accounting')
    require((root / 'download/http/001.bin').stat().st_size == spec['exactBytes'], 'Data preserved raw size')
    analysis = root / 'extract/extract'; state = load(analysis / 'state.json'); audit = load(analysis / 'audit.json')
    require(state['status'] == 'extracted_publisher_file_analysis_pending' and state['independentAuditComplete'], 'Data completed native audit')
    require(state['sourceIdentity']['sourceSha256'] == receipt['sha256'] and state['sourceIdentity']['sourceMd5'] == spec['md5'], 'Data framing/acquisition digests')
    require(state['hashFramingBytesRead'] == spec['exactBytes'], 'Data separate framing read accounting')
    require(len(state['passes']) == 4 and all(p['status'] == 'eof' and p['counts'] == state['passes'][0]['counts'] for p in state['passes']), 'Data four matching EOF scans')
    require(state['scanObjectVisits'] == 4 * sum(state['passes'][0]['counts'].values()), 'Data four-pass visit accounting')
    require([w['id'] for w in state['windows']] == [w['id'] for w in plan['extractConfig']['windows']]
        and all(w['status'] == 'complete_from_acquired_file_only' for w in state['windows']), 'Data all-window completion')
    output = analysis / 'elements.jsonl'
    require(output.stat().st_size == state['extractBytes'] == audit['extractBytes'] <= plan['extractConfig']['proposedCaps']['normalizedExtractBytes'], 'Data output byte accounting')
    require(digest(output) == state['outputSha256'] == audit['outputSha256'] and audit['independentSelectionNativeIdentityAndOutputAudit'], 'Data saved output hash/audit')
    require(not state['sourceFeasibilityQualified'] and not state['publisherBoundaryQualified'], 'Source gates cannot be promoted by extraction')
    raw = root / 'download/http/001.bin'; before = raw.stat(); began = time.monotonic()
    require(digest(raw) == receipt['sha256'], 'Final preserved raw SHA256 drift')
    after = raw.stat(); require((before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
        (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Raw file changed during final verification')
    (root / 'completion-check.json').write_bytes(json_bytes({'status': 'passed_acquired_file_only', 'finalRawHashBytesRead': before.st_size,
        'finalRawHashSecondsBeforeReceipt': time.monotonic() - began, 'rawSha256': receipt['sha256'], 'sourceFeasibilityQualified': False}))


def resource_probe():
    memory = memory_guard(); tmp = os.statvfs('/tmp'); require(tmp.f_blocks * tmp.f_frsize == 268435456, 'Data tmpfs size drift')
    quota, period = map(int, Path('/sys/fs/cgroup/cpu.max').read_text().split())
    require(quota == 2 * period and Path('/sys/fs/cgroup/pids.max').read_text().strip() == '64', 'Data CPU/PID guard drift')
    require(resource.getrlimit(resource.RLIMIT_CORE) == (0, 0) and resource.getrlimit(resource.RLIMIT_FSIZE) == (25769803776, 25769803776), 'Data core/file limits drift')
    require(os.statvfs('/').f_flag & os.ST_RDONLY, 'Data read-only root missing')
    from coarse_osm_input import absolute_timeout
    timer = False
    try:
        with absolute_timeout(.03): time.sleep(3)
    except Exception: timer = True
    require(timer, 'Data absolute timeout control')
    code = 'import sys,time;sys.path.insert(0,"/code");from coarse_timing_input import start_watchdog;start_watchdog(.05);time.sleep(3)'
    child = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, timeout=2)
    require(child.returncode == -9, 'Data watchdog control')
    with tempfile.TemporaryDirectory() as name:
        caps = {'sqlitePageBytes': 4096, 'sqliteMaxPagesEach': 4, 'sqliteCacheBytesEach': 8192, 'sqliteIndexBytesEach': 16384}
        index = Coordinates(Path(name) / 'capped.sqlite', caps); full = False
        try:
            for i in range(10000): index.add({'id': i + 1, 'lon': 0., 'lat': 0.})
        except sqlite3.DatabaseError: full = True
        finally: index.close()
        require(full and (Path(name) / 'capped.sqlite').stat().st_size <= 16384, 'Data SQLite page-bound control')
    return {'memory': memory, 'tmpBytes': tmp.f_blocks * tmp.f_frsize, 'cpuQuota': quota, 'cpuPeriod': period, 'pidsLimit': 64, 'rootReadOnly': True,
        'coreLimit': list(resource.getrlimit(resource.RLIMIT_CORE)), 'fileSizeLimit': list(resource.getrlimit(resource.RLIMIT_FSIZE)),
        'producerSha256': digest(__file__), 'watchdogKilledStalledChild': True, 'absoluteTimerInterrupted': True, 'tinySqlitePageCapStoppedWrites': True,
        'scope': 'Actual configured4GiB/zero swap/256MiB tmp plus tiny timeout/SQLite controls; no4GiB allocation/OOM-pressure/national performance claim.'}


if __name__ == '__main__' and sys.argv[1:] == ['--probe']: print(json.dumps(resource_probe(), indent=2))
