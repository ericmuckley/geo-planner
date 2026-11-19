"""Qualify every incoming/all-outgoing/to-port for frozen mandatory-turn metadata."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from coarse_timing_input import require, start_watchdog

IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
PREFIX = 'data/coarse-quality/us-osm-conditional-only-ports-'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(root, name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 1048576, 'Only-turn source ports record cap')
    with (root/name).open('xb') as stream:
        stream.write(raw)


def worker(plan):
    from collections import Counter
    from dataclasses import asdict
    import unittest
    from coarse_osm_country_screen_v1 import owned_usage,resource_metrics
    from coarse_osm_data import verify_worker_inputs
    root=Path('/work');began=time.monotonic();timer=start_watchdog(900)
    def check():
        require(time.monotonic()-began<900,'Only-turn ports worker deadline')
        require(owned_usage(root)['conservativeAllocatedBytes']<=67108864,'Only-turn ports owned cap')
    try:
        cgroup=Path('/sys/fs/cgroup')
        require((cgroup/'memory.max').read_text().strip()==str(4*1024**3) and (cgroup/'memory.swap.max').read_text().strip()=='0','Only-turn ports memory/swap')
        verify_worker_inputs({'workerFiles':{dest:plan['inputs'][name] for name,dest in plan['mounts'].items()}})
        before={name:Path(name).stat() for name in plan['mounts'].values()}
        if plan['operation']=='controls':
            import coarse_osm_conditional_node_turns_v2_test as policy_tests
            import coarse_osm_conditional_node_inventory_v1_test as contributor_tests
            import coarse_osm_conditional_node_ports_v1_test as port_tests
            import coarse_osm_conditional_fact_io_v1_test as io_tests
            import coarse_osm_conditional_only_node_v1_test as only_tests
            import coarse_osm_conditional_only_ports_v1_test as only_port_tests
            require(not Path('/facts').exists() and not Path('/inputs/candidate-metadata.json').exists(),'Port controls synthetic only')
            tested=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (policy_tests,contributor_tests,port_tests,io_tests,only_tests,only_port_tests)))
            controls=dict(tests=tested.testsRun,successful=tested.wasSuccessful(),failures=len(tested.failures),errors=len(tested.errors),skips=len(tested.skipped))
            require(controls==dict(tests=45,successful=True,failures=0,errors=0,skips=0),'Complete conditional port actual Linux controls')
            save(root,'report.json',{'status':'conditional_only_source_ports_controls_passed','controls':controls,'sourcePbfReads':0,'routingQueries':0})
            return 0
        from coarse_osm_conditional_fact_io_v1 import Rows
        from coarse_osm_conditional_only_ports_v1 import qualify,audit
        from coarse_osm_conditional_only_node_v1 import classify
        expected={'ids':143560,'anchors':46881,'ways':28995,'arcs':79148} if plan['operation']=='capture' else {'ids':42993567,'anchors':5731903,'ways':4227238,'arcs':9882872}
        require(plan['operation'] in ('capture','run') and plan['sourceCounts']==expected,'Complete conditional port source dimensions')
        with Path('/inputs/candidate-metadata.json').open('rb') as stream:raw=stream.read(16777217)
        require(len(raw)==plan['metadataArtifact']['bytes']<=16777216 and hashlib.sha256(raw).hexdigest()==plan['metadataArtifact']['sha256'],'Complete bound candidate metadata')
        candidates=json.loads(raw)['candidates'];rules=[]
        require(len(candidates)==158,'All metadata candidates retained')
        for row in candidates:
            result=classify(row['source']);rule=result['rule'];require(rule is not None,'Every original metadata candidate still qualifies')
            require({k:(str(v) if type(v) is int else v) for k,v in asdict(rule).items()}==row['derived'],'Every original and derived native ID agrees')
            rules.append(rule)
        opened=[]
        try:
            fields={}
            for name,format in [('ids','<Q'),('anchors','<I'),('ways','<QddII'),('arcs','<IIIIIb3sQ')]:
                field=Rows('/facts/input',plan['sourceRoster'],name,format,check);opened.append(field);fields[name]=field
                require(len(field)==expected[name],'Source port complete field count: '+name)
            phase=time.monotonic();result=qualify(fields,rules,check)
            require(result['sourceGeometryReferenceCount']==plan['sourceGeometryReferences'],'Complete source geometry offset endpoint')
            raw=(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
            require(len(raw)<=33554432,'Complete source port output cap')
            with (root/'source-port-descriptors.json').open('xb') as stream:stream.write(raw)
            restored=json.loads((root/'source-port-descriptors.json').read_bytes())
            require(restored==result,'All source port descriptor bytes reopen exactly')
            proof=audit(fields,rules,restored,check)
            for field in opened:field.verify_unchanged()
        finally:
            for field in reversed(opened):field.close()
        for name,stat in before.items():
            after=Path(name).stat()
            require((stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'All port inputs unchanged')
        save(root,'report.json',{'status':'complete_typed_conditional_only_source_ports_independently_audited','operation':plan['operation'],
            'sourceCounts':expected,'metadataCandidates':158,'statusCounts':dict(Counter(row['status'] for row in result['rows'])),
            'sourceSupportedRules':proof['supportedRules'],'retainedFallbackRules':158-proof['supportedRules'],
            **{k:v for k,v in result.items() if k!='rows'},'independentAudit':proof,
            'artifact':{'file':'source-port-descriptors.json','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},
            'sourcePortConstructionAndIndependentLookupJoinSeconds':time.monotonic()-phase,
            'workerSecondsIncludingBindingsAllSourceScansAuditsAndPreservation':time.monotonic()-began,
            'sourcePbfReads':0,'sourceConstructorExecutions':0,'routingQueries':0,'providerRequests':0,'applicationDbReads':0,
            'sourcePermissionsOrPricesChanged':False,'appActivated':False,
            'scope':plan['scope']})
        return 0
    except BaseException as error:
        save(root,'failure.json',{'status':'conditional_node_ports_stopped','error':repr(error),'workerSeconds':time.monotonic()-began});raise
    finally:
        save(root,'metrics.json',resource_metrics())
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


def driver(recipe, pin):
    from coarse_osm_full_monitor_v1 import owned_usage
    from prepare_osm_native_lock_v1 import cleanup_owned, settle_error
    from run_osm_country_screen_v1 import isolation
    repo = Path(__file__).resolve().parents[1]
    recipe = Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe) == pin, 'Only-turn source ports recipe binding')
    plan = json.loads(recipe.read_bytes())
    operation = plan['operation']
    require(operation in ('controls', 'capture', 'run') and plan['output'] == PREFIX+operation+'-v1', 'Only-turn source ports exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+plan.get('additionalActiveReservationBytes', 0)+67108864+268435456 < 72*1024**3, 'Only-turn source ports aggregate reservation')
    require(set(plan['mounts']) == set(plan['inputs']), 'Only-turn source ports complete input bindings')
    if operation != 'controls':
        required={'/facts/input/'+name for name in plan['sourceRoster']}
        actual={destination for destination in plan['mounts'].values() if destination.startswith('/facts/')}
        require(required==actual and all(name.startswith(('cost-facts/ids-','cost-facts/anchors-','cost-facts/ways-','cost-facts/arcs-')) for name in plan['sourceRoster']), 'Source-gap complete field mounts')
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/', '/paths/')), 'Only-turn source ports input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Only-turn source ports input SHA/no PBF')
    require(operation == 'controls' or plan['admission'] == {'tests': 45, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}, 'Only-turn source ports qualification before facts')
    if operation=='run':require(plan['capturedAdmission']=={'allMetadataCandidatesReplayed':158,'independentPortAuditPassed':True,'completeCapturedTypedSource':True},'Complete captured port qualification before national facts')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-conditional-only-ports-'+owner[:12]
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
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_conditional_only_ports_v1.py', '/inputs/recipe.json', pin, '--worker']
        created = call(command)
        require(created.returncode == 0, created.stderr)
        identity = created.stdout.strip()
        require(len(identity) == 64, 'Only-turn source ports exact owned ID')
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        isolation(observed, 'controls')
        save(root, 'container-initial.json', observed)
        with (root/'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began < 1020 and owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Only-turn source ports host deadline/owned cap')
                time.sleep(.5)
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        save(root, 'container-result.json', {'State': observed['State'], 'clientExitCode': child.returncode})
        require(child.returncode == observed['State']['ExitCode'] == 0 and not observed['State']['OOMKilled'], 'Only-turn source ports worker exit/OOM')
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
    require(sha(args.recipe) == args.pin, 'Only-turn source ports recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe, args.pin))
