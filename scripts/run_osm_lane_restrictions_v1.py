"""Fresh-epoch native/single/multi restriction qualification and source joins."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from coarse_timing_input import require, start_watchdog

IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
PREFIX = 'data/coarse-quality/us-osm-lane-restrictions-'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(root, name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 1048576, 'Lane restriction record cap')
    with (root/name).open('xb') as stream:
        stream.write(raw)


def worker(plan):
    from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
    from coarse_osm_data import verify_worker_inputs
    root = Path('/work')
    began = time.monotonic()
    timer = start_watchdog(900)
    def check():
        require(time.monotonic()-began < 900, 'Lane restriction worker deadline')
        require(owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Lane restriction owned cap')
    try:
        cgroup = Path('/sys/fs/cgroup')
        require((cgroup/'memory.max').read_text().strip() == str(4*1024**3) and (cgroup/'memory.swap.max').read_text().strip() == '0', 'Lane restriction memory/swap')
        files = {destination: plan['inputs'][name] for name, destination in plan['mounts'].items()}
        verify_worker_inputs({'workerFiles': files})
        before = {name: Path(name).stat() for name in files}
        if plan['operation']=='controls':
            import unittest
            import coarse_osm_car_entry_native_v1_test as native_tests
            import coarse_osm_entry_resolution_audit_v1_test as audit_tests
            import coarse_osm_multiway_country_v1_test as multi_tests
            import coarse_osm_lane_restrictions_v1_test as epoch_tests
            artifact=('/artifacts/car-entry.so',plan['artifact']['sha256'])
            native_tests.configure_native(*artifact);epoch_tests.ARTIFACT=artifact
            require(not Path('/facts').exists(),'Restriction controls have no real facts')
            suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (native_tests,audit_tests,multi_tests,epoch_tests))
            tested=unittest.TextTestRunner(verbosity=2).run(suite)
            controls={'tests':tested.testsRun,'successful':tested.wasSuccessful(),'failures':len(tested.failures),'errors':len(tested.errors),'skips':len(tested.skipped)}
            save(root,'controls.json',controls)
            require(controls=={'tests':36,'successful':True,'failures':0,'errors':0,'skips':0},'Fresh native/audit/multi/epoch controls')
            save(root,'report.json',{'status':'fresh_lane_restriction_pipeline_controls_passed','controls':controls,'sourcePbfReads':0,'routingQueries':0})
            return 0
        from coarse_osm_car_entry_native_v1 import NativeEntries
        from coarse_osm_lane_restrictions_v1 import resolve
        require(plan['operation'] in ('capture','run'),'Fresh restriction operation')
        metadata=Path('/inputs/unsupported.jsonl');rules=Path('/inputs/rules.bin');fallback=Path('/inputs/fallback.u64')
        if plan['operation']=='capture':
            import struct
            from coarse_osm_car_policy_v1 import restriction_policy
            from coarse_osm_restriction_entry_v1 import entry_restriction
            elements=[];single=[];constant=set();seen=0
            with Path('/inputs/captured-relations.jsonl').open('rb') as stream:
                while line:=stream.readline(2097153):
                    check();seen+=1;require(seen<=10000 and len(line)<=2097152 and line.endswith(b'\n'),'Captured relation bounds')
                    element=json.loads(line)['element']
                    policy=restriction_policy(element)
                    if policy['status']!='closed-unsupported':continue
                    elements.append(element);rule=entry_restriction(element)
                    if rule:single.append((rule.identity,rule.from_way,rule.via_way,rule.to_way))
                    else:constant.update(policy['memberWays'])
            require(seen==4900 and len(elements)==819,'Complete captured relation denominator')
            metadata=root/'capture-unsupported.jsonl';rules=root/'capture-rules.bin';fallback=root/'capture-fallback.u64'
            with metadata.open('xb') as stream:
                for element in elements:stream.write((json.dumps(element,separators=(',',':'))+'\n').encode())
            with rules.open('xb') as stream:stream.write(b''.join(struct.pack('<QQQQ',*r) for r in single))
            with fallback.open('xb') as stream:stream.write(b''.join(struct.pack('<Q',w) for w in sorted(constant)))
            require(plan['dimensions'][3:]==[len(single),len(constant)],'Captured fresh metadata dimensions')
        native=NativeEntries('/artifacts/car-entry.so',plan['artifact']['sha256'])
        report=resolve(native,'/facts',metadata,rules,fallback,root/'resolved',plan['dimensions'],plan['metadataCount'],check)
        if plan['operation']=='capture':
            import struct
            from coarse_osm_car_packed_audit_v1 import rows,ARC
            from coarse_osm_multiway_entry_v1 import plan_multiway
            identities=[r[0] for r in rows('/facts','ways',struct.Struct('<Q24x'))]
            arcs=[{'tail':a[0],'head':a[1],'way':identities[a[2]]} for a in rows('/facts','arcs',ARC)]
            require(len(identities)<=200000 and len(arcs)<=200000,'Captured object bound')
            expected=plan_multiway(elements,arcs,len(arcs))
            closed={r[0] for r in struct.iter_unpack('<Q',(root/'resolved/final/closures-0000.bin').read_bytes())}
            pairs=set(struct.iter_unpack('<II',(root/'resolved/final/entry-pairs-pre.u32').read_bytes()))
            require(closed==expected['closed'] and pairs==set(expected['pairs'])|set(expected['multiPairs']),'Complete captured oracle closure and prepair identity')
            report['capturedClosureAndPairsMatchQualifiedObjectPrototype']=True
            report['capturedReferencePostArcs']=len(arcs)-sum(a['way'] in closed for a in arcs)
        assets = {}
        for filename in sorted((root/'resolved').rglob('*')):
            if filename.is_dir():continue
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
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe) == pin, 'Lane restriction recipe binding')
    plan = json.loads(recipe.read_bytes())
    operation = plan['operation']
    require(operation in ('controls', 'capture', 'run') and plan['output'] == PREFIX+operation+'-v1', 'Lane restriction exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan.get('additionalActiveReservationBytes', 0)+67108864+268435456 < 72*1024**3, 'Lane restriction aggregate reservation')
    require(set(plan['mounts']) == set(plan['inputs']), 'Lane restriction complete input bindings')
    
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/', '/paths/')), 'Lane restriction input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Lane restriction input SHA/no PBF')
    require(operation == 'controls' or plan['admission'] == {'tests': 36, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Lane restriction qualification before facts')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-lane-restrictions-country-'+owner[:12]
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
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_lane_restrictions_v1.py', '/inputs/recipe.json', pin, '--worker']
        created = call(command)
        require(created.returncode == 0, created.stderr)
        identity = created.stdout.strip()
        require(len(identity) == 64, 'Lane restriction exact owned ID')
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        isolation(observed, 'controls')
        save(root, 'container-initial.json', observed)
        with (root/'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began < 1020 and owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Lane restriction host deadline/owned cap')
                time.sleep(.5)
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        save(root, 'container-result.json', {'State': observed['State'], 'clientExitCode': child.returncode})
        require(child.returncode == observed['State']['ExitCode'] == 0 and not observed['State']['OOMKilled'], 'Lane restriction worker exit/OOM')
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
    require(sha(args.recipe) == args.pin, 'Lane restriction recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe, args.pin))
