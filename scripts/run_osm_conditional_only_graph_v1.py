"""Compile the source-qualified conditional-node graph and audit every native field."""
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
PREFIX = 'data/coarse-quality/us-osm-conditional-only-graph-'


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
        from coarse_osm_car_packed_native_v1 import NativePacked
        from coarse_osm_incoming_entry_graph_audit_v1 import audit
        if plan['operation'] == 'controls':
            import importlib
            import unittest
            names = ['coarse_osm_incoming_entry_pairs_v1_test','coarse_osm_incoming_entry_graph_audit_v1_test']
            require(not Path('/facts').exists() and not Path('/view').exists(), 'Incoming-entry controls are synthetic only')
            suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(name)) for name in names)
            tested = unittest.TextTestRunner(verbosity=2).run(suite)
            controls = dict(tests=tested.testsRun,successful=tested.wasSuccessful(),failures=len(tested.failures),errors=len(tested.errors),skips=len(tested.skipped))
            require(controls == dict(tests=18,successful=True,failures=0,errors=0,skips=0), 'All incoming-entry Linux controls')
            save(root,'report.json',{'status':'conditional_only_incoming_entry_graph_controls_passed','controls':controls,'sourcePbfReads':0,'routingQueries':0})
            return 0
        require(plan['operation'] == 'run', 'Entry graph operation')
        dimensions = plan['dimensions']
        require(len(dimensions) == 6 and all(type(n) is int and 0 < n < 2**32 for n in dimensions), 'Lane graph source dimensions')
        resolution = json.loads(Path('/inputs/lane-resolution-report.json').read_bytes())
        require(resolution['status'] == 'fresh_source_epoch_single_and_multi_restrictions_independently_audited', 'Fresh lane restriction resolution')
        facts = json.loads(Path('/inputs/conditional-node-facts-report.json').read_bytes())
        require(facts['status'] == 'conditional_only_national_facts_and_retention_independently_audited'
                and facts['previousConvertedRelations'] == 7480 and facts['convertedOnlyRelations'] == 158
                and facts['representedOnlyRelations'] == 30 and facts['inactiveFromOnlyRelations'] == 128
                and facts['allIndependentContributorsRetained'] and facts['allOldAllowedTransitionsPreserved']
                and facts['everyCurrentTypedTurnByteExact'] and facts['everyCurrentFlagRetainedInNativeOrder']
                and facts['sourcePreArcIdsRetained'] and not facts['postArcIdsReusable'] and not facts['appActivated'], 'Complete qualified mandatory fact source epoch')
        require([dimensions[2], dimensions[1], dimensions[3]] == resolution['dimensions'][:3]
                and dimensions[4] == facts['newFinalPostArcs']
                and dimensions[5] == facts['turnAudit']['allSourceTurnsIndependentlyCompared']
                and facts['preconditionalPostArcs'] == resolution['multiVia']['proposedPostArcs']
                and plan['baselinePost'] == facts['originalConservativePostArcs'] == resolution['originalConservativePostArcs']
                and plan['comparisonParentPostArcs'] == facts['currentPostArcs'], 'Exact new closure and typed-turn dimensions')
        flag_order = facts['currentFlagOrderAudit']
        require(flag_order['spatialAndNativeRowsIndependentlyCompared'] == dimensions[1]
                and flag_order['sourceQualifiedOpenedNodeIdsPreserved'] == facts['priorIncompleteNodeOpeningsPreserved'] == 1488
                and flag_order['everyOriginalFlagReproducedThroughBijection'] and flag_order['everyFinalFlagRoundTripsExactly']
                and flag_order['signalsReversalAndIndependentBlockersPreserved']
                and facts['turnAudit']['oldSourceTurnsByteExact'] == 409178, 'All current native-order flags, prior node openings and turns retain')
        pricing = json.loads(Path('/inputs/timing-cost-report.json').read_bytes())
        require(pricing['status'] == 'complete_typed_tagged_timing_costs_and_independent_python_prices_passed'
                and pricing['countryCostFactsBuilt'] and pricing['allPhysicalArcDescriptorsAndOrderExact']
                and pricing['allDirectionsDefaultsRolesAndFlagsExact'] and pricing['nodeFlagsChanged'] == 0
                and not pricing['originalLegalSpeedSourceFactsModified']
                and pricing['sourceCounts']['arcs'] == dimensions[3], 'Exact physical membership permits current restriction-index reuse')
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
        old_final = root/'old-entry-forbidden.u24'
        original_augmentation = native.augment('/facts/cost-facts', '/view/closures-0000.bin', '/inputs/old-entry-pairs-pre.u32', routing, old_final, dimensions[2:3]+dimensions[1:2]+dimensions[3:5])
        from coarse_osm_incoming_entry_pairs_v1 import merge_incoming_pairs
        augmentation, incoming_projection = merge_incoming_pairs('/facts/cost-facts','/view',routing,
            '/inputs/old-entry-pairs-pre.u32','/inputs/entry-pairs-pre.u32',old_final,final,dimensions,original_augmentation,check)
        augment_seconds = time.monotonic()-phase
        check()
        phase = time.monotonic()
        proof = audit('/facts/cost-facts', '/view', routing, '/inputs/entry-pairs-pre.u32', final, dimensions, augmentation, baseline_post=plan['baselinePost'], check=check)
        audit_seconds = time.monotonic()-phase
        for name, stat in before.items():
            after = Path(name).stat()
            require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Entry graph input stat drift')
        paths = {'routing/'+path.name: (final if path.name == 'forbidden-turns.u24' else path) for path in routing.iterdir()}
        assets = {name: {'path': str(path.relative_to(root)), 'bytes': path.stat().st_size, 'sha256': sha(path)} for name, path in paths.items()}
        save(root, 'artifacts.json', assets)
        save(root, 'report.json', {'status': 'conditional_only_national_graph_and_independent_complete_audit_passed', 'basePackedResult': base, 'previousFinalPostArcs': facts['currentPostArcs'], 'mandatoryIncomingProjection': incoming_projection, 'originalNativeAugmentation': original_augmentation, 'mandatoryRepresentedRules': facts['representedOnlyRelations'], 'mandatoryInactiveFromRules': facts['inactiveFromOnlyRelations'], 'comparisonParentPostArcs': plan['comparisonParentPostArcs'],
                                 'augmentationCounts': augmentation, 'independentAudit': proof, 'assets': assets,
                                 'finalPayloadBytes': sum(row['bytes'] for row in assets.values()),
                                 'nativeEncodingSeconds': encode_seconds, 'nativeAugmentationSeconds': augment_seconds,
                                 'independentAuditSeconds': audit_seconds, 'workerSecondsIncludingBindingsAndAllOperations': time.monotonic()-began,
                                 'sourcePbfReads': 0, 'sourceConstructorExecutions': 0, 'routingQueries': 0, 'providerRequests': 0,
                                 'spatialOrPaidGeometryOrCodecBuilt': False, 'appActivated': False,
                                 'scope': 'All old25398entrypairs pass unchanged nativeaugment, new38mandatory bans use separately audited source-to-CSR mapping; incoming oldclosed is sufficient to preserve every oldallowedtransition, outgoing may be anysourceway. Full independent native-identity/currentflag-order/price/reverse/turn/allpair audit. Fresh CSR IDs from qualified fixed-profile inactive conditional-no-turn source facts; every represented ban remains and all absent eligible directed incidences independently replay, including the already qualified native-order passable-node correction. All source costs/directions/geometry/native IDs/PRE descriptors and order retain exactly. Every old typed turn/unrelated contributor remains; converted junction bans concern formerly whole-way-closed members. Complete independent cost/flag/physical-reverse/source-turn audit plus exact mapped single/multi entry union. Auditor preservation statement compares the conservative ORIGINAL closure baseline on this same physical/cost epoch, not a transplanted preceding CSR. All numeric POST IDs, spatial geometry/history/storage/endpoints/maps remain new pending stages. No PBF/source constructor/query/provider/DB/accuracy/app admission.'})
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
    require(operation in ('controls','run') and plan['output'] == PREFIX+operation+'-v1', 'Entry graph exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+268435456+268435456 < 72*1024**3, 'Entry graph aggregate reservation')
    require(set(plan['mounts'])|set(plan['viewMounts'].values()) == set(plan['inputs']), 'Entry graph complete input bindings')
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/')), 'Entry graph input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Entry graph input SHA/no PBF')
    for destination, name in plan['viewMounts'].items():
        require(name in plan['inputs'] and destination.startswith(('/view/','/facts/cost-facts/')) and Path(destination).name == Path(name).name, 'Entry graph readonly view binding')
    require(operation != 'controls' or not plan['viewMounts'], 'Entry graph controls have no real fact view')
    require(operation != 'run' or plan['admission'] == dict(tests=18,successful=True,failures=0,errors=0,skips=0) and plan['nativeFactAdmission'] == dict(tests=122,successful=True,failures=0,errors=0,skips=0) and plan['admission']['successful'] and plan['admission']['skips'] == 0, 'Entry graph qualification admission')
    require(shutil.disk_usage(repo/'data/coarse-quality').free >= 1073741824, 'Entry graph disk headroom')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-conditional-only-graph-'+owner[:12]
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
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_conditional_only_graph_v1.py', '/inputs/recipe.json', pin, '--worker']
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
