"""Full cached-node parity, then one bounded national read-only original-tag collection."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

from coarse_osm_selected_node_tag_audit_v1 import audit, collect
from coarse_osm_selected_node_tags_v1 import SelectedNodeTags
from coarse_osm_country_screen_v1 import owned_usage,resource_metrics
from coarse_osm_data import verify_worker_inputs
from coarse_timing_input import require,start_watchdog
from run_osm_explicit_lane_source_v1 import IMAGE,sha,save
from run_osm_topology_v1 import SOURCE,SCAN

PREFIX='data/coarse-quality/us-osm-selected-node-tags-source-'


def worker(plan):
    root=Path('/work');operation=plan['operation'];began=time.monotonic()
    timer=start_watchdog(180 if operation=='capture' else 2700)
    engine=None;last_progress=last_storage=-1.
    def check():
        nonlocal last_progress,last_storage
        elapsed=time.monotonic()-began
        require(elapsed<(180 if operation=='capture' else 2700),'Selected-node tags worker deadline')
        if elapsed-last_storage>=1:
            last_storage=elapsed
            require(owned_usage(root)['conservativeAllocatedBytes']<=67108864,'Selected-node tags owned cap')
        if engine is not None and elapsed-last_progress>=15:
            last_progress=elapsed
            print(json.dumps({'workerSeconds':elapsed,'nativeProgress':engine.progress()}),flush=True)
    try:
        cgroup=Path('/sys/fs/cgroup')
        require((cgroup/'memory.max').read_text().strip()==str(4*1024**3) and (cgroup/'memory.swap.max').read_text().strip()=='0','Selected-node tags memory/swap')
        verify_worker_inputs({'workerFiles':{dest:plan['inputs'][name] for name,dest in plan['mounts'].items()}})
        causes=json.loads(Path('/inputs/causes-v2.json').read_bytes())
        require(causes['blockedGraphNodes']==13776 and causes['rawNodesKnown']==97 and not causes['sourceReconciliationMismatchNodeIds'],'Current source-cause prerequisites')
        mapping=gzip.decompress(Path('/inputs/blocked-nodes.json.gz').read_bytes())
        require(hashlib.sha256(mapping).hexdigest()==plan['mappingRawSha256'],'Native ID mapping raw seal')
        rows=json.loads(mapping)
        nodes={int(row['sourceNodeId']):row for row in rows}
        require(len(nodes)==13776,'Every current graph blocker selected')
        contributors={int(key):value['restrictionContributorIds'] for key,value in causes['nodeEvidence'].items() if value['restrictionContributorIds']}
        require(len(contributors)==1501,'Every independent node-only restriction contributor')
        engine=SelectedNodeTags('/artifacts/selected-node-tags.so',plan['artifact']['sha256'],aggregate_visits=1770542426)
        output=root/'original-node-tags.bin'
        if operation=='capture':
            import unittest
            import coarse_osm_selected_node_tag_audit_v1_test as audit_tests
            tested=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(audit_tests))
            result={'tests':tested.testsRun,'successful':tested.wasSuccessful(),'failures':len(tested.failures),'errors':len(tested.errors),'skips':len(tested.skipped)}
            save(root,'audit-controls.json',result)
            require(result=={'tests':7,'successful':True,'failures':0,'errors':0,'skips':0},'Independent tag/audit controls')
            import sqlite3
            from coarse_osm_country_wire_v4 import framed_records
            from coarse_osm_projector_v1 import reference_seal
            from coarse_osm_conditional_census_v1_test import CAPS
            expected=[]
            db=sqlite3.connect('file:/inputs/source-cache.sqlite?mode=ro&immutable=1',uri=True)
            db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-16384')
            try:
                for identity in sorted(nodes):
                    check()
                    found=db.execute("SELECT id,raw FROM objects WHERE kind='node' AND id=?",(identity,)).fetchone()
                    if found is not None:
                        require(found[0]==identity and len(found[1])<=1048576,'Bound cached original node')
                        expected.append(json.loads(found[1]))
            finally:db.close()
            require(len(expected)==97,'Complete cached blocked-node corpus')
            nodes={r['id']:nodes[r['id']] for r in expected}
            engine.begin(output,sorted(nodes))
            try:
                receipt=engine.validate_frames(framed_records(expected),SOURCE['state'],CAPS,check=check)
                require(receipt['nativeEof'] and receipt['counts']=={'node':97} and receipt['semanticSha256']==reference_seal(expected) and receipt['pythonProjectionFrames']==0,'Complete captured field/semantic parity')
                counts=engine.finish()
            finally:engine.release()
            independent=audit(output,counts,nodes,contributors,check)
            require(all(independent['nodeEvidence'][str(r['id'])]['rawTags']==r['tags'] for r in expected),'All cached original raw tags equal after native roundtrip')
            measured={'receipt':receipt,'selectedTags':counts,'independentTagAudit':independent}
        else:
            require(operation=='run','Selected-node tags operation')
            measured=collect(engine,Path('/source.pbf'),SOURCE['state'],SCAN,SOURCE,{'node':1606229364,'way':162688797,'relation':1624265},SOURCE['semanticSha256'],output,nodes,contributors,check)
            require(measured['independentTagAudit']['selectedNodes']==13776,'All national graph blockers captured')
            expected={key:row['rawTags'] for key,row in causes['nodeEvidence'].items() if row['rawNodeKnown']}
            require(len(expected)==97 and all(measured['independentTagAudit']['nodeEvidence'][key]['rawTags']==tags for key,tags in expected.items()),'Every previously cached original node tag exact')
        # Large complete tag evidence stays ignored; small summary retains counts and hash.
        independent=measured.pop('independentTagAudit')
        raw=(json.dumps(independent,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
        require(len(raw)<=16777216,'Complete tag evidence bound')
        compressed=gzip.compress(raw,mtime=0)
        with (root/'node-evidence.json.gz').open('xb') as stream:stream.write(compressed)
        artifact={'bytes':len(compressed),'sha256':hashlib.sha256(compressed).hexdigest(),'rawBytes':len(raw),'rawSha256':hashlib.sha256(raw).hexdigest()}
        save(root,'receipt.json',measured['receipt'])
        save(root,'report.json',{'status':'complete_'+operation+'_original_blocked_node_tags_audited',
             'selectedTags':measured['selectedTags'],'causeCounts':independent['causeCounts'],
             'artifacts':{'original-node-tags.bin':{'bytes':independent['bytes'],'sha256':independent['sha256']},'node-evidence.json.gz':artifact},
             'allCached97OriginalTagsExact':True,'unknownRawNodeIds':[],
             'sourceValidationAndCollectionSeconds':measured.get('sourceValidationAndCollectionSeconds'),
             'workerSecondsIncludingBindingsCollectionAndIndependentAudit':time.monotonic()-began,
             'sourcePbfScans':int(operation=='run'),'sourceConstructorExecutions':0,'routingQueries':0,'providerRequests':0,'applicationDbReads':0,
             'sourcePermissionsOrPricesChanged':False,'appActivated':False,
             'scope':'Original tags for every selected blocked graph native ID, all independent raw-node and node-only restriction contributors reconciled, exact parity with all97cached original nodes. Captured stage is metadata-native-frame parity only; national stage retains full unchanged PBF framing/hash/stat/semantic/count/EOF guards and zero ordinary Python projections. No geometry/graph/cost/permission change, new route/map/score, lawful-passage or app admission. Offline worker time includes bindings/source guards/IO/audit, not app query/cloud latency.'})
        return 0
    except BaseException as error:
        save(root,'failure.json',{'status':'selected_node_tags_stopped','error':repr(error),'workerSeconds':time.monotonic()-began})
        raise
    finally:
        save(root,'metrics.json',resource_metrics())
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


def driver(recipe,pin):
    # Keep the established isolated source driver; change only stage admission and worker.
    import json
    import subprocess
    import uuid
    from prepare_osm_native_lock_v1 import cleanup_owned,settle_error
    from run_osm_country_screen_v1 import isolation
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==pin,'Selected-node tags recipe binding')
    plan=json.loads(recipe.read_bytes());operation=plan['operation']
    require(operation in ('capture','run') and plan['output']==PREFIX+operation+'-v1','Selected-node tags exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+67108864+268435456<72*1024**3,'Selected-node tags aggregate reservation')
    require(set(plan['inputs'])==set(plan['mounts']),'Complete selected-tag input roster')
    for name,dest in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and dest.startswith(('/code/','/reference/','/facts/','/inputs/','/artifacts/','/tools/')),'Selected-node tags input scope')
        require(not name.endswith(('.pbf','/001.bin')) and sha(repo/name)==plan['inputs'][name],'Selected-node tags input SHA/no ordinary source mount')
    require(plan['source']==SOURCE and plan['scanCaps']==SCAN,'Unchanged original source/scan guards')
    require(plan['nativeAdmission']=={'tests':35,'successful':True,'failures':0,'errors':0,'skips':0},'Selected-node tags actual native qualification')
    if operation=='run':
        require(plan['capturedAdmission']=={'selectedNodes':97,'allOriginalTagsExact':True,'allBlockingAndSignalCausesReconciled':True},'Complete captured qualification before source')
        original=repo/SOURCE['path']
        require(original.is_file() and not original.is_symlink() and original.stat().st_size==SOURCE['bytes'],'Exact readonly cached source')
    root=repo/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner=uuid.uuid4().hex;name='geo-planner-selected-node-tags-source-'+owner[:12]
    save(root,'owner.json',{'name':name,'label':owner,'image':IMAGE})
    began=time.monotonic();identity=child=None;code=2
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=15)
    try:
        command=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,
                 '--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64',
                 '--tmpfs','/tmp:rw,size=256m','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864','--env','PYTHONPATH=/code:/tools/site:/reference','--env','LD_LIBRARY_PATH=/tools/runtime','--env','OSMIUM_MAX_INPUT_QUEUE_SIZE=2','--env','OSMIUM_MAX_OSMDATA_QUEUE_SIZE=2']
        for source,dest in plan['mounts'].items():command+=['--mount',f'type=bind,src={repo/source},dst={dest},readonly']
        if operation=='run':command+=['--mount',f'type=bind,src={repo/SOURCE["path"]},dst=/source.pbf,readonly']
        command+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_selected_node_tags_source_v1.py','/inputs/recipe.json',pin,'--worker']
        created=call(command);require(created.returncode==0,created.stderr);identity=created.stdout.strip();require(len(identity)==64,'Selected-node tags exact owner')
        observed=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(observed,'controls');save(root,'container-initial.json',observed)
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began<(240 if operation=='capture' else 3000) and owned_usage(root)['conservativeAllocatedBytes']<=67108864,'Selected-node tags host deadline/allocation')
                time.sleep(.5)
        observed=json.loads(call(['docker','inspect',identity]).stdout)[0];save(root,'container-result.json',{'State':observed['State'],'clientExitCode':child.returncode})
        require(child.returncode==observed['State']['ExitCode']==0 and not observed['State']['OOMKilled'],'Selected-node tags worker exit/OOM');code=0
    except BaseException as error:save(root,'driver-failure.json',{'error':repr(error),'hostSeconds':time.monotonic()-began})
    finally:
        if child and child.poll() is None:child.kill();child.wait(timeout=5)
        if not (root/'container-result.json').exists():settle_error(call,identity,name,owner,root,child.returncode if child else None)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    save(root,'run-summary.json',{'exitCode':code,'hostSecondsIncludingCleanup':time.monotonic()-began,'sourcePbfScanIntended':operation=='run'})
    return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('pin');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    require(sha(args.recipe)==args.pin,'Selected-node tags recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe,args.pin))
