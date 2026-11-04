"""Bounded Linux facts-reader controls on synthetic records only."""
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
OUTPUT='data/coarse-quality/us-osm-attribute-controls-v1'
CAPS={'memoryBytes':536870912,'tmpBytes':33554432,'fileBytes':33554432,'ownedBytes':2097152,'workerSeconds':60,'hostSeconds':120}
MOUNTS={name:'/code/'+Path(name).name for name in ['scripts/run_osm_attribute_controls_v1.py','scripts/coarse_osm_attributes_v1.py','scripts/coarse_osm_attributes_v1_test.py','scripts/coarse_osm_records.py','scripts/coarse_timing_input.py']}
MOUNTS.update({'data/coarse-quality/us-osm-tools-v3/prepare/runtime/libexpat.so.1':'/runtime/libexpat.so.1',
    'docs/evidence/coarse-osm-extraction-2026-10-30/qualification-raw/v15/controls/disk-extract/elements.jsonl':'/inputs/tiny.jsonl'})


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(root,name,value):(root/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def validate(plan):
    require(plan['phase']=='attribute_facts_controls_v1' and plan['image']==IMAGE and plan['output']==OUTPUT and plan['caps']==CAPS,'Facts exact phase/image/caps')
    require(plan['mounts']==MOUNTS and set(plan['inputs'])==set(MOUNTS) and plan['tests']==11,'Facts exact input/test scope')


def worker(plan):
    root=Path('/work');timer=start_watchdog(60);began=time.monotonic()
    try:
        for name,path in MOUNTS.items():
            source=Path(path);require(source.is_file() and not source.is_symlink() and source.stat().st_size<=1048576 and sha(source)==plan['inputs'][name],'Facts worker input drift/type/size')
        memory=Path('/sys/fs/cgroup');require((memory/'memory.max').read_text().strip()==str(CAPS['memoryBytes']) and (memory/'memory.swap.max').read_text().strip()=='0','Facts hard memory/swap')
        tmp=os.statvfs('/tmp');require(tmp.f_blocks*tmp.f_frsize==CAPS['tmpBytes'] and resource.getrlimit(resource.RLIMIT_FSIZE)==(CAPS['fileBytes'],CAPS['fileBytes']),'Facts tmp/file guards')
        import coarse_osm_attributes_v1_test as tests
        from coarse_osm_attributes_v1 import way_facts
        from coarse_osm_records import strict_json
        suite=unittest.defaultTestLoader.loadTestsFromModule(tests);result=unittest.TextTestRunner(verbosity=2).run(suite)
        controls={'tests':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)}
        save(root,'controls.json',controls);require(result.wasSuccessful() and result.testsRun==11 and not result.skipped,'Facts target controls failed')
        rows=[strict_json(line) for line in Path('/inputs/tiny.jsonl').read_bytes().splitlines()];nodes={r['element']['id']:r for r in rows if r['element']['type']=='node'}
        ways=[r for r in rows if r['element']['type']=='way'];require(len(rows)==4 and len(ways)==1,'Facts synthetic fixture scope')
        facts=[way_facts(r,nodes,snapshot=r['publisherStateUtc']) for r in ways]
        require(all(f['sourceRecord']==r and f['carPermission']=='unreviewed' and not f['usableForTiming'] for f,r in zip(facts,ways)),'Facts lost fields or inferred timing permission')
        require(facts[0]['speed']['kmh']==88.51392 and facts[0]['accessTags']=={'access':'private'} and facts[0]['barrierNodeIds']==[1] and not facts[0]['plainNumericWithoutSpeedScopes'],'Facts source scope/unit/barrier preservation')
        save(root,'facts.json',facts)
        save(root,'result.json',{'status':'passed_linux_attribute_facts_controls','controls':controls,'tinyInputSha256':sha('/inputs/tiny.jsonl'),'factsSha256':sha(root/'facts.json'),
             'seconds':time.monotonic()-began,'nativeOrNationalInputRead':False,'sourceBoundaryOrUsableLimitQualified':False,'modelChanged':False})
        return 0
    except BaseException as error:
        save(root,'worker-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:2000],'sourceOrModelAdmitted':False});return 2
    finally:
        save(root,'metrics.json',{name:(Path('/sys/fs/cgroup')/name).read_text().strip() for name in ['memory.max','memory.swap.max','memory.peak','memory.events']})
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


def isolation(observed):
    host=observed['HostConfig'];expected={'NetworkMode':'none','Memory':CAPS['memoryBytes'],'MemorySwap':CAPS['memoryBytes'],'ReadonlyRootfs':True,'NanoCpus':1000000000,'PidsLimit':32,'Tmpfs':{'/tmp':'rw,size=32m'}}
    require(observed['Image']==IMAGE and all(host[k]==v for k,v in expected.items()),'Facts observed isolation')
    require(not host.get('CapAdd') and {x.removeprefix('CAP_') for x in host['CapDrop']}=={'ALL'} and 'no-new-privileges' in host['SecurityOpt'],'Facts capabilities')
    require(all(not m['RW'] for m in observed['Mounts'] if m['Destination']!='/work'),'Facts readonly inputs')
    require({u['Name']:(u['Soft'],u['Hard']) for u in host['Ulimits']}=={'core':(0,0),'fsize':(CAPS['fileBytes'],CAPS['fileBytes'])},'Facts file/core limits')


def driver(plan,recipe,pin):
    from prepare_osm_native_lock_v1 import cleanup_owned
    repo=Path(__file__).resolve().parents[1];root=repo/OUTPUT;require(not root.exists(),'Facts fresh output required');root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner=uuid.uuid4().hex;name='geo-planner-attribute-facts-'+owner[:12];began=time.monotonic();identity=child=None;code=2
    save(root,'owner.json',{'label':owner,'name':name,'image':IMAGE})
    def check():
        require(time.monotonic()-began<110,'Facts host deadline')
        require(sum(p.stat().st_size for p in root.rglob('*') if p.is_file())<=CAPS['ownedBytes'],'Facts owned byte cap')
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=10)
    try:
        for name_input,pin_input in plan['inputs'].items():
            source=repo/name_input;require(source.is_file() and not source.is_symlink() and source.stat().st_size<=1048576 and sha(source)==pin_input,'Facts host input drift/type/size')
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
              '--memory=512m','--memory-swap=512m','--cpus=1','--pids-limit=32','--tmpfs','/tmp:rw,size=32m','--ulimit','core=0:0','--ulimit','fsize=33554432:33554432','--env','PYTHONPATH=/code','--env','LD_LIBRARY_PATH=/runtime']
        for source,destination in MOUNTS.items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_attribute_controls_v1.py','/inputs/recipe.json',pin,'--worker']
        created=call(args);require(created.returncode==0,created.stderr);identity=created.stdout.strip();observed=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(observed)
        save(root,'container-initial.json',{'Image':observed['Image'],'HostConfig':observed['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in observed['Mounts']]})
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:check();time.sleep(.25)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0];save(root,'container-result.json',{'State':final['State'],'clientExitCode':child.returncode})
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Facts worker failed/OOM');code=0
    except BaseException as error:save(root,'driver-failure.json',{'errorType':type(error).__name__,'error':str(error)[:2000]})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    save(root,'run-summary.json',{'exitCode':code,'seconds':time.monotonic()-began,'networkRequests':0,'nationalOrPbfReads':0,'modelChanged':False});return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    recipe=Path(args.recipe).resolve();require(sha(recipe)==args.sha256,'Facts recipe checksum');plan=json.loads(recipe.read_bytes());validate(plan)
    raise SystemExit(worker(plan) if args.worker else driver(plan,recipe,args.sha256))
