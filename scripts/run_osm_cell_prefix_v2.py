"""V2 launcher reuses the immutable prefix worker; corrected recipe closure."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time
import uuid

import run_osm_cell_prefix_v1 as prior
from run_osm_cell_prefix_v1 import (sha,strict_json,require,canonical,owned_usage,capacity,IMAGE,SITE,RUNTIME,
    ARTIFACT,FILE,OWNED,isolation,settle_error,cleanup_owned,worker)

OUTPUTS={stage:f'data/coarse-quality/us-osm-cell-prefix-{stage}-v2' for stage in ('controls','run')}


def validate(plan):
    require(plan['output']==OUTPUTS.get(plan['stage']),'Prefix V2output')
    prior.validate(plan|{'output':prior.OUTPUTS[plan['stage']]})
    require(plan['mounts'].get('scripts/coarse_osm_full_monitor_v1.py')=='/code/coarse_osm_full_monitor_v1.py','Prefix V2monitor closure')


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
               '--entrypoint=python3',IMAGE,'-B','/code/run_osm_cell_prefix_v2.py','/inputs/recipe.json',pin,'--worker']
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
