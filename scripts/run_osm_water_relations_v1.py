"""Separately qualified lossless water relation/member-ID stage; no geometry yet."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from coarse_timing_input import require, start_watchdog
from run_osm_topology_v1 import SOURCE, SCAN

IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
PREFIX = 'data/coarse-quality/us-osm-water-relations-'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def save(root,name,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    require(len(raw)<=1048576,'Water relation small-record cap')
    with (root/name).open('xb') as stream:stream.write(raw)


def worker(plan):
    from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
    from coarse_osm_data import verify_worker_inputs
    from coarse_osm_water_relations_v1 import water_relations, source_guard
    from coarse_osm_water_relation_store_v1 import RelationStore, audit
    root=Path('/work');operation=plan['operation'];began=time.monotonic()
    limit=120 if operation=='controls' else 2700
    timer=start_watchdog(limit)
    last_check=-1.
    def check():
        nonlocal last_check
        elapsed=time.monotonic()-began
        require(elapsed<limit,'Water relation deadline')
        if elapsed-last_check>=1:
            last_check=elapsed
            require(owned_usage(root)['conservativeAllocatedBytes']<=67108864,'Water relation owned cap')
    def guard(label):
        record=source_guard('/source.pbf',SOURCE,check)
        save(root,'source-'+label+'.json',record)
        print(json.dumps({'sourceGuard':label,'seconds':record['seconds']}),flush=True)
        return record['stat']
    try:
        c=Path('/sys/fs/cgroup')
        require((c/'memory.max').read_text().strip()==str(4*1024**3) and (c/'memory.swap.max').read_text().strip()=='0','Water relation memory/swap')
        quota,period=map(int,(c/'cpu.max').read_text().split())
        require(quota==2*period and int((c/'pids.max').read_text())==64,'Water relation CPU/PIDs')
        verify_worker_inputs({'workerFiles':{destination:plan['inputs'][name] for name,destination in plan['mounts'].items()}})
        if operation=='controls':
            import unittest
            require(not Path('/source.pbf').exists(),'Water relation controls must not mount national source')
            suite=unittest.defaultTestLoader.loadTestsFromNames(['coarse_osm_relation_tail_v1_test','coarse_osm_water_relations_v1_test'])
            result=unittest.TextTestRunner(verbosity=2).run(suite)
            controls={'tests':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)}
            require(controls=={'tests':26,'successful':True,'failures':0,'errors':0,'skips':0},'Water relation controls failed')
            save(root,'report.json',{'status':'water_relation_controls_passed','controls':controls,'nationalSourceMounted':False})
            return 0
        require(operation=='run','Water relation operation')
        census=json.loads(Path('/inputs/water-census-report.json').read_bytes())
        receipt=json.loads(Path('/inputs/water-census-receipt.json').read_bytes())
        require(census['status']=='complete_national_water_metadata_census_passed' and receipt['nativeEof'] and receipt['semanticSha256']==SOURCE['semanticSha256'],'Water relation completed native source prerequisite')
        before=guard('before')
        with RelationStore(root) as store:
            scan=water_relations('/source.pbf',source_bytes=SOURCE['bytes'],state=SOURCE['state'],expected_relations=1624265,consume=store.consume,check=check)
            stored=store.finish()
        water=census['water'];counts=stored['counts']
        mapping={'relations':'waterRelations','wayMembers':'waterWayMembers','nodeMembers':'waterNodeMembers','relationMembers':'waterRelationMembers',
                 'outerWayMembers':'outerWayMembers','innerWayMembers':'innerWayMembers','otherRoleWayMembers':'otherRoleWayMembers',
                 'multipolygons':'multipolygonWaterRelations','otherTypes':'otherTypeWaterRelations','maxMembers':'maximumWaterRelationMembers'}
        require(all(counts[k]==water[v] for k,v in mapping.items()) and scan['waterRecordsSelected']==water['waterRelations'],'Water relation exact independent native census parity')
        audited=audit(root,stored,check)
        require(guard('after')==before,'Water relation pre/post source stat')
        check()
        outputs={name:{'bytes':(root/name).stat().st_size,'sha256':sha(root/name)} for name in ('water-relations.jsonl.gz','member-way-ids.u64')}
        save(root,'report.json',{'status':'national_water_relations_and_member_ids_passed','scan':scan,'stored':stored,'independentAudit':audited,'outputs':outputs,
                               'workerSecondsIncludingBindingsSourceGuardsAudit':time.monotonic()-began,
                               'nativeCensusParity':True,'missingMemberWaysOrNestedRelationsResolved':False,
                               'coordinatesOrGeometryRetained':False,'maskOrModelChanged':False,'routingQueries':0,'providerRequests':0,'appActivated':False})
        return 0
    except BaseException as error:
        save(root,'failure.json',{'status':'water_relations_stopped','error':repr(error),'workerSeconds':time.monotonic()-began})
        raise
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
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe) == pin, 'Water source recipe binding')
    plan = json.loads(recipe.read_bytes())
    operation = plan['operation']
    require(operation in ('controls', 'run') and plan['output'] == PREFIX+operation+'-v1', 'Water source exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+67108864+268435456 < 64*1024**3, 'Water source aggregate reservation')
    require(set(plan['mounts']) == set(plan['inputs']), 'Water source complete input bindings')
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/', '/tools/')), 'Water source input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Water source input SHA/no PBF')
    require(plan['source'] == SOURCE and plan['scanCaps'] == SCAN, 'Water exact original source/scan guards')
    require(operation == 'controls' or plan['relationAdmission'] == {'tests':26,'successful':True,'failures':0,'errors':0,'skips':0} and plan['nativeAdmission'] == {'tests':32,'successful':True,'failures':0,'errors':0,'skips':0} and plan['controllerAdmission'] == {'positivePipeline':True,'wrongSourceRejected':True,'nationalSourceMounted':False}, 'Water source qualification admission')
    if operation == 'run':
        original = repo/SOURCE['path']
        require(original.is_file() and not original.is_symlink() and original.stat().st_size == SOURCE['bytes'], 'Water exact read-only cached source')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-water-relations-'+owner[:12]
    save(root, 'owner.json', {'name': name, 'label': owner, 'image': IMAGE})
    began = time.monotonic()
    identity = child = None
    code = 2
    def call(args):
        return subprocess.run(args, capture_output=True, text=True, timeout=15)
    try:
        command = ['docker', 'create', '--pull=never', '--init', '--name', name, '--label', 'geo-planner.stream-owner='+owner,
                   '--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=4g', '--memory-swap=4g', '--cpus=2', '--pids-limit=64',
                   '--tmpfs', '/tmp:rw,size=256m', '--ulimit', 'core=0:0', '--ulimit', 'fsize=67108864:67108864', '--env', 'PYTHONPATH=/code:/tools/site:/reference', '--env', 'LD_LIBRARY_PATH=/tools/runtime', '--env', 'OSMIUM_MAX_INPUT_QUEUE_SIZE=2', '--env', 'OSMIUM_MAX_OSMDATA_QUEUE_SIZE=2']
        for source, destination in plan['mounts'].items():
            command += ['--mount', f'type=bind,src={repo/source},dst={destination},readonly']
        if operation == 'run':
            command += ['--mount', f'type=bind,src={repo/SOURCE["path"]},dst=/source.pbf,readonly']
        command += ['--mount', f'type=bind,src={root},dst=/work', '--mount', f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly',
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_water_relations_v1.py', '/inputs/recipe.json', pin, '--worker']
        created = call(command)
        require(created.returncode == 0, created.stderr)
        identity = created.stdout.strip()
        require(len(identity) == 64, 'Water source exact owned ID')
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        isolation(observed, 'controls')
        save(root, 'container-initial.json', observed)
        with (root/'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began < (180 if operation=='controls' else 3000) and owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Water source host deadline/owned cap')
                time.sleep(.5)
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        save(root, 'container-result.json', {'State': observed['State'], 'clientExitCode': child.returncode})
        require(child.returncode == observed['State']['ExitCode'] == 0 and not observed['State']['OOMKilled'], 'Water source worker exit/OOM')
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
    require(sha(args.recipe) == args.pin, 'Water source recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe, args.pin))
