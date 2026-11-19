"""Qualify incomplete-maneuver node rules and full flag composition in isolation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from coarse_timing_input import require, start_watchdog

IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
PREFIX = 'data/coarse-quality/us-osm-incomplete-node-'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(root, name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 1048576, 'Conditional node facts record cap')
    with (root/name).open('xb') as stream:
        stream.write(raw)


def worker(plan):
    import importlib
    import unittest
    from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
    from coarse_osm_data import verify_worker_inputs
    import coarse_osm_car_entry_native_v1_test as entry_tests
    import coarse_osm_car_packed_native_v1_test as packed_tests
    root = Path('/work'); began = time.monotonic(); timer = start_watchdog(900)
    try:
        cgroup = Path('/sys/fs/cgroup')
        require((cgroup/'memory.max').read_text().strip() == str(4*1024**3)
                and (cgroup/'memory.swap.max').read_text().strip() == '0', 'Incomplete-node control memory/swap')
        verify_worker_inputs({'workerFiles': {dest: plan['inputs'][name] for name, dest in plan['mounts'].items()}})
        require(not Path('/facts').exists() and not Path('/paths').exists(), 'Synthetic-only controls have no real facts/paths')
        artifact = ('/artifacts/car-entry.so', plan['artifact']['sha256'])
        entry_tests.configure_native(*artifact); packed_tests.ARTIFACT = artifact
        names = ['coarse_osm_conditional_node_facts_v1_test', 'coarse_osm_entry_graph_audit_v1_test',
                 'coarse_osm_car_entry_native_v1_test', 'coarse_osm_fact_view_v1_test',
                 'coarse_osm_conditional_entry_baseline_v1_test', 'coarse_osm_conditional_entry_preservation_v1_test',
                 'coarse_osm_car_packed_native_v1_test', 'coarse_osm_passable_node_overlay_v1_test',
                 'coarse_osm_car_passable_barriers_v1_test', 'coarse_osm_incomplete_node_restrictions_v1_test',
                 'coarse_osm_incomplete_node_flags_v1_test']
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(n)) for n in names)
        tested = unittest.TextTestRunner(verbosity=2).run(suite)
        result = dict(tests=tested.testsRun, successful=tested.wasSuccessful(), failures=len(tested.failures), errors=len(tested.errors), skips=len(tested.skipped))
        require(result == dict(tests=75, successful=True, failures=0, errors=0, skips=0), 'All actual Linux composition/compiler controls')
        require(time.monotonic()-began < 900 and owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Control deadline/owned cap')
        save(root, 'report.json', {'status': 'incomplete_node_policy_flag_composition_and_native_controls_passed', 'controls': result,
             'sourcePbfReads': 0, 'routingQueries': 0, 'actualNodeFlagsChanged': False, 'appActivated': False})
        return 0
    except BaseException as error:
        save(root, 'failure.json', {'status': 'incomplete_node_controls_stopped', 'error': repr(error)}); raise
    finally:
        save(root, 'metrics.json', resource_metrics())
        if timer.poll() is None: timer.terminate()
        timer.wait(timeout=5)


def driver(recipe, pin):
    from coarse_osm_full_monitor_v1 import owned_usage
    from prepare_osm_native_lock_v1 import cleanup_owned, settle_error
    from run_osm_country_screen_v1 import isolation
    repo = Path(__file__).resolve().parents[1]
    recipe = Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe) == pin, 'Conditional node facts recipe binding')
    plan = json.loads(recipe.read_bytes())
    operation = plan['operation']
    require(operation == 'controls' and plan['output'] == PREFIX+operation+'-v1', 'Conditional node facts exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan.get('additionalActiveReservationBytes', 0)+67108864+268435456 < 72*1024**3, 'Conditional node facts aggregate reservation')
    require(set(plan['mounts']) == set(plan['inputs']), 'Conditional node facts complete input bindings')
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/', '/paths/')), 'Conditional node facts input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Conditional node facts input SHA/no PBF')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-incomplete-node-'+owner[:12]
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
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_incomplete_node_controls_v1.py', '/inputs/recipe.json', pin, '--worker']
        created = call(command)
        require(created.returncode == 0, created.stderr)
        identity = created.stdout.strip()
        require(len(identity) == 64, 'Conditional node facts exact owned ID')
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        isolation(observed, 'controls')
        save(root, 'container-initial.json', observed)
        with (root/'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began < 1020 and owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Conditional node facts host deadline/owned cap')
                time.sleep(.5)
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        save(root, 'container-result.json', {'State': observed['State'], 'clientExitCode': child.returncode})
        require(child.returncode == observed['State']['ExitCode'] == 0 and not observed['State']['OOMKilled'], 'Conditional node facts worker exit/OOM')
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
    require(sha(args.recipe) == args.pin, 'Conditional node facts recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe, args.pin))
