"""Adopt source-local mandatory-turn deltas while preserving current flags, turns and prices."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from coarse_timing_input import require, start_watchdog

IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
PREFIX = 'data/coarse-quality/us-osm-conditional-only-facts-v2-'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(root, name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 1048576, 'Conditional node facts record cap')
    with (root/name).open('xb') as stream:
        stream.write(raw)


def worker(plan):
    from dataclasses import asdict
    from collections import Counter
    import gzip
    import shutil
    import struct
    from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
    from coarse_osm_data import verify_worker_inputs
    from coarse_osm_conditional_fact_io_v1 import Rows
    from coarse_osm_conditional_node_facts_v1 import TURN, audit_turns, merge_turns, native_passable_flags
    from coarse_osm_inactive_conditional_turns_v1 import audit_effects, relation_overlay
    from coarse_osm_conditional_only_node_v1 import classify as classify_only
    from coarse_osm_conditional_only_effects_v1 import POLICY as INACTIVE_FROM_POLICY, audit_effects as audit_only_ports
    from coarse_osm_conditional_only_local_v1 import local_candidates
    from coarse_osm_conditional_only_effects_v1 import overlay as only_overlay
    root = Path('/work'); began = time.monotonic(); timer = start_watchdog(900)
    def check():
        require(time.monotonic() - began < 900, 'Conditional facts worker deadline')
        require(owned_usage(root)['conservativeAllocatedBytes'] <= 268435456, 'Conditional facts owned cap')
    def unpack_gzip(name, pin):
        with gzip.open(name, 'rb') as stream:
            raw = stream.read(33554433)
        require(len(raw) == pin['rawBytes'] <= 33554432 and hashlib.sha256(raw).hexdigest() == pin['rawSha256'], 'Complete bound compressed evidence')
        return json.loads(raw)
    def plain_json(path, maximum):
        with Path(path).open('rb') as stream: raw = stream.read(maximum+1)
        require(len(raw) <= maximum, 'Bounded complete plain source record')
        return json.loads(raw)
    def sorted_words(path, count):
        raw = Path(path).read_bytes()
        values = [v[0] for v in struct.iter_unpack('<Q', raw)]
        require(len(values) == count and values == sorted(set(values)) and (not values or values[0] > 0), 'Exact complete closure union')
        return set(values)
    def decisions(path):
        raw = Path(path).read_bytes(); require(len(raw) <= 1600000 and len(raw) % 16 == 0, 'Bounded resolution decisions')
        rows = list(struct.iter_unpack('<QII', raw))
        require(all(r[1] in (0, 2, 3) and (i == 0 or rows[i-1][0] < r[0]) for i, r in enumerate(rows)), 'Complete sorted resolution statuses')
        return {identity: status for identity, status, _ in rows}
    try:
        require(plan['inactiveFromPolicy'] == INACTIVE_FROM_POLICY, 'Exact fixed-profile mandatory inactive-FROM policy')
        cgroup = Path('/sys/fs/cgroup')
        require((cgroup/'memory.max').read_text().strip() == str(4*1024**3) and (cgroup/'memory.swap.max').read_text().strip() == '0', 'Conditional facts memory/swap')
        verify_worker_inputs({'workerFiles': {dest: plan['inputs'][name] for name, dest in plan['mounts'].items()}})
        before = {dest: Path(dest).stat() for dest in plan['mounts'].values()}
        artifact = ('/artifacts/car-entry.so', plan['artifact']['sha256'])
        if plan['operation'] == 'controls':
            import importlib
            import unittest
            import coarse_osm_car_entry_native_v1_test as entry_tests
            import coarse_osm_car_packed_native_v1_test as packed_tests
            entry_tests.configure_native(*artifact); packed_tests.ARTIFACT = artifact
            names = ['coarse_osm_conditional_node_facts_v1_test', 'coarse_osm_entry_graph_audit_v1_test',
                     'coarse_osm_car_entry_native_v1_test', 'coarse_osm_fact_view_v1_test',
                     'coarse_osm_conditional_entry_baseline_v1_test', 'coarse_osm_conditional_entry_preservation_v1_test',
                     'coarse_osm_car_packed_native_v1_test', 'coarse_osm_passable_node_overlay_v1_test',
                     'coarse_osm_car_passable_barriers_v1_test', 'coarse_osm_conditional_node_ports_v1_test', 'coarse_osm_inactive_conditional_turns_v1_test', 'coarse_osm_conditional_only_node_v1_test', 'coarse_osm_conditional_only_ports_v1_test', 'coarse_osm_conditional_only_overlay_v1_test', 'coarse_osm_conditional_only_local_v1_test', 'coarse_osm_conditional_only_effects_v1_test', 'coarse_osm_native_flag_order_v1_test']
            require(not Path('/facts').exists(), 'Conditional facts controls are synthetic only')
            suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(n)) for n in names)
            tested = unittest.TextTestRunner(verbosity=2).run(suite)
            result = dict(tests=tested.testsRun, successful=tested.wasSuccessful(), failures=len(tested.failures), errors=len(tested.errors), skips=len(tested.skipped))
            require(result == dict(tests=122, successful=True, failures=0, errors=0, skips=0), 'Complete actual Linux fact/compiler controls')
            save(root, 'report.json', {'status': 'conditional_only_fact_compiler_controls_passed', 'controls': result, 'sourcePbfReads': 0, 'routingQueries': 0})
            return 0
        captured = plan['operation'] == 'capture'
        require(plan['operation'] in ('capture', 'run'), 'Conditional facts data operation')
        expected = dict(ids=143560, anchors=46881, ways=28995, arcs=79148) if captured else dict(ids=42993567, anchors=5731903, ways=4227238, arcs=9882872)
        require(plan['sourceCounts'] == expected, 'Complete source dimensions')
        metadata = unpack_gzip('/inputs/candidate-metadata.json.gz', plan['metadataArtifact'])['candidates']
        port_body = unpack_gzip('/inputs/source-port-descriptors.json.gz', plan['portsArtifact'])
        require(len(metadata) == len(port_body['rows']) == 7480, 'Every frozen metadata/physical descriptor retained')
        with Path('/inputs/raw-relations.jsonl').open('rb') as stream:
            elements = []
            while line := stream.readline(2097153):
                require(len(line) <= 2097152 and line.endswith(b'\n'), 'Bounded original relation line')
                elements.append(json.loads(line))
                require(len(elements) <= (819 if captured else 70376), 'Original unsupported relation count cap')
        require(len(elements) == (819 if captured else 70376), 'Every current local unsupported relation present')
        old_closed = sorted_words('/inputs/current-closures.bin', 506 if captured else 29657)
        single, multi = decisions('/inputs/single-decisions.bin'), decisions('/inputs/multi-decisions.bin')
        result = relation_overlay(elements, single, multi, old_closed, metadata, port_body['rows'])
        current_closed = sorted_words('/inputs/profile-current-closures.bin', 154 if captured else 16968)
        require(result['closed'] == current_closed, 'Complete existing source-local closure baseline')
        only_metadata = plain_json('/inputs/only-metadata.json', 16777216)['candidates']
        only_ports = plain_json('/inputs/only-source-ports.json', 33554432)
        require(len(only_metadata) == len(only_ports['rows']) == 158, 'Every global mandatory certificate retained')
        local = local_candidates(elements, single, multi, only_metadata, only_ports['rows'])
        if not captured: require(not local['outside'], 'Complete national mandatory source corpus')
        prior_local = set(result['added']) | result['inactiveRelations']
        require(len(prior_local) == result['convertedRelations'] == (209 if captured else 7480), 'Every existing local conversion retains')
        entry_pairs = list(struct.iter_unpack('<II', Path('/inputs/entry-pairs-pre.u32').read_bytes()))
        only_result = only_overlay(local['closingRelations'], prior_local, current_closed, local['metadata'], local['ports'], entry_pairs, expected['arcs'])
        combined_pairs = b''.join(struct.pack('<II', *pair) for pair in only_result['entryPairs'])
        (root/'entry-pairs-pre.u32').write_bytes(combined_pairs)
        new_closed = only_result['closed']
        require(result['convertedRelations'] > 0 and (captured or result['sourceSupportedOutsideLocalMetadata'] == 0), 'Complete supported local conversions')
        old_turns = Path('/facts/input/cost-facts/turns-0000.bin').read_bytes()
        require(len(old_turns) == (4078 if captured else 409178)*TURN.size, 'Complete old typed turn source')
        new_turns = merge_turns(old_turns, result['added'])
        require(len(new_turns) <= 16777216, 'Derived turn fact chunk bound')
        turn_proof = audit_turns(old_turns, new_turns, result['added'])
        require(new_turns == Path('/inputs/profile-current-turns.bin').read_bytes(), 'Every current typed turn byte retained')
        opened = []
        try:
            fields = {}
            for name, shape in [('ids', '<Q'), ('anchors', '<I'), ('ways', '<QddII'), ('arcs', '<IIIIIb3sQ')]:
                field = Rows('/facts/input', plan['sourceRoster'], name, shape, check)
                opened.append(field); fields[name] = field
                require(len(field) == expected[name], 'Complete source field count')
            effect_proof = audit_effects(fields, metadata, port_body, check)
            only_rules = []
            for row in only_metadata:
                rule = classify_only(row['source'])['rule']
                require(rule is not None and {k: str(v) if type(v) is int else v for k,v in asdict(rule).items()} == row['derived'], 'Every original mandatory source rule retains')
                only_rules.append(rule)
            only_port_proof = audit_only_ports(fields, only_rules, only_ports, check)
            require(captured or result['inactiveOutsideLocalMetadata'] == 0, 'All national inactive candidates are local source records')
            mapping = unpack_gzip('/inputs/blocked-nodes.json.gz', plan['mappingArtifact'])
            evidence = unpack_gzip('/inputs/node-evidence.json.gz', plan['nodeEvidenceArtifact'])['nodeEvidence']
            original_flags = Path('/facts/input/cost-facts/flags-0000.bin').read_bytes()
            require(len(original_flags) == expected['anchors'], 'All native flag bytes present')
            flags, flag_proof = native_passable_flags(original_flags, mapping, evidence, fields['ids'], fields['anchors'])
            current_flags = Path('/inputs/profile-current-flags.bin').read_bytes()
            require(len(current_flags) == expected['anchors'] and all(v < 8 for v in current_flags), 'Exact current source-qualified flag profile')
            if captured:
                require(current_flags == flags, 'Captured current flags exactly reproduce')
                preserved_incomplete = 0
                flag_order_proof = None
            else:
                incomplete = plain_json('/inputs/current-incomplete-flags-report.json', 1048576)
                require(incomplete['status'] == 'complete_source_qualified_incomplete_node_flags_independently_audited' and incomplete['openedVertices'] == 1488 and incomplete['everyIndependentUnconvertedRestrictionContributorRetained'], 'Existing incomplete-node source qualification')
                import sys
                from array import array
                from coarse_osm_native_flag_order_v1 import rebase_flags
                raw_permutation = Path('/inputs/current-spatial-to-native.u32').read_bytes()
                require(sys.byteorder == 'little' and len(raw_permutation) == 4*expected['anchors'], 'Complete spatial-to-native flag permutation bytes')
                permutation = array('I'); permutation.frombytes(raw_permutation); del raw_permutation
                qualified_nodes = [v[0] for v in struct.iter_unpack('<Q', Path('/inputs/current-opened-node-ids.u64').read_bytes())]
                require(len(qualified_nodes) == 1488, 'Every prior qualified opened source node retained')
                require(flags == Path('/inputs/profile-current-native-flags.bin').read_bytes(), 'Every prior native passable flag reproduces before permutation')
                current_flags, flag_order_proof = rebase_flags(flags, Path('/inputs/current-original-spatial-flags.u8').read_bytes(),
                    current_flags, permutation, fields['ids'], fields['anchors'], qualified_nodes)
                preserved_incomplete = flag_order_proof['sourceQualifiedOpenedNodeIdsPreserved']
                require(preserved_incomplete == 1488, 'All prior incomplete-node openings preserved')
                del permutation
            flags = current_flags
            mandatory_via_flags = Counter(str(flags[row['viaAnchor']]) for row in only_ports['rows']
                                          if row['status'] == 'source-ports-supported')
            original_closed = sorted_words('/facts/input/cost-facts/closures-0000.bin', 1711 if captured else 149699)
            current_mask = bytearray(fields['ways'][i][0] in old_closed for i in range(expected['ways']))
            prior_mask = bytearray(fields['ways'][i][0] in current_closed for i in range(expected['ways']))
            new_mask = bytearray(fields['ways'][i][0] in new_closed for i in range(expected['ways']))
            original_mask = bytearray(fields['ways'][i][0] in original_closed for i in range(expected['ways']))
            counts = [0, 0, 0, 0]; seen = 0
            for part in fields['arcs'].parts:
                for row in fields['arcs'].row.iter_unpack(part):
                    way = row[2]; require(way < expected['ways'], 'Every retained arc references a source way')
                    counts[0] += not original_mask[way]; counts[1] += not current_mask[way]; counts[2] += not prior_mask[way]; counts[3] += not new_mask[way]; seen += 1
                check()
            require(seen == expected['arcs'] and counts[1] == (77459 if captured else 9826630) and counts[2] == (78757 if captured else 9853365) and counts[3] >= counts[2], 'Exact original/preconditional/current/new retained pre-arc counts')
            for field in opened: field.verify_unchanged()
        finally:
            for field in reversed(opened): field.close()
        facts = root/'cost-facts'; facts.mkdir()
        closures = b''.join(struct.pack('<Q', identity) for identity in sorted(new_closed))
        for name, raw in [('turns', new_turns), ('closures', closures), ('flags', flags)]:
            with (facts/(name+'-0000.bin')).open('xb') as stream: stream.write(raw)
        assets = {'cost-facts/'+p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in facts.iterdir()}
        require((facts/'turns-0000.bin').read_bytes() == new_turns and (facts/'closures-0000.bin').read_bytes() == closures and (facts/'flags-0000.bin').read_bytes() == flags, 'Every derived fact byte reopens exactly')
        compiler = None
        if captured:
            from coarse_osm_car_packed_native_v1 import NativePacked
            from coarse_osm_car_entry_native_v1 import NativeEntries
            from coarse_osm_entry_graph_audit_v1 import audit
            assembled = root/'compiler-view'; assembled.mkdir()
            for path in Path('/facts/input/cost-facts').iterdir():
                if not path.name.startswith(('turns-', 'closures-', 'flags-')):
                    shutil.copyfile(path, assembled/path.name)
                    require(sha(assembled/path.name) == sha(path), 'Captured compiler unchanged physical source field')
            for path in facts.iterdir(): shutil.copyfile(path, assembled/path.name)
            routing = root/'base-routing'; routing.mkdir()
            dimensions = [expected['ids'], expected['anchors'], expected['ways'], expected['arcs'], counts[3], len(new_turns)//TURN.size]
            native = NativePacked(*artifact).encode(assembled, routing, dimensions)
            final = root/'entry-forbidden.u24'
            augmentation = NativeEntries(*artifact).augment('/facts/input/cost-facts', assembled/'closures-0000.bin', str(root/'entry-pairs-pre.u32'), routing, final, [expected['ways'], expected['anchors'], expected['arcs'], counts[3]])
            proof = audit('/facts/input/cost-facts', assembled, routing, str(root/'entry-pairs-pre.u32'), final, dimensions, augmentation, baseline_post=counts[0], check=check)
            compiler = {'dimensions': dimensions, 'nativeResult': native, 'augmentationCounts': augmentation, 'independentCompleteSourceAndEntryAudit': proof, 'physicalFieldsCopiedExactly': True}
        for name, stat in before.items():
            after = Path(name).stat()
            require((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'All facts and source evidence unchanged')
        assets['entry-pairs-pre.u32'] = {'bytes': len(combined_pairs), 'sha256': hashlib.sha256(combined_pairs).hexdigest()}
        if not captured:
            require(closures == Path('/inputs/expected-national-closures.bin').read_bytes() and combined_pairs == Path('/inputs/expected-national-entry-pairs.u32').read_bytes(), 'Every national source-fact delta byte matches the independently qualified overlay')
        save(root, 'artifacts.json', assets)
        save(root, 'report.json', {
            'status': 'conditional_only_captured_facts_and_native_compiler_audited' if captured else 'conditional_only_national_facts_and_retention_independently_audited',
            'sourceCounts': expected, 'allOriginalUnsupportedRelations': len(elements),
            'previousConvertedRelations': result['convertedRelations'], 'previousSourcePortAudit': effect_proof,
            'mandatoryMetadata': 158, 'localMandatoryMetadata': len(local['metadata']), 'outsideLocalMetadata': local['outside'],
            'convertedOnlyRelations': len(only_result['convertedRelations']), 'representedOnlyRelations': len(only_result['representedRelations']),
            'inactiveFromOnlyRelations': len(only_result['inactiveRelations']), 'localFallbackRelations': len(only_result['fallbackRelations']),
            'mandatorySourcePortAudit': only_port_proof, 'currentClosedWays': len(current_closed), 'newClosedWays': len(new_closed),
            'newUnclosedWayIds': only_result['openedWayIds'], 'newMandatoryPairs': len(only_result['mandatoryPairs']),
            'newEntryPairs': len(only_result['newEntryPairs']), 'combinedEntryPairs': len(only_result['entryPairs']),
            'allIndependentContributorsRetained': True, 'allOldAllowedTransitionsPreserved': True,
            'everyCurrentTypedTurnByteExact': True, 'everyCurrentFlagRetainedInNativeOrder': True, 'currentFlagOrderAudit': flag_order_proof,
            'certifiedViaNativeNodeFlagCountsPerRule': dict(mandatory_via_flags),
            'previousPassableNodeAudit': flag_proof, 'priorIncompleteNodeOpeningsPreserved': preserved_incomplete,
            'originalConservativePostArcs': counts[0], 'preconditionalPostArcs': counts[1],
            'currentPostArcs': counts[2], 'newFinalPostArcs': counts[3],
            'allPreArcRetentionMappingsCounted': seen, 'turnAudit': turn_proof, 'compiler': compiler,
            'sourcePreArcIdsRetained': True, 'postArcIdsReusable': False, 'sourcePbfReads': 0,
            'sourceConstructorExecutions': 0, 'routingQueries': 0, 'providerRequests': 0, 'applicationDbReads': 0,
            'newTimingOrAccuracyQualified': False, 'appActivated': False,
            'workerSecondsIncludingBindingsSourceReplaysNativeAndIndependentAudits': time.monotonic()-began,
            'scope': plan['scope']})
        return 0
    except BaseException as error:
        save(root, 'failure.json', {'status': 'conditional_node_facts_stopped', 'error': repr(error), 'workerSeconds': time.monotonic()-began})
        raise
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
    require(operation in ('controls', 'capture', 'run') and plan['output'] == PREFIX+operation+'-v1', 'Conditional node facts exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan.get('additionalActiveReservationBytes', 0)+268435456+268435456 < 72*1024**3, 'Conditional node facts aggregate reservation')
    require(set(plan['mounts']) == set(plan['inputs']), 'Conditional node facts complete input bindings')
    if operation != 'controls':
        required={'/facts/input/'+name for name in plan['sourceRoster']}
        actual={destination for destination in plan['mounts'].values() if destination.startswith('/facts/')}
        require(required==actual, 'Conditional facts complete field mounts')
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/', '/paths/')), 'Conditional node facts input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Conditional node facts input SHA/no PBF')
    require(operation == 'controls' or plan['admission'] == {'tests': 122, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Conditional node facts qualification before facts')
    if operation=='run':require(plan['capturedAdmission']=={'completeCapturedCompiler':True,'independentAllSourceAudit':True,'allOtherContributorsRetained':True,'everyCurrentTurnAndNativeFlagExact':True,'allMandatoryMetadataRetained':158},'Complete captured port qualification before national facts')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-conditional-only-facts-'+owner[:12]
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
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_conditional_only_facts_v2.py', '/inputs/recipe.json', pin, '--worker']
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
                require(time.monotonic()-began < 1020 and owned_usage(root)['conservativeAllocatedBytes'] <= 268435456, 'Conditional node facts host deadline/owned cap')
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
