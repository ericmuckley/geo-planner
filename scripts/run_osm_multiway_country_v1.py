"""Offline multi-via entry metadata with independent source joins and fixed hard limits."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from coarse_timing_input import require, start_watchdog

IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
PREFIX = 'data/coarse-quality/us-osm-multiway-country-'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(root, name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 1048576, 'Multiway country record cap')
    with (root/name).open('xb') as stream:
        stream.write(raw)


def worker(plan):
    from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
    from coarse_osm_data import verify_worker_inputs
    root = Path('/work')
    began = time.monotonic()
    timer = start_watchdog(900)
    def check():
        require(time.monotonic()-began < 900, 'Multiway country worker deadline')
        require(owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Multiway country owned cap')
    try:
        cgroup = Path('/sys/fs/cgroup')
        require((cgroup/'memory.max').read_text().strip() == str(4*1024**3) and (cgroup/'memory.swap.max').read_text().strip() == '0', 'Multiway country memory/swap')
        files = {destination: plan['inputs'][name] for name, destination in plan['mounts'].items()}
        verify_worker_inputs({'workerFiles': files})
        before = {name: Path(name).stat() for name in files}
        if plan['operation'] == 'controls':
            import unittest
            import coarse_osm_multiway_country_v1_test as country
            import coarse_osm_multiway_entry_v1_test as multi
            import coarse_osm_context_turns_v1_test as context
            import coarse_osm_absent_entry_v1_test as absent
            import coarse_osm_restriction_entry_v1_test as rules
            import coarse_osm_entry_graph_v1_test as graph
            require(not Path('/facts').exists(), 'Multiway controls use synthetic data only')
            suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (country,multi,context,absent,rules,graph))
            tested = unittest.TextTestRunner(verbosity=2).run(suite)
            controls = {'tests': tested.testsRun, 'successful': tested.wasSuccessful(), 'failures': len(tested.failures), 'errors': len(tested.errors), 'skips': len(tested.skipped)}
            require(controls == {'tests': 46, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Multiway country Linux controls')
            save(root, 'report.json', {'status': 'multiway_country_controls_passed', 'controls': controls, 'sourcePbfReads': 0, 'routingQueries': 0})
            return 0
        from coarse_osm_multiway_country_v1 import resolve
        require(plan['operation'] == 'run' and plan['dimensions'] == [4227238,5731903,9878318,9807359,70376,46533], 'Multiway full dimensions')
        report = resolve('/facts','/inputs/unsupported.jsonl','/inputs/decisions.bin','/facts/closures-0000.bin',
                         '/inputs/entry-pairs-pre.u32',root/'resolved',plan['dimensions'],check)
        require((report['oldClosureIds'],report['oldEntryPairsRetained']) == (40259,22964), 'Multiway exact parent closure/entry baseline')
        assets = {}
        for filename in sorted((root/'resolved').iterdir()):
            require(filename.is_file() and not filename.is_symlink() and filename.stat().st_size <= 67108864, 'Multiway output field bound')
            assets[str(filename.relative_to(root))] = {'bytes':filename.stat().st_size,'sha256':sha(filename)}
        report['assets'] = assets
        for name, stat in before.items():
            after = Path(name).stat()
            require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Footprint input stat drift')
        report['workerSecondsIncludingBindingsConstructionAndAudit'] = time.monotonic()-began
        report['appActivated'] = False
        save(root, 'report.json', report)
        return 0
    except BaseException as error:
        save(root, 'failure.json', {'status': 'multiway_country_stopped', 'error': repr(error), 'workerSeconds': time.monotonic()-began})
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
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe) == pin, 'Multiway country recipe binding')
    plan = json.loads(recipe.read_bytes())
    operation = plan['operation']
    require(operation in ('controls', 'run') and plan['output'] == PREFIX+operation+'-v1', 'Multiway country exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan.get('additionalActiveReservationBytes', 0)+67108864+268435456 < 72*1024**3, 'Multiway country aggregate reservation')
    require(set(plan['mounts']) == set(plan['inputs']), 'Multiway country complete input bindings')
    if operation == 'run':
        from coarse_osm_conditional_attribute_mounts_v2 import validate_fact_mounts
        validate_fact_mounts(plan['mounts'])
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/', '/paths/')), 'Multiway country input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Multiway country input SHA/no PBF')
    require(operation == 'controls' or plan['admission'] == {'tests': 46, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Multiway country qualification before facts')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-multiway-country-'+owner[:12]
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
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_multiway_country_v1.py', '/inputs/recipe.json', pin, '--worker']
        created = call(command)
        require(created.returncode == 0, created.stderr)
        identity = created.stdout.strip()
        require(len(identity) == 64, 'Multiway country exact owned ID')
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        isolation(observed, 'controls')
        save(root, 'container-initial.json', observed)
        with (root/'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began < 1020 and owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Multiway country host deadline/owned cap')
                time.sleep(.5)
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        save(root, 'container-result.json', {'State': observed['State'], 'clientExitCode': child.returncode})
        require(child.returncode == observed['State']['ExitCode'] == 0 and not observed['State']['OOMKilled'], 'Multiway country worker exit/OOM')
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
    require(sha(args.recipe) == args.pin, 'Multiway country recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe, args.pin))
