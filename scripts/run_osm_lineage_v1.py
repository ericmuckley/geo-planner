"""Bounded way-lineage geometry prototype with arbitrary internal-point access; no ETA model."""
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
OUTPUTS={stage:f'data/coarse-quality/us-osm-lineage-{stage}-v1' for stage in ('controls','run')}
CAPS={'memoryBytes':2147483648,'tmpBytes':67108864,'fileBytes':134217728,'ownedBytes':268435456,'workerSeconds':600,'hostSeconds':660}
CODE=['coarse_osm_bulk_pbf','run_osm_lineage_v1','coarse_osm_lineage_v1','coarse_osm_lineage_v1_test','coarse_osm_backbone_v1','coarse_osm_backbone_v1_test','coarse_osm_match_v1','coarse_osm_match_v1_test','coarse_osm_attribute_inventory_v1','coarse_osm_attributes_v1','coarse_osm_records','coarse_path_features','coarse_timing_chains','coarse_timing_fragments','coarse_timing_fragments_audit','coarse_timing_compatibility_audit','analyze_timing_cache','analyze_timing_compatibility','coarse_timing_input','coarse_timing_parquet','coarse_backbone_paths','coarse_backbone_codec']
SOURCES={'data/coarse-quality/us-osm-disk-capture-run-v1/extract/elements.jsonl':'/inputs/captured.jsonl','data/coarse-quality/us-osm-backbone-run-v1/report.json':'/inputs/baseline.json'}


def mounts(stage):
    return {**{'scripts/'+name+'.py':'/code/'+name+'.py' for name in CODE},
            'data/coarse-quality/us-osm-tools-v3/prepare/runtime/libexpat.so.1':'/runtime/libexpat.so.1',**(SOURCES if stage=='run' else {})}


def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save(root,name,value):(root/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def validate(plan):
    from coarse_osm_backbone_v1 import CAPS as DATA_CAPS,PROFILES
    stage=plan['stage'];require(stage in OUTPUTS and plan['phase']=='native_way_lineage_v1' and plan['image']==IMAGE and plan['output']==OUTPUTS[stage] and plan['caps']==CAPS,'Lineage exact phase/image/caps')
    require(plan['mounts']==mounts(stage) and set(plan['inputs'])==set(mounts(stage)),'Lineage exact input scope')
    require(plan['dataCaps']==(DATA_CAPS|{'nodeCanonicalBytes':1048576} if stage=='controls' else DATA_CAPS) and plan['profiles']==list(PROFILES[1:]),'Lineage exact data caps/profiles')
    require(len(plan['windows'])==(2 if stage=='controls' else 21) and plan['sourceSnapshotUtc']=='2026-10-25T21:21:21Z','Lineage original area/snapshot')
    if stage=='run':require(plan['controllerAdmission']['qualified'] and plan['controllerAdmission']['tests']==12 and plan['captureAdmission']['qualified'],'Lineage prior controls/capture')


def worker(plan):
    import io
    from coarse_osm_lineage_v1 import build
    from coarse_osm_records import canonical
    root=Path('/work');timer=start_watchdog(CAPS['workerSeconds']);began=time.monotonic();written=0;roster={}
    def check():require(time.monotonic()-began<CAPS['workerSeconds'],'Lineage worker deadline')
    def emit(name,raw):
        nonlocal written
        check();path=root/name;require(not Path(name).is_absolute() and '..' not in Path(name).parts and not path.exists(),'Lineage fresh bounded artifact path')
        require(len(raw)<=CAPS['fileBytes'] and written+len(raw)<=CAPS['ownedBytes']-1048576,'Lineage file/owned output cap');path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(raw)
        written+=len(raw);roster[name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    try:
        for name,path in mounts(plan['stage']).items():
            source=Path(path);limit=plan['dataCaps']['inputBytes'] if path=='/inputs/captured.jsonl' else 4194304
            require(source.is_file() and not source.is_symlink() and source.stat().st_size<=limit and sha(source)==plan['inputs'][name],'Lineage worker input drift/type/size')
        memory=Path('/sys/fs/cgroup');require((memory/'memory.max').read_text().strip()==str(CAPS['memoryBytes']) and (memory/'memory.swap.max').read_text().strip()=='0','Lineage hard memory/swap')
        tmp=os.statvfs('/tmp');require(tmp.f_blocks*tmp.f_frsize==CAPS['tmpBytes'] and resource.getrlimit(resource.RLIMIT_FSIZE)==(CAPS['fileBytes'],CAPS['fileBytes']),'Lineage tmp/file guards')
        if plan['stage']=='controls':
            import coarse_osm_lineage_v1_test as tests
            result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
            save(root,'controls.json',{'tests':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)})
            require(result.wasSuccessful() and result.testsRun==12 and not result.skipped,'Lineage target controls failed')
            rows=tests.fixture();raw=b''.join(canonical(r)+b'\n' for r in rows);factory=lambda:io.BytesIO(raw);baseline=tests.baseline(rows)
        else:
            from coarse_osm_bulk_pbf import stat_key
            path=Path('/inputs/captured.jsonl');before=stat_key(path);factory=lambda:path.open('rb');baseline=next(p for p in json.loads(Path('/inputs/baseline.json').read_bytes())['profiles'] if p['id']=='major-roads')
        report=build(factory,snapshot=plan['sourceSnapshotUtc'],windows=plan['windows'],baseline=baseline,caps=plan['dataCaps'],writer=emit,check=check)
        if plan['stage']=='run':require(before==stat_key(path) and report['captureReceipt']['sha256']==plan['inputs'][next(iter(SOURCES))] and report['captureReceipt']['types']=={'node':1123919,'relation':4900,'way':239253} and report['captureReceipt']['rows']==report['captureReceipt']['memberships']==1368072,'Lineage complete unchanged input')
        require(not any(report[k] for k in ('carPolicyReviewed','etaQualified','nationalArtifactBuilt','vercelQualified','modelChanged')),'Lineage premature model/permission admission')
        save(root,'report.json',report);save(root,'artifacts.json',roster)
        save(root,'result.json',{'status':'passed_way_lineage_geometry_prototype','stage':plan['stage'],'reportSha256':sha(root/'report.json'),'artifactsSha256':sha(root/'artifacts.json'),'seconds':time.monotonic()-began,'outputBytesMetered':written,'modelChanged':False,'etaQualified':False})
        return 0
    except BaseException as error:
        save(root,'worker-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:2000],'sourceOrModelAdmitted':False});return 2
    finally:
        save(root,'metrics.json',{name:(Path('/sys/fs/cgroup')/name).read_text().strip() for name in ['memory.max','memory.swap.max','memory.peak','memory.events']})
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


def isolation(observed):
    host=observed['HostConfig'];expected={'NetworkMode':'none','Memory':CAPS['memoryBytes'],'MemorySwap':CAPS['memoryBytes'],'ReadonlyRootfs':True,'NanoCpus':1000000000,'PidsLimit':32,'Tmpfs':{'/tmp':'rw,size=64m'}}
    require(observed['Image']==IMAGE and all(host[k]==v for k,v in expected.items()),'Lineage observed isolation')
    require(not host.get('CapAdd') and {x.removeprefix('CAP_') for x in host['CapDrop']}=={'ALL'} and 'no-new-privileges' in host['SecurityOpt'],'Lineage capabilities')
    require(all(not m['RW'] for m in observed['Mounts'] if m['Destination']!='/work'),'Lineage readonly inputs')
    require({u['Name']:(u['Soft'],u['Hard']) for u in host['Ulimits']}=={'core':(0,0),'fsize':(CAPS['fileBytes'],CAPS['fileBytes'])},'Lineage file/core limits')


def driver(plan,recipe,pin):
    from prepare_osm_native_lock_v1 import cleanup_owned
    repo=Path(__file__).resolve().parents[1];root=repo/OUTPUTS[plan['stage']];require(not root.exists(),'Lineage fresh output required');root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner=uuid.uuid4().hex;name='geo-planner-lineage-'+owner[:12];began=time.monotonic();identity=child=None;code=2
    save(root,'owner.json',{'label':owner,'name':name,'image':IMAGE})
    def check():
        require(time.monotonic()-began<CAPS['hostSeconds']-10,'Lineage host deadline')
        require(sum(p.stat().st_size for p in root.rglob('*') if p.is_file())<=CAPS['ownedBytes'],'Lineage owned byte cap')
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=10)
    try:
        for name_input,pin_input in plan['inputs'].items():
            source=repo/name_input;limit=plan['dataCaps']['inputBytes'] if mounts(plan['stage'])[name_input]=='/inputs/captured.jsonl' else 4194304
            require(source.is_file() and not source.is_symlink() and source.stat().st_size<=limit and sha(source)==pin_input,'Lineage host input drift/type/size')
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
              '--memory=2g','--memory-swap=2g','--cpus=1','--pids-limit=32','--tmpfs','/tmp:rw,size=64m','--ulimit','core=0:0','--ulimit','fsize=134217728:134217728','--env','PYTHONPATH=/code','--env','LD_LIBRARY_PATH=/runtime']
        for source,destination in mounts(plan['stage']).items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_lineage_v1.py','/inputs/recipe.json',pin,'--worker']
        created=call(args);require(created.returncode==0,created.stderr);identity=created.stdout.strip();observed=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(observed)
        save(root,'container-initial.json',{'Image':observed['Image'],'HostConfig':observed['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in observed['Mounts']]})
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:check();time.sleep(.25)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0];save(root,'container-result.json',{'State':final['State'],'clientExitCode':child.returncode})
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Lineage worker failed/OOM');code=0
    except BaseException as error:save(root,'driver-failure.json',{'errorType':type(error).__name__,'error':str(error)[:2000]})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    save(root,'run-summary.json',{'exitCode':code,'seconds':time.monotonic()-began,'networkRequests':0,'pbfOrNativeHelperReads':0,'stage':plan['stage'],'modelChanged':False});return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    recipe=Path(args.recipe).resolve();require(sha(recipe)==args.sha256,'Lineage recipe checksum');plan=json.loads(recipe.read_bytes());validate(plan)
    raise SystemExit(worker(plan) if args.worker else driver(plan,recipe,args.sha256))
