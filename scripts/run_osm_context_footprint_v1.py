"""Offline complete typed-fact turn-context footprint under fixed hard limits."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from coarse_timing_input import require, start_watchdog

IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
PREFIX = 'data/coarse-quality/us-osm-context-footprint-'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(root, name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 1048576, 'Context footprint record cap')
    with (root/name).open('xb') as stream:
        stream.write(raw)


def worker(plan):
    from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
    from coarse_osm_data import verify_worker_inputs
    root = Path('/work')
    began = time.monotonic()
    timer = start_watchdog(900)
    def check():
        require(time.monotonic()-began < 900, 'Context footprint worker deadline')
        require(owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Context footprint owned cap')
    try:
        cgroup = Path('/sys/fs/cgroup')
        require((cgroup/'memory.max').read_text().strip() == str(4*1024**3) and (cgroup/'memory.swap.max').read_text().strip() == '0', 'Context footprint memory/swap')
        files = {destination: plan['inputs'][name] for name, destination in plan['mounts'].items()}
        verify_worker_inputs({'workerFiles': files})
        before = {name: Path(name).stat() for name in files}
        if plan['operation'] == 'controls':
            import unittest
            import coarse_osm_context_footprint_v1_test as tests
            require(not any(Path(n).exists() for n in ('/facts', '/paths', '/inputs/rules.bin', '/inputs/decisions.bin', '/inputs/entry-pairs-pre.u32')), 'Footprint controls use synthetic data only')
            tested = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
            controls = {'tests': tested.testsRun, 'successful': tested.wasSuccessful(), 'failures': len(tested.failures), 'errors': len(tested.errors), 'skips': len(tested.skipped)}
            require(controls == {'tests': 8, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Context footprint Linux controls')
            save(root, 'report.json', {'status': 'context_footprint_controls_passed', 'controls': controls, 'sourcePbfReads': 0, 'routingQueries': 0})
            return 0
        from coarse_osm_context_footprint_v1 import inventory
        require(plan['operation'] == 'run' and plan['dimensions'] == [4227238, 5731903, 9878318, 9807359, 46533], 'Context footprint full dimensions')
        report, raw = inventory('/facts', '/inputs/rules.bin', '/inputs/decisions.bin', '/inputs/entry-pairs-pre.u32', plan['dimensions'], check)
        require((report['closureIdsRetained'], report['resolvedRulesRetained'], report['inactiveMissingMemberRulesRetained'], report['noJoinFallbackRulesRetained']) == (40259, 23138, 23257, 138), 'Context footprint unchanged source resolution')
        require((report['sourcePreEntryPairsChecked'], report['activeEntryPairs'], report['entryPairsBlockedByOtherClosures']) == (22964, 20185, 2779), 'Context footprint complete entry-pair reconciliation')
        graph = json.loads(Path('/inputs/graph-report.json').read_bytes())
        candidate = json.loads(Path('/inputs/candidate-report.json').read_bytes())
        require(graph['augmentationCounts'] == [22964, 234013, 20185, 2779, 252230, 9807359], 'Footprint parent graph identity')
        held = candidate['retainedBackingBytes']
        maximum = max(x['stats']['maximumBackingBufferBytes'] for phase in candidate['phases'] for x in [phase['diagnostic'], *phase['productions']])
        require((held, maximum) == (157868131, 59671443), 'Footprint measured parent array-buffer scopes')
        # These are explicit proposed typed-array increments, not a runtime or app measurement.
        saved_turn_bytes = (252230-234013)*6
        proposed_held = held-saved_turn_bytes+report['rawContextRuntimeFieldsUpperBoundBytes']+report['triggerIncomingBitsetBytes']
        proposed_query = maximum+report['additionalQueryLabelBytes']
        report['componentLayoutProjection'] = {'measuredParentHeldBackingBytes': held, 'measuredParentQueryMaximumBackingBytes': maximum,
            'supportedOnlyForbiddenFieldBytesSaved': saved_turn_bytes, 'proposedHeldTypedBackingUpperBytes': proposed_held,
            'proposedQueryBackingOnSameParentWorkspaceBytes': proposed_query, 'retainedCapBytes': 162238546,
            'queryCapBytes': 67108864, 'retainedProjectionFits': proposed_held <= 162238546,
            'queryProjectionFits': proposed_query <= 67108864, 'isRuntimeOrFullAppAdmission': False,
            'scope': 'All-prefix/all-retained-to-arc overcount plus a separate incoming trigger bitset and one u32 label per context state. Parent workspace is measured on83 cases, not an arbitrary-query bound; actual loader/search/display/retained/package/first-estimate gates remain.'}
        with (root/'prefix-counts.bin').open('xb') as stream:
            stream.write(raw)
        report['artifact'] = {'file': 'prefix-counts.bin', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'format': 'little-endian QQIIII:fromWay,viaWay,viaArcs,exitUpper,ruleCount,activeEntryPairs;offline inventory only'}
        for name, stat in before.items():
            after = Path(name).stat()
            require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Footprint input stat drift')
        report['workerSecondsIncludingBindingsAndCompleteInventory'] = time.monotonic()-began
        report['appActivated'] = False
        save(root, 'report.json', report)
        return 0
    except BaseException as error:
        save(root, 'failure.json', {'status': 'context_footprint_stopped', 'error': repr(error), 'workerSeconds': time.monotonic()-began})
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
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe) == pin, 'Context footprint recipe binding')
    plan = json.loads(recipe.read_bytes())
    operation = plan['operation']
    require(operation in ('controls', 'run') and plan['output'] == PREFIX+operation+'-v1', 'Context footprint exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan.get('additionalActiveReservationBytes', 0)+67108864+268435456 < 72*1024**3, 'Context footprint aggregate reservation')
    require(set(plan['mounts']) == set(plan['inputs']), 'Context footprint complete input bindings')
    if operation == 'run':
        from coarse_osm_conditional_attribute_mounts_v2 import validate_fact_mounts
        validate_fact_mounts(plan['mounts'])
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/', '/paths/')), 'Context footprint input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Context footprint input SHA/no PBF')
    require(operation == 'controls' or plan['admission'] == {'tests': 8, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Context footprint qualification before facts')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-context-footprint-'+owner[:12]
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
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_context_footprint_v1.py', '/inputs/recipe.json', pin, '--worker']
        created = call(command)
        require(created.returncode == 0, created.stderr)
        identity = created.stdout.strip()
        require(len(identity) == 64, 'Context footprint exact owned ID')
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        isolation(observed, 'controls')
        save(root, 'container-initial.json', observed)
        with (root/'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began < 1020 and owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Context footprint host deadline/owned cap')
                time.sleep(.5)
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        save(root, 'container-result.json', {'State': observed['State'], 'clientExitCode': child.returncode})
        require(child.returncode == observed['State']['ExitCode'] == 0 and not observed['State']['OOMKilled'], 'Context footprint worker exit/OOM')
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
    require(sha(args.recipe) == args.pin, 'Context footprint recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe, args.pin))
