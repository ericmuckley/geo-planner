"""Isolated saved-water point evidence scan; no routing or mask policy."""
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
PREFIX='data/coarse-quality/us-osm-water-raster-source-'
MEMORY=1073741824
TMP=67108864
OWNED=67108864


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save(root,name,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();require(len(raw)<=1048576,'Water raster small-record cap')
    with (root/name).open('xb') as stream:stream.write(raw)


def worker(plan):
    root=Path('/work');operation=plan['operation'];began=time.monotonic();limit=120 if operation=='controls' else 1800
    timer=start_watchdog(limit);last=-1.;last_log=0.
    def check():
        nonlocal last,last_log
        elapsed=time.monotonic()-began;require(elapsed<limit,'Water raster worker deadline')
        if elapsed-last>=1:last=elapsed;require(owned_usage(root)['conservativeAllocatedBytes']<=OWNED,'Water raster owned cap')
        if elapsed-last_log>=15:last_log=elapsed;print(json.dumps({'workerSeconds':elapsed,'phase':'complete-source-raster-and-binary-audit'}),flush=True)
    try:
        from coarse_osm_full_monitor_v1 import owned_usage
        from coarse_osm_data import verify_worker_inputs
        c=Path('/sys/fs/cgroup');quota,period=map(int,(c/'cpu.max').read_text().split())
        require(int((c/'memory.max').read_text())==MEMORY and int((c/'memory.swap.max').read_text())==0 and quota==period and int((c/'pids.max').read_text())==64,'Water raster hard resources')
        tmp=os.statvfs('/tmp')
        require(tmp.f_blocks*tmp.f_frsize==TMP and resource.getrlimit(resource.RLIMIT_FSIZE)==(67108864,67108864),'Water raster tmp/file limits')
        verify_worker_inputs({'workerFiles':{destination:plan['inputs'][name] for name,destination in plan['mounts'].items()}})
        require(not Path('/source.pbf').exists() and not Path('/inputs/node-index').exists(),'Water raster no PBF or coordinate input')
        if operation=='controls':
            import unittest
            require(not Path('/inputs/polygons').exists(),'Water raster controls no real geometry')
            suite=unittest.TestSuite()
            import importlib
            for name in ('coarse_osm_water_raster_v1_test','coarse_osm_water_reference_store_v1_test','prepare_osm_water_raster_v1_test'):
                module=importlib.import_module(name);module.ARTIFACT=('/inputs/water-raster.so',plan['artifact']['sha256'])
                suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
            result=unittest.TextTestRunner(verbosity=2).run(suite)
            controls={'tests':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)}
            require(controls=={'tests':21,'successful':True,'failures':0,'errors':0,'skips':0},'Water raster controls failed')
            save(root,'report.json',{'status':'water_raster_full_pipeline_controls_passed','controls':controls,'nationalDataMounted':False,'sourcePbfReads':0,'maskOrModelChanged':False})
            return 0
        require(operation=='run','Water raster operation')
        from prepare_osm_water_raster_v1 import prepare
        from coarse_osm_water_raster_v1 import WaterRaster
        polygons=json.loads(Path('/inputs/water-polygon-report.json').read_bytes())
        exclusions=json.loads(Path('/inputs/water-exclusion-report.json').read_bytes())
        require(polygons['status']=='national_saved_water_polygon_feasibility_and_source_replay_complete' and exclusions['status']=='all_excluded_water_source_geometry_bounds_and_saved_point_overlap_complete','Water raster complete bound parents')
        require(plan['gridE7']==[-1250000000,240000000,50000,11800,5200],'Water raster frozen model-domain grid')
        engine=WaterRaster('/inputs/water-raster.so',plan['artifact']['sha256'])
        try:
            result=prepare(root,engine,'/inputs/polygons',polygons,exclusions,tuple(plan['gridE7']),check)
            require(result['statistics']['planeBytes']==result['statistics']['nativeBackingBytes']==15340000 and result['manifest']['grid']['cells']==61360000,'Water raster full-country bit backing')
            require(result['statistics']['excludedBoxes']==594 and result['statistics']['incompleteBoxes']==1 and len(result['manifest']['sourceIncompleteFeatures'])==1,'Water raster complete exclusions/source-gap metadata')
        finally:engine.release()
        require(engine.stats()['nativeBackingBytes']==0,'Water raster native arrays released after output')
        save(root,'report.json',{'status':'national_compact_water_raster_derivative_and_binary_audit_complete','raster':result,
                                'workerSecondsIncludingBindingsSourceRasterAndOutput':time.monotonic()-began,'sourcePbfReads':0,'modelQueries':0,'providerRequests':0,'maskOrModelChanged':False,'appActivated':False,
                                'producerNativeArraysReleased':True,'scope':'Complete accepted planar source raster data and explicit boundary/exclusion uncertainty, all binary/gzip bytes reopened. No geographic completeness/shoreline accuracy/land/fallback/connector/mask-policy/routing/ETA/app qualification.'})
        return 0
    except BaseException as error:
        save(root,'failure.json',{'status':'water_raster_derivative_stopped','error':repr(error),'workerSeconds':time.monotonic()-began});return 2
    finally:
        c=Path('/sys/fs/cgroup')
        save(root,'metrics.json',{name:(c/name).read_text().strip() for name in ('memory.current','memory.peak','memory.events','cpu.stat','memory.max','memory.swap.max')})
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


def driver(recipe,pin):
    from coarse_osm_full_monitor_v1 import owned_usage
    from prepare_osm_native_lock_v1 import cleanup_owned,settle_error
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==pin,'Water raster recipe binding')
    plan=json.loads(recipe.read_bytes());operation=plan['operation']
    require(operation in ('controls','run') and plan['output']==PREFIX+operation+'-v1','Water raster exact namespace')
    require(plan['retainedBytes']==72*1024**3 and plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+OWNED+TMP<plan['retainedBytes'],'Water raster aggregate reservation')
    require(set(plan['inputs'])==set(plan['mounts']),'Water raster exact input roster')
    for name,destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/','/inputs/','/tools/','/reference/')) and not name.endswith(('.pbf','/001.bin')),'Water raster readonly scope/no PBF')
        require(sha(repo/name)==plan['inputs'][name],'Water raster input binding')
    require(operation=='controls' or plan['admission']=={'tests':21,'successful':True,'failures':0,'errors':0,'skips':0},'Water raster qualified controls')
    root=repo/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner=uuid.uuid4().hex;name='geo-planner-water-raster-source-'+owner[:12];save(root,'owner.json',{'name':name,'label':owner,'image':IMAGE})
    began=time.monotonic();identity=child=None;code=2
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=15)
    try:
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=1g','--memory-swap=1g','--cpus=1','--pids-limit=64','--tmpfs','/tmp:rw,size=64m','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864','--env','PYTHONPATH=/code:/tools/site:/reference','--env','LD_LIBRARY_PATH=/tools/runtime']
        for source,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_water_raster_source_v1.py','/inputs/recipe.json',pin,'--worker']
        created=call(args);require(created.returncode==0,created.stderr);identity=created.stdout.strip();require(len(identity)==64,'Water raster owned identity')
        observed=json.loads(call(['docker','inspect',identity]).stdout)[0];host=observed['HostConfig']
        require(observed['Image']==IMAGE and host['NetworkMode']=='none' and host['Memory']==host['MemorySwap']==MEMORY and host['NanoCpus']==1000000000 and host['PidsLimit']==64 and host['ReadonlyRootfs'] and host['Tmpfs']=={'/tmp':'rw,size=64m'},'Water raster observed isolation')
        require(not host.get('CapAdd') and {c.removeprefix('CAP_') for c in host['CapDrop']}=={'ALL'} and 'no-new-privileges' in host['SecurityOpt'],'Water raster capabilities')
        require({u['Name']:(u['Soft'],u['Hard']) for u in host['Ulimits']}=={'core':(0,0),'fsize':(67108864,67108864)},'Water raster observed file/core limits')
        require(all(not m['RW'] for m in observed['Mounts'] if m['Destination']!='/work'),'Water raster readonly inputs')
        save(root,'container-initial.json',observed)
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began<(180 if operation=='controls' else 1860) and owned_usage(root)['conservativeAllocatedBytes']<=OWNED,'Water raster host deadline/owned cap');time.sleep(.5)
        observed=json.loads(call(['docker','inspect',identity]).stdout)[0];save(root,'container-result.json',{'State':observed['State'],'clientExitCode':child.returncode})
        require(child.returncode==observed['State']['ExitCode']==0 and not observed['State']['OOMKilled'],'Water raster worker exit/OOM');code=0
    except BaseException as error:save(root,'driver-failure.json',{'error':repr(error),'hostSeconds':time.monotonic()-began})
    finally:
        if child and child.poll() is None:child.kill();child.wait(timeout=5)
        if not (root/'container-result.json').exists():settle_error(call,identity,name,owner,root,child.returncode if child else None)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    save(root,'run-summary.json',{'exitCode':code,'hostSecondsIncludingCleanup':time.monotonic()-began,'sourcePbfReads':0})
    return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('pin');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    require(sha(args.recipe)==args.pin,'Water raster recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe,args.pin))
