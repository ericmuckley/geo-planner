"""Bounded, offline captured-road/Census geometry opportunity diagnostic."""
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
OUTPUTS={stage:f'data/coarse-quality/us-osm-speed-opportunity-{stage}-v1' for stage in ('controls','run')}
CAPS={'memoryBytes':536870912,'tmpBytes':33554432,'fileBytes':33554432,'ownedBytes':4194304,'workerSeconds':300,'hostSeconds':360}
CODE=['run_osm_speed_opportunity_v1','coarse_osm_speed_opportunity_v1','coarse_osm_speed_opportunity_v1_test','coarse_osm_attributes_v1','coarse_osm_records','coarse_timing_input','coarse_timing_parquet','coarse_backbone_paths','coarse_backbone_codec','coarse_path_features']
SOURCES={'data/coarse-quality/us-osm-disk-capture-run-v1/extract/elements.jsonl':'/inputs/captured.jsonl',
         'data/coarse-quality/overture-timing-cache-analysis-v2/matches.jsonl':'/inputs/census.jsonl'}

def mounts(stage):
    return {**{'scripts/'+name+'.py':'/code/'+name+'.py' for name in CODE},
            'data/coarse-quality/us-osm-tools-v3/prepare/runtime/libexpat.so.1':'/runtime/libexpat.so.1',**(SOURCES if stage=='run' else {})}


def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save(root,name,value):(root/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def validate(plan):
    from coarse_osm_speed_opportunity_v1 import CAPS as DATA_CAPS
    stage=plan['stage'];require(stage in OUTPUTS and plan['phase']=='speed_geometry_opportunity_v1' and plan['image']==IMAGE and plan['output']==OUTPUTS[stage] and plan['caps']==CAPS,'Opportunity exact phase/image/caps')
    require(plan['mounts']==mounts(stage) and set(plan['inputs'])==set(mounts(stage)),'Opportunity exact input scope')
    require(plan['dataCaps']==DATA_CAPS,'Opportunity exact data caps')
    require(len(plan['windows'])==(2 if stage=='controls' else 21) and plan['sourceSnapshotUtc']=='2026-10-25T21:21:21Z','Opportunity original windows/snapshot')
    if stage=='run':require(plan['controllerAdmission']['qualified'] and plan['controllerAdmission']['tests']==10 and plan['captureAdmission']['qualified'],'Opportunity prior admissions')


def worker(plan):
    import io
    from coarse_osm_speed_opportunity_v1 import opportunity
    root=Path('/work');timer=start_watchdog(CAPS['workerSeconds']);began=time.monotonic()
    def check():require(time.monotonic()-began<CAPS['workerSeconds'],'Opportunity worker deadline')
    try:
        for name,path in mounts(plan['stage']).items():
            source=Path(path);limit=plan['dataCaps']['inputBytes'] if path=='/inputs/captured.jsonl' else 4194304
            require(source.is_file() and not source.is_symlink() and source.stat().st_size<=limit and sha(source)==plan['inputs'][name],'Opportunity worker input drift/type/size')
        memory=Path('/sys/fs/cgroup');require((memory/'memory.max').read_text().strip()==str(CAPS['memoryBytes']) and (memory/'memory.swap.max').read_text().strip()=='0','Opportunity hard memory/swap')
        tmp=os.statvfs('/tmp');require(tmp.f_blocks*tmp.f_frsize==CAPS['tmpBytes'] and resource.getrlimit(resource.RLIMIT_FSIZE)==(CAPS['fileBytes'],CAPS['fileBytes']),'Opportunity tmp/file guards')
        if plan['stage']=='controls':
            import coarse_osm_speed_opportunity_v1_test as tests
            result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
            save(root,'controls.json',{'tests':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)})
            require(result.wasSuccessful() and result.testsRun==10 and not result.skipped,'Opportunity target controls failed')
            from coarse_osm_records import canonical
            stream=io.BytesIO(b''.join(canonical(r)+b'\n' for r in tests.fixture({'maxspeed':'55 mph','access':'private','maxspeed:conditional':'20 @ wet'},split=True)))
            source_records=tests.source();before=None
        else:
            path=Path('/inputs/captured.jsonl');before=path.stat();stream=path.open('rb');source_records=[]
            with Path('/inputs/census.jsonl').open('rb') as census:
                while line:=census.readline(4194305):
                    require(len(line)<=4194304 and len(source_records)<plan['dataCaps']['sourceRecords'],'Opportunity Census row/count cap');source_records.append(json.loads(line))
            require(len(source_records)==2469,'Opportunity original Census roster count')
        try:profile,arcs,masks=opportunity(stream,source_records,snapshot=plan['sourceSnapshotUtc'],windows=plan['windows'],caps=plan['dataCaps'],check=check)
        finally:stream.close()
        if before is not None:
            after=path.stat();require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'Opportunity input changed')
            require(profile['inputSha256']==plan['inputs'][next(iter(SOURCES))] and profile['types']==plan['expectedTypes'] and profile['rows']==1368072 and profile['memberships']==1368072,'Opportunity complete captured roster')
            require(profile['allWindows']['arcWindowRecords']==2469 and abs(profile['allWindows']['sourceKm']-plan['expectedSourceKm'])<1e-9,'Opportunity unchanged Census denominator')
        require(not any(profile[k] for k in ('sourceAdequacyQualified','carPermissionReviewed','uniqueMatchesQualified','usableLimitOrMatchingQualified','modelChanged')),'Opportunity inferred usability or costs')
        payloads={'opportunity.json':(json.dumps(profile,indent=2,allow_nan=False)+'\n').encode(),
                  'arcs.jsonl':b''.join((json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode() for r in arcs),'sample-masks.bin':masks}
        require(sum(len(v) for v in payloads.values())+sum(p.stat().st_size for p in root.rglob('*') if p.is_file())+65536<=CAPS['ownedBytes'],'Opportunity projected owned output cap')
        for name,raw in payloads.items():
            with (root/name).open('xb') as output:output.write(raw)
        save(root,'result.json',{'status':'passed_geometry_opportunity_diagnostic','stage':plan['stage'],'records':profile['rows'],'opportunitySha256':sha(root/'opportunity.json'),'arcsSha256':sha(root/'arcs.jsonl'),'sampleMasksSha256':sha(root/'sample-masks.bin'),'seconds':time.monotonic()-began,'usableLimitOrMatchingQualified':False,'modelChanged':False})
        return 0
    except BaseException as error:
        save(root,'worker-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:2000],'sourceOrModelAdmitted':False});return 2
    finally:
        save(root,'metrics.json',{name:(Path('/sys/fs/cgroup')/name).read_text().strip() for name in ['memory.max','memory.swap.max','memory.peak','memory.events']})
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


def isolation(observed):
    host=observed['HostConfig'];expected={'NetworkMode':'none','Memory':CAPS['memoryBytes'],'MemorySwap':CAPS['memoryBytes'],'ReadonlyRootfs':True,'NanoCpus':1000000000,'PidsLimit':32,'Tmpfs':{'/tmp':'rw,size=32m'}}
    require(observed['Image']==IMAGE and all(host[k]==v for k,v in expected.items()),'Opportunity observed isolation')
    require(not host.get('CapAdd') and {x.removeprefix('CAP_') for x in host['CapDrop']}=={'ALL'} and 'no-new-privileges' in host['SecurityOpt'],'Opportunity capabilities')
    require(all(not m['RW'] for m in observed['Mounts'] if m['Destination']!='/work'),'Opportunity readonly inputs')
    require({u['Name']:(u['Soft'],u['Hard']) for u in host['Ulimits']}=={'core':(0,0),'fsize':(CAPS['fileBytes'],CAPS['fileBytes'])},'Opportunity file/core limits')


def driver(plan,recipe,pin):
    from prepare_osm_native_lock_v1 import cleanup_owned
    repo=Path(__file__).resolve().parents[1];root=repo/OUTPUTS[plan['stage']];require(not root.exists(),'Opportunity fresh output required');root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner=uuid.uuid4().hex;name='geo-planner-speed-opportunity-'+owner[:12];began=time.monotonic();identity=child=None;code=2
    save(root,'owner.json',{'label':owner,'name':name,'image':IMAGE})
    def check():
        require(time.monotonic()-began<CAPS['hostSeconds']-10,'Opportunity host deadline')
        require(sum(p.stat().st_size for p in root.rglob('*') if p.is_file())<=CAPS['ownedBytes'],'Opportunity owned byte cap')
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=10)
    try:
        for name_input,pin_input in plan['inputs'].items():
            source=repo/name_input;limit=plan['dataCaps']['inputBytes'] if mounts(plan['stage'])[name_input]=='/inputs/captured.jsonl' else 4194304
            require(source.is_file() and not source.is_symlink() and source.stat().st_size<=limit and sha(source)==pin_input,'Opportunity host input drift/type/size')
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
              '--memory=512m','--memory-swap=512m','--cpus=1','--pids-limit=32','--tmpfs','/tmp:rw,size=32m','--ulimit','core=0:0','--ulimit','fsize=33554432:33554432','--env','PYTHONPATH=/code','--env','LD_LIBRARY_PATH=/runtime']
        for source,destination in mounts(plan['stage']).items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_speed_opportunity_v1.py','/inputs/recipe.json',pin,'--worker']
        created=call(args);require(created.returncode==0,created.stderr);identity=created.stdout.strip();observed=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(observed)
        save(root,'container-initial.json',{'Image':observed['Image'],'HostConfig':observed['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in observed['Mounts']]})
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:check();time.sleep(.25)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0];save(root,'container-result.json',{'State':final['State'],'clientExitCode':child.returncode})
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Opportunity worker failed/OOM');code=0
    except BaseException as error:save(root,'driver-failure.json',{'errorType':type(error).__name__,'error':str(error)[:2000]})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    save(root,'run-summary.json',{'exitCode':code,'seconds':time.monotonic()-began,'networkRequests':0,'pbfOrNativeHelperReads':0,'stage':plan['stage'],'modelChanged':False});return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    recipe=Path(args.recipe).resolve();require(sha(recipe)==args.sha256,'Opportunity recipe checksum');plan=json.loads(recipe.read_bytes());validate(plan)
    raise SystemExit(worker(plan) if args.worker else driver(plan,recipe,args.sha256))
