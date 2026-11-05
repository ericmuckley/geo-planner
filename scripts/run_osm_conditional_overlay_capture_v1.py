"""Isolated synthetic qualification with the cached native cost kernel only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid
from coarse_timing_input import require,start_watchdog
from prepare_osm_native_lock_v1 import IMAGE,cleanup_owned,settle_error

OUTPUT='data/coarse-quality/us-osm-conditional-overlay-capture-v1'


def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save(root,name,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();require(len(raw)<=1048576,'Overlay small record bound')
    with (root/name).open('xb') as stream:stream.write(raw)


def worker(plan):
    from coarse_osm_country_screen_v1 import owned_usage,resource_metrics
    from coarse_osm_data import verify_worker_inputs
    from coarse_osm_conditional_overlay_capture_v1 import run
    root=Path('/work');timer=start_watchdog(120);began=time.monotonic()
    def check():
        require(time.monotonic()-began<120 and owned_usage(root)['conservativeAllocatedBytes']<=67108864,'Captured overlay deadline/storage')
    try:
        c=Path('/sys/fs/cgroup');require((c/'memory.max').read_text().strip()==str(4*1024**3) and (c/'memory.swap.max').read_text().strip()=='0','Captured overlay memory/swap')
        quota,period=map(int,(c/'cpu.max').read_text().split());require(quota==2*period,'Captured overlay CPU')
        verify_worker_inputs({'workerFiles':{dest:plan['inputs'][name] for name,dest in plan['mounts'].items()}})
        require(not Path('/source.pbf').exists(),'Captured overlay has no national source')
        result=run(plan,root,check)
        save(root,'report.json',result|{'workerSecondsIncludingBindingsMergeAndAudit':time.monotonic()-began});return 0
    except BaseException as error:save(root,'failure.json',{'error':repr(error),'workerSeconds':time.monotonic()-began});return 2
    finally:
        save(root,'metrics.json',resource_metrics())
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


def driver(recipe,pin,plan):
    from coarse_osm_full_monitor_v1 import owned_usage
    from run_osm_country_screen_v1 import isolation
    repo=Path(__file__).resolve().parents[1];root=repo/OUTPUT
    require(plan['output']==OUTPUT and plan['tests']==18 and plan['admission']=={'tests':18,'successful':True,'failures':0,'errors':0,'skips':0},'Captured overlay exact output/native admission')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+104857600+67108864+268435456<72*1024**3,'Overlay aggregate reservation')
    require(set(plan['inputs'])==set(plan['mounts']),'Overlay exact mounted roster')
    for name,dest in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and dest.startswith(('/code/','/reference/','/inputs/','/artifacts/','/tools/','/facts/')) and not name.endswith(('.pbf','.sqlite')) and (not name.endswith('.jsonl') or dest=='/facts/capture/deferred-relations.jsonl'),'Overlay synthetic-only input scope')
        require(sha(repo/name)==plan['inputs'][name],'Overlay host binding')
    root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes());began=time.monotonic()
    owner=uuid.uuid4().hex;name='geo-planner-conditional-overlay-'+owner[:12];identity=child=None;code=2
    save(root,'owner.json',{'name':name,'label':owner,'image':IMAGE})
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=15)
    try:
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--tmpfs','/tmp:rw,size=256m','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864','--env','PYTHONPATH=/code:/tools/site:/reference','--env','LD_LIBRARY_PATH=/tools/runtime']
        for source,dest in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source},dst={dest},readonly']
        args+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_conditional_overlay_capture_v1.py','/inputs/recipe.json',pin,'--worker']
        created=call(args);require(created.returncode==0,created.stderr);identity=created.stdout.strip();require(len(identity)==64,'Overlay owned ID')
        observed=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(observed,'controls');save(root,'container-initial.json',observed)
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began<180 and owned_usage(root)['conservativeAllocatedBytes']<=67108864,'Overlay host deadline/storage');time.sleep(.5)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0];save(root,'container-result.json',{'State':final['State'],'clientExitCode':child.returncode})
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Overlay worker exit/OOM');code=0
    except BaseException as error:save(root,'driver-failure.json',{'error':repr(error),'hostSeconds':time.monotonic()-began})
    finally:
        if child and child.poll() is None:child.kill();child.wait(timeout=5)
        if not (root/'container-result.json').exists():settle_error(call,identity,name,owner,root,child.returncode if child else None)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    save(root,'run-summary.json',{'exitCode':code,'hostSecondsIncludingCleanup':time.monotonic()-began,'sourcePbfReads':0,'countryGraphReads':0});return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('pin');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    recipe=Path(args.recipe).resolve();require(sha(recipe)==args.pin,'Overlay recipe pin');plan=json.loads(recipe.read_bytes())
    raise SystemExit(worker(plan) if args.worker else driver(recipe,args.pin,plan))
