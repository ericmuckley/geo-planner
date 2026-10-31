"""Offline V2 lookup-integrity correction, reusing V1's exact compiled codec."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import resource
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
from run_osm_delta_v1 import CAPS,PROPOSAL,ASSET_PROOF,guards,isolation

OUTPUT='data/coarse-quality/us-osm-delta-v2'
ARTIFACT={'path':'data/coarse-quality/us-osm-delta-v1/build/delta.so','bytes':201016,
    'sha256':'efe338cabf78035b93b936afb623741162e376df8451e5fede8590bbf724dc23'}


def validate(plan):
    require(plan['phase']=='offline_native_delta_v2' and plan['caps']==CAPS,'Delta V2 phase/caps drift')
    require(plan['imageId']==IMAGE and plan['imagePull']=='never' and plan['output']==OUTPUT,'Delta V2 image/output drift')
    require(plan['phases']==['controls'] and plan['network']=='none' and plan['artifact']==ARTIFACT,'Delta V2 artifact/network/phase drift')
    require(plan['mounts'].get(PROPOSAL)=='/'+PROPOSAL,'Delta V2 proposal mount')
    for source,destination in plan['mounts'].items():
        require(source.startswith('scripts/') and source.endswith(('.py','.cpp')) and '..' not in Path(source).parts or source in (ASSET_PROOF,PROPOSAL),'Delta V2 no road/sample mounts')
        require(destination.startswith('/code/') or source==PROPOSAL and destination=='/'+PROPOSAL,'Delta V2 code mount path')
        require(plan['inputs'][source]==plan['workerFiles'][destination],'Delta V2 mount binding')
    require(plan['inputs'][ARTIFACT['path']]==plan['workerFiles']['/artifacts/delta.so']==ARTIFACT['sha256'],'Delta V2 artifact binding')


def worker(plan,root,phase):
    root=Path(root);watchdog=start_watchdog(CAPS['workerSeconds']);began=time.monotonic()
    def check():
        require(time.monotonic()-began<CAPS['workerSeconds'],'Delta worker deadline')
        require(tree_bytes(root)<CAPS['workingBytesIncludingTmp']-CAPS['tmpBytes'],'Delta worker storage cap')
    try:
        verify_worker_inputs(plan);guards(root,phase)
        import coarse_osm_delta_v2_test as tests
        artifact=strict_json(Path('/artifacts/result.json').read_bytes())
        tests.configure_native('/artifacts/delta.so',artifact['artifactSha256'])
        modules=['coarse_osm_stream_v1_test','coarse_osm_stream_driver_v1_test','coarse_osm_validation_v4_test','coarse_osm_delta_v2_test']
        suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in modules)
        result=unittest.TextTestRunner().run(suite)
        save(root/'controls.json',{'tests':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
            'codec':'actual_compiled_c_abi','legacyControls':27,'newControls':19})
        if not result.wasSuccessful() or result.skipped:return 2
        from coarse_osm_delta_v2 import Index,Storage
        from coarse_osm_compact_v1 import Index as FixedIndex
        from coarse_osm_delta_extract_v2 import extract
        from coarse_osm_native_smoke import fixture_records,STATE
        from coarse_osm_bulk import extract as reference_extract
        proposal=deepcopy(strict_json(Path('/'+PROPOSAL).read_bytes()))
        proposal['source']['proposedPublisherReplicationStateUtc']=STATE;proposal['windows']=[{'id':'a','bbox':[0,0,1,1]},{'id':'b','bbox':[.25,.25,.75,.75]}]
        proposal['proposedCaps'].update(sqliteIndexBytesEach=1048576,sqliteMaxPagesEach=256,sqliteCacheBytesEach=8192,
            workingBytesIncludingTmp=33554432,tmpBytes=65536,pythonSelectionStateBytes=4194304,retainedNativeObjectBytes=1048576,
            normalizedExtractBytes=1048576,scanNodesPerPass=100,scanWaysPerPass=100,scanRelationsPerPass=100,scanObjectVisitsTotal=1200,wallSeconds=30)
        codec=tests.CODEC
        integrated=root/'two-pass';integrated.mkdir()
        native=extract(lambda:iter(fixture_records()),proposal,integrated,codec=codec)
        old=root/'four-pass';old.mkdir();reference=reference_extract(lambda:iter(fixture_records()),proposal,old,source_identity={'publisherStateUtc':STATE})
        require(native['independentAuditComplete'] and reference['independentAuditComplete'] and (integrated/'elements.jsonl').read_bytes()==(old/'elements.jsonl').read_bytes(),'Delta preserved output/audit mismatch')
        delta=Index(root/'delta-index',Storage(CAPS['indexBytes'],CAPS['fileBytes']),codec=codec)
        fixed=FixedIndex(root/'fixed-index',Storage(CAPS['indexBytes'],CAPS['fileBytes']))
        for identity in range(1,20001):
            check();x=(identity%100)*1000000;delta.add_xy(identity,x,0);fixed.add({'id':identity,'lon':x/10000000,'lat':0.})
        delta.finish();fixed.finish()
        require(delta.points([20000,1,10000,1])==fixed.points([20000,1,10000,1]),'Delta fixed-coordinate mismatch')
        save(root/'result.json',{'status':'native_delta_index_synthetic_qualified','artifactSha256':artifact['artifactSha256'],
            'syntheticConsecutiveRows':20000,'deltaIndexBytes':delta.generated_bytes,'fixedIndexBytes':fixed.generated_bytes,
            'outputSha256':sha(integrated/'elements.jsonl'),'twoPassVisits':native['scanObjectVisits'],'fourPassVisits':reference['scanObjectVisits'],
            'independentAuditComplete':True,'codecWrappedEncodedRows':codec.encoded_rows,'codecWrappedDecodedRows':codec.decoded_rows,'codecWrappedCalls':codec.calls,
            'counterScope':'C ABI encode/decode rows through the bounded Python wrapper, including refused decode calls. Direct fixed null/short-buffer ABI controls and legacy controls are outside this counter.',
            'cachePayloadCeilingBytes':CAPS['cachePayloadBytes'],'maxRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'scope':'Synthetic format/coordinate/output equivalence and bounded C ABI only; no real-sample timing or national forecast.',
            'nativeMetadataValidatorImplemented':False,'nativeIndexIoImplemented':False,'fullImportAdmitted':False,'sourceOrSavedSampleReads':0,'modelChanged':False})
        delta.close();fixed.close();return 0
    except Exception as error:
        save(root/'worker-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:1000],'nativeMetadataValidatorImplemented':False,'fullImportAdmitted':False})
        return 2
    finally:
        if watchdog.poll() is None:watchdog.terminate()
        watchdog.wait(timeout=5)


def driver(recipe,expected,output):
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==expected,'Delta V2 recipe path/hash')
    plan=strict_json(recipe.read_bytes());validate(plan)
    root=(repo/output).resolve();require(root==repo/OUTPUT and not root.exists(),'Delta V2 fresh exact output required')
    root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json')
    began=time.monotonic();deadline=began+CAPS['workSeconds'];hard=began+CAPS['hostSeconds'];owner=uuid.uuid4().hex
    save(root/'owner.json',{'label':owner,'image':IMAGE,'labelKey':'geo-planner.stream-owner'});identity=child=None;code=None;success=False
    phase=root/'controls';phase.mkdir();name='geo-planner-delta-v2-'+owner[:12]
    save(phase/'owner.json',{'name':name,'label':owner})
    def check():
        require(time.monotonic()<deadline,'Delta V2 shared host deadline')
        require(tree_bytes(root)<=CAPS['workingBytesIncludingTmp']-CAPS['tmpBytes'],'Delta V2 owned storage cap')
        require(shutil.disk_usage(root).free>=2147483648,'Delta V2 disk headroom')
    def call(args,**kwargs):
        check();return subprocess.run(args,capture_output=True,text=True,timeout=min(15,max(.01,deadline-time.monotonic())),**kwargs)
    try:
        for source,pin in plan['inputs'].items():check();require(sha(repo/source)==pin,'Delta V2 input drift: '+source)
        observed=capacity(repo);require(observed['hostDiskAvailableBytes']>=3221225472 and observed['hostMemoryBytes']>=8589934592 and observed['dockerMemoryBytes']>=6442450944,'Delta V2 capacity')
        save(root/'capacity-at-start.json',observed)
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
            '--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864','--tmpfs=/tmp:rw,size=256m','--env','LD_LIBRARY_PATH=/tools/runtime']
        for source,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={repo/plan["site"]},dst=/tools/site,readonly']
        for filename,source in plan['runtime'].items():args+=['--mount',f'type=bind,src={repo/source},dst=/tools/runtime/{filename},readonly']
        args+=['--mount',f'type=bind,src={repo/ARTIFACT["path"]},dst=/artifacts/delta.so,readonly',
            '--mount',f'type=bind,src={repo/Path(ARTIFACT["path"]).parent/"result.json"},dst=/artifacts/result.json,readonly',
            '--mount',f'type=bind,src={phase},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly',
            '--entrypoint=python3',IMAGE,'-B','/code/run_osm_delta_v2.py','/inputs/recipe.json',expected,'/work','--worker']
        identity=call(args,check=True).stdout.strip();require(len(identity)==64,'Delta V2 owned ID')
        initial=json.loads(call(['docker','inspect',identity],check=True).stdout)[0];isolation(initial,'controls')
        save(phase/'container-initial.json',{'Image':initial['Image'],'HostConfig':initial['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in initial['Mounts']]})
        with (phase/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:
                check();require((phase/'worker.log').stat().st_size<=CAPS['reportBytes'],'Delta V2 log cap');time.sleep(.25)
        code=child.returncode;final=json.loads(call(['docker','inspect',identity],check=True).stdout)[0]
        save(phase/'container-result.json',{'Image':final['Image'],'State':final['State'],'clientExitCode':code})
        require(final['State']['ExitCode']==code and not final['State']['OOMKilled'],'Delta V2 final exit/OOM')
        success=code==0
    except (Exception,KeyboardInterrupt) as error:
        save(root/'driver-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:1000],'fullImportAdmitted':False})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        def cleanup_call(args):return subprocess.run(args,capture_output=True,text=True,timeout=max(1,min(15,hard-time.monotonic())))
        try:
            if not (phase/'container-result.json').exists():settle_error(cleanup_call,identity,name,owner,phase,child.returncode if child is not None else None)
        finally:cleanup_owned(cleanup_call,identity,name,owner,IMAGE,phase)
    require(time.monotonic()-began<CAPS['hostSeconds'],'Delta V2 final host deadline')
    save(root/'run-summary.json',{'status':'native_delta_index_synthetic_qualified' if success else 'stopped','workerClientExitCode':code,
        'hostSecondsIncludingInputHashesControlsCleanup':time.monotonic()-began,'networkRequests':0,'recompiled':False,'sourceOrSavedSampleReads':0,
        'nativeMetadataValidatorImplemented':False,'nativeIndexIoImplemented':False,'fullImportAdmitted':False,'modelChanged':False})
    return 0 if success else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('output');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    if args.worker:
        require(sha(args.recipe)==args.sha256,'Delta V2 worker binding');plan=strict_json(Path(args.recipe).read_bytes());validate(plan)
        sys.path.insert(0,'/tools/site');raise SystemExit(worker(plan,args.output,'controls'))
    raise SystemExit(driver(args.recipe,args.sha256,args.output))
