"""Collect all excluded-major-way original tags from the cached source, not route samples."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

from coarse_osm_selected_way_tag_audit_v1 import audit, collect
from coarse_osm_selected_way_tags_v1 import SelectedWayTags
from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
from coarse_osm_data import verify_worker_inputs
from coarse_timing_input import require, start_watchdog
from run_osm_explicit_lane_source_v1 import IMAGE, sha, save
from run_osm_topology_v1 import SOURCE, SCAN

PREFIX = 'data/coarse-quality/us-osm-selected-way-tags-source-'


def selection(plan, check):
    selected={};digest=hashlib.sha256();raw_bytes=0
    with gzip.open('/inputs/excluded-geometries.jsonl.gz','rb') as stream:
        while raw:=stream.readline(4194305):
            if len(selected)%256==0:check()
            require(len(raw)<=4194304 and raw.endswith(b'\n') and len(selected)<52743, 'Bound complete source selection')
            row=json.loads(raw);identity=row['sourceWay']
            require(type(identity) is int and 0<identity<2**63 and (not selected or identity>next(reversed(selected))), 'Sorted complete selected way IDs')
            selected[identity]={k:row[k] for k in ('sourceWay','storedSourceFlags','baseEligible','finalFallbackClosed')}
            digest.update(raw);raw_bytes+=len(raw)
    require(len(selected)==52743 and raw_bytes==plan['geometryRawBytes'] and digest.hexdigest()==plan['geometryRawSha256'], 'Every original source-selected way retained')
    return selected


def worker(plan):
    root=Path('/work');operation=plan['operation'];began=time.monotonic();engine=None;last_storage=last_progress=-1.
    timer=start_watchdog(180 if operation=='capture' else 2700)
    def check():
        nonlocal last_storage,last_progress
        elapsed=time.monotonic()-began
        require(elapsed<(180 if operation=='capture' else 2700), 'Selected-way tags worker deadline')
        if elapsed-last_storage>=1:
            last_storage=elapsed
            require(owned_usage(root)['conservativeAllocatedBytes']<=67108864, 'Selected-way tags owned cap')
        if engine is not None and elapsed-last_progress>=15:
            last_progress=elapsed;print(json.dumps({'workerSeconds':elapsed,'nativeProgress':engine.progress()}),flush=True)
    try:
        c=Path('/sys/fs/cgroup')
        require((c/'memory.max').read_text().strip()==str(4*1024**3) and (c/'memory.swap.max').read_text().strip()=='0', 'Selected-way tags memory/swap')
        verify_worker_inputs({'workerFiles':{dest:plan['inputs'][name] for name,dest in plan['mounts'].items()}})
        selected=selection(plan,check)
        known=json.loads(gzip.decompress(Path('/inputs/cached-way-evidence.json.gz').read_bytes()))
        expected_tags={str(r['sourceWay']):r['rawTags'] for r in known['knownWays']}
        require(len(expected_tags)==616 and len(known['unknownRawWayIds'])==52127, 'Entire prior raw-tag coverage denominator')
        engine=SelectedWayTags('/artifacts/selected-way-tags.so',plan['artifact']['sha256'],aggregate_visits=1770542426)
        output=root/'original-way-tags.bin'
        if operation=='capture':
            import unittest
            import coarse_osm_selected_way_tag_audit_v1_test as tests
            tested=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
            controls=dict(tests=tested.testsRun,successful=tested.wasSuccessful(),failures=len(tested.failures),errors=len(tested.errors),skips=len(tested.skipped))
            save(root,'audit-controls.json',controls)
            require(controls==dict(tests=8,successful=True,failures=0,errors=0,skips=0), 'Independent way audit controls')
            import sqlite3
            from coarse_osm_country_wire_v4 import framed_records
            from coarse_osm_projector_v1 import reference_seal
            from coarse_osm_conditional_census_v1_test import CAPS
            db=sqlite3.connect('file:/inputs/source-cache.sqlite?mode=ro&immutable=1',uri=True)
            db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-16384');expected=[]
            try:
                for identity in sorted(map(int,expected_tags)):
                    check();found=db.execute("SELECT id,raw FROM objects WHERE kind='way' AND id=?",(identity,)).fetchone()
                    require(found is not None and found[0]==identity and len(found[1])<=4194304, 'Every prior cached original way')
                    record=json.loads(found[1]);require(record['tags']==expected_tags[str(identity)], 'Prior cached raw tags exact');expected.append(record)
            finally:db.close()
            selected={r['id']:selected[r['id']] for r in expected};engine.begin(output,sorted(selected))
            try:
                receipt=engine.validate_frames(framed_records(expected),SOURCE['state'],CAPS,check=check)
                require(receipt['nativeEof'] and receipt['counts']=={'way':616} and receipt['semanticSha256']==reference_seal(expected) and receipt['pythonProjectionFrames']==0, 'All616captured source field/semantic parity')
                counts=engine.finish()
            finally:engine.release()
            measured=dict(receipt=receipt,selectedTags=counts,independentTagAudit=audit(output,counts,selected,check))
        else:
            require(operation=='run', 'Selected-way tags operation')
            measured=collect(engine,Path('/source.pbf'),SOURCE['state'],SCAN,SOURCE,{'node':1606229364,'way':162688797,'relation':1624265},SOURCE['semanticSha256'],output,selected,check)
        independent=measured.pop('independentTagAudit')
        require(all(independent['wayEvidence'][key]['rawTags']==tags for key,tags in expected_tags.items()), 'Every prior616original way tags exact')
        raw=(json.dumps(independent,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
        require(len(raw)<=48*1048576, 'Complete raw-way evidence cap')
        packed=gzip.compress(raw,mtime=0);require(len(packed)<=16*1048576, 'Compressed raw-way evidence cap')
        with (root/'way-evidence.json.gz').open('xb')as stream:stream.write(packed)
        artifact=dict(bytes=len(packed),sha256=hashlib.sha256(packed).hexdigest(),rawBytes=len(raw),rawSha256=hashlib.sha256(raw).hexdigest())
        save(root,'receipt.json',measured['receipt'])
        save(root,'report.json',dict(status='complete_'+operation+'_original_excluded_major_way_tags_audited',selectedTags=measured['selectedTags'],
             causeCounts=independent['currentBaseReasonCounts'],artifacts={'original-way-tags.bin':dict(bytes=independent['bytes'],sha256=independent['sha256']),'way-evidence.json.gz':artifact},
             allCached616OriginalTagsExact=True,unknownRawWayIds=[],sourceValidationAndCollectionSeconds=measured.get('sourceValidationAndCollectionSeconds'),
             workerSecondsIncludingBindingsCollectionAndIndependentAudit=time.monotonic()-began,sourcePbfScans=int(operation=='run'),sourceConstructorExecutions=0,routingQueries=0,providerRequests=0,applicationDbReads=0,
             sourcePermissionsOrPricesChanged=False,appActivated=False,
             scope='Complete old52743source-selected excluded-major-way corpus, never selected cities/routes. Original tags independently replay base eligibility; old selection fallback flags remain explicitly historical, not current closure IDs. Current membership/causal corridor diagnosis is separate. All616cached original tags must match. National stage keeps unchanged full hash/stat/framing/semantic/count/EOF guards and zero ordinary Python projections; no geometry/graph/cost/permission change, provider/data acquisition, fitted policy or accuracy/app admission. Offline duration includes source validation/IO/audit, not query/cloud latency.'))
        check();return 0
    except BaseException as error:
        save(root,'failure.json',dict(status='selected_way_tags_stopped',error=repr(error),workerSeconds=time.monotonic()-began));raise
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
        require(plan['capturedAdmission']=={'selectedWays':616,'allOriginalTagsExact':True,'allBaseEligibilityReconciled':True},'Complete captured qualification before source')
        original=repo/SOURCE['path']
        require(original.is_file() and not original.is_symlink() and original.stat().st_size==SOURCE['bytes'],'Exact readonly cached source')
    root=repo/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner=uuid.uuid4().hex;name='geo-planner-selected-way-tags-source-'+owner[:12]
    save(root,'owner.json',{'name':name,'label':owner,'image':IMAGE})
    began=time.monotonic();identity=child=None;code=2
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=15)
    try:
        command=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,
                 '--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64',
                 '--tmpfs','/tmp:rw,size=256m','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864','--env','PYTHONPATH=/code:/tools/site:/reference','--env','LD_LIBRARY_PATH=/tools/runtime','--env','OSMIUM_MAX_INPUT_QUEUE_SIZE=2','--env','OSMIUM_MAX_OSMDATA_QUEUE_SIZE=2']
        for source,dest in plan['mounts'].items():command+=['--mount',f'type=bind,src={repo/source},dst={dest},readonly']
        if operation=='run':command+=['--mount',f'type=bind,src={repo/SOURCE["path"]},dst=/source.pbf,readonly']
        command+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_selected_way_tags_source_v1.py','/inputs/recipe.json',pin,'--worker']
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
