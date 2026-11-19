"""Isolated audit controls and one metadata-only national entry-resolution stage."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from coarse_timing_input import require, start_watchdog

IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
PREFIX = 'data/coarse-quality/us-osm-conditional-entry-resolution-v3-'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(root, name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 1048576, 'Entry resolution record cap')
    with (root/name).open('xb') as stream:
        stream.write(raw)


def worker(plan):
    from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
    from coarse_osm_data import verify_worker_inputs
    root = Path('/work')
    began = time.monotonic()
    timer = start_watchdog(900)
    def check():
        require(time.monotonic()-began < 900, 'Entry resolution worker deadline')
        require(owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Entry resolution owned cap')
    try:
        cgroup = Path('/sys/fs/cgroup')
        require((cgroup/'memory.max').read_text().strip() == str(4*1024**3) and (cgroup/'memory.swap.max').read_text().strip() == '0', 'Entry resolution memory/swap')
        files={destination:plan['inputs'][name] for name,destination in plan['mounts'].items()}
        files.update({destination:plan['inputs'][name] for destination,name in plan['viewMounts'].items()})
        verify_worker_inputs({'workerFiles':files})
        if plan['operation'] == 'controls':
            import unittest
            import coarse_osm_entry_resolution_audit_v1_test as old_tests
            import coarse_osm_car_entry_native_v1_test as native_tests
            import coarse_osm_fact_view_v1_test as view_tests
            import coarse_osm_conditional_entry_baseline_v1_test as baseline_tests
            import coarse_osm_conditional_entry_preservation_v1_test as preservation_tests
            native_tests.configure_native('/artifacts/car-entry.so',plan['artifact']['sha256'])
            require(not Path('/facts').exists(),'Entry controls cannot mount real facts')
            suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (old_tests,native_tests,view_tests,baseline_tests,preservation_tests))
            tested=unittest.TextTestRunner(verbosity=2).run(suite)
            result={'tests':tested.testsRun,'successful':tested.wasSuccessful(),'failures':len(tested.failures),'errors':len(tested.errors),'skips':len(tested.skipped)}
            save(root,'controls.json',result)
            require(result=={'tests':37,'successful':True,'failures':0,'errors':0,'skips':0},'Complete new entry/view/preservation controls')
            save(root,'report.json',{'status':'conditional_entry_independent_native_view_controls_passed','controls':result,'sourcePbfReads':0,'countryFactReads':0})
            return 0
        require(plan['operation'] == 'run', 'Entry resolution operation')
        from coarse_osm_car_entry_native_v1 import NativeEntries
        from coarse_osm_entry_resolution_audit_v1 import audit
        native = NativeEntries('/artifacts/car-entry.so', plan['artifact']['sha256'])
        dims = plan['dimensions']
        require(dims == [4227238, 5731903, 9878318, 46533, 39869], 'Entry resolution fixed source dimensions')
        before={destination:Path(destination).stat() for destination in files if destination.startswith(('/facts/','/inputs/rules','/inputs/fallback','/inputs/arc-insertions'))}
        import struct
        from coarse_osm_conditional_entry_baseline_v1 import baseline
        from coarse_osm_conditional_entry_preservation_v1 import audit as preserve
        from coarse_osm_conditional_fact_io_v1 import Rows
        from coarse_osm_car_packed_audit_v1 import rows
        catalog=json.loads(Path('/inputs/fact-views.json').read_bytes())['views']['country']
        roster={'cost-facts/'+Path(dest).name:{'bytes':entry['bytes'],'sha256':entry['sha256']} for dest,entry in catalog['files'].items()}
        raw_insertions=Path('/inputs/arc-insertions.u32').read_bytes();require(len(raw_insertions)==260576,'Complete source insertion ledger')
        insertions=list(struct.iter_unpack('<IIII',raw_insertions))
        way_rows=Rows('/facts',roster,'ways','<QddII',check);closure_rows=Rows('/facts',roster,'closures','<Q',check)
        try:delta=baseline(way_rows,closure_rows,insertions,9837326,9620680,dims[2])
        finally:way_rows.close();closure_rows.close()
        output = root/'resolved'
        output.mkdir()
        phase = time.monotonic()
        counts = native.resolve('/facts/cost-facts', '/inputs/rules.bin', '/inputs/fallback.u64', output, dims)
        native_seconds = time.monotonic()-phase
        check()
        phase = time.monotonic()
        proof = audit('/facts/cost-facts', '/inputs/rules.bin', '/inputs/fallback.u64', output, dims, counts, baseline_post=delta['newPostUnderOriginalClosures'], check=check)
        audit_seconds = time.monotonic()-phase
        old_closed=[r[0] for r in struct.iter_unpack('<Q',Path('/inputs/old-entry-closures.bin').read_bytes())]
        new_closed=[r[0] for r in struct.iter_unpack('<Q',(output/'closures-0000.bin').read_bytes())]
        old_pairs=list(struct.iter_unpack('<II',Path('/inputs/old-entry-pairs.u32').read_bytes()))
        new_pairs=list(struct.iter_unpack('<II',(output/'entry-pairs-pre.u32').read_bytes()))
        way_rows=Rows('/facts',roster,'ways','<QddII',check);arc_rows=Rows('/facts',roster,'arcs','<IIIIIb3xQ',check)
        try:preservation=preserve(old_closed,new_closed,old_pairs,new_pairs,insertions,9837326,dims[2],lambda arc:way_rows[arc_rows[arc][2]][0])
        finally:way_rows.close();arc_rows.close()
        for name, stat in before.items():
            after = Path(name).stat()
            require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Entry resolution input stat drift')
        assets = {str(path.relative_to(root)): {'bytes': path.stat().st_size, 'sha256': sha(path)} for path in output.iterdir()}
        save(root, 'artifacts.json', assets)
        save(root, 'report.json', {'status': 'conditional_national_entry_resolution_and_independent_audit_passed', 'nativeCounts': counts, 'independentAudit': proof,'originalClosureBaselineDelta':delta,'previousEntryPreservation':preservation,
                                 'nativeSecondsIncludingInputReadsAndOutput': native_seconds, 'independentAuditSeconds': audit_seconds,
                                 'workerSecondsIncludingBindingsAndBothOperations': time.monotonic()-began,
                                 'assets': assets, 'sourcePbfReads': 0, 'sourceConstructorExecutions': 0, 'routingQueries': 0, 'providerRequests': 0,
                                 'runtimeGraphBuilt': False, 'appActivated': False,
                                 'scope': 'Resolved only restriction metadata against all pre-closure facts, with exhaustive independent typed source/pair/decision/closure proof. Routing/spatial/paid geometry/codec/ETA/app qualification are separate.'})
        return 0
    except BaseException as error:
        save(root, 'failure.json', {'status': 'entry_resolution_stopped', 'error': repr(error), 'workerSeconds': time.monotonic()-began})
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
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe) == pin, 'Entry resolution recipe binding')
    plan = json.loads(recipe.read_bytes())
    operation = plan['operation']
    require(operation in ('controls', 'run') and plan['output'] == PREFIX+operation+'-v1', 'Entry resolution exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+67108864+268435456 < 72*1024**3, 'Entry resolution aggregate reservation')
    require(set(plan['mounts'])|set(plan['viewMounts'].values()) == set(plan['inputs']), 'Entry resolution complete input bindings')
    for destination,source in plan['viewMounts'].items():
        require(destination.startswith('/facts/cost-facts/') and Path(destination).name==Path(source).name and source in plan['inputs'],'Readonly complete native field view')
    require(operation!='controls' or not plan['viewMounts'],'Entry controls have no graph view')
    require(operation!='run' or plan['admission']=={'tests':37,'successful':True,'failures':0,'errors':0,'skips':0},'New entry wrapper qualification')
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/')), 'Entry resolution input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Entry resolution input SHA/no PBF')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-entry-resolve-'+owner[:12]
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
        for destination,source in plan['viewMounts'].items():
            command += ['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        command += ['--mount', f'type=bind,src={root},dst=/work', '--mount', f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly',
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_conditional_entry_resolution_v3.py', '/inputs/recipe.json', pin, '--worker']
        created = call(command)
        require(created.returncode == 0, created.stderr)
        identity = created.stdout.strip()
        require(len(identity) == 64, 'Entry resolution exact owned ID')
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        isolation(observed, 'controls')
        save(root, 'container-initial.json', observed)
        with (root/'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began < 1020 and owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Entry resolution host deadline/owned cap')
                time.sleep(.5)
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        save(root, 'container-result.json', {'State': observed['State'], 'clientExitCode': child.returncode})
        require(child.returncode == observed['State']['ExitCode'] == 0 and not observed['State']['OOMKilled'], 'Entry resolution worker exit/OOM')
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
    require(sha(args.recipe) == args.pin, 'Entry resolution recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe, args.pin))
