"""Isolated saved-water polygon pipeline; never mount the source PBF."""
import argparse
from array import array
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import uuid

from coarse_timing_input import require,start_watchdog

IMAGE='sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
PREFIX='data/coarse-quality/us-osm-water-polygons-'
MEMORY=4294967296
TMP=268435456
OWNED=2147483648


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save(root,name,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();require(len(raw)<=1048576,'Water polygon small-record cap')
    with (root/name).open('xb') as stream:stream.write(raw)


def worker(plan):
    root=Path('/work');operation=plan['operation'];began=time.monotonic();limit=180 if operation=='controls' else 2700
    timer=start_watchdog(limit);last=-1.;last_log=0.
    def check():
        nonlocal last,last_log
        elapsed=time.monotonic()-began;require(elapsed<limit,'Water polygon worker deadline')
        if elapsed-last>=1:last=elapsed;require(owned_usage(root)['conservativeAllocatedBytes']<=OWNED,'Water polygon owned cap')
        if elapsed-last_log>=15:last_log=elapsed;print(json.dumps({'workerSeconds':elapsed,'phase':'saved-coordinate-way-and-polygon-pipeline'}),flush=True)
    try:
        from coarse_osm_full_monitor_v1 import owned_usage
        from coarse_osm_data import verify_worker_inputs
        c=Path('/sys/fs/cgroup');quota,period=map(int,(c/'cpu.max').read_text().split())
        require(int((c/'memory.max').read_text())==MEMORY and int((c/'memory.swap.max').read_text())==0 and quota==2*period and int((c/'pids.max').read_text())==64,'Water polygon hard resources')
        tmp=os.statvfs('/tmp')
        require(tmp.f_blocks*tmp.f_frsize==TMP and resource.getrlimit(resource.RLIMIT_FSIZE)==(67108864,67108864),'Water polygon tmp/file limits')
        verify_worker_inputs({'workerFiles':{destination:plan['inputs'][name] for name,destination in plan['mounts'].items()}})
        require(not Path('/source.pbf').exists() ,'Water polygon no PBF or coordinate input')
        from coarse_osm_water_catalog_v1 import WaterCatalog
        artifact=('/inputs/catalog-artifact.so',plan['catalogArtifact']['sha256'])
        coordinate_artifact=('/inputs/coordinate-artifact.so',plan['coordinateArtifact']['sha256'])
        if operation=='controls':
            import unittest,importlib
            require(not Path('/inputs/ways').exists() and not Path('/inputs/coordinates').exists() and not Path('/inputs/node-index').exists(),'Water polygon controls no country data')
            suite=unittest.TestSuite()
            for name in ('coarse_osm_water_area_v1_test','coarse_osm_water_ring_topology_v1_test','coarse_osm_water_catalog_v1_test','prepare_osm_water_catalog_v1_test','coarse_osm_water_reference_store_v1_test'):
                module=importlib.import_module(name);module.ARTIFACT=artifact;module.COORDINATE_ARTIFACT=coordinate_artifact
                suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
            result=unittest.TextTestRunner(verbosity=2).run(suite)
            controls={'tests':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)}
            save(root,'controls.json',controls)
            require(controls=={'tests':43,'successful':True,'failures':0,'errors':0,'skips':0},'Water polygon pipeline controls failed')
            save(root,'report.json',{'status':'water_polygon_saved_data_pipeline_controls_passed','controls':controls,'nationalDataMounted':False,'sourcePbfReads':0,'maskOrModelChanged':False})
            return 0
        require(operation=='run','Water polygon operation')
        from prepare_osm_water_catalog_v1 import load_catalog
        from assemble_osm_water_polygons_v1 import assemble
        reference=json.loads(Path('/inputs/water-references-report.json').read_bytes())
        coordinates=json.loads(Path('/inputs/water-coordinate-report.json').read_bytes())
        endpoints=json.loads(Path('/inputs/water-endpoint-report.json').read_bytes())
        require(reference['status']=='national_water_exact_references_and_unique_ids_audited' and coordinates['status']=='national_water_exact_coordinate_closure_and_source_shadow_audited' and endpoints['status']=='national_water_endpoint_and_relation_chain_diagnosis_complete','Water polygon complete source evidence')
        ids=array('Q');raw=Path('/inputs/member-way-ids.u64').read_bytes()
        require(sys.byteorder=='little' and len(raw)==3666040,'Water polygon member-ID platform/count');ids.frombytes(raw)
        catalog=WaterCatalog(*artifact)
        try:
            loaded,selected,counts=load_catalog(catalog,coordinate_artifact,'/inputs/reference-store',reference,'/inputs/coordinates',coordinates,check)
            require((loaded['statistics']['nodes'],loaded['statistics']['ways'],loaded['statistics']['references'],loaded['statistics']['taggedWays'],loaded['statistics']['backingBytes'])==(101738006,2829193,104806243,2374342,2514354329),'Water polygon complete source table counts/backing')
            save(root,'catalog-audit.json',loaded)
            result=assemble(root,catalog,selected,counts,ids,'/inputs/endpoints',endpoints,check)
            require(sum(result['statusCounts']['1'].values())==2374342 and sum(result['statusCounts']['2'].values())==68734 and sum(result['statusCounts']['3'].values())==17,'Water polygon all source features/ambiguities retained')
        finally:catalog.release()
        require(catalog.stats()['backingBytes']==0,'Water polygon released native table backing')
        check();save(root,'report.json',{'status':'national_saved_water_polygon_feasibility_and_source_replay_complete','catalog':loaded,'polygons':result,
                                       'producerNativeTablesReleased':True,'sourcePbfReads':0,'maskOrModelChanged':False,'appActivated':False,
                                       'workerSecondsIncludingInputBindingsCatalogAuditGeometryAndOutputReplay':time.monotonic()-began,
                                       'scope':'Complete cached saved water-feature geometry feasibility. Source gaps/ambiguities/invalid objects explicit, no geographic completeness/shoreline accuracy or mask/routing/app admission. No source PBF scan or provider/DB operation.'})
        return 0
    except BaseException as error:
        save(root,'failure.json',{'status':'water_polygon_diagnosis_stopped','error':repr(error),'workerSeconds':time.monotonic()-began});return 2
    finally:
        c=Path('/sys/fs/cgroup')
        save(root,'metrics.json',{name:(c/name).read_text().strip() for name in ('memory.current','memory.peak','memory.events','cpu.stat','memory.max','memory.swap.max')})
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


def driver(recipe,pin):
    from coarse_osm_full_monitor_v1 import owned_usage
    from prepare_osm_native_lock_v1 import cleanup_owned,settle_error
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==pin,'Water polygon recipe binding')
    plan=json.loads(recipe.read_bytes());operation=plan['operation']
    require(operation in ('controls','run') and plan['output']==PREFIX+operation+'-v1','Water polygon exact namespace')
    require(plan['retainedBytes']==72*1024**3 and plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+OWNED+TMP<plan['retainedBytes'],'Water polygon aggregate reservation')
    require(set(plan['inputs'])==set(plan['mounts']),'Water polygon exact input roster')
    for name,destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/','/inputs/','/tools/','/reference/')) and not name.endswith(('.pbf','/001.bin')),'Water polygon readonly scope/no PBF')
        require(sha(repo/name)==plan['inputs'][name],'Water polygon input binding')
    require(operation=='controls' or plan['admission']=={'tests':43,'successful':True,'failures':0,'errors':0,'skips':0},'Water polygon qualified controls')
    root=repo/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner=uuid.uuid4().hex;name='geo-planner-water-polygons-'+owner[:12];save(root,'owner.json',{'name':name,'label':owner,'image':IMAGE})
    began=time.monotonic();identity=child=None;code=2
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=15)
    try:
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--tmpfs','/tmp:rw,size=256m','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864','--env','PYTHONPATH=/code:/tools/site:/reference','--env','LD_LIBRARY_PATH=/tools/runtime']
        for source,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_water_polygons_v1.py','/inputs/recipe.json',pin,'--worker']
        created=call(args);require(created.returncode==0,created.stderr);identity=created.stdout.strip();require(len(identity)==64,'Water polygon owned identity')
        observed=json.loads(call(['docker','inspect',identity]).stdout)[0];host=observed['HostConfig']
        require(observed['Image']==IMAGE and host['NetworkMode']=='none' and host['Memory']==host['MemorySwap']==MEMORY and host['NanoCpus']==2000000000 and host['PidsLimit']==64 and host['ReadonlyRootfs'] and host['Tmpfs']=={'/tmp':'rw,size=256m'},'Water polygon observed isolation')
        require(not host.get('CapAdd') and {c.removeprefix('CAP_') for c in host['CapDrop']}=={'ALL'} and 'no-new-privileges' in host['SecurityOpt'],'Water polygon capabilities')
        require({u['Name']:(u['Soft'],u['Hard']) for u in host['Ulimits']}=={'core':(0,0),'fsize':(67108864,67108864)},'Water polygon observed file/core limits')
        require(all(not m['RW'] for m in observed['Mounts'] if m['Destination']!='/work'),'Water polygon readonly inputs')
        save(root,'container-initial.json',observed)
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began<(240 if operation=='controls' else 3000) and owned_usage(root)['conservativeAllocatedBytes']<=OWNED,'Water polygon host deadline/owned cap');time.sleep(.5)
        observed=json.loads(call(['docker','inspect',identity]).stdout)[0];save(root,'container-result.json',{'State':observed['State'],'clientExitCode':child.returncode})
        require(child.returncode==observed['State']['ExitCode']==0 and not observed['State']['OOMKilled'],'Water polygon worker exit/OOM');code=0
    except BaseException as error:save(root,'driver-failure.json',{'error':repr(error),'hostSeconds':time.monotonic()-began})
    finally:
        if child and child.poll() is None:child.kill();child.wait(timeout=5)
        if not (root/'container-result.json').exists():settle_error(call,identity,name,owner,root,child.returncode if child else None)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    save(root,'run-summary.json',{'exitCode':code,'hostSecondsIncludingCleanup':time.monotonic()-began,'sourcePbfReads':0})
    return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('pin');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    require(sha(args.recipe)==args.pin,'Water polygon recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe,args.pin))
