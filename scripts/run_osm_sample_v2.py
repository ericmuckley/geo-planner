"""One frozen offline sample-plan control or fixed saved-sample run; no national input."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest
import uuid

from coarse_osm_build_v1 import sha
from coarse_osm_data import verify_worker_inputs
from coarse_osm_data_v3 import tree_bytes
from coarse_osm_native_lock_v1 import save
from coarse_osm_records import strict_json
from coarse_timing_input import require,start_watchdog
from prepare_osm_input_v3 import capacity
from prepare_osm_native_lock_v1 import IMAGE,settle_error,cleanup_owned
from run_osm_delta_v1 import PROPOSAL,guards,isolation
from coarse_osm_sample_v2 import CAPS,ARTIFACT,SAMPLES,CASES,samples
from coarse_osm_projector_v1 import NativeProjector

ADMISSION='docs/evidence/coarse-osm-sample-plan-2026-10-27/control-acceptance-v2.json'


def layout(phase):
    require(phase in ('controls','sample'),'Sample phase')
    return 'data/coarse-quality/us-osm-sample-'+('controls-v2' if phase=='controls' else 'v2')


def validate(plan):
    require(plan['phase'] in ('controls','sample') and plan['caps']==CAPS,'Sample phase/caps drift')
    require(plan['imageId']==IMAGE and plan['imagePull']=='never' and plan['output']==layout(plan['phase']),'Sample image/output drift')
    require(plan['network']=='none' and plan['artifact']==ARTIFACT and plan['samples']==SAMPLES and plan['cases']==CASES,'Sample artifact/cases/network drift')
    for source,destination in plan['mounts'].items():
        require(source.startswith('scripts/') and source.endswith(('.py','.cpp')) and '..' not in Path(source).parts or source==PROPOSAL or source==ADMISSION and plan['phase']=='sample','No national/source mounts')
        require(destination.startswith('/code/') or source==PROPOSAL and destination=='/'+PROPOSAL or source==ADMISSION and destination=='/inputs/admission.json','Sample code/input path')
        require(plan['inputs'][source]==plan['workerFiles'][destination],'Sample code mount binding')
    require(plan['inputs'][ARTIFACT['path']]==plan['workerFiles']['/artifacts/projector.so']==ARTIFACT['sha256'],'Sample artifact binding')
    expected={'/samples/prefix.pbf':SAMPLES['prefix']['sha256'],'/samples/mixed.jsonl':SAMPLES['mixed']['sha256']} if plan['phase']=='sample' else {}
    require(plan['sampleWorkerFiles']==expected,'Sample-only mount closure')
    if plan['phase']=='sample':
        require(plan['mounts'].get(ADMISSION)=='/inputs/admission.json','Sample controls prerequisite')


def worker(plan,root):
    root=Path(root);watchdog=start_watchdog(CAPS['workerSeconds'])
    try:
        verify_worker_inputs(plan|{'workerFiles':plan['workerFiles']|plan['sampleWorkerFiles']});guards(root,'controls')
        if plan['phase']=='sample':
            admission=strict_json(Path('/inputs/admission.json').read_bytes())
            require(admission['allControlsPassed'] and admission['bothSourceSamplesNotDecoded'] and admission['ownedWorkerIndependentlyRemoved'],'Sample guard prerequisite failed')
            engine=NativeProjector('/artifacts/projector.so',ARTIFACT['sha256'])
            return samples(plan,root,engine)
        import coarse_osm_delta_v2_test as delta
        import coarse_osm_projector_v1_test as projector
        for module in (delta,projector):module.configure_native('/artifacts/projector.so',ARTIFACT['sha256'])
        modules=['coarse_osm_stream_v1_test','coarse_osm_stream_driver_v1_test','coarse_osm_validation_v4_test','coarse_osm_delta_v2_test','coarse_osm_projector_v1_test','coarse_osm_sample_v1_test','coarse_osm_sample_v2_test']
        result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in modules))
        visits=sum(engine.visits for engine in projector.ENGINES);require(visits<=CAPS['aggregateVisits'],'Sample new-projector control visits')
        save(root/'controls.json',{'tests':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
            'projectorAggregateVisits':visits,'priorControls':71,'scope':'Synthetic only; legacy controls keep their frozen separate object/codec bounds. No saved sample mounted or decoded.'})
        return 0 if result.wasSuccessful() and not result.skipped else 2
    except Exception as error:
        save(root/'worker-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:1000],'fullImportAdmitted':False})
        return 2
    finally:
        if watchdog.poll() is None:watchdog.terminate()
        watchdog.wait(timeout=5)


def driver(recipe,expected,output):
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==expected,'Sample recipe path/hash')
    plan=strict_json(recipe.read_bytes());validate(plan)
    root=(repo/output).resolve();require(root==repo/layout(plan['phase']) and not root.exists(),'Sample fresh exact output required')
    root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json')
    began=time.monotonic();deadline=began+CAPS['workSeconds'];hard=began+CAPS['hostSeconds'];owner=uuid.uuid4().hex
    save(root/'owner.json',{'label':owner,'image':IMAGE,'labelKey':'geo-planner.stream-owner'});identity=child=None;code=None;success=False
    phase=root/plan['phase'];phase.mkdir();name='geo-planner-sample-'+plan['phase']+'-'+owner[:12]
    save(phase/'owner.json',{'name':name,'label':owner})
    def check():
        require(time.monotonic()<deadline,'Sample shared host deadline')
        require(tree_bytes(root)<=CAPS['workingBytesIncludingTmp']-CAPS['tmpBytes'],'Sample owned storage cap')
        require(shutil.disk_usage(root).free>=2147483648,'Sample disk headroom')
    def call(args,**kwargs):
        check();return subprocess.run(args,capture_output=True,text=True,timeout=min(15,max(.01,deadline-time.monotonic())),**kwargs)
    try:
        for source,pin in plan['inputs'].items():check();require(sha(repo/source)==pin,'Sample input drift: '+source)
        observed=capacity(repo);require(observed['hostDiskAvailableBytes']>=3221225472 and observed['hostMemoryBytes']>=8589934592 and observed['dockerMemoryBytes']>=6442450944,'Sample capacity')
        save(root/'capacity-at-start.json',observed)
        if plan['phase']=='sample':
            for key,pin in SAMPLES.items():require(sha(repo/pin['path'])==pin['sha256'] and (repo/pin['path']).stat().st_size==pin['bytes'],'Fixed saved sample binding')
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
            '--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864','--tmpfs=/tmp:rw,size=256m','--env','LD_LIBRARY_PATH=/tools/runtime']
        for source,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        if plan['phase']=='sample':
            for key,destination in (('prefix','/samples/prefix.pbf'),('mixed','/samples/mixed.jsonl')):args+=['--mount',f'type=bind,src={repo/SAMPLES[key]["path"]},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={repo/plan["site"]},dst=/tools/site,readonly']
        for filename,source in plan['runtime'].items():args+=['--mount',f'type=bind,src={repo/source},dst=/tools/runtime/{filename},readonly']
        args+=['--mount',f'type=bind,src={repo/ARTIFACT["path"]},dst=/artifacts/projector.so,readonly',
            '--mount',f'type=bind,src={phase},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly',
            '--entrypoint=python3',IMAGE,'-B','/code/run_osm_sample_v2.py','/inputs/recipe.json',expected,'/work','--worker']
        identity=call(args,check=True).stdout.strip();require(len(identity)==64,'Sample owned ID')
        initial=json.loads(call(['docker','inspect',identity],check=True).stdout)[0];isolation(initial,'controls')
        save(phase/'container-initial.json',{'Image':initial['Image'],'HostConfig':initial['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in initial['Mounts']]})
        with (phase/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:
                check();require((phase/'worker.log').stat().st_size<=CAPS['reportBytes'],'Sample log cap');time.sleep(.25)
        code=child.returncode;final=json.loads(call(['docker','inspect',identity],check=True).stdout)[0]
        save(phase/'container-result.json',{'Image':final['Image'],'State':final['State'],'clientExitCode':code})
        require(final['State']['ExitCode']==code and not final['State']['OOMKilled'],'Sample final exit/OOM')
        success=code==0
    except (Exception,KeyboardInterrupt) as error:
        save(root/'driver-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:1000],'fullImportAdmitted':False})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        def cleanup_call(args):return subprocess.run(args,capture_output=True,text=True,timeout=max(1,min(15,hard-time.monotonic())))
        try:
            if not (phase/'container-result.json').exists():settle_error(cleanup_call,identity,name,owner,phase,child.returncode if child is not None else None)
        finally:cleanup_owned(cleanup_call,identity,name,owner,IMAGE,phase)
    require(time.monotonic()-began<CAPS['hostSeconds'],'Sample final host deadline')
    save(root/'run-summary.json',{'status':('sample_controls_passed' if plan['phase']=='controls' else 'fixed_sample_screen_passed') if success else 'stopped','workerClientExitCode':code,
        'hostSecondsIncludingInputHashesControlsCleanup':time.monotonic()-began,'networkRequests':0,'recompiled':False,'savedSamplesMounted':plan['phase']=='sample','nationalSourceMounted':False,
        'nativeMetadataValidatorImplemented':True,'nativeIndexIoImplemented':False,'fullImportAdmitted':False,'modelChanged':False})
    return 0 if success else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('output');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    if args.worker:
        require(sha(args.recipe)==args.sha256,'Sample worker binding');plan=strict_json(Path(args.recipe).read_bytes());validate(plan)
        sys.path.insert(0,'/tools/site');raise SystemExit(worker(plan,args.output))
    raise SystemExit(driver(args.recipe,args.sha256,args.output))
