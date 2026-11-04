"""Single-use bounded packed-country controls, encoding or independent audit."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
SOURCE = 'data/coarse-quality/us-osm-car-cost-country-run-v1'
CAPTURE = 'data/coarse-quality/us-osm-car-cost-graph-captured-v5'
REFERENCE = 'data/coarse-quality/us-osm-car-packed-equivalence-v1'
OUTPUTS = {stage:'data/coarse-quality/us-osm-car-packed-country-'+stage+'-v1' for stage in ('controls','run','audit')}
IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
CAPS = {'memoryBytes':4294967296,'tmpBytes':268435456,'fileBytes':67108864,
        'ownedBytes':{'controls':67108864,'run':268435456,'audit':67108864},
        'workerSeconds':{'controls':180,'run':1800,'audit':1800},
        'hostSeconds':{'controls':240,'run':1860,'audit':1860}}


def require(ok, message):
    if not ok:raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def load(path):return json.loads(Path(path).read_bytes())


def write(root, name, value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();path=root/name
    require(path.parent==root and not path.exists() and len(raw)<=2097152,'Packed fresh bounded record')
    with path.open('xb') as stream:stream.write(raw)


def validate(plan):
    stage=plan['stage'];require(stage in OUTPUTS,'Packed stage')
    require(plan['source']==SOURCE and plan['output']==OUTPUTS[stage] and plan['image']==IMAGE and plan['caps']==CAPS,'Packed exact configuration')
    require(plan['priorReserveBytes']==64500000000 and plan['metadataScratchReserveBytes']==104857600,'Packed reserve identity')
    require(64500000000+sum(plan['newClosedAllocations'].values())+104857600+CAPS['ownedBytes'][stage]+CAPS['tmpBytes']<68719476736,'Packed retained envelope')
    require(set(plan['mounts'])==set(plan['hostFiles']) and len(set(plan['mounts'].values()))==len(plan['mounts']),'Packed input roster')
    for src,dest in plan['mounts'].items():
        require(not Path(src).is_absolute() and '..' not in Path(src).parts and dest.startswith(('/code/','/reference/','/runtime/','/repo/','/native/')),'Packed input path')
        require(not src.endswith(('.pbf','/001.bin','.sqlite')) and 'primary-index' not in src,'Packed no raw source/DB/fine input')
    require(plan['workerFiles']=={dest:plan['hostFiles'][src] for src,dest in plan['mounts'].items()},'Packed worker bindings')
    if stage=='run':
        require(plan['admission']['nativeLinuxControls']==8 and plan['admission']['capturedWireBytesIdentical']==1027089 and plan['admission']['independentCapturedAuditPassed'],'Packed before national encoding')


def expected(repo, source):
    facts=load(repo/source/'audit.json')['facts']
    return [facts[key] for key in ('selectedNodes','anchors','majorWays','preClosureArcs','postClosureArcs','supportedViaNodeRules')]


def worker(plan):
    sys.path.insert(0,'/code')
    from coarse_timing_input import start_watchdog
    from coarse_osm_car_packed_audit_v1 import audit
    import unittest
    root=Path('/work');repo=Path('/repo');stage=plan['stage'];began=time.monotonic();timer=start_watchdog(CAPS['workerSeconds'][stage])
    try:
        validate(plan)
        for name,pin in plan['workerFiles'].items():require(sha(name)==pin,'Packed worker input binding '+name)
        cgroup=Path('/sys/fs/cgroup');require((cgroup/'memory.max').read_text().strip()==str(CAPS['memoryBytes']) and (cgroup/'memory.swap.max').read_text().strip()=='0','Packed hard memory/swap')
        tmp=os.statvfs('/tmp');require(tmp.f_blocks*tmp.f_frsize==CAPS['tmpBytes'] and resource.getrlimit(resource.RLIMIT_FSIZE)==(CAPS['fileBytes'],CAPS['fileBytes']),'Packed hard tmp/file')
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(['coarse_osm_car_packed_audit_v1_test','coarse_osm_car_packed_controller_v1_test']))
        controls={'tests':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)}
        write(root,'controls.json',controls);require(controls=={'tests':12,'successful':True,'failures':0,'errors':0,'skips':0},'Packed independent auditor controls')
        if stage=='controls':
            result=audit(repo/CAPTURE/'cost-facts',repo/REFERENCE/'routing',expected(repo,CAPTURE))
        elif stage=='run':
            from coarse_osm_car_packed_native_v1 import NativePacked
            native=NativePacked('/native/car-packed.so',plan['artifactSha256'])
            output=root/'routing';output.mkdir();start=time.monotonic()
            result=native.encode(repo/SOURCE/'cost-facts',output,expected(repo,SOURCE))
            result.update(status='national_packed_routing_encoded_audit_pending',secondsNativeEncoding=time.monotonic()-start,
                          snappingAndGeographyBuilt=False,etaQualified=False,vercelQualified=False)
            artifacts={str(path.relative_to(root)):{'bytes':path.stat().st_size,'sha256':sha(path)} for path in sorted(output.iterdir())}
            require(sum(row['bytes'] for row in artifacts.values())==result['payloadBytes']<=192*1048576,'Packed total native output')
            write(root,'artifacts.json',artifacts)
        else:
            result=audit(repo/SOURCE/'cost-facts',repo/OUTPUTS['run']/'routing',expected(repo,SOURCE))
        result.update(secondsIncludingBindingsControlsAndOperation=time.monotonic()-began,modelChanged=False,networkRequests=0,applicationDbReads=0)
        write(root,'result.json',result);return 0
    except BaseException as error:
        write(root,'worker-failure.json',{'errorType':type(error).__name__,'error':str(error)[:2000]});return 2
    finally:
        write(root,'metrics.json',{name:(Path('/sys/fs/cgroup')/name).read_text().strip() for name in ('memory.max','memory.swap.max','memory.peak','memory.events','cpu.stat')})
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


def driver(plan, recipe, repo):
    sys.path.insert(0,str(repo/'scripts'))
    from coarse_osm_python_bindings_v1 import require_bindings
    from coarse_osm_full_monitor_v1 import owned_usage
    from prepare_osm_native_lock_v1 import cleanup_owned,settle_error
    validate(plan)
    require_bindings(repo,['scripts/coarse_osm_car_packed_audit_v1.py','scripts/coarse_osm_car_packed_audit_v1_test.py','scripts/coarse_osm_car_packed_controller_v1_test.py',str(HERE.relative_to(repo)/'packed_country_driver_v1.py')],plan['mounts'],[str(HERE.relative_to(repo))])
    stage=plan['stage'];root=repo/OUTPUTS[stage];require(not root.exists(),'Packed fresh root');root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json')
    began=time.monotonic();owner=uuid.uuid4().hex;name='geo-planner-packed-'+stage+'-'+owner[:12];identity=child=None;code=2
    write(root,'owner.json',{'name':name,'label':owner,'image':IMAGE})
    def check():
        require(time.monotonic()-began<CAPS['hostSeconds'][stage]-15,'Packed host deadline')
        usage=owned_usage(root);require(usage['conservativeAllocatedBytes']<=CAPS['ownedBytes'][stage] and usage['entries']<=1024,'Packed owned bytes/entries')
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=10)
    try:
        for src,pin in plan['hostFiles'].items():check();require(sha(repo/src)==pin,'Packed host input binding '+src)
        if stage!='controls':
            parent=load(repo/SOURCE/'owner.json');absent=call(['docker','inspect',parent['name']])
            require(absent.returncode!=0 and 'No such' in absent.stderr and load(repo/SOURCE/'cleanup.json')['independentInspectAbsent'],'Packed closed source owner')
        if stage=='audit':require(load(repo/OUTPUTS['run']/'cleanup.json')['independentInspectAbsent'] and load(repo/OUTPUTS['run']/'run-summary.json')['exitCode']==0,'Packed closed successful run before audit')
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--tmpfs','/tmp:rw,size=256m','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864','--env','PYTHONPATH=/code:/reference','--env','LD_LIBRARY_PATH=/runtime']
        for src,dest in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/src},dst={dest},readonly']
        args+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/packed_country_driver_v1.py','/inputs/recipe.json',sha(recipe),'--worker']
        created=call(args);require(created.returncode==0,created.stderr);identity=created.stdout.strip();require(len(identity)==64,'Packed exact owned identity')
        initial=json.loads(call(['docker','inspect',identity]).stdout)[0];host=initial['HostConfig']
        require(initial['Image']==IMAGE and host['NetworkMode']=='none' and host['Memory']==host['MemorySwap']==CAPS['memoryBytes'] and host['NanoCpus']==2000000000 and host['PidsLimit']==64 and host['Tmpfs']=={'/tmp':'rw,size=256m'} and host['ReadonlyRootfs'],'Packed observed isolation')
        require(not host.get('CapAdd') and set(host['CapDrop'])=={'ALL'} and 'no-new-privileges' in host['SecurityOpt'] and all(not mount['RW'] for mount in initial['Mounts'] if mount['Destination']!='/work'),'Packed capabilities/readonly inputs')
        write(root,'container-initial.json',{'Image':initial['Image'],'HostConfig':host,'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in initial['Mounts']]})
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:check();time.sleep(.5)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0];write(root,'container-result.json',{'State':final['State'],'clientExitCode':child.returncode})
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Packed worker failed/OOM');code=0
    except BaseException as error:write(root,'driver-failure.json',{'errorType':type(error).__name__,'error':str(error)[:2000]})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        if not (root/'container-result.json').exists():settle_error(call,identity,name,owner,root,child.returncode if child is not None else None)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    write(root,'run-summary.json',{'exitCode':code,'secondsIncludingBindingsOperationAndCleanup':time.monotonic()-began,'sourcePbfReads':0,'sourceConstructorExecutions':0,'networkRequests':0,'modelChanged':False});return code


if __name__=='__main__':
    recipe=Path(sys.argv[1]).resolve();require(sha(recipe)==sys.argv[2],'Packed frozen recipe');plan=load(recipe)
    raise SystemExit(worker(plan) if '--worker' in sys.argv else driver(plan,recipe,HERE.parents[2]))
