"""Isolated controls/one new relation-metadata audit, never a graph constructor."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from coarse_timing_input import require

IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
PREFIX = 'data/coarse-quality/us-osm-car-relation-metadata-'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 1048576, 'Relation metadata small-record cap')
    with Path(path).open('xb') as stream:
        stream.write(raw)


def worker(plan):
    from coarse_timing_input import start_watchdog
    root = Path('/work')
    began = time.monotonic()
    watchdog = start_watchdog(plan['workerSeconds'])
    def check():
        require(time.monotonic()-began < plan['workerSeconds'], 'Relation metadata worker deadline')
    def metrics():
        c = Path('/sys/fs/cgroup')
        return {'memoryPeakBytes': int((c/'memory.peak').read_text()),
                'memoryEvents': dict(line.split() for line in (c/'memory.events').read_text().splitlines()),
                'swapCurrentBytes': int((c/'memory.swap.current').read_text()),
                'cpuStat': (c/'cpu.stat').read_text(), 'scope': 'Actual Linux cgroup including file cache.'}
    try:
        c = Path('/sys/fs/cgroup')
        require(int((c/'memory.max').read_text()) == 4*1024**3 and int((c/'memory.swap.max').read_text()) == 0, 'Relation metadata memory/swap')
        quota, period = map(int, (c/'cpu.max').read_text().split())
        require(quota == 2*period and int((c/'pids.max').read_text()) == 64, 'Relation metadata CPU/PID cap')
        for name, pin in plan['workerFiles'].items():
            require(sha(name) == pin, 'Relation metadata worker input binding')
        if plan['operation'] == 'controls':
            import unittest
            require(not Path('/source.pbf').exists(), 'Relation controls must not mount real source')
            suite = unittest.defaultTestLoader.loadTestsFromNames(['coarse_osm_relation_tail_v1_test', 'coarse_osm_relation_audit_v1_test'])
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            controls = {'tests': result.testsRun, 'successful': result.wasSuccessful(), 'failures': len(result.failures), 'errors': len(result.errors), 'skips': len(result.skipped)}
            require(controls == {'tests': 16, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Relation metadata controls fail')
            save(root/'report.json', {'status': 'isolated_relation_metadata_controls_passed', 'controls': controls, 'sourcePbfReads': 0, 'hostedRequests': 0})
            return 0
        require(plan['operation'] == 'run', 'Relation metadata operation')
        from coarse_osm_bulk_pbf import stat_key
        from coarse_osm_relation_audit_v1 import fact_rows, read_closed_ids, RelationAudit, TURN
        from coarse_osm_relation_tail_v1 import selected_relations
        source = Path('/source.pbf')
        def guard(label):
            before = stat_key(source)
            size = 0
            digest, md5 = hashlib.sha256(), hashlib.md5()
            started = time.monotonic()
            with source.open('rb') as stream:
                while raw := stream.read(8*1048576):
                    check()
                    size += len(raw)
                    require(size <= plan['source']['bytes'], 'Relation metadata source byte cap')
                    digest.update(raw)
                    md5.update(raw)
            require(size == plan['source']['bytes'] and digest.hexdigest() == plan['source']['sha256'] and md5.hexdigest() == plan['source']['md5'] and stat_key(source) == before, 'Relation metadata whole-source identity/stat')
            record = {'bytes': size, 'sha256': digest.hexdigest(), 'md5': md5.hexdigest(), 'stat': before, 'seconds': time.monotonic()-started}
            save(root/f'source-{label}.json', record)
            print(json.dumps({'sourceGuard': label, 'seconds': record['seconds']}), flush=True)
            return before
        before = guard('before')
        closures = read_closed_ids('/facts', plan['factRoster'], check)
        turns = fact_rows('/facts', plan['factRoster'], 'turns', TURN, check)
        invalid = json.loads(Path('/inputs/invalid.json').read_bytes())['records']
        output = root/'unsupported-relations.jsonl'
        with output.open('xb') as stream:
            sink = RelationAudit(turns, closures, invalid, stream)
            consumed = 0
            def consume(e):
                nonlocal consumed
                sink.consume(e)
                consumed += 1
                if consumed % 65536 == 0:
                    print(json.dumps({'restrictionRecords': consumed, 'unsupported': sink.counts['closed-unsupported']}), flush=True)
            scan = selected_relations(source, source_bytes=plan['source']['bytes'], state=plan['source']['publisherState'],
                                      expected_relations=1624265, consume=consume, check=check)
            parity = sink.finish()
            stream.flush()
            os.fsync(stream.fileno())
        require(sha(output) == parity['selectedMetadataSha256'] and output.stat().st_size == parity['selectedMetadataBytes'], 'Relation metadata output identity')
        require(scan['headersVisited'] == 221321 and parity['closureWayIdsMatched'] == 149699, 'Relation metadata source framing/closure parity')
        require(stat_key(source) == before, 'Relation metadata source drift')
        after = guard('after')
        require(before == after, 'Relation metadata pre/post source stats')
        save(root/'unlocatable-records.json', sink.invalid)
        save(root/'report.json', {'status': 'complete_national_relation_metadata_parity_passed', 'scan': scan, 'parity': parity,
                                  'sourcePbfScans': 1, 'wholeSourceHashPasses': 2, 'workerSecondsIncludingHashesScanParityOutput': time.monotonic()-began,
                                  'sourceConstructorExecutions': 0, 'nodeWayObjectsProjected': 0, 'providerRequests': 0, 'applicationDbReads': 0,
                                  'countryGraphChanged': False, 'appActivated': False,
                                  'scope': 'New selected relation metadata only. Whole fixed source hashes/parent full seals reused; complete relation-section count/order and exact old turn/closure/unlocatable parity. Earlier node/way bodies are not redecoded or semantically revalidated.'})
        return 0
    except BaseException as error:
        save(root/'failure.json', {'status': 'relation_metadata_stopped', 'error': repr(error), 'workerSeconds': time.monotonic()-began})
        raise
    finally:
        save(root/'metrics.json', metrics())
        if watchdog.poll() is None:
            watchdog.terminate()
        watchdog.wait(timeout=5)


def driver(recipe, pin):
    from coarse_osm_full_monitor_v1 import owned_usage
    from run_osm_country_screen_v1 import isolation
    repo = Path(__file__).resolve().parents[1]
    recipe = Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe) == pin, 'Relation metadata recipe binding')
    plan = json.loads(recipe.read_bytes())
    require(plan['operation'] in ('controls', 'run') and plan['output'] == PREFIX+plan['operation']+'-v1', 'Relation metadata exact namespace')
    require(plan['workerSeconds'] == 900 and plan['hostSeconds'] == 1020 and plan['maxOwnedBytes'] == 134217728 and plan['tmpBytes'] == 268435456, 'Relation metadata fixed caps')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan['maxOwnedBytes']+plan['tmpBytes'] < 64*1024**3, 'Relation metadata aggregate disk cap')
    for name, expected in plan['bindings'].items():
        require(sha(repo/name) == expected, 'Relation metadata host code/evidence binding')
    if plan['operation'] == 'run':
        source = repo/plan['source']['path']
        require(source.is_file() and not source.is_symlink() and source.stat().st_size == plan['source']['bytes'], 'Relation metadata source path/type/size')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    save(root/'owner.json', {'label': owner, 'labelKey': 'geo-planner.stream-owner', 'image': IMAGE})
    began = time.monotonic()
    identity = child = None
    def call(args):
        return subprocess.run(args, capture_output=True, text=True, timeout=15)
    def inspect():
        r = call(['docker', 'inspect', identity])
        require(r.returncode == 0, 'Relation metadata owned inspect')
        observed = json.loads(r.stdout)[0]
        require(observed['Id'] == identity and observed['Config']['Labels'].get('geo-planner.stream-owner') == owner, 'Relation metadata exact ownership')
        return observed
    try:
        command = ['docker', 'create', '--pull=never', '--init', '--name', 'geo-planner-relmeta-'+owner[:12], '--label', 'geo-planner.stream-owner='+owner,
                   '--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=4g', '--memory-swap=4g', '--cpus=2', '--pids-limit=64',
                   '--ulimit', 'core=0:0', '--ulimit', 'fsize=67108864:67108864', '--tmpfs', '/tmp:rw,size=256m', '--env', 'PYTHONPATH=/code:/reference', '--env', 'PYTHONDONTWRITEBYTECODE=1']
        for name, destination in plan['mounts'].items():
            command += ['--mount', f'type=bind,src={repo/name},dst={destination},readonly']
        command += ['--mount', f'type=bind,src={root},dst=/work', '--mount', f'type=bind,src={recipe},dst=/inputs/plan.json,readonly',
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_relation_metadata_v1.py', '/inputs/plan.json', pin, '--worker']
        created = call(command)
        require(created.returncode == 0, created.stderr)
        identity = created.stdout.strip()
        require(len(identity) == 64 and all(c in '0123456789abcdef' for c in identity), 'Relation metadata owned ID')
        observed = inspect()
        isolation(observed, 'controls')
        save(root/'container-initial.json', observed)
        with (root/'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began < plan['hostSeconds'], 'Relation metadata host deadline')
                require(owned_usage(root)['conservativeAllocatedBytes'] <= plan['maxOwnedBytes'], 'Relation metadata owned cap')
                time.sleep(.5)
        observed = inspect()
        save(root/'container-result.json', observed)
        require(child.returncode == 0 and observed['State']['ExitCode'] == 0 and not observed['State']['OOMKilled'], 'Relation metadata worker exit/OOM')
        require(owned_usage(root)['conservativeAllocatedBytes'] <= plan['maxOwnedBytes'], 'Relation metadata final owned cap')
        save(root/'run-summary.json', {'exitCode': child.returncode, 'operation': plan['operation'], 'hostSecondsIncludingCleanupPending': time.monotonic()-began})
        return 0
    except BaseException as error:
        save(root/'driver-failure.json', {'error': repr(error), 'hostSeconds': time.monotonic()-began})
        raise
    finally:
        if identity:
            observed = inspect()
            if observed['State']['Running']:
                require(call(['docker', 'kill', identity]).returncode == 0, 'Relation metadata owned kill')
            if child:
                child.wait(timeout=15)
            save(root/'container-before-removal.json', inspect())
            require(call(['docker', 'rm', identity]).returncode == 0, 'Relation metadata owned removal')
            absent = call(['docker', 'inspect', identity])
            require(absent.returncode != 0 and 'No such' in absent.stderr, 'Relation metadata independent exact-ID absence')
            save(root/'cleanup.json', {'ownedContainer': identity, 'removed': True, 'independentInspectAbsent': True, 'hostSecondsIncludingCleanup': time.monotonic()-began})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('pin')
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        require(sha(args.plan) == args.pin, 'Relation metadata worker recipe SHA')
        raise SystemExit(worker(json.loads(Path(args.plan).read_bytes())))
    raise SystemExit(driver(args.plan, args.pin))
