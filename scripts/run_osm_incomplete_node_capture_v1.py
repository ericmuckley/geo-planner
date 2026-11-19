"""Complete captured source, node-flag composition and native CSR consumer audit."""
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
    from array import array
    import gzip
    import shutil
    from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
    from coarse_osm_data import verify_worker_inputs
    from coarse_osm_incomplete_node_flags_v1 import rules_from_metadata, build, audit
    from coarse_osm_car_packed_native_v1 import NativePacked
    from coarse_osm_car_packed_audit_v1 import audit as audit_packed
    root = Path('/work'); began = time.monotonic(); timer = start_watchdog(900)
    def check():
        require(time.monotonic()-began < 900 and owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Captured composition deadline/owned cap')
    def decoded(path, pin):
        with gzip.open(path, 'rb') as stream: raw = stream.read(16777217)
        require(len(raw) == pin['rawBytes'] <= 16777216 and hashlib.sha256(raw).hexdigest() == pin['rawSha256'], 'Complete captured evidence binding')
        return json.loads(raw)
    try:
        cgroup = Path('/sys/fs/cgroup')
        require((cgroup/'memory.max').read_text().strip() == str(4*1024**3) and (cgroup/'memory.swap.max').read_text().strip() == '0', 'Captured composition memory/swap')
        verify_worker_inputs({'workerFiles': {dest: plan['inputs'][name] for name, dest in plan['mounts'].items()}})
        before = {dest: Path(dest).stat() for dest in plan['mounts'].values()}
        require(plan['admission'] == dict(tests=75, successful=True, failures=0, errors=0, skips=0), 'All75actualLinuxcontrols before source')
        metadata = decoded('/inputs/incomplete-node-metadata.json.gz', plan['metadataArtifact'])
        rules = rules_from_metadata(metadata['incompleteRelations']); require(len(rules) == 2525, 'All frozen incomplete source records replay')
        mapping = decoded('/inputs/blocked-nodes.json.gz', plan['mappingArtifact'])
        all_tags = decoded('/inputs/node-evidence.json.gz', plan['nodeEvidenceArtifact'])['nodeEvidence']
        evidence = {str(row['sourceNodeId']): all_tags[str(row['sourceNodeId'])] for row in mapping}
        source = Path('/facts')
        current = (source/'flags-0000.bin').read_bytes()
        require(len(current) == 46881 and len(mapping) == 97, 'Complete captured flags and original blockers')
        permutation = array('I', range(len(current)))
        proposed, changes = build(current, mapping, evidence, permutation, rules)
        proof = audit(current, proposed, mapping, evidence, permutation, rules)
        require(list(proof['changedVertices']) == [row['vertex'] for row in changes], 'Every captured proposed flag independently replays')
        view = root/'compiler-view'; view.mkdir()
        for path in source.iterdir():
            require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 16777216, 'Complete bounded captured source view')
            if path.name == 'flags-0000.bin':
                with (view/path.name).open('xb') as stream: stream.write(proposed)
            else:
                shutil.copyfile(path, view/path.name)
                require(sha(view/path.name) == sha(path), 'All other captured physical and turn facts byte-exact')
        dimensions = [143560, 46881, 28995, 79148, 78363, 4178]
        routing = root/'routing'; routing.mkdir()
        native = NativePacked('/artifacts/car-entry.so', plan['artifact']['sha256']).encode(view, routing, dimensions)
        derived = audit_packed(view, routing, dimensions)
        compared = []
        for path in routing.iterdir():
            previous = Path('/parent-routing')/path.name
            require(previous.is_file(), 'Every captured routing field present in qualified parent')
            if path.name == 'node-flags.u8':
                require(path.read_bytes() == proposed and previous.read_bytes() == current, 'Native formatter copies every new flag exactly')
            else:
                require(path.read_bytes() == previous.read_bytes(), 'Every other captured CSR byte and numeric ID unchanged')
                compared.append(path.name)
        for name, stat in before.items():
            after = Path(name).stat()
            require((stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns) == (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns), 'All captured source/code inputs preserved')
        save(root, 'report.json', {'status': 'complete_captured_incomplete_node_flag_and_native_consumer_audit_passed',
             'dimensions': dimensions, 'originalBlockedNodes': 97, 'openedVertices': len(changes),
             'flagAudit': {k: list(v) if k == 'changedVertices' else v for k,v in proof.items()},
             'nativeResult': native, 'independentCompleteSourceCsrAudit': derived,
             'unchangedOtherRoutingFields': sorted(compared), 'allOtherSourceFactsByteExact': True,
             'sourcePbfReads': 0, 'routingQueries': 0, 'providerRequests': 0, 'applicationDbReads': 0, 'appActivated': False,
             'workerSecondsIncludingBindingsCompositionCompilerAndFullAudit': time.monotonic()-began,
             'scope': 'Complete captured source view/current flags, original97blockers/known original tags, all2525national incomplete records, full46881native identity permutation, all78363costs/reverses/4178turns/2598basepairs independently checked. Only captured node-blocker bits change. Every other source and all10other baseCSRfields byte-identical to qualified parent; numeric IDs and parent entry/history mappings retain by complete byte identity. No new finalentry/history compile or route/accuracy claim; country5.7millionflags/permutation/runtime still pending. Protected4GiB/zeroSwap/2CPU/netnone/readonly/64PIDs/file64MiB/owned64MiB/tmp256MiB/900sworker1020shost, all reservations under72GiB. No PBF/provider/DB/app.'})
        return 0
    except BaseException as error:
        save(root, 'failure.json', {'status': 'incomplete_node_capture_stopped', 'error': repr(error)}); raise
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
    require(operation == 'capture' and plan['output'] == PREFIX+operation+'-v1', 'Conditional node facts exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan.get('additionalActiveReservationBytes', 0)+67108864+268435456 < 72*1024**3, 'Conditional node facts aggregate reservation')
    require(set(plan['mounts']) == set(plan['inputs']), 'Conditional node facts complete input bindings')
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/', '/paths/', '/parent-routing/')), 'Conditional node facts input scope')
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
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_incomplete_node_capture_v1.py', '/inputs/recipe.json', pin, '--worker']
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
