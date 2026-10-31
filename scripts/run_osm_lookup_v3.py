"""Frozen qualification and ABBA replay of saved coordinate queries, no PBF mount."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import struct
import subprocess
import sys
import time
import unittest
import uuid

from coarse_osm_build_v1 import sha
from coarse_osm_country_screen_v1 import BoundedCodec, ProbeReader, owned_usage
from coarse_osm_country_screen_v4 import Resources
from coarse_osm_lookup_v3 import Reader
from coarse_osm_data import verify_worker_inputs
from coarse_osm_records import canonical
from coarse_timing_input import require,start_watchdog
from prepare_osm_input_v3 import capacity
from prepare_osm_native_lock_v1 import cleanup_owned,settle_error
from run_osm_country_screen_v4 import IMAGE,SITE,RUNTIME,isolation

REPORT='docs/evidence/coarse-osm-lookup-2026-10-30'
ARTIFACT='data/coarse-quality/us-osm-country-controls-v5/build/country-screen.so'
ARTIFACT_SHA='9c81c86e3605738430b1c8f9f762bce71830740e5c46737485371ef8c0561166'
PROBE='data/coarse-quality/us-osm-country-screen-v4/screen/pass-b/probe'
QUERIES='data/coarse-quality/us-osm-way-batch-run-v2'
TINY='data/coarse-quality/us-osm-country-controls-v5/controls'
GLOBAL='docs/evidence/coarse-osm-country-exec-2026-10-30/screen-raw-v4/screen/pass-b'
PARENT_SEAL='f43b43173e5f667b6b19d525c0a0833c4a8f804bca6a26447c20fc9ead64ca83'
OUTPUTS={stage:f'data/coarse-quality/us-osm-lookup-v3-{stage}' for stage in ('controls','run')}
CAPS=dict(hostSeconds=1200,hostWorkSeconds=1140,workerSeconds=900,caseSeconds=180,
          rowsEach=80000000,callsEach=20000,ioEach=12*1024**3)
CONTROL_CAPS=CAPS|dict(hostSeconds=600,hostWorkSeconds=570,workerSeconds=300,caseSeconds=60,rowsEach=2000000,callsEach=10000,ioEach=64*1024**2)
PRODUCERS={'scripts/coarse_osm_lookup_v3.py','scripts/coarse_osm_lookup_v3_test.py','scripts/run_osm_lookup_v3.py'}
WITNESS=struct.Struct('<qdd')
GATES={'newMeanPointsRatioMaximum':0.9,'completeCaseMeanNoWorse':True}


def validate(plan):
    stage=plan['stage'];require(stage in OUTPUTS and plan['phase']=='saved_lookup_v3','Lookup phase/stage')
    require(plan['caps']==(CAPS if stage=='run' else CONTROL_CAPS) and plan['gates']==GATES,'Lookup frozen caps/gates')
    require(plan['output']==OUTPUTS[stage] and plan['imageId']==IMAGE and plan['network']=='none','Lookup output/image/network')
    require(plan['artifact']=={'path':ARTIFACT,'sha256':ARTIFACT_SHA} and plan['parentSeal']==PARENT_SEAL,'Lookup exact artifact/parent')
    require(plan['site']==SITE and plan['runtime']==RUNTIME and plan['caseOrder']==['old','new','new','old'],'Lookup runtime/order')
    require(not any(name.endswith(('.pbf','.osm','.bin.pbf')) for name in plan['inputs']),'Lookup refuses PBF source')
    for name,destination in plan['mounts'].items():
        require('..' not in Path(name).parts and (name.startswith(('scripts/','docs/evidence/')) or name in (QUERIES+'/ledger.json',TINY+'/reference-fields.json')),'Lookup code/record mount')
        require(destination.startswith(('/code/','/inputs/')) and plan['workerFiles'][destination]==plan['inputs'][name],'Lookup mounted binding')
    for name in plan['inputs']:
        require('..' not in Path(name).parts and (name.startswith(('scripts/','docs/evidence/',SITE+'/',PROBE+'/',QUERIES+'/witness/',TINY+'/two-pass/pass-b/probe/'))
                or name in (ARTIFACT,QUERIES+'/ledger.json',TINY+'/reference-fields.json',*RUNTIME.values())),'Lookup input closure')
    require(plan['workerFiles']['/artifact/helper.so']==plan['inputs'][ARTIFACT]==ARTIFACT_SHA,'Lookup artifact binding')
    if stage=='run':
        admission=plan['admission']
        require(admission['qualified'] and admission['tests']==6 and admission['skips']==0 and admission['positiveReferences']==400,'Lookup target qualification')
        require(set(admission['producers'])==PRODUCERS and all(plan['inputs'].get(name)==pin for name,pin in admission['producers'].items()),'Lookup complete admitted producer binding')
        require(plan['inputs'][REPORT+'/controls-plan.json']==admission['recipeSha256'] and plan['inputs'][REPORT+'/verify_controls.py']==admission['proofSha256'],'Lookup independent proof binding')


def reader(kind,caps,path='/probe'):
    codec=BoundedCodec('/artifact/helper.so',ARTIFACT_SHA,row_budget=caps['rowsEach'],calls=caps['callsEach'])
    instance=(ProbeReader if kind=='old' else Reader)(path,codec,index_limit=384*1024**2,catalog_limit=4*1024**2,read_limit=caps['ioEach'])
    return instance,codec


def statistics(instance,codec):
    return dict(authenticatedShardBytes=instance.loaded_bytes,decodedRows=codec.decoded_rows,codecCalls=codec.calls,
                catalogBytes=instance.catalog_bytes,hits=instance.hits,misses=instance.misses,evictions=instance.evictions)


def run_case(kind,number,ledger,caps,resources):
    started=time.monotonic();watchdog=start_watchdog(caps['caseSeconds']);instance=None
    try:
        instance,codec=reader(kind,caps);setup=time.monotonic()-started;points_seconds=0.;count=0;digest=hashlib.sha256()
        for row in ledger:
            resources.check();require(time.monotonic()-started<caps['caseSeconds'],'Lookup replay deadline')
            raw=(Path('/queries')/row['file']).read_bytes()
            require(len(raw)==row['references']*WITNESS.size and hashlib.sha256(raw).hexdigest()==row['witnessSha256'],'Lookup witness binding')
            entries=list(WITNESS.iter_unpack(raw));keys=[entry[0] for entry in entries]
            before=time.monotonic();actual=instance.points(keys);points_seconds+=time.monotonic()-before
            require(len(actual)==len(entries),'Lookup returned occurrences')
            for (identity,x,y),point in zip(entries,actual):
                require(struct.pack('<dd',x,y)==struct.pack('<dd',*point),'Lookup replay exact ordered coordinate bits')
                digest.update(WITNESS.pack(identity,*point))
            count+=len(entries)
        result=dict(kind=kind,references=count,setupSeconds=setup,pointsSeconds=points_seconds,
                    orderedWitnessSha256=digest.hexdigest(),statistics=statistics(instance,codec),secondsBeforeRecordClose=time.monotonic()-started)
        resources.write(resources.root/f'case-{number}.json',result)
        require(time.monotonic()-started<caps['caseSeconds'],'Lookup complete case deadline')
        result['secondsThroughRecordClose']=time.monotonic()-started
        resources.write(resources.root/f'case-{number}-close.json',{'secondsThroughRecordClose':result['secondsThroughRecordClose'],'scope':'Includes case record close, excludes this footer serialization.'})
        return result
    finally:
        if instance is not None:instance.close()
        if watchdog.poll() is None:watchdog.terminate()
        watchdog.wait(timeout=5)


def worker(plan,root):
    caps=plan['caps'];root=Path(root);resources=Resources(root,seconds=caps['workerSeconds']);watchdog=start_watchdog(caps['workerSeconds'])
    try:
        verify_worker_inputs(plan);resources.check(force=True)
        require(resource.getrlimit(resource.RLIMIT_FSIZE)==(67108864,67108864),'Lookup file limit')
        tmp=os.statvfs('/tmp');require(tmp.f_blocks*tmp.f_frsize==268435456,'Lookup tmp capacity')
        if plan['stage']=='controls':
            suite=unittest.defaultTestLoader.loadTestsFromName('coarse_osm_lookup_v3_test')
            outcome=unittest.TextTestRunner(verbosity=2).run(suite)
            resources.write(root/'controls.json',dict(tests=outcome.testsRun,successful=outcome.wasSuccessful(),skips=len(outcome.skipped)))
            require(outcome.wasSuccessful() and not outcome.skipped and outcome.testsRun==6,'Lookup target controls')
            fields=json.loads(Path('/inputs/fields.json').read_text());coords={row['id']:(row['lon'],row['lat']) for row in fields if row['type']=='node'}
            keys=[identity for row in fields if row['type']=='way' for identity in row['nodes']]
            expected=b''.join(struct.pack('<dd',*coords[key]) for key in keys);proof=[]
            for kind in ('old','new'):
                instance,codec=reader(kind,caps,'/tiny')
                try:
                    actual=b''.join(struct.pack('<dd',*point) for point in instance.points(keys));require(actual==expected,'Lookup tiny native coordinate oracle')
                    proof.append(dict(kind=kind,references=len(keys),coordinateBitsSha256=hashlib.sha256(actual).hexdigest(),statistics=statistics(instance,codec)))
                finally:instance.close()
            require(proof[0]['statistics']==proof[1]['statistics'],'Lookup tiny identical integrity/decoding')
            resources.write(root/'positive.json',proof);resources.write(root/'result.json',{'status':'lookup_controls_passed','nationalPbfRead':False});return 0
        ledger=json.loads(Path('/inputs/ledger.json').read_text())
        require(len(ledger)==135 and sum(row['references'] for row in ledger)==2135008,'Lookup exact saved cohort')
        cases=[run_case(kind,number,ledger,caps,resources) for number,kind in enumerate(plan['caseOrder'])]
        require(all(case['statistics']==cases[0]['statistics'] and case['orderedWitnessSha256']==plan['expectedWitnessSha256'] and case['references']==2135008 for case in cases),'Lookup equal integrity/cache/correctness accounting')
        old=[case for case in cases if case['kind']=='old'];new=[case for case in cases if case['kind']=='new']
        means={kind:{field:sum(case[field] for case in rows)/2 for field in ('pointsSeconds','secondsThroughRecordClose')} for kind,rows in [('old',old),('new',new)]}
        passed=means['new']['pointsSeconds']<=plan['gates']['newMeanPointsRatioMaximum']*means['old']['pointsSeconds'] and means['new']['secondsThroughRecordClose']<=means['old']['secondsThroughRecordClose']
        resources.write(root/'result.json',dict(status='lookup_replay_passed' if passed else 'lookup_performance_gate_failed',cases=cases,means=means,
                        performanceGatesPassed=passed,nationalPbfRead=False,fullIndexAllocated=False,modelChanged=False))
        return 0 if passed else 2
    except BaseException as error:
        (root/'worker-failure.json').write_bytes(canonical(dict(status='stopped',error=str(error),nationalPbfRead=False))+b'\n');return 2
    finally:
        try:resources.write(root/'metrics-end.json',resources.result())
        finally:
            if watchdog.poll() is None:watchdog.terminate()
            watchdog.wait(timeout=5)


def driver(recipe,pin):
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==pin,'Lookup exact recipe path/hash')
    plan=json.loads(recipe.read_text());validate(plan);caps=plan['caps'];root=repo/plan['output'];require(not root.exists(),'Lookup fresh exact output')
    root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json');started=time.monotonic();owner=uuid.uuid4().hex
    name='geo-planner-lookup-v3-'+owner[:12];identity=child=None;success=False
    def save(name,value):(root/name).write_bytes(canonical(value)+b'\n')
    def check():
        require(time.monotonic()-started<caps['hostWorkSeconds'],'Lookup host deadline')
        require(owned_usage(root)['conservativeAllocatedBytes']<768*1024**2 and shutil.disk_usage(root).free>=2147483648,'Lookup host allocation/headroom')
    def call(args):check();return subprocess.run(args,capture_output=True,text=True,timeout=15)
    save('owner.json',dict(name=name,label=owner,image=IMAGE,labelKey='geo-planner.stream-owner'))
    try:
        for input_path,expected in plan['inputs'].items():check();require(sha(repo/input_path)==expected,'Lookup input drift: '+input_path)
        measured=capacity(repo);require(measured['dockerMemoryBytes']>=6442450944 and measured['hostMemoryBytes']>=8589934592,'Lookup capacity');save('capacity-at-start.json',measured)
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL',
              '--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864',
              '--tmpfs','/tmp:rw,size=256m','--env','LD_LIBRARY_PATH=/tools/runtime','--env','PYTHONPATH=/code:/tools/site']
        for input_path,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/input_path},dst={destination},readonly']
        for runtime_name,input_path in RUNTIME.items():args+=['--mount',f'type=bind,src={repo/input_path},dst=/tools/runtime/{runtime_name},readonly']
        args+=['--mount',f'type=bind,src={repo/SITE},dst=/tools/site,readonly','--mount',f'type=bind,src={repo/ARTIFACT},dst=/artifact/helper.so,readonly',
               '--mount',f'type=bind,src={repo/(TINY+"/two-pass/pass-b/probe")},dst=/tiny,readonly']
        for filename in ('global-catalog.json','global-directory.bin'):args+=['--mount',f'type=bind,src={repo/GLOBAL/filename},dst=/inputs/global/{filename},readonly']
        if plan['stage']=='run':args+=['--mount',f'type=bind,src={repo/PROBE},dst=/probe,readonly','--mount',f'type=bind,src={repo/(QUERIES+"/witness")},dst=/queries,readonly']
        args+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,
               '-B','/code/run_osm_lookup_v3.py','/inputs/recipe.json',pin,'--worker']
        result=call(args);require(result.returncode==0,result.stderr);identity=result.stdout.strip();require(len(identity)==64,'Lookup owned identity')
        initial=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(initial,'controls')
        save('container-initial.json',dict(Image=initial['Image'],HostConfig=initial['HostConfig'],Mounts=[dict(Destination=m['Destination'],RW=m['RW']) for m in initial['Mounts']]))
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:check();time.sleep(.5)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0];save('container-result.json',dict(State=final['State'],clientExitCode=child.returncode))
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Lookup worker exit/gates/OOM');success=True
    except BaseException as error:save('driver-failure.json',dict(status='stopped',error=str(error)))
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        def cleanup_call(args):return subprocess.run(args,capture_output=True,text=True,timeout=15)
        if not (root/'container-result.json').exists():settle_error(cleanup_call,identity,name,owner,root,child.returncode if child else None)
        cleanup_owned(cleanup_call,identity,name,owner,IMAGE,root)
    require(time.monotonic()-started<caps['hostSeconds'],'Lookup final host deadline')
    save('run-summary.json',dict(status='lookup_passed' if success else 'stopped',hostSeconds=time.monotonic()-started,nationalPbfRead=False,networkRequests=0,modelChanged=False))
    return 0 if success else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    require(sha(args.recipe)==args.sha256,'Lookup recipe binding');plan=json.loads(Path(args.recipe).read_text());validate(plan)
    raise SystemExit(worker(plan,'/work') if args.worker else driver(args.recipe,args.sha256))
