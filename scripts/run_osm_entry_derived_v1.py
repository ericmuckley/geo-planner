"""New entry-candidate spatial/geometry derivations through sealed generic helpers."""
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
PREFIX = 'data/coarse-quality/us-osm-car-entry-derived-'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(root, name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 1048576, 'Entry derived record cap')
    with (root/name).open('xb') as stream:
        stream.write(raw)


def worker(plan):
    from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
    from coarse_osm_data import verify_worker_inputs
    root = Path('/work')
    began = time.monotonic()
    timer = start_watchdog(1200)
    def check():
        require(time.monotonic()-began < 1200, 'Entry derived worker deadline')
        require(owned_usage(root)['conservativeAllocatedBytes'] <= 268435456, 'Entry derived owned cap')
    try:
        cgroup = Path('/sys/fs/cgroup')
        require((cgroup/'memory.max').read_text().strip() == str(4*1024**3) and (cgroup/'memory.swap.max').read_text().strip() == '0', 'Entry derived memory/swap')
        verify_worker_inputs({'workerFiles': {destination: plan['inputs'][name] for name, destination in plan['mounts'].items()}})
        before = {name: Path(name).stat() for name in plan['mounts'].values()}
        operation = plan['operation']
        if operation == 'controls':
            import unittest
            import coarse_osm_car_spatial_native_v1_test as spatial_tests
            import coarse_osm_car_spatial_audit_v1_test as spatial_audit_tests
            import coarse_osm_car_paid_geometry_v1_test as geometry_tests
            import coarse_osm_car_paid_geometry_audit_v1_test as geometry_audit_tests
            spatial_tests.ARTIFACT = ('/artifacts/car-spatial.so', plan['artifacts']['spatial']['sha256'])
            geometry_tests.ARTIFACT = ('/artifacts/car-paid-geometry.so', plan['artifacts']['geometry']['sha256'])
            require(not Path('/facts').exists() and not Path('/routing').exists(), 'Entry derived synthetic controls only')
            suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (spatial_tests, spatial_audit_tests, geometry_tests, geometry_audit_tests))
            tested = unittest.TextTestRunner(verbosity=2).run(suite)
            controls = {'tests': tested.testsRun, 'successful': tested.wasSuccessful(), 'failures': len(tested.failures), 'errors': len(tested.errors), 'skips': len(tested.skipped)}
            require(controls == {'tests': 30, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Entry derived actual Linux controls')
            save(root, 'report.json', {'status': 'entry_derived_controls_passed', 'controls': controls, 'sourcePbfReads': 0})
            return 0
        if operation == 'spatial':
            from coarse_osm_car_spatial_native_v1 import NativeSpatial
            from coarse_osm_car_spatial_audit_v1 import audit
            output = root/'routing'
            output.mkdir()
            phase = time.monotonic()
            result = NativeSpatial('/artifacts/car-spatial.so', plan['artifacts']['spatial']['sha256']).encode('/routing', output)
            native_seconds = time.monotonic()-phase
            require(result['vertices'] == 5731903 and result['arcs'] == 9703850 and result['forbiddenTurnPairs'] == 249140, 'Entry spatial dimensions/turn pairs')
            check()
            phase = time.monotonic()
            proof = audit('/routing', output)
            audit_seconds = time.monotonic()-phase
        else:
            require(operation == 'geometry', 'Entry derived operation')
            from coarse_osm_car_paid_geometry_v1 import NativePaidGeometry
            from coarse_osm_car_paid_geometry_audit_v1 import audit
            dimensions = [42993567, 5731903, 4227238, 48163649, 9837326, 9703850]
            require(plan['dimensions'] == dimensions, 'Entry geometry source dimensions')
            output = root/'geometry'
            output.mkdir()
            phase = time.monotonic()
            result = NativePaidGeometry('/artifacts/car-paid-geometry.so', plan['artifacts']['geometry']['sha256']).build('/facts', '/inputs/offsets.u24', '/inputs/old-arc-to-new.u32', output, dimensions)
            native_seconds = time.monotonic()-phase
            check()
            phase = time.monotonic()
            proof = audit('/facts', '/inputs/offsets.u24', '/inputs/old-arc-to-new.u32', output, dimensions, check)
            audit_seconds = time.monotonic()-phase
        check()
        for name, stat in before.items():
            after = Path(name).stat()
            require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Entry derived input stat drift')
        assets = {str(path.relative_to(root)): {'bytes': path.stat().st_size, 'sha256': sha(path)} for path in output.iterdir()}
        save(root, 'artifacts.json', assets)
        save(root, 'report.json', {'status': 'entry_'+operation+'_and_complete_independent_audit_passed', 'nativeResult': result, 'independentAudit': proof,
                                 'nativeOperationSeconds': native_seconds, 'independentAuditSeconds': audit_seconds,
                                 'workerSecondsIncludingBindingsAndBothOperations': time.monotonic()-began,
                                 'assets': assets, 'sourcePbfReads': 0, 'sourceConstructorExecutions': 0, 'routingQueries': 0,
                                 'providerRequests': 0, 'appActivated': False, 'accuracyQualified': False,
                                 'scope': 'New candidate inputs through sealed generic helpers, with complete independent output audit. Source PBF not mounted. Codec/query/ETA/app qualification are separate.'})
        return 0
    except BaseException as error:
        save(root, 'failure.json', {'status': 'entry_derived_stopped', 'error': repr(error), 'workerSeconds': time.monotonic()-began})
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
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe) == pin, 'Entry derived recipe binding')
    plan = json.loads(recipe.read_bytes())
    operation = plan['operation']
    require(operation in ('controls', 'spatial', 'geometry') and plan['output'] == PREFIX+operation+'-v1', 'Entry derived exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+268435456+268435456 < 64*1024**3, 'Entry derived aggregate reservation')
    require(set(plan['mounts']) == set(plan['inputs']), 'Entry derived complete input bindings')
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/', '/routing/')), 'Entry derived input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Entry derived input SHA/no PBF')
    require(shutil.disk_usage(repo/'data/coarse-quality').free >= 1073741824, 'Entry derived disk headroom')
    require(operation == 'controls' or plan['admission'] == {'tests': 30, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Entry derived qualification admission')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-entry-derived-'+owner[:12]
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
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_entry_derived_v1.py', '/inputs/recipe.json', pin, '--worker']
        created = call(command)
        require(created.returncode == 0, created.stderr)
        identity = created.stdout.strip()
        require(len(identity) == 64, 'Entry derived exact owned ID')
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        isolation(observed, 'controls')
        save(root, 'container-initial.json', observed)
        with (root/'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began < 1320 and owned_usage(root)['conservativeAllocatedBytes'] <= 268435456, 'Entry derived host deadline/owned cap')
                time.sleep(.5)
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        save(root, 'container-result.json', {'State': observed['State'], 'clientExitCode': child.returncode})
        require(child.returncode == observed['State']['ExitCode'] == 0 and not observed['State']['OOMKilled'], 'Entry derived worker exit/OOM')
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
    require(sha(args.recipe) == args.pin, 'Entry derived recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe, args.pin))
