"""One frozen offline native index implementation check, synthetic inputs only."""
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
from coarse_osm_data import memory_guard, verify_worker_inputs
from coarse_osm_data_v3 import tree_bytes
from coarse_osm_native_lock_v1 import save
from coarse_osm_records import strict_json
from coarse_timing_input import require, start_watchdog
from prepare_osm_input_v3 import capacity
from prepare_osm_native_lock_v1 import IMAGE, settle_error, cleanup_owned
from run_osm_build_v1 import COMPILER, tool

CAPS={'hostSeconds':600,'workSeconds':570,'workerSeconds':300,'workingBytesIncludingTmp':1073741824,
    'tmpBytes':268435456,'fileBytes':67108864,'indexBytes':33554432,'reportBytes':2097152,
    'nativeCodecRows':2000000,'cacheBlocks':64,'cachePayloadBytes':4194304}
OUTPUT='data/coarse-quality/us-osm-delta-v1'
ASSET_ROOT='data/coarse-quality/us-osm-native-build-v1/prepare/rootfs'
ASSET_PROOF='docs/evidence/coarse-osm-native-build-2026-10-27/asset_contents.py'
PROPOSAL='docs/evidence/coarse-osm-offline-plan-2026-10-26/proposal.json'
FLAGS=['-std=c++17','-O2','-fPIC','-shared','-fvisibility=hidden','-static-libstdc++','-static-libgcc',
    '/work/delta.cpp','-Wl,-z,defs','-Wl,--exclude-libs,ALL','-o','/work/delta.so']


def validate(plan):
    require(plan['phase']=='offline_native_delta_v1' and plan['caps']==CAPS,'Delta phase/caps drift')
    require(plan['imageId']==IMAGE and plan['imagePull']=='never' and plan['output']==OUTPUT,'Delta image/output drift')
    require(plan['phases']==['build','controls'] and plan['network']=='none' and plan['flags']==FLAGS,'Delta stages/network/flags drift')
    require(plan['mounts'].get(PROPOSAL)=='/'+PROPOSAL and plan['mounts'].get('scripts/coarse_osm_delta_v1.cpp')=='/code/coarse_osm_delta_v1.cpp','Delta code/proposal mount closure')
    require(plan['rootfs']['path']==ASSET_ROOT and plan['rootfs']['portable']['portableTreeSha256']=='a64ef22d93c8b49689ccfefe09c67a62e67422cb84c6edb86089533fb33ebd72','Delta qualified rootfs drift')
    for source,destination in plan['mounts'].items():
        require(source.startswith('scripts/') and source.endswith(('.py','.cpp')) and '..' not in Path(source).parts or source in (ASSET_PROOF,PROPOSAL),'No road/sample mounts')
        require(destination.startswith('/code/') or source==PROPOSAL and destination=='/'+PROPOSAL,'Delta mount destination')
        require(plan['inputs'][source]==plan['workerFiles'][destination],'Delta mount binding')


def guards(root,phase):
    disk=os.statvfs('/builder/tmp' if phase=='build' else '/tmp')
    require(disk.f_blocks*disk.f_frsize==CAPS['tmpBytes'],'Delta tmp guard')
    require(resource.getrlimit(resource.RLIMIT_FSIZE)==(CAPS['fileBytes'],CAPS['fileBytes']),'Delta file guard')
    save(root/'resource-guards.json',{'memory':memory_guard(),'tmpBytes':CAPS['tmpBytes'],'fileBytes':CAPS['fileBytes'],
        'phase':phase,'watchdogSeconds':CAPS['workerSeconds'],'sysChrootCapability':phase=='build'})


def worker(plan,root,phase):
    root=Path(root);watchdog=start_watchdog(CAPS['workerSeconds']);began=time.monotonic()
    def check():
        require(time.monotonic()-began<CAPS['workerSeconds'],'Delta worker deadline')
        require(tree_bytes(root)<CAPS['workingBytesIncludingTmp']-CAPS['tmpBytes'],'Delta worker storage cap')
    try:
        verify_worker_inputs(plan);guards(root,phase)
        if phase=='build':
            root.chmod(0o777);shutil.copyfile('/code/coarse_osm_delta_v1.cpp',root/'delta.cpp')
            tool(root,'compiler-version',[COMPILER,'--version'],check)
            tool(root,'compile',[COMPILER,*FLAGS],check)
            elf=tool(root,'elf',['/usr/bin/readelf','-h','-d','-V','-Ws','/work/delta.so'],check)
            require('AArch64' in elf and 'gp_delta_abi' in elf and 'gp_delta_decode' in elf and 'GLIBCXX_' not in elf,'Delta ELF machine/exports/runtime')
            import re
            needed=re.findall(r'\(NEEDED\).*?\[([^\]]+)\]',elf)
            require(set(needed)<={'libm.so.6','libc.so.6','ld-linux-aarch64.so.1'},'Delta unqualified dynamic dependency')
            artifact=root/'delta.so'
            save(root/'result.json',{'status':'compiled_delta_controls_pending','artifactSha256':sha(artifact),'artifactBytes':artifact.stat().st_size,
                'sourceSha256':sha(root/'delta.cpp'),'flags':FLAGS,'needed':needed,'elfSha256':sha(root/'elf.log')})
            return 0
        import coarse_osm_delta_v1_test as tests
        artifact=strict_json(Path('/artifacts/result.json').read_bytes())
        tests.configure_native('/artifacts/delta.so',artifact['artifactSha256'])
        modules=['coarse_osm_stream_v1_test','coarse_osm_stream_driver_v1_test','coarse_osm_validation_v4_test','coarse_osm_delta_v1_test']
        suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in modules)
        result=unittest.TextTestRunner().run(suite)
        save(root/'controls.json',{'tests':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
            'codec':'actual_compiled_c_abi','legacyControls':27,'newControls':17})
        if not result.wasSuccessful() or result.skipped:return 2
        from coarse_osm_delta_v1 import Index,Storage
        from coarse_osm_compact_v1 import Index as FixedIndex
        from coarse_osm_delta_extract_v1 import extract
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


def isolation(observed,phase):
    tmp='/builder/tmp' if phase=='build' else '/tmp'
    expected={'NetworkMode':'none','Memory':4294967296,'MemorySwap':4294967296,'ReadonlyRootfs':True,'NanoCpus':2000000000,'PidsLimit':64,'Tmpfs':{tmp:'rw,size=256m'}}
    require(observed['Image']==IMAGE and all(observed['HostConfig'][k]==v for k,v in expected.items()),'Delta isolation drift')
    allowed={'/work','/builder/work'} if phase=='build' else {'/work'}
    require(all(not m['RW'] for m in observed['Mounts'] if m['Destination'] not in allowed),'Delta writable input')
    require({c.removeprefix('CAP_') for c in observed['HostConfig'].get('CapAdd') or []}==({'SYS_CHROOT'} if phase=='build' else set()),'Delta added capability drift')
    require({c.removeprefix('CAP_') for c in observed['HostConfig'].get('CapDrop') or []}=={'ALL'} and 'no-new-privileges' in observed['HostConfig']['SecurityOpt'],'Delta capability/security drift')
    require({u['Name']:(u['Soft'],u['Hard']) for u in observed['HostConfig']['Ulimits']}=={'core':(0,0),'fsize':(CAPS['fileBytes'],CAPS['fileBytes'])},'Delta file/core limits')


def driver(recipe,expected,output):
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==expected,'Delta recipe path/hash')
    plan=strict_json(recipe.read_bytes());validate(plan)
    root=(repo/output).resolve();require(root==repo/OUTPUT and not root.exists(),'Delta fresh exact output required')
    root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json')
    began=time.monotonic();deadline=began+CAPS['workSeconds'];hard=began+CAPS['hostSeconds'];owner=uuid.uuid4().hex
    save(root/'owner.json',{'label':owner,'image':IMAGE,'labelKey':'geo-planner.stream-owner'});codes={};success=False
    def check():
        require(time.monotonic()<deadline,'Delta shared host deadline')
        require(tree_bytes(root)<=CAPS['workingBytesIncludingTmp']-CAPS['tmpBytes'],'Delta owned storage cap')
        require(shutil.disk_usage(root).free>=2147483648,'Delta disk headroom')
    def call(args,**kwargs):
        check();return subprocess.run(args,capture_output=True,text=True,timeout=min(15,max(.01,deadline-time.monotonic())),**kwargs)
    def run_phase(phase):
        p=root/phase;p.mkdir();identity=child=None;name='geo-planner-delta-v1-'+phase+'-'+owner[:12]
        save(p/'owner.json',{'name':name,'label':owner})
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
            '--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--ulimit','core=0:0','--ulimit',f'fsize={CAPS["fileBytes"]}:{CAPS["fileBytes"]}',
            '--tmpfs',('/builder/tmp' if phase=='build' else '/tmp')+':rw,size=256m','--env','LD_LIBRARY_PATH=/tools/runtime']
        if phase=='build':args+=['--cap-add=SYS_CHROOT','--mount',f'type=bind,src={repo/ASSET_ROOT},dst=/builder,readonly','--mount',f'type=bind,src={p},dst=/builder/work']
        else:args+=['--mount',f'type=bind,src={root/"build"},dst=/artifacts,readonly']
        for source,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={repo/plan["site"]},dst=/tools/site,readonly']
        for filename,source in plan['runtime'].items():args+=['--mount',f'type=bind,src={repo/source},dst=/tools/runtime/{filename},readonly']
        args+=['--mount',f'type=bind,src={p},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_delta_v1.py','/inputs/recipe.json',expected,'/work','--worker','--phase',phase]
        try:
            identity=call(args,check=True).stdout.strip();require(len(identity)==64,'Delta owned container ID')
            initial=json.loads(call(['docker','inspect',identity],check=True).stdout)[0];isolation(initial,phase)
            save(p/'container-initial.json',{'Image':initial['Image'],'HostConfig':initial['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in initial['Mounts']]})
            with (p/'worker.log').open('xb') as log:
                child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
                while child.poll() is None:
                    check();require((p/'worker.log').stat().st_size<=CAPS['reportBytes'],'Delta worker log cap');time.sleep(.25)
            final=json.loads(call(['docker','inspect',identity],check=True).stdout)[0]
            save(p/'container-result.json',{'Image':final['Image'],'State':final['State'],'clientExitCode':child.returncode})
            require(final['State']['ExitCode']==child.returncode and not final['State']['OOMKilled'],'Delta worker exit/OOM')
            return child.returncode
        finally:
            if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
            def cleanup_call(args):return subprocess.run(args,capture_output=True,text=True,timeout=max(1,min(15,hard-time.monotonic())))
            try:
                if not (p/'container-result.json').exists():settle_error(cleanup_call,identity,name,owner,p,child.returncode if child is not None else None)
            finally:cleanup_owned(cleanup_call,identity,name,owner,IMAGE,p)
    try:
        for name,pin in plan['inputs'].items():check();require(sha(repo/name)==pin,'Delta input drift: '+name)
        observed=capacity(repo)
        require(observed['hostDiskAvailableBytes']>=3221225472 and observed['hostMemoryBytes']>=8589934592 and observed['dockerMemoryBytes']>=6442450944,'Delta starting capacity')
        save(root/'capacity-at-start.json',observed)
        import importlib.util
        spec=importlib.util.spec_from_file_location('qualified_asset_contents',repo/ASSET_PROOF);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        require(module.snapshot(repo/ASSET_ROOT)==plan['rootfs']['portable'],'Delta qualified compiler contents drift')
        check();save(root/'asset-verification.json',{'portableRootfsVerified':True,'scope':'File content/path/link hashes only; original Linux permission seal remains in the parent proof.'})
        for phase in plan['phases']:
            codes[phase]=run_phase(phase);require(codes[phase]==0,'Delta phase stopped: '+phase)
        success=True
    except (Exception,KeyboardInterrupt) as error:
        save(root/'driver-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:1000],'fullImportAdmitted':False})
    require(time.monotonic()-began<CAPS['hostSeconds'],'Delta final host deadline')
    save(root/'run-summary.json',{'status':'native_delta_index_synthetic_qualified' if success else 'stopped','phaseClientExitCodes':codes,
        'hostSecondsIncludingInputAssetHashesBuildControlsCleanup':time.monotonic()-began,'networkRequests':0,'sourceOrSavedSampleReads':0,
        'nativeMetadataValidatorImplemented':False,'nativeIndexIoImplemented':False,'fullImportAdmitted':False,'modelChanged':False})
    return 0 if success else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('output')
    parser.add_argument('--worker',action='store_true');parser.add_argument('--phase',choices=['build','controls']);args=parser.parse_args()
    if args.worker:
        require(args.phase is not None and sha(args.recipe)==args.sha256,'Delta worker binding');plan=strict_json(Path(args.recipe).read_bytes());validate(plan)
        sys.path.insert(0,'/tools/site');raise SystemExit(worker(plan,args.output,args.phase))
    raise SystemExit(driver(args.recipe,args.sha256,args.output))
