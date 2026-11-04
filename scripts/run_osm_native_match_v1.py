"""Bounded native geometry adapter/matcher; no usable-limit/model admission."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import unittest
import uuid

from coarse_timing_input import require,start_watchdog

IMAGE='sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
OUTPUTS={stage:f'data/coarse-quality/us-osm-native-match-{stage}-v1' for stage in ('controls','run')}
CAPS={'memoryBytes':1073741824,'tmpBytes':67108864,'fileBytes':134217728,'ownedBytes':536870912,'workerSeconds':1800,'hostSeconds':1860}
CODE=['run_osm_native_match_v1', 'coarse_osm_match_v1', 'coarse_osm_match_v1_test', 'coarse_osm_attribute_inventory_v1', 'coarse_osm_attributes_v1', 'coarse_osm_records', 'coarse_path_features', 'coarse_timing_chains', 'coarse_timing_fragments', 'coarse_timing_fragments_audit', 'coarse_timing_compatibility_audit', 'analyze_timing_cache', 'analyze_timing_compatibility', 'coarse_timing_input', 'coarse_timing_parquet', 'coarse_backbone_paths', 'coarse_backbone_codec']
SOURCES={'data/coarse-quality/us-osm-disk-capture-run-v1/extract/elements.jsonl':'/inputs/captured.jsonl',
         'data/coarse-quality/overture-timing-cache-analysis-v2/matches.jsonl':'/inputs/census.jsonl'}

def mounts(stage):
    return {**{'scripts/'+name+'.py':'/code/'+name+'.py' for name in CODE},
            'data/coarse-quality/us-osm-tools-v3/prepare/runtime/libexpat.so.1':'/runtime/libexpat.so.1',**(SOURCES if stage=='run' else {})}


def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save(root,name,value):(root/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def validate(plan):
    from coarse_osm_match_v1 import CAPS as DATA_CAPS
    stage=plan['stage'];require(stage in OUTPUTS and plan['phase']=='native_connected_geometry_v1' and plan['image']==IMAGE and plan['output']==OUTPUTS[stage] and plan['caps']==CAPS,'Native matcher exact phase/image/caps')
    require(plan['mounts']==mounts(stage) and set(plan['inputs'])==set(mounts(stage)),'Native matcher exact input scope')
    require(plan['dataCaps']==(DATA_CAPS|{'nodeCanonicalBytes':1048576} if stage=='controls' else DATA_CAPS),'Native matcher exact data caps')
    require(len(plan['windows'])==(1 if stage=='controls' else 21) and plan['sourceSnapshotUtc']=='2026-10-25T21:21:21Z','Native matcher original windows/snapshot')
    if stage=='run':require(plan['controllerAdmission']['qualified'] and plan['controllerAdmission']['tests']==15 and plan['captureAdmission']['qualified'],'Native matcher prior admissions')


def worker(plan):
    from collections import Counter
    import io
    from coarse_osm_match_v1 import read_nodes,read_window,Index,match,summary
    from coarse_osm_records import canonical
    root=Path('/work');timer=start_watchdog(CAPS['workerSeconds']);began=time.monotonic();written=0
    def check():require(time.monotonic()-began<CAPS['workerSeconds'],'Native matcher worker deadline')
    def emit(name,value,append=False):
        nonlocal written
        check();raw=canonical(value)+b'\n';require(written+len(raw)<=CAPS['ownedBytes']-1048576,'Native matcher output byte cap');path=root/name
        path.parent.mkdir(parents=True,exist_ok=True);old=path.stat().st_size if path.exists() else 0
        require((old if append else 0)+len(raw)<=CAPS['fileBytes'],'Native matcher output file cap')
        with path.open('ab' if append else 'xb') as stream:stream.write(raw)
        written+=len(raw)
    try:
        for name,path in mounts(plan['stage']).items():
            source=Path(path);limit=plan['dataCaps']['inputBytes'] if path=='/inputs/captured.jsonl' else 4194304
            require(source.is_file() and not source.is_symlink() and source.stat().st_size<=limit and sha(source)==plan['inputs'][name],'Native matcher worker input drift/type/size')
        memory=Path('/sys/fs/cgroup');require((memory/'memory.max').read_text().strip()==str(CAPS['memoryBytes']) and (memory/'memory.swap.max').read_text().strip()=='0','Native matcher hard memory/swap')
        tmp=os.statvfs('/tmp');require(tmp.f_blocks*tmp.f_frsize==CAPS['tmpBytes'] and resource.getrlimit(resource.RLIMIT_FSIZE)==(CAPS['fileBytes'],CAPS['fileBytes']),'Native matcher tmp/file guards')
        if plan['stage']=='controls':
            import coarse_osm_match_v1_test as tests
            result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
            save(root,'controls.json',{'tests':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)})
            require(result.wasSuccessful() and result.testsRun==15 and not result.skipped,'Native matcher target controls failed')
            tags={'highway':'primary','maxspeed':'55 mph','access':'private','maxspeed:conditional':'20 @ wet'}
            fixture=b''.join(canonical(r)+b'\n' for r in tests.fixture(ways=[([1,2],tags),([2,3],tags)]));source_records=[tests.source()];open_capture=lambda:io.BytesIO(fixture)
        else:
            path=Path('/inputs/captured.jsonl');before=path.stat();open_capture=lambda:path.open('rb');source_records=[]
            with Path('/inputs/census.jsonl').open('rb') as census:
                while line:=census.readline(4194305):
                    require(len(line)<=4194304 and len(source_records)<5000,'Native matcher Census row/count cap');source_records.append(json.loads(line))
            require(len(source_records)==2469 and len({(r['windowId'],r['arc']) for r in source_records})==2469,'Native matcher original Census roster')
        with open_capture() as stream:nodes,receipt=read_nodes(stream,plan['sourceSnapshotUtc'],check,plan['dataCaps'])
        if plan['stage']=='run':require(receipt['sha256']==plan['inputs'][next(iter(SOURCES))] and receipt['types']=={'node':1123919,'relation':4900,'way':239253} and receipt['rows']==receipt['memberships']==1368072,'Native matcher complete captured roster')
        emit('node-receipt.json',receipt);records=[];window_reports=[];review=[]
        for window in plan['windows']:
            check();wid=window['id'];box=window['bbox']
            with open_capture() as stream:metadata,lines,scan=read_window(stream,nodes,wid,check,plan['dataCaps'])
            require(scan['sha256']==receipt['sha256'] and scan['bytes']==receipt['bytes'] and scan['rows']==receipt['rows'],'Native matcher repeated input drift')
            index=Index(lines,box,check,plan['dataCaps']);selected=[];bindings={}
            for original in source_records:
                if original['windowId']!=wid:continue
                require(original['sourceClassKph'] in (85,105),'Native matcher original source class')
                r=match(original,metadata,lines,index,box,check,plan['dataCaps']);r['sourceRecordSha256']=hashlib.sha256(canonical(original)).hexdigest()
                for binding in r.pop('alignedPartBindings',[]):bindings[binding['ordinal']]=binding
                emit('windows/'+wid+'/matches.jsonl',r,True);selected.append(r);records.append(r)
                if r['status']=='single_acquired_file_geometric_path':
                    candidate=r['candidates'][0];identity=[(metadata[i]['nativeWayId'],metadata[i]['nativeWayVersion'],metadata[i]['firstNodeIndex'],metadata[i]['lastNodeIndex']) for i in candidate['nativeParts']]
                    rank=hashlib.sha256(canonical([plan['sourceSnapshotUtc'],identity,wid])).hexdigest();review.append({'rank':rank,'windowId':wid,'arc':r['arc'],'nativePathIdentity':identity,'sourceRecordSha256':r['sourceRecordSha256'],'physicalMatchReviewed':False,'usableForTiming':False})
            for ordinal,binding in sorted(bindings.items()):emit('windows/'+wid+'/part-bindings.jsonl',binding,True)
            ws={'id':wid,'captureScan':scan,'nativePartRoleCounts':dict(Counter(m['nativeTags'].get('highway','') for m in metadata)),'totals':summary(selected),
                'classes':{str(k):summary([r for r in selected if r['sourceClassKph']==k]) for k in (85,105)},'indexSegments':len(index.segments),'indexBinEntries':index.entries,'sampleComparisons':index.comparisons,'alignedPartBindings':len(bindings)}
            emit('windows/'+wid+'/report.json',ws);window_reports.append(ws)
            print(json.dumps({'window':wid,'nativeWays':scan['ways'],'nativeParts':scan['parts'],'sourceRecords':len(selected),'statuses':ws['totals']['statusCounts']}),flush=True)
            del metadata,lines,index,bindings,selected
        require(sum(w['totals']['arcWindowRecords'] for w in window_reports)==len(source_records),'Native matcher all original windows/records')
        if plan['stage']=='run':
            require(abs(summary(records)['sourceKm']-plan['expectedSourceKm'])<1e-9,'Native matcher unchanged Census denominator');after=path.stat();require(before==after,'Native matcher input changed')
        review=sorted(review,key=lambda r:(r['rank'],r['arc']))[:50];emit('review-selection.json',{'method':'AscendingSHA256(snapshot/nativePathIdentity/window),arc tiebreak;50single acquired-file geometric records or every such record if fewer. No physical match assertion/admission.','records':review,'physicalMatchReviewed':False})
        profile={'format':'native-osm-connected-geometry-v1','stage':plan['stage'],'captureReceipt':receipt,'allWindows':summary(records),'windows':window_reports,
                 'classes':{str(k):summary([r for r in records if r['sourceClassKph']==k]) for k in (85,105)},'sourceRecordCount':len(source_records),'reviewRecords':len(review),
                 'sourceAdequacyQualified':False,'carPermissionReviewed':False,'uniquePhysicalMatchQualified':False,'usableLimitOrMatchingQualified':False,'modelChanged':False,
                 'scope':'Native OSM node-ID junction parts and generic undirected terminal-fragment geometry. All acquired competitors retained; unknown role/unrepresented aligned geometry and search caps remain unresolved. Direction/access/grade/barriers/restrictions are raw context, not driving permission, qualified physical matches or usable timing costs.21validation areas do not establish national accuracy.'}
        emit('report.json',profile)
        save(root,'result.json',{'status':'passed_native_geometry_diagnostic','stage':plan['stage'],'reportSha256':sha(root/'report.json'),'reviewSha256':sha(root/'review-selection.json'),'seconds':time.monotonic()-began,'outputBytesMetered':written,'usableLimitOrMatchingQualified':False,'modelChanged':False})
        return 0
    except BaseException as error:
        save(root,'worker-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:2000],'sourceOrModelAdmitted':False});return 2
    finally:
        save(root,'metrics.json',{name:(Path('/sys/fs/cgroup')/name).read_text().strip() for name in ['memory.max','memory.swap.max','memory.peak','memory.events']})
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


def isolation(observed):
    host=observed['HostConfig'];expected={'NetworkMode':'none','Memory':CAPS['memoryBytes'],'MemorySwap':CAPS['memoryBytes'],'ReadonlyRootfs':True,'NanoCpus':1000000000,'PidsLimit':32,'Tmpfs':{'/tmp':'rw,size=64m'}}
    require(observed['Image']==IMAGE and all(host[k]==v for k,v in expected.items()),'Native matcher observed isolation')
    require(not host.get('CapAdd') and {x.removeprefix('CAP_') for x in host['CapDrop']}=={'ALL'} and 'no-new-privileges' in host['SecurityOpt'],'Native matcher capabilities')
    require(all(not m['RW'] for m in observed['Mounts'] if m['Destination']!='/work'),'Native matcher readonly inputs')
    require({u['Name']:(u['Soft'],u['Hard']) for u in host['Ulimits']}=={'core':(0,0),'fsize':(CAPS['fileBytes'],CAPS['fileBytes'])},'Native matcher file/core limits')


def driver(plan,recipe,pin):
    from prepare_osm_native_lock_v1 import cleanup_owned
    repo=Path(__file__).resolve().parents[1];root=repo/OUTPUTS[plan['stage']];require(not root.exists(),'Native matcher fresh output required');root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner=uuid.uuid4().hex;name='geo-planner-native-match-'+owner[:12];began=time.monotonic();identity=child=None;code=2
    save(root,'owner.json',{'label':owner,'name':name,'image':IMAGE})
    def check():
        require(time.monotonic()-began<CAPS['hostSeconds']-10,'Native matcher host deadline')
        require(sum(p.stat().st_size for p in root.rglob('*') if p.is_file())<=CAPS['ownedBytes'],'Native matcher owned byte cap')
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=10)
    try:
        for name_input,pin_input in plan['inputs'].items():
            source=repo/name_input;limit=plan['dataCaps']['inputBytes'] if mounts(plan['stage'])[name_input]=='/inputs/captured.jsonl' else 4194304
            require(source.is_file() and not source.is_symlink() and source.stat().st_size<=limit and sha(source)==pin_input,'Native matcher host input drift/type/size')
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
              '--memory=1g','--memory-swap=1g','--cpus=1','--pids-limit=32','--tmpfs','/tmp:rw,size=64m','--ulimit','core=0:0','--ulimit','fsize=134217728:134217728','--env','PYTHONPATH=/code','--env','LD_LIBRARY_PATH=/runtime']
        for source,destination in mounts(plan['stage']).items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_native_match_v1.py','/inputs/recipe.json',pin,'--worker']
        created=call(args);require(created.returncode==0,created.stderr);identity=created.stdout.strip();observed=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(observed)
        save(root,'container-initial.json',{'Image':observed['Image'],'HostConfig':observed['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in observed['Mounts']]})
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:check();time.sleep(.25)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0];save(root,'container-result.json',{'State':final['State'],'clientExitCode':child.returncode})
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Native matcher worker failed/OOM');code=0
    except BaseException as error:save(root,'driver-failure.json',{'errorType':type(error).__name__,'error':str(error)[:2000]})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    save(root,'run-summary.json',{'exitCode':code,'seconds':time.monotonic()-began,'networkRequests':0,'pbfOrNativeHelperReads':0,'stage':plan['stage'],'modelChanged':False});return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    recipe=Path(args.recipe).resolve();require(sha(recipe)==args.sha256,'Native matcher recipe checksum');plan=json.loads(recipe.read_bytes());validate(plan)
    raise SystemExit(worker(plan) if args.worker else driver(plan,recipe,args.sha256))
