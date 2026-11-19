"""Isolated qualification/national metadata resolver from immutable pre-closure facts."""
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
PREFIX = 'data/coarse-quality/us-osm-absent-entry-country-'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(root, name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 1048576, 'Absent-entry record cap')
    with (root/name).open('xb') as stream:
        stream.write(raw)


def worker(plan):
    from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
    from coarse_osm_data import verify_worker_inputs
    root = Path('/work')
    began = time.monotonic()
    timer = start_watchdog(1200)
    def check():
        require(time.monotonic()-began < 1200, 'Absent-entry worker deadline')
        require(owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Absent-entry owned cap')
    try:
        cgroup = Path('/sys/fs/cgroup')
        require((cgroup/'memory.max').read_text().strip() == str(4*1024**3) and (cgroup/'memory.swap.max').read_text().strip() == '0', 'Absent-entry memory/swap')
        verify_worker_inputs({'workerFiles': {destination: plan['inputs'][name] for name, destination in plan['mounts'].items()}})
        before = {name: Path(name).stat() for name in plan['mounts'].values()}
        if plan['operation'] == 'controls':
            import unittest
            import coarse_osm_absent_entry_country_v1_test as country
            import coarse_osm_absent_entry_v1_test as captured
            import coarse_osm_restriction_entry_v1_test as rules
            import coarse_osm_entry_graph_v1_test as graph
            import coarse_osm_conditional_attribute_mounts_v2_test as layout
            require(not Path('/facts').exists() and not Path('/baseline').exists(), 'Absent-entry controls synthetic only')
            suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(module) for module in (country, captured, rules, graph, layout))
            tested = unittest.TextTestRunner(verbosity=2).run(suite)
            controls = {'tests': tested.testsRun, 'successful': tested.wasSuccessful(), 'failures': len(tested.failures), 'errors': len(tested.errors), 'skips': len(tested.skipped)}
            require(controls == {'tests': 28, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Absent-entry country controls')
            save(root, 'report.json', {'status': 'absent_entry_country_controls_passed', 'controls': controls, 'sourcePbfReads': 0, 'nationalRoutingQueries': 0})
            return 0
        require(plan['operation'] == 'run', 'Absent-entry operation')
        from coarse_osm_absent_entry_country_v1 import resolve
        report = resolve('/facts', '/inputs/rules.bin', '/inputs/fallback.u64', '/baseline', root/'resolved',
                         plan['dimensions'], plan['nativeCounts'], baseline_post=plan['baselinePostArcs'], check=check)
        require(report['baselineAudit'] == plan['expectedBaselineAudit'], 'Frozen complete baseline audit parity')
        for name, old in before.items():
            new = Path(name).stat()
            require((old.st_dev,old.st_ino,old.st_size,old.st_mtime_ns,old.st_ctime_ns) == (new.st_dev,new.st_ino,new.st_size,new.st_mtime_ns,new.st_ctime_ns), 'Absent-entry input drift')
        assets = {}
        for path in sorted((root/'resolved').iterdir()):
            require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 67108864, 'Absent-entry output file bound')
            assets[str(path.relative_to(root))] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
        report.update(assets=assets, workerSecondsIncludingBindingsAuditAndResolution=time.monotonic()-began)
        save(root, 'report.json', report)
        check()
        return 0
    except BaseException as error:
        save(root, 'failure.json', {'status': 'absent_entry_country_stopped', 'error': repr(error), 'workerSeconds': time.monotonic()-began})
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
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe) == pin, 'Absent-entry recipe binding')
    plan = json.loads(recipe.read_bytes())
    operation = plan['operation']
    require(plan['workerSeconds'] == 1200 and plan['hostSeconds'] == 1320, 'Absent-entry exact deadlines')
    require(operation in ('controls', 'run') and plan['output'] == PREFIX+operation+'-v1', 'Absent-entry exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan.get('additionalActiveReservationBytes', 0)+67108864+268435456 < 72*1024**3, 'Absent-entry aggregate reservation')
    require(set(plan['mounts']) == set(plan['inputs']), 'Absent-entry complete input bindings')
    if operation == 'run':
        from coarse_osm_conditional_attribute_mounts_v2 import validate_fact_mounts
        validate_fact_mounts(plan['mounts'])
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/', '/paths/', '/baseline/')), 'Absent-entry input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Absent-entry input SHA/no PBF')
    require(operation == 'controls' or plan['admission'] == {'tests': 28, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Absent-entry qualification before facts')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-absent-entry-country-'+owner[:12]
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
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_absent_entry_country_v1.py', '/inputs/recipe.json', pin, '--worker']
        created = call(command)
        require(created.returncode == 0, created.stderr)
        identity = created.stdout.strip()
        require(len(identity) == 64, 'Absent-entry exact owned ID')
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        isolation(observed, 'controls')
        save(root, 'container-initial.json', observed)
        with (root/'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began < 1320 and owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Absent-entry host deadline/owned cap')
                time.sleep(.5)
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        save(root, 'container-result.json', {'State': observed['State'], 'clientExitCode': child.returncode})
        require(child.returncode == observed['State']['ExitCode'] == 0 and not observed['State']['OOMKilled'], 'Absent-entry worker exit/OOM')
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
    require(sha(args.recipe) == args.pin, 'Absent-entry recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe, args.pin))
