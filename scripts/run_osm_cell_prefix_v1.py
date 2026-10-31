"""Measure lossless V1-to-V2 cell conversion on closed parts, without a PBF scan."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import stat
import subprocess
import time
import unittest
import uuid

from coarse_osm_build_v1 import sha
from coarse_osm_country_screen_v4 import Resources
from coarse_osm_data import memory_guard, verify_worker_inputs
from coarse_osm_full_monitor_v1 import owned_usage
from coarse_osm_records import canonical, strict_json
from coarse_osm_window_cells_v1 import Cells
from coarse_osm_window_codec_v1 import ENVELOPE, BODY as OLD_BODY, body as old_body
from coarse_osm_window_codec_v2 import Codec, BODY, body
from coarse_timing_input import require, start_watchdog
from prepare_osm_input_v3 import capacity
from prepare_osm_native_lock_v1 import cleanup_owned, settle_error
from run_osm_country_screen_v4 import IMAGE, SITE, RUNTIME, isolation

REPORT='docs/evidence/coarse-osm-extraction-2026-10-30'
ARTIFACT='data/coarse-quality/us-osm-country-controls-v13/build/country-screen.so'
ARTIFACT_SHA='e82ccc44579ded7e7a6fcae5cdd3a6267250f3f3e00968195e45e567f1c0138e'
RETAINED=55406628967
OWNED=768*1024**2
FILE=64*1024**2
OUTPUTS={stage:f'data/coarse-quality/us-osm-cell-prefix-{stage}-v1' for stage in ('controls','run')}
CAPS={'hostSeconds':1800,'workerSeconds':1500,'inputBytes':2080277463,'parts':31,
      'blocks':400000,'rows':1606229364,'codecRows':8000000000,'codecCalls':1000000}
CONTROL_CAPS=CAPS|{'hostSeconds':600,'workerSeconds':300,'inputBytes':83,'parts':1,'blocks':1,'rows':4,
                  'codecRows':2000000,'codecCalls':100000}


def validate(plan):
    stage=plan['stage'];require(stage in OUTPUTS and plan['phase']=='cell_prefix_conversion_v1','Prefix phase')
    require(plan['caps']==(CAPS if stage=='run' else CONTROL_CAPS),'Prefix exact caps')
    require(plan['output']==OUTPUTS[stage] and plan['imageId']==IMAGE and plan['network']=='none','Prefix output/isolation')
    require(plan['artifact']=={'path':ARTIFACT,'sha256':ARTIFACT_SHA} and plan['site']==SITE and plan['runtime']==RUNTIME,'Prefix qualified runtime')
    require(plan['retainedBytes']==RETAINED and plan['ownedBytes']==OWNED and RETAINED+OWNED+256*1024**2<64*1024**3,'Prefix retained arithmetic')
    require(plan['parent']=={'recipe':REPORT+'/qualification-plan-v13.json','sha256':'e3c3f12d84f0bb0eea3629da292dd6187cf587925eb420c110ca53939ccc2237','tests':65,'skips':0},'Prefix parent admission')
    require(0<len(plan['parts'])==plan['caps']['parts'] and sum(p['bytes'] for p in plan['parts'])==plan['caps']['inputBytes'],'Prefix part census')
    require(len({p['path'] for p in plan['parts']})==len(plan['parts']),'Prefix duplicate input')
    for part in plan['parts']:
        require(type(part['bytes']) is int and 0<part['bytes']<=FILE and len(part['sha256'])==64,'Prefix part bound')
        require('..' not in Path(part['path']).parts and part['path'].startswith('data/coarse-quality/'),'Prefix part path')
    if stage=='run':
        require(len(plan['windows'])==21 and plan['controllerAdmission']['qualified'] and plan['controllerAdmission']['tests']>=8,'Prefix controller admission')
        require(all(plan['inputs'].get(name)==pin for name,pin in plan['controllerAdmission']['producers'].items()),'Prefix controller drift')
    Cells(plan['windows'])
    for name,destination in plan['mounts'].items():
        require('..' not in Path(name).parts and name.startswith(('scripts/','docs/evidence/')) and destination.startswith(('/code/','/inputs/')),'Prefix bounded mount')
        require(plan['inputs'][name]==plan['workerFiles'][destination],'Prefix mounted binding')
    require(plan['inputs'][ARTIFACT]==plan['workerFiles']['/artifacts/helper.so']==ARTIFACT_SHA,'Prefix artifact pin')
    for name in plan['inputs']:
        require(name.startswith(('scripts/','docs/evidence/',SITE+'/')) or name in RUNTIME.values() or name==ARTIFACT,'Prefix input scope')


def measure(path,expected,codec,caps,check=lambda:None,previous=0):
    path=Path(path);before=path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==expected['bytes']<=FILE,'Prefix input kind/size')
    old_hash=hashlib.sha256();new_hash=hashlib.sha256()
    result=dict(blocks=0,rows=0,oldBytes=0,newBytes=0,oldIdBytes=0,newIdBytes=0,idRunBlocks=0,rawIdBlocks=0,cellRuns=0,first=None,last=previous)
    with path.open('rb') as stream:
        while True:
            check();head=stream.read(ENVELOPE.size+OLD_BODY.size)
            if not head:break
            require(len(head)==ENVELOPE.size+OLD_BODY.size,'Prefix truncated header')
            n,first,last,ids,runs=OLD_BODY.unpack_from(head,ENVELOPE.size)
            require(0<n<=4096 and n-1<=ids<=9*(n-1) and 0<runs<=n,'Prefix block declared bounds')
            size=ids+4*runs;require(OLD_BODY.size+size<=65536 and result['oldBytes']+len(head)+size<=expected['bytes'],'Prefix block length')
            tail=stream.read(size);require(len(tail)==size,'Prefix truncated body');raw=head+tail
            _,count,low,high=old_body(raw)
            require(result['last']<low<=high and result['blocks']<caps['blocks'] and result['rows']+count<=caps['rows'],'Prefix ID order/count cap')
            converted=codec.from_v1(raw);payload,new_count,new_low,new_high=body(converted)
            require((new_count,new_low,new_high)==(count,low,high) and len(converted)<=len(raw)+4,'Prefix conversion metadata/size')
            _,_,_,new_ids,id_runs,cell_runs=BODY.unpack_from(payload)
            require(cell_runs==runs and payload[BODY.size+new_ids:]==raw[ENVELOPE.size+OLD_BODY.size+ids:],'Prefix cell stream drift')
            old_hash.update(raw);new_hash.update(converted)
            for key,value in [('blocks',1),('rows',count),('oldBytes',len(raw)),('newBytes',len(converted)),('oldIdBytes',ids),('newIdBytes',new_ids),('idRunBlocks',int(id_runs>0)),('rawIdBlocks',int(id_runs==0)),('cellRuns',runs)]:result[key]+=value
            if result['first'] is None:result['first']=low
            result['last']=high
    require(result['blocks']>0 and result['oldBytes']==expected['bytes'] and old_hash.hexdigest()==expected['sha256'],'Prefix whole-part hash/EOF')
    after=path.lstat()
    require(all(getattr(after,key)==getattr(before,key) for key in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')),'Prefix input changed during conversion')
    return result|{'oldSha256':old_hash.hexdigest(),'convertedSha256':new_hash.hexdigest(),'everyIdAndCellNativeRoundtrip':True}


def worker(plan,root):
    root=Path(root);caps=plan['caps'];resources=Resources(root,seconds=caps['workerSeconds']);watchdog=start_watchdog(caps['workerSeconds'])
    codec=None
    try:
        verify_worker_inputs(plan);memory_guard()
        require(resource.getrlimit(resource.RLIMIT_FSIZE)==(FILE,FILE),'Prefix file limit')
        disk=os.statvfs('/tmp');require(disk.f_blocks*disk.f_frsize==256*1024**2,'Prefix tmp limit')
        if plan['stage']=='run':
            proposal=strict_json(Path('/inputs/proposal.json').read_bytes());require(plan['windows']==proposal['windows'],'Prefix original windows')
            closed=strict_json(Path('/inputs/closed.json').read_bytes())
            require(plan['parts']==[{'path':closed['root']+'/'+name,**{key:item[key] for key in ('bytes','sha256')}} for name,item in closed['roster'].items() if item.get('ignoredPart')],'Prefix original closed parts')
        if plan['stage']=='controls':
            suite=unittest.defaultTestLoader.loadTestsFromName('coarse_osm_cell_prefix_v1_test');result=unittest.TextTestRunner(verbosity=2).run(suite)
            resources.write(root/'controls.json',{'tests':result.testsRun,'successful':result.wasSuccessful(),'skips':len(result.skipped)})
            require(result.wasSuccessful() and not result.skipped and result.testsRun>=8,'Prefix qualification')
        codec=Codec('/artifacts/helper.so',ARTIFACT_SHA,Cells(plan['windows']),row_budget=caps['codecRows'],call_budget=caps['codecCalls'])
        parts=[];previous=0;began=time.monotonic()
        for i,part in enumerate(plan['parts']):
            summary=measure(f'/parts/{i:04d}.bin',part,codec,caps,resources.check,previous)
            parts.append(summary);previous=summary['last']
            resources.write(root/f'part-{i:04d}.json',summary)
        totals={key:sum(p[key] for p in parts) for key in ('blocks','rows','oldBytes','newBytes','oldIdBytes','newIdBytes','idRunBlocks','rawIdBlocks','cellRuns')}
        require(totals['rows']<=caps['rows'] and totals['blocks']<=caps['blocks'],'Prefix aggregate census cap')
        resources.write(root/'result.json',{'status':'passed_prefix_conversion','totals':totals,'parts':len(parts),'conversionSeconds':time.monotonic()-began,
            'codecRows':codec.rows,'codecCalls':codec.calls,'retainedBytes':RETAINED,'ownedLimitBytes':OWNED,'inputUnchanged':True,
            'nationalSourceRead':False,'fullFineIndexRead':False,'completeBankCapacityQualified':False,'modelChanged':False})
        return 0
    except BaseException as error:
        resources.write(root/'failure.json',{'errorType':type(error).__name__,'error':str(error)[:3000],'codecRows':codec.rows if codec else 0,'codecCalls':codec.calls if codec else 0,'modelChanged':False})
        return 2
    finally:
        try:resources.write(root/'metrics-end.json',resources.result())
        finally:
            if watchdog.poll() is None:watchdog.terminate()
            watchdog.wait(timeout=5)


def driver(recipe,pin):
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==pin,'Prefix recipe path/hash')
    plan=strict_json(recipe.read_bytes());validate(plan);caps=plan['caps'];root=repo/plan['output']
    require(not root.exists(),'Prefix new output required');root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json')
    began=time.monotonic();owner=uuid.uuid4().hex;name='geo-planner-cell-prefix-'+owner[:12];identity=child=None;success=False
    def save(filename,value):(root/filename).write_bytes(canonical(value)+b'\n')
    def check():
        require(time.monotonic()-began<caps['hostSeconds']-30,'Prefix host deadline')
        require(owned_usage(root)['conservativeAllocatedBytes']<OWNED and shutil.disk_usage(root).free>=2*1024**3,'Prefix host disk cap')
        require(not (root/'worker.log').exists() or (root/'worker.log').stat().st_size<=2*1024**2,'Prefix log cap')
    def call(args):check();return subprocess.run(args,capture_output=True,text=True,timeout=15)
    save('owner.json',{'name':name,'label':owner,'image':IMAGE,'labelKey':'geo-planner.stream-owner'})
    try:
        for input_path,value in plan['inputs'].items():
            check();path=repo/input_path
            require(path.is_file() and not path.is_symlink() and path.stat().st_nlink==1 and sha(path)==value,'Prefix input drift: '+input_path)
        current=capacity(repo);require(current['hostDiskAvailableBytes']>=3*1024**3 and current['dockerMemoryBytes']>=6*1024**3,'Prefix initial capacity');save('capacity-at-start.json',current)
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL',
              '--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--ulimit','core=0:0','--ulimit',f'fsize={FILE}:{FILE}',
              '--tmpfs','/tmp:rw,size=256m','--env','LD_LIBRARY_PATH=/tools/runtime','--env','PYTHONPATH=/code:/tools/site']
        for source,dest in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source},dst={dest},readonly']
        for filename,source in RUNTIME.items():args+=['--mount',f'type=bind,src={repo/source},dst=/tools/runtime/{filename},readonly']
        for i,part in enumerate(plan['parts']):args+=['--mount',f'type=bind,src={repo/part["path"]},dst=/parts/{i:04d}.bin,readonly']
        args+=['--mount',f'type=bind,src={repo/SITE},dst=/tools/site,readonly','--mount',f'type=bind,src={repo/ARTIFACT},dst=/artifacts/helper.so,readonly',
               '--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly',
               '--entrypoint=python3',IMAGE,'-B','/code/run_osm_cell_prefix_v1.py','/inputs/recipe.json',pin,'--worker']
        result=call(args);require(result.returncode==0,result.stderr);identity=result.stdout.strip();require(len(identity)==64,'Prefix owned identity')
        initial=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(initial,'controls')
        save('container-initial.json',{'Image':initial['Image'],'HostConfig':initial['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in initial['Mounts']]})
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:check();time.sleep(.5)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0];save('container-result.json',{'State':final['State'],'clientExitCode':child.returncode})
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Prefix exit/OOM');success=True
    except BaseException as error:save('driver-failure.json',{'errorType':type(error).__name__,'error':str(error)[:3000]})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        def cleanup_call(args):return subprocess.run(args,capture_output=True,text=True,timeout=15)
        if not (root/'container-result.json').exists():settle_error(cleanup_call,identity,name,owner,root,child.returncode if child else None)
        cleanup_owned(cleanup_call,identity,name,owner,IMAGE,root)
    require(time.monotonic()-began<caps['hostSeconds'],'Prefix final deadline')
    save('run-summary.json',{'status':'passed_prefix_conversion' if success else 'stopped','hostSecondsIncludingBindingsAndCleanup':time.monotonic()-began,'networkRequests':0,'modelChanged':False})
    return 0 if success else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    require(sha(args.recipe)==args.sha256,'Prefix recipe binding');plan=strict_json(Path(args.recipe).read_bytes());validate(plan)
    raise SystemExit(worker(plan,'/work') if args.worker else driver(args.recipe,args.sha256))
