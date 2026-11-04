"""New national entry-corrected packed graph and independent complete audit."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from coarse_timing_input import require, start_watchdog

IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
PREFIX = 'data/coarse-quality/us-osm-car-entry-graph-'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(root, name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 1048576, 'Entry graph record cap')
    with (root/name).open('xb') as stream:
        stream.write(raw)


def worker(plan):
    from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
    from coarse_osm_data import verify_worker_inputs
    from coarse_osm_car_entry_native_v1 import NativeEntries
    root = Path('/work')
    began = time.monotonic()
    timer = start_watchdog(900)
    def check():
        require(time.monotonic()-began < 900, 'Entry graph worker deadline')
        require(owned_usage(root)['conservativeAllocatedBytes'] <= 268435456, 'Entry graph owned cap')
    try:
        cgroup = Path('/sys/fs/cgroup')
        require((cgroup/'memory.max').read_text().strip() == str(4*1024**3) and (cgroup/'memory.swap.max').read_text().strip() == '0', 'Entry graph memory/swap')
        files = {destination: plan['inputs'][name] for name, destination in plan['mounts'].items()}
        files.update({destination: plan['inputs'][name] for destination, name in plan['viewMounts'].items()})
        verify_worker_inputs({'workerFiles': files})
        before = {name: Path(name).stat() for name in files}
        artifact = ('/artifacts/car-entry.so', plan['artifact']['sha256'])
        native = NativeEntries(*artifact)
        if plan['operation'] == 'controls':
            import unittest
            import coarse_osm_entry_graph_audit_v1_test as audit_tests
            import coarse_osm_car_entry_native_v1_test as native_tests
            native_tests.configure_native(*artifact)
            require(not Path('/facts').exists() and not Path('/view').exists(), 'Entry graph controls cannot mount real facts')
            suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (audit_tests, native_tests))
            tested = unittest.TextTestRunner(verbosity=2).run(suite)
            result = {'tests': tested.testsRun, 'successful': tested.wasSuccessful(), 'failures': len(tested.failures), 'errors': len(tested.errors), 'skips': len(tested.skipped)}
            require(result == {'tests': 21, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Entry graph actual Linux controls')
            save(root, 'report.json', {'status': 'entry_graph_controls_passed', 'controls': result, 'sourcePbfReads': 0})
            return 0
        from coarse_osm_car_packed_native_v1 import NativePacked
        from coarse_osm_entry_graph_audit_v1 import audit
        require(plan['operation'] == 'run', 'Entry graph operation')
        dimensions = plan['dimensions']
        require(dimensions == [42993567, 5731903, 4227238, 9837326, 9703850, 409178], 'Entry graph source dimensions')
        # A second read-only bind view substitutes the independently audited
        # closure file. No source copy, symlink, constructor or old recipe.
        routing = root/'base-routing'
        routing.mkdir()
        phase = time.monotonic()
        base = NativePacked(*artifact).encode('/view', routing, dimensions)
        encode_seconds = time.monotonic()-phase
        check()
        phase = time.monotonic()
        final = root/'entry-forbidden.u24'
        augmentation = native.augment('/facts', '/view/closures-0000.bin', '/inputs/entry-pairs-pre.u32', routing, final, dimensions[2:3]+dimensions[1:2]+dimensions[3:5])
        augment_seconds = time.monotonic()-phase
        check()
        phase = time.monotonic()
        proof = audit('/facts', '/view', routing, '/inputs/entry-pairs-pre.u32', final, dimensions, augmentation, baseline_post=9620680, check=check)
        audit_seconds = time.monotonic()-phase
        for name, stat in before.items():
            after = Path(name).stat()
            require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Entry graph input stat drift')
        paths = {'routing/'+path.name: (final if path.name == 'forbidden-turns.u24' else path) for path in routing.iterdir()}
        assets = {name: {'path': str(path.relative_to(root)), 'bytes': path.stat().st_size, 'sha256': sha(path)} for name, path in paths.items()}
        save(root, 'artifacts.json', assets)
        save(root, 'report.json', {'status': 'national_entry_graph_and_independent_complete_audit_passed', 'basePackedResult': base,
                                 'augmentationCounts': augmentation, 'independentAudit': proof, 'assets': assets,
                                 'finalPayloadBytes': sum(row['bytes'] for row in assets.values()),
                                 'nativeEncodingSeconds': encode_seconds, 'nativeAugmentationSeconds': augment_seconds,
                                 'independentAuditSeconds': audit_seconds, 'workerSecondsIncludingBindingsAndAllOperations': time.monotonic()-began,
                                 'sourcePbfReads': 0, 'sourceConstructorExecutions': 0, 'routingQueries': 0, 'providerRequests': 0,
                                 'spatialOrPaidGeometryOrCodecBuilt': False, 'appActivated': False,
                                 'scope': 'New complete packed graph/source cost/flags/reverse/supported and entry-turn audit. Original open arcs/allowed transitions retained. Spatial/paid geometry/codec/ETA/app remain separate.'})
        return 0
    except BaseException as error:
        save(root, 'failure.json', {'status': 'entry_graph_stopped', 'error': repr(error), 'workerSeconds': time.monotonic()-began})
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
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe) == pin, 'Entry graph recipe binding')
    plan = json.loads(recipe.read_bytes())
    operation = plan['operation']
    require(operation in ('controls', 'run') and plan['output'] == PREFIX+operation+'-v1', 'Entry graph exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+268435456+268435456 < 64*1024**3, 'Entry graph aggregate reservation')
    require(set(plan['mounts']) == set(plan['inputs']), 'Entry graph complete input bindings')
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/')), 'Entry graph input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Entry graph input SHA/no PBF')
    for destination, name in plan['viewMounts'].items():
        require(name in plan['inputs'] and destination.startswith('/view/') and Path(destination).name == Path(name).name, 'Entry graph readonly view binding')
    require(operation != 'controls' or not plan['viewMounts'], 'Entry graph controls have no real fact view')
    require(operation != 'run' or plan['admission']['tests'] == 21 and plan['admission']['successful'] and plan['admission']['skips'] == 0, 'Entry graph qualification admission')
    require(shutil.disk_usage(repo/'data/coarse-quality').free >= 1073741824, 'Entry graph disk headroom')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-entry-graph-'+owner[:12]
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
        for destination, source in plan['viewMounts'].items():
            command += ['--mount', f'type=bind,src={repo/source},dst={destination},readonly']
        command += ['--mount', f'type=bind,src={root},dst=/work', '--mount', f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly',
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_entry_graph_v1.py', '/inputs/recipe.json', pin, '--worker']
        created = call(command)
        require(created.returncode == 0, created.stderr)
        identity = created.stdout.strip()
        require(len(identity) == 64, 'Entry graph exact owned ID')
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        isolation(observed, 'controls')
        save(root, 'container-initial.json', observed)
        with (root/'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began < 1020 and owned_usage(root)['conservativeAllocatedBytes'] <= 268435456, 'Entry graph host deadline/owned cap')
                time.sleep(.5)
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        save(root, 'container-result.json', {'State': observed['State'], 'clientExitCode': child.returncode})
        require(child.returncode == observed['State']['ExitCode'] == 0 and not observed['State']['OOMKilled'], 'Entry graph worker exit/OOM')
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
    require(sha(args.recipe) == args.pin, 'Entry graph recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe, args.pin))
