"""Run separately frozen national native cost-fact preflight or construction."""
import hashlib,json,os
from pathlib import Path
import resource,shutil,subprocess,sys,time,uuid

HERE=Path(__file__).resolve().parent
IMAGE='sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
LIMITS={operation:{'memoryBytes':4294967296,'tmpBytes':268435456,'fileBytes':67108864,'ownedBytes':67108864 if operation=='controls' else 2147483648,'workerSeconds':180 if operation=='controls' else 3600,'hostSeconds':210 if operation=='controls' else 3900} for operation in ('controls','run')}
OUTPUTS={operation:'data/coarse-quality/us-osm-car-cost-country-'+operation+'-v1' for operation in ('controls','run')}
SOURCE='data/coarse-quality/us-osm-car-capacity-run-v3'


def require(ok,message):
    if not ok:raise ValueError(message)
def load(path):return json.loads(Path(path).read_bytes())
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def write(root,name,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();path=root/name
    require(path.parent==root and not path.exists() and len(raw)<=2097152,'Audit fresh bounded record')
    with path.open('xb') as stream:stream.write(raw)


def worker(plan):
    caps=LIMITS[plan['operation']]
    sys.path.insert(0,'/code')
    from coarse_timing_input import start_watchdog
    import importlib.util
    root=Path('/work');timer=start_watchdog(caps['workerSeconds'])
    try:
        require(plan['caps']==caps and plan['image']==IMAGE and plan['source']==SOURCE and plan['output']==OUTPUTS[plan['operation']],'Audit exact configuration')
        require(plan['admission']=={'tests':83,'successful':True,'failures':0,'errors':0,'skips':0},'All83 target constructor controls before captured input')
        for name,pin in plan['workerFiles'].items():require(sha(name)==pin,'Audit worker binding '+name)
        cgroup=Path('/sys/fs/cgroup');require((cgroup/'memory.max').read_text().strip()==str(caps['memoryBytes']) and (cgroup/'memory.swap.max').read_text().strip()=='0','Audit hard memory/swap')
        tmp=os.statvfs('/tmp');require(tmp.f_blocks*tmp.f_frsize==caps['tmpBytes'] and resource.getrlimit(resource.RLIMIT_FSIZE)==(caps['fileBytes'],caps['fileBytes']),'Audit hard tmp/file')
        spec=importlib.util.spec_from_file_location('captured_cost_constructor','/repo/docs/evidence/coarse-osm-car-capacity-2026-11-01/country_cost_entry_v1.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);audit=module.audit
        import unittest
        import coarse_osm_car_cost_country_v1_test as tests
        import coarse_osm_car_cost_country_audit_v1_test as audit_tests
        import coarse_osm_python_bindings_v1_test as binding_tests
        suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(binding_tests),unittest.defaultTestLoader.loadTestsFromModule(tests),unittest.defaultTestLoader.loadTestsFromModule(audit_tests)])
        tested=unittest.TextTestRunner(verbosity=2).run(suite)
        controls={'tests':tested.testsRun,'successful':tested.wasSuccessful(),'failures':len(tested.failures),'errors':len(tested.errors),'skips':len(tested.skipped)}
        write(root,'preparation-controls.json',controls)
        require(controls=={'tests':21,'successful':True,'failures':0,'errors':0,'skips':0},'Captured mutable writer controls before real input')
        result=audit();write(root,'audit.json',result);return 0
    except BaseException as error:
        write(root,'worker-failure.json',{'errorType':type(error).__name__,'error':str(error)[:2000]});return 2
    finally:
        write(root,'metrics.json',{name:(Path('/sys/fs/cgroup')/name).read_text().strip() for name in ('memory.max','memory.swap.max','memory.peak','memory.events','cpu.stat')})
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


def driver(plan,recipe,repo):
    caps=LIMITS[plan['operation']]
    sys.path.insert(0,str(repo/'scripts'))
    from prepare_osm_native_lock_v1 import cleanup_owned,settle_error
    require(plan['caps']==caps and plan['image']==IMAGE and plan['source']==SOURCE and plan['output']==OUTPUTS[plan['operation']],'Audit frozen configuration')
    from coarse_osm_python_bindings_v1 import require_bindings
    from coarse_osm_car_cost_country_v1 import validate
    validate(plan)
    required=require_bindings(repo,plan['dependencyRoots'],plan['mounts'],['docs/evidence/coarse-osm-car-capacity-2026-11-01'])
    require(required<=set(plan['hostFiles']),'Complete transitive worker code hashes before output/data')
    root=repo/OUTPUTS[plan['operation']];require(not root.exists(),'Audit fresh output root');root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json')
    began=time.monotonic();owner=uuid.uuid4().hex;name='geo-planner-car-country-cost-'+owner[:12];identity=child=None;code=2
    write(root,'owner.json',{'name':name,'label':owner,'image':IMAGE})
    def check():
        require(time.monotonic()-began<caps['hostSeconds']-15,'Audit host deadline')
        require(sum(p.stat().st_size for p in root.rglob('*') if p.is_file())<=caps['ownedBytes'],'Audit owned output cap')
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=10)
    try:
        for path,pin in plan['hostFiles'].items():check();require(sha(repo/path)==pin,'Audit host code/closed evidence binding '+path)
        source_owner=load(repo/SOURCE/'owner.json');absent=call(['docker','inspect',source_owner['name']]);require(absent.returncode!=0 and 'No such' in absent.stderr,'Audit source worker must already be absent')
        require(load(repo/SOURCE/'cleanup.json')['independentInspectAbsent'] and load(repo/SOURCE/'run-summary.json')['exitCode']==0,'Audit closed source lifecycle')
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--tmpfs','/tmp:rw,size=256m','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864','--env','PYTHONPATH=/code:/reference:/tools/site','--env','LD_LIBRARY_PATH=/tools/runtime:/runtime']
        for source,dest in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source},dst={dest},readonly']
        args+=['--mount',f'type=bind,src={repo/SOURCE},dst=/repo/{SOURCE},readonly','--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/country_cost_driver_v1.py','/inputs/recipe.json',sha(recipe),'--worker']
        created=call(args);require(created.returncode==0,created.stderr);identity=created.stdout.strip();require(len(identity)==64,'Audit exact worker identity')
        initial=json.loads(call(['docker','inspect',identity]).stdout)[0];host=initial['HostConfig']
        require(initial['Image']==IMAGE and host['NetworkMode']=='none' and host['Memory']==host['MemorySwap']==caps['memoryBytes'] and host['NanoCpus']==2000000000 and host['PidsLimit']==64 and host['Tmpfs']=={'/tmp':'rw,size=256m'} and host['ReadonlyRootfs'],'Audit observed isolation')
        require(not host.get('CapAdd') and set(host['CapDrop'])=={'ALL'} and 'no-new-privileges' in host['SecurityOpt'] and all(not m['RW'] for m in initial['Mounts'] if m['Destination']!='/work'),'Audit capabilities/readonly inputs')
        write(root,'container-initial.json',{'Image':initial['Image'],'HostConfig':host,'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in initial['Mounts']]})
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:check();time.sleep(.5)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0];write(root,'container-result.json',{'State':final['State'],'clientExitCode':child.returncode})
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Audit worker failed/OOM');code=0
    except BaseException as error:write(root,'driver-failure.json',{'errorType':type(error).__name__,'error':str(error)[:2000]})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        if not (root/'container-result.json').exists():settle_error(call,identity,name,owner,root,child.returncode if child is not None else None)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    write(root,'run-summary.json',{'exitCode':code,'secondsIncludingBindingsAuditCleanup':time.monotonic()-began,'operation':plan['operation'],'plannedGuardedCountryScans':int(plan['operation']=='run'),'nativeLibraryUsed':plan['operation']=='run','networkRequests':0,'modelChanged':False});return code


if __name__=='__main__':
    recipe=Path(sys.argv[1]).resolve();require(sha(recipe)==sys.argv[2],'Audit recipe binding');plan=load(recipe)
    raise SystemExit(worker(plan) if '--worker' in sys.argv else driver(plan,recipe,HERE.parents[2]))
