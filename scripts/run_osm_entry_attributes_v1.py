"""Offline selected-path source-attribute diagnosis under the fixed hard limits."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from coarse_timing_input import require, start_watchdog

IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
PREFIX = 'data/coarse-quality/us-osm-car-entry-attributes-'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(root, name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 1048576, 'Entry attributes record cap')
    with (root/name).open('xb') as stream:
        stream.write(raw)


def worker(plan):
    from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
    from coarse_osm_data import verify_worker_inputs
    root = Path('/work')
    began = time.monotonic()
    timer = start_watchdog(900)
    def check():
        require(time.monotonic()-began < 900, 'Entry attributes worker deadline')
        require(owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Entry attributes owned cap')
    try:
        cgroup = Path('/sys/fs/cgroup')
        require((cgroup/'memory.max').read_text().strip() == str(4*1024**3) and (cgroup/'memory.swap.max').read_text().strip() == '0', 'Entry attributes memory/swap')
        verify_worker_inputs({'workerFiles': {destination: plan['inputs'][name] for name, destination in plan['mounts'].items()}})
        before = {name: Path(name).stat() for name in plan['mounts'].values()}
        if plan['operation'] == 'controls':
            import unittest
            import coarse_osm_entry_attributes_v1_test as tests
            require(not Path('/facts').exists() and not Path('/paths').exists(), 'Entry attribute controls use synthetic inputs')
            tested = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
            controls = {'tests': tested.testsRun, 'successful': tested.wasSuccessful(), 'failures': len(tested.failures), 'errors': len(tested.errors), 'skips': len(tested.skipped)}
            require(controls == {'tests': 7, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Entry attributes controls')
            save(root, 'report.json', {'status': 'entry_attribute_controls_passed', 'controls': controls})
            return 0
        from coarse_osm_entry_attributes_v1 import annotate, summarize
        require(plan['operation'] == 'run', 'Entry attribute operation')
        path_report = json.loads(Path('/inputs/path-report.json').read_bytes())
        require(path_report['paths'] == 80 and path_report['unavailable'] == 3 and len(path_report['rows']) == 83, 'Entry attribute all-case path input')
        records, selected, raw_total = [], set(), 0
        for item in path_report['rows']:
            if 'unavailable' in item:
                continue
            asset = item['asset']
            require(Path(asset['filename']).name == asset['filename'], 'Entry path filename scope')
            path = Path('/paths')/asset['filename']
            require(path.stat().st_size == asset['compressedBytes'] <= 2097152 and sha(path) == asset['sha256'], 'Entry path compressed identity')
            with gzip.open(path, 'rb') as stream:
                raw = stream.read(33554433)
            raw_total += len(raw)
            require(len(raw) == asset['rawBytes'] <= 33554432 and raw_total <= 134217728 and hashlib.sha256(raw).hexdigest() == asset['rawSha256'], 'Entry path raw identity/cap')
            record = json.loads(raw)
            require(record['sample']['id'] == item['id'] and sum(record['components'].values()) == record['sumTicks'] == item['sumTicks'], 'Entry attribute exact source path sum')
            records.append(record)
            if record['road'] is not None:
                selected.update(step['arc'] for step in record['road']['steps'])
            require(len(selected) <= 200000, 'Entry selected arc cap')
        require(len(records) == 80, 'Entry all80 paths retained')
        phase = time.monotonic()
        attributes = annotate('/facts', '/inputs/offsets.u24', '/inputs/arc-map.u32', selected, [4227238, 5731903, 9837326, 9703850], check)
        attribute_seconds = time.monotonic()-phase
        features = [summarize(record, attributes) for record in records]
        for row, record in zip(features, records):
            row.update(set=record['sample']['set'], candidateMinutes=record['sumTicks']/480, referenceMinutes=record['sample']['referenceMinutes'])
        raw = json.dumps(attributes, separators=(',', ':'), allow_nan=False).encode()
        require(len(raw) <= 50331648, 'Entry selected attribute raw cap')
        packed = gzip.compress(raw, compresslevel=9, mtime=0)
        require(len(packed) <= 16777216, 'Entry selected attribute compressed cap')
        with (root/'arc-attributes.json.gz').open('xb') as stream:
            stream.write(packed)
        for name, stat in before.items():
            after = Path(name).stat()
            require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Entry attribute input drift')
        save(root, 'report.json', {'status': 'all80_path_source_speed_attributes_complete', 'paths': 80, 'unavailable': 3, 'selectedArcs': len(attributes),
                                 'waysChecked': 4227238, 'preArcMappingsChecked': 9837326, 'retainedArcMappingsChecked': 9703850,
                                 'rows': features, 'attributeSecondsIncludingSourceReads': attribute_seconds,
                                 'workerSecondsIncludingBindingsPathsAndSourceAnnotation': time.monotonic()-began,
                                 'sourcePbfReads': 0, 'routingQueries': 0, 'providerRequests': 0, 'policyFitOrChange': False, 'appActivated': False,
                                 'artifact': {'file': 'arc-attributes.json.gz', 'bytes': len(packed), 'sha256': hashlib.sha256(packed).hexdigest(), 'rawBytes': len(raw), 'rawSha256': hashlib.sha256(raw).hexdigest()},
                                 'scope': 'Closed derived source speed/default/class facts for every selected winner arc, no source PBF or new model query. Tagged speeds are source maxspeed values, not measured driving speeds. All path road tick groups reconcile exactly; development observations are not a fitted or nationwide timing policy.'})
        check()
        return 0
    except BaseException as error:
        save(root, 'failure.json', {'status': 'entry_attributes_stopped', 'error': repr(error), 'workerSeconds': time.monotonic()-began})
        raise
    finally:
        save(root, 'metrics.json', resource_metrics())
        if timer.poll() is None:
            timer.terminate()
        timer.wait(timeout=5)


def driver(recipe, pin):
    from coarse_osm_full_monitor_v1 import owned_usage
    from prepare_osm_native_lock_v1 import cleanup_owned, settle_error
    from run_osm_country_screen_v1 import isolation
    repo = Path(__file__).resolve().parents[1]
    recipe = Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe) == pin, 'Entry attributes recipe binding')
    plan = json.loads(recipe.read_bytes())
    operation = plan['operation']
    require(operation in ('controls', 'run') and plan['output'] == PREFIX+operation+'-v1', 'Entry attributes exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+67108864+268435456 < 64*1024**3, 'Entry attributes aggregate reservation')
    require(set(plan['mounts']) == set(plan['inputs']), 'Entry attributes complete input bindings')
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/', '/paths/')), 'Entry attributes input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Entry attributes input SHA/no PBF')
    require(operation == 'controls' or plan['admission'] == {'tests': 7, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Entry attributes qualification before facts')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-entry-attributes-'+owner[:12]
    save(root, 'owner.json', {'name': name, 'label': owner, 'image': IMAGE})
    began = time.monotonic()
    identity = child = None
    code = 2
    def call(args):
        return subprocess.run(args, capture_output=True, text=True, timeout=15)
    try:
        command = ['docker', 'create', '--pull=never', '--init', '--name', name, '--label', 'geo-planner.stream-owner='+owner,
                   '--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=4g', '--memory-swap=4g', '--cpus=2', '--pids-limit=64',
                   '--tmpfs', '/tmp:rw,size=256m', '--ulimit', 'core=0:0', '--ulimit', 'fsize=67108864:67108864', '--env', 'PYTHONPATH=/code:/reference']
        for source, destination in plan['mounts'].items():
            command += ['--mount', f'type=bind,src={repo/source},dst={destination},readonly']
        command += ['--mount', f'type=bind,src={root},dst=/work', '--mount', f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly',
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_entry_attributes_v1.py', '/inputs/recipe.json', pin, '--worker']
        created = call(command)
        require(created.returncode == 0, created.stderr)
        identity = created.stdout.strip()
        require(len(identity) == 64, 'Entry attributes exact owned ID')
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        isolation(observed, 'controls')
        save(root, 'container-initial.json', observed)
        with (root/'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began < 1020 and owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Entry attributes host deadline/owned cap')
                time.sleep(.5)
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        save(root, 'container-result.json', {'State': observed['State'], 'clientExitCode': child.returncode})
        require(child.returncode == observed['State']['ExitCode'] == 0 and not observed['State']['OOMKilled'], 'Entry attributes worker exit/OOM')
        code = 0
    except BaseException as error:
        save(root, 'driver-failure.json', {'error': repr(error), 'hostSeconds': time.monotonic()-began})
    finally:
        if child and child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        if not (root/'container-result.json').exists():
            settle_error(call, identity, name, owner, root, child.returncode if child else None)
        cleanup_owned(call, identity, name, owner, IMAGE, root)
    save(root, 'run-summary.json', {'exitCode': code, 'hostSecondsIncludingCleanup': time.monotonic()-began, 'sourcePbfReads': 0})
    return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe')
    parser.add_argument('pin')
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    require(sha(args.recipe) == args.pin, 'Entry attributes recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe, args.pin))
