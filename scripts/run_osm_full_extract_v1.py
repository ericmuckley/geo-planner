"""Frozen two-pass extraction, tiny controller qualification before national use."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import time
import unittest
import uuid

from coarse_osm_build_v1 import sha
from coarse_osm_bulk_pbf import stat_key
from coarse_osm_country_screen_v1 import MAX_VISITS,owned_usage
from coarse_osm_data import memory_guard,verify_worker_inputs
from coarse_osm_full_extract_v2 import extract
from coarse_osm_full_resources_v1 import FullResources,FullScreen,BoundIndexStorage,OWNED_LIMIT,TMP,FILE_LIMIT
from coarse_osm_records import canonical,strict_json
from coarse_timing_input import require,start_watchdog
from prepare_osm_input_v3 import capacity
from prepare_osm_native_lock_v1 import cleanup_owned,settle_error
from run_osm_country_screen_v4 import IMAGE,SOURCE,SITE,RUNTIME,PROPOSAL

REPORT='docs/evidence/coarse-osm-extraction-2026-10-30'
ARTIFACT='data/coarse-quality/us-osm-country-controls-v6/build/country-screen.so'
ARTIFACT_SHA='1084fc1b6e9b1a627b52180fd91df0b46e01a967fbd399c2bad672a4f675f48a'
FIXTURE='data/coarse-quality/us-osm-country-controls-v8/controls'
CATALOG='docs/evidence/coarse-osm-country-exec-2026-10-30/screen-raw-v4/screen/pass-b/global-catalog.json'
SEMANTIC='209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16'
OUTPUTS={stage:f'data/coarse-quality/us-osm-full-extract-{stage}-v1' for stage in ('controls','run')}
RUN_CAPS=dict(hostSeconds=14400,hostWorkSeconds=14340,workerSeconds=13800,passSeconds=6900,hashSeconds=240,
              requiredInitialFreeBytes=80*1024**3,lookupBytesPerPass=4*1024**4,codecRows=48000000000,codecCalls=12000000)
CONTROL_CAPS=RUN_CAPS|dict(hostSeconds=600,hostWorkSeconds=570,workerSeconds=300,passSeconds=90,hashSeconds=30,
                          requiredInitialFreeBytes=3*1024**3,lookupBytesPerPass=64*1024**2,codecRows=2000000,codecCalls=10000)
MODULES=['coarse_osm_full_resources_v1_test','coarse_osm_full_driver_v1_test']


def proposal_for(base,stage,caps):
    proposal=deepcopy(base);limits=proposal['proposedCaps']
    limits.update(workingBytesIncludingTmp=OWNED_LIMIT+TMP,wallSeconds=caps['workerSeconds'],
                  scanNodesPerPass=SOURCE['counts']['node'],scanWaysPerPass=SOURCE['counts']['way'],
                  scanRelationsPerPass=SOURCE['counts']['relation'],scanObjectVisitsTotal=2*MAX_VISITS)
    if stage=='controls':
        proposal['windows']=[{'id':'a','bbox':[0,0,1,1]},{'id':'b','bbox':[.25,.25,.75,.75]}]
        limits.update(sqliteIndexBytesEach=1048576,sqliteMaxPagesEach=256,sqliteCacheBytesEach=8192)
    return proposal


def validate(plan):
    stage=plan['stage'];require(stage in OUTPUTS and plan['phase']=='full_road_extraction_v1','Full phase/stage')
    require(plan['caps']==(RUN_CAPS if stage=='run' else CONTROL_CAPS),'Full exact resource limits')
    require(plan['imageId']==IMAGE and plan['network']=='none' and plan['output']==OUTPUTS[stage],'Full image/output/network')
    require(plan['site']==SITE and plan['runtime']==RUNTIME and plan['artifact']=={'path':ARTIFACT,'sha256':ARTIFACT_SHA},'Full qualified tools')
    require(plan['prototypeQualification']=={'recipe':REPORT+'/qualification-plan-v8.json',
        'sha256':'2f502d0943e30cc5e0133f87838248113422cb218f53a399ca606b8b2ea9559f','tests':260,'skips':0},'Full prototype qualification')
    require(plan['proposal']==PROPOSAL and plan['source']['path'] not in plan['inputs'],'Full proposal/source identity scope')
    require(plan['workerFiles']['/artifacts/helper.so']==plan['inputs'][ARTIFACT]==ARTIFACT_SHA,'Full artifact binding')
    if stage=='run':
        require(plan['source']==SOURCE and plan['catalog']==CATALOG and plan['semantic']==SEMANTIC and plan['highwayWays']==52053199,'Full fixed acquired source/census')
        require(plan['controllerAdmission']['qualified'] and plan['controllerAdmission']['tests']>=12,'Full controller admission')
        require(all(plan['inputs'].get(name)==pin for name,pin in plan['controllerAdmission']['producers'].items()),'Full qualified controller drift')
    else:
        require(plan['source']['path']==FIXTURE+'/full-fixture.pbf' and plan['source']['counts']=={'node':4,'way':3,'relation':2},'Full synthetic qualification source')
        require(plan['catalog']==FIXTURE+'/full-prototype/audit-index/index.json' and plan['highwayWays']==2,'Full synthetic index binding')
        require(plan['referenceOutput']==FIXTURE+'/full-prototype/elements.jsonl','Full synthetic independent output binding')
    for name,destination in plan['mounts'].items():
        require('..' not in Path(name).parts and name.startswith(('scripts/','docs/evidence/',FIXTURE+'/')),'Full code/evidence mount')
        require(destination.startswith(('/code/','/inputs/')) and plan['inputs'][name]==plan['workerFiles'][destination],'Full mounted checksum')
    for name in plan['inputs']:
        require('..' not in Path(name).parts and (name.startswith(('scripts/','docs/evidence/',SITE+'/',FIXTURE+'/')) or name in RUNTIME.values() or name==ARTIFACT),'Full closed input allowlist')
    require(plan['mounts'][plan['catalog']]=='/inputs/catalog.json' and plan['mounts'][PROPOSAL]=='/inputs/proposal.json','Full required catalog/proposal mounts')


def isolation(observed):
    expected={'NetworkMode':'none','Memory':4294967296,'MemorySwap':4294967296,'ReadonlyRootfs':True,
              'NanoCpus':2000000000,'PidsLimit':64,'Tmpfs':{'/tmp':'rw,size=256m'}}
    require(observed['Image']==IMAGE and all(observed['HostConfig'][key]==value for key,value in expected.items()),'Full worker isolation')
    require(all(not m['RW'] for m in observed['Mounts'] if m['Destination']!='/work'),'Full writable input mount')
    host=observed['HostConfig']
    require(not host.get('CapAdd') and {c.removeprefix('CAP_') for c in host['CapDrop']}=={'ALL'} and 'no-new-privileges' in host['SecurityOpt'],'Full capabilities/security')
    require({u['Name']:(u['Soft'],u['Hard']) for u in host['Ulimits']}=={'core':(0,0),'fsize':(FILE_LIMIT,FILE_LIMIT)},'Full file/core limits')


def output_ledger(path,windows):
    counts={window['id']:Counter() for window in windows};unique=Counter();seen=set();occurrences=0
    with Path(path).open('rb') as stream:
        for line in stream:
            row=strict_json(line);element=row['element'];key=element['type'],element['id']
            require(key not in seen and row['elementSha256']==hashlib.sha256(canonical(element)).hexdigest(),'Full normalized typed identity/field digest')
            require(row['windowIds'] and len(set(row['windowIds']))==len(row['windowIds']),'Full window membership duplicates/empty')
            seen.add(key);unique[key[0]]+=1
            for window in row['windowIds']:
                require(window in counts,'Full unknown output window');counts[window][key[0]]+=1;occurrences+=1
    return {'uniqueCounts':dict(unique),'uniqueElements':len(seen),'windowOccurrences':occurrences,
            'windows':[{'id':key,'status':'complete_from_acquired_file_only','counts':dict(value),'elements':sum(value.values())} for key,value in counts.items()]}


def worker(plan,root):
    root=Path(root);caps=plan['caps'];resources=FullResources(root,seconds=caps['workerSeconds'])
    watchdog=start_watchdog(caps['workerSeconds']);pass_watchdog=None;engine=None;last=0.;sequence=0
    def check():
        nonlocal last,sequence
        resources.check()
        if engine is not None and time.monotonic()-last>=60:
            last=time.monotonic();sequence+=1
            resources.write(root/f'progress-{sequence:04d}.json',{'seconds':time.monotonic()-resources.began,'native':engine.progress(),
                'codecDecodedRows':engine.codec.decoded_rows,'codecCalls':engine.codec.calls})
    def rotate_watchdog():
        nonlocal pass_watchdog
        if pass_watchdog is not None:
            if pass_watchdog.poll() is None:pass_watchdog.terminate()
            require(pass_watchdog.wait(timeout=5)==-15,'Full pass watchdog expired')
        pass_watchdog=start_watchdog(caps['passSeconds'])
    try:
        verify_worker_inputs(plan)
        require(resource.getrlimit(resource.RLIMIT_FSIZE)==(FILE_LIMIT,FILE_LIMIT),'Full process file cap')
        disk=os.statvfs('/tmp');require(disk.f_blocks*disk.f_frsize==TMP,'Full tmp guard')
        resources.write(root/'resource-guards.json',{'memory':memory_guard(),'fileBytes':FILE_LIMIT,'tmpBytes':TMP,'watchdogSeconds':caps['workerSeconds']})
        if plan['stage']=='controls':
            suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in MODULES)
            result=unittest.TextTestRunner(verbosity=2).run(suite)
            resources.write(root/'controls.json',{'tests':result.testsRun,'successful':result.wasSuccessful(),'skips':len(result.skipped),'failures':len(result.failures),'errors':len(result.errors)})
            require(result.wasSuccessful() and not result.skipped and result.testsRun>=12,'Full controller controls')
        manifest=strict_json(Path('/inputs/catalog.json').read_bytes())
        proposal=proposal_for(strict_json(Path('/inputs/proposal.json').read_bytes()),plan['stage'],caps)
        work=root/'extract';work.mkdir();storage=BoundIndexStorage(work,resources,manifest)
        engine=FullScreen('/artifacts/helper.so',ARTIFACT_SHA,aggregate_visits=2*MAX_VISITS,codec_rows=caps['codecRows'],codec_calls=caps['codecCalls'])
        rotate_watchdog();started=time.monotonic()
        state=extract('/source.pbf',proposal,work,engine=engine,source=plan['source'],storage=storage,
                      lookup_io=caps['lookupBytesPerPass'],check=check,before_second=rotate_watchdog)
        resources.write(root/'extraction-result.json',state)
        require(state['status']=='passed_all_highway_extraction_prototype' and state['independentAuditComplete'],'Full extraction stopped: '+state.get('error',''))
        receipts=state['nativeReceipts'];require(len(receipts)==2 and engine.visits==2*sum(plan['source']['counts'].values()),'Full aggregate source count')
        for receipt in receipts:
            require(receipt['nativeEof'] and receipt['counts']==plan['source']['counts'] and receipt['semanticSha256']==plan['semantic'],'Full source EOF/count/field seal')
            require(receipt['batchWays']==receipt['highwayWays']==plan['highwayWays'],'Full all-highway batch delivery')
        require(strict_json((work/'audit-index/index.json').read_bytes())==manifest and storage.shard_writes==2*len(manifest['shards']) and storage.shard_removals==len(manifest['shards']),'Full physical index/rebuild closure')
        require(not list((work/'primary-index').glob('[0-9]*.bin')),'Full rolling replacement residue')
        ledger=output_ledger(work/'elements.jsonl',proposal['windows'])
        require(ledger['uniqueElements']==state['retainedElements'] and ledger['windowOccurrences']==state['windowOccurrences'],'Full output ledger accounting')
        if plan['stage']=='controls':require((work/'elements.jsonl').read_bytes()==Path('/inputs/reference-output.jsonl').read_bytes(),'Full controller independent reference output')
        resources.write(root/'window-ledger.json',ledger)
        resources.write(root/'result.json',{'status':'passed_full_road_capture','stage':plan['stage'],'sourcePasses':2,'sourceObjects':engine.visits,
            'protectedExtractionSeconds':time.monotonic()-started,'codecDecodedRows':engine.codec.decoded_rows,'codecCalls':engine.codec.calls,
            'indexShardWrites':storage.shard_writes,'indexShardRemovals':storage.shard_removals,'indexWrittenBytes':storage.written_bytes,
            'rawAcquiredFileCaptureComplete':True,'nationalPhysicalIndexAllocated':plan['stage']=='run',
            'sourceFeasibilityQualified':False,'publisherBoundaryQualified':False,'sourceAdapterImplemented':False,'modelChanged':False,
            'timingScope':'Complete protected extraction including framing, native callbacks, lookup, index writes/replacement, independent materialization, output audit and close; excludes input binding and worker lifecycle.'})
        return 0
    except BaseException as error:
        resources.write(root/'worker-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:3000],
            'lastNativeReceipt':engine.last if engine else None,'derivedIndexesTrusted':False,'rawAcquiredFileCaptureComplete':False,'modelChanged':False})
        return 2
    finally:
        try:resources.write(root/'metrics-end.json',resources.result())
        finally:
            for timer in (pass_watchdog,watchdog):
                if timer is not None:
                    if timer.poll() is None:timer.terminate()
                    timer.wait(timeout=5)


def source_binding(path,spec,check,seconds):
    before=stat_key(path);require(path.is_file() and not path.is_symlink() and path.stat().st_size==spec['bytes'],'Full source type/length')
    digest=hashlib.sha256();md5=hashlib.md5();count=0;started=time.monotonic()
    with path.open('rb') as stream:
        while data:=stream.read(8*1024**2):
            check();require(time.monotonic()-started<seconds,'Full host source hash deadline')
            count+=len(data);require(count<=spec['bytes'],'Full source byte cap');digest.update(data);md5.update(data)
    require(count==spec['bytes'] and digest.hexdigest()==spec['sha256'] and md5.hexdigest()==spec['md5'] and stat_key(path)==before,'Full source identity/stability')
    return {'bytesRead':count,'sha256':digest.hexdigest(),'md5':md5.hexdigest(),'seconds':time.monotonic()-started}


def driver(recipe,pin):
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==pin,'Full recipe path/hash')
    plan=strict_json(recipe.read_bytes());validate(plan);caps=plan['caps'];root=repo/plan['output']
    require(not root.exists(),'Full fresh output required');root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json')
    started=time.monotonic();owner=uuid.uuid4().hex;name='geo-planner-full-extract-'+owner[:12];identity=child=None;success=False
    def save(filename,value):(root/filename).write_bytes(canonical(value)+b'\n')
    def check():
        require(time.monotonic()-started<caps['hostWorkSeconds'],'Full host deadline')
        require(owned_usage(root)['conservativeAllocatedBytes']<OWNED_LIMIT,'Full host storage cap')
        require(shutil.disk_usage(root).free>=2*1024**3,'Full disk headroom')
        require(not (root/'worker.log').exists() or (root/'worker.log').stat().st_size<=2*1024**2,'Full log cap')
    def call(args):check();return subprocess.run(args,capture_output=True,text=True,timeout=15)
    save('owner.json',{'name':name,'label':owner,'image':IMAGE,'labelKey':'geo-planner.stream-owner'})
    try:
        for input_path,expected in plan['inputs'].items():check();require(sha(repo/input_path)==expected,'Full input drift: '+input_path)
        actual={str(p.relative_to(repo)) for p in (repo/SITE).rglob('*') if p.is_file()}
        require(actual=={p for p in plan['inputs'] if p.startswith(SITE+'/')} and not any(p.is_symlink() for p in (repo/SITE).rglob('*')),'Full site closure')
        measured=capacity(repo)
        require(measured['hostDiskAvailableBytes']>=caps['requiredInitialFreeBytes'] and measured['dockerMemoryBytes']>=6442450944 and measured['hostMemoryBytes']>=8589934592 and min(measured['hostCpuCount'],measured['dockerCpuCount'])>=2,'Full starting capacity')
        save('capacity-at-start.json',measured)
        source=repo/plan['source']['path'];save('host-source-binding.json',source_binding(source,plan['source'],check,caps['hashSeconds']))
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL',
              '--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--ulimit','core=0:0','--ulimit',f'fsize={FILE_LIMIT}:{FILE_LIMIT}',
              '--tmpfs','/tmp:rw,size=256m','--env','LD_LIBRARY_PATH=/tools/runtime','--env','PYTHONPATH=/code:/tools/site',
              '--env','OSMIUM_MAX_INPUT_QUEUE_SIZE=2','--env','OSMIUM_MAX_OSMDATA_QUEUE_SIZE=2']
        for input_path,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/input_path},dst={destination},readonly']
        for filename,input_path in RUNTIME.items():args+=['--mount',f'type=bind,src={repo/input_path},dst=/tools/runtime/{filename},readonly']
        args+=['--mount',f'type=bind,src={repo/SITE},dst=/tools/site,readonly','--mount',f'type=bind,src={repo/ARTIFACT},dst=/artifacts/helper.so,readonly',
               '--mount',f'type=bind,src={source},dst=/source.pbf,readonly','--mount',f'type=bind,src={root},dst=/work',
               '--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,
               '-B','/code/run_osm_full_extract_v1.py','/inputs/recipe.json',pin,'--worker']
        result=call(args);require(result.returncode==0,result.stderr);identity=result.stdout.strip();require(len(identity)==64,'Full owned container identity')
        initial=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(initial)
        save('container-initial.json',{'Image':initial['Image'],'HostConfig':initial['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in initial['Mounts']]})
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:check();time.sleep(.5)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0];save('container-result.json',{'State':final['State'],'clientExitCode':child.returncode})
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Full worker exit/OOM');success=True
    except BaseException as error:save('driver-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:3000]})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        def cleanup_call(args):return subprocess.run(args,capture_output=True,text=True,timeout=15)
        if not (root/'container-result.json').exists():settle_error(cleanup_call,identity,name,owner,root,child.returncode if child else None)
        cleanup_owned(cleanup_call,identity,name,owner,IMAGE,root)
    require(time.monotonic()-started<caps['hostSeconds'],'Full final host deadline')
    save('run-summary.json',{'status':'passed_full_road_capture' if success else 'stopped','hostSecondsIncludingBindingsAndCleanup':time.monotonic()-started,'networkRequests':0,'modelChanged':False})
    return 0 if success else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    require(sha(args.recipe)==args.sha256,'Full recipe binding');plan=strict_json(Path(args.recipe).read_bytes());validate(plan)
    raise SystemExit(worker(plan,'/work') if args.worker else driver(args.recipe,args.sha256))
