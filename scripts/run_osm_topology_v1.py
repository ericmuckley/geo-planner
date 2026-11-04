"""Offline qualified fixed-record national topology census; no graph or ETA model."""
import argparse
import importlib.util
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
from coarse_osm_country_screen_v1 import owned_usage,resource_metrics,SOURCE_COUNTS,default_limits
from coarse_osm_records import strict_json
from coarse_timing_input import require,start_watchdog
from prepare_osm_native_lock_v1 import IMAGE,cleanup_owned,settle_error
from run_osm_build_v1 import COMPILER,tool
from run_osm_country_screen_v15 import FLAGS as LEGACY_FLAGS,ASSET_ROOT,HEADERS
FLAGS=list(LEGACY_FLAGS);FLAGS.insert(FLAGS.index("-Wl,-z,defs"),"/work/topology-kernel.cpp")

OUTPUTS={stage:'data/coarse-quality/us-osm-topology-'+stage+'-v1' for stage in ('build','controls','run')}
CAPS={'memoryBytes':4294967296,'tmpBytes':268435456,'fileBytes':67108864,'ownedBytes':{'build':67108864,'controls':67108864,'run':2147483648},'entries':1024,
      'priorRetainedReserveBytes':62610000000,'overallRetainedBytes':68719476736,
      'workerSeconds':{'build':150,'controls':150,'run':2700},'hostSeconds':{'build':180,'controls':180,'run':3000}}
SOURCE={'path':'data/coarse-quality/us-osm-input-v3/download/http/001.bin','bytes':12229320016,
        'sha256':'1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff','md5':'c5abaec55e724255277f22fb97941e5a',
        'state':'2026-10-25T21:21:21Z','semanticSha256':'209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16'}
SCAN={'singleNormalizedElementBytes':4194304,'scanNodesPerPass':1606229364,'scanWaysPerPass':162688797,
      'scanRelationsPerPass':1624265,'scanObjectVisitsTotal':1770542426,
      'pbfHeaderBytesExclusiveMaximum':65536,'pbfUncompressedBlobBytesExclusiveMaximum':33554432}
PROPOSAL='docs/evidence/coarse-osm-offline-plan-2026-10-26/proposal.json'
PRIOR='docs/evidence/coarse-osm-country-exec-2026-10-30/screen-raw-v4/screen/pass-b/summary.json'


def validate(plan):
    stage=plan['stage'];require(stage in OUTPUTS and plan['phase']=='native_national_topology_v1','Topology phase')
    require(plan['caps']==CAPS and plan['source']==SOURCE and plan['scanCaps']==SCAN and plan['image']==IMAGE and plan['flags']==FLAGS,'Topology fixed source/caps/compiler/image')
    require(plan['output']==OUTPUTS[stage] and plan['network']=='none' and plan['imagePull']=='never','Topology exclusive output/network')
    require(set(plan['mounts'])==set(plan['inputs']),'Topology input roster')
    for path,dest in plan['mounts'].items():
        require('..' not in Path(path).parts and not Path(path).is_absolute(),'Topology relative input')
        require(path.startswith('scripts/') and dest=='/code/'+Path(path).name or (path in (PROPOSAL,PRIOR) and dest=='/'+path or path=='docs/evidence/coarse-osm-national-footprint-2026-11-01/raw-run-v1/receipt.json' and dest=='/inputs/footprint-receipt.json') or path==plan['assetProof'] and dest=='/code/qualified_asset_contents.py' or path.startswith(plan['site']+'/') and dest=='/tools/site/'+path.removeprefix(plan['site']+'/') or path in plan['runtime'].values() and dest.startswith('/tools/runtime/'),'Topology allowed readonly input')
    require(plan['rootfs']['path']==ASSET_ROOT and {k:v['path'] for k,v in plan['headers'].items()}==HEADERS,'Topology cached compiler scope')
    require(CAPS['priorRetainedReserveBytes']+sum(CAPS['ownedBytes'].values())+CAPS['tmpBytes']<CAPS['overallRetainedBytes'],'Topology retained envelope')
    if stage!='build':require(plan['artifact']['path']==OUTPUTS['build']+'/country-screen.so','Topology compiled artifact path')
    if stage=='run':require(plan['admission']['tests']==39 and plan['admission']['skips']==0 and plan['admission']['successful'] and plan['admission']['independentProofPassed'],'Topology controls admission')


def bounded_save(root,name,value):
    path=root/name;raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    require(path.parent==root and not path.exists() and not path.is_symlink() and len(raw)<=2097152,'Topology exclusive bounded record')
    with path.open('xb') as stream:stream.write(raw)


def worker(plan):
    from coarse_osm_data import verify_worker_inputs,memory_guard
    root=Path('/work');stage=plan['stage'];began=time.monotonic();last_check=last_progress=0.;engine=None;streams=None
    timer=start_watchdog(CAPS['workerSeconds'][stage])
    def check():
        nonlocal last_check,last_progress
        now=time.monotonic();require(now-began<CAPS['workerSeconds'][stage],'Topology worker deadline')
        if now-last_check>=1:
            last_check=now;usage=owned_usage(root)
            require(usage['conservativeAllocatedBytes']<=CAPS['ownedBytes'][stage] and usage['entries']<=CAPS['entries'],'Topology owned allocation/namespace cap')
        if engine is not None and now-last_progress>=15:
            last_progress=now
            # Fixed small stdout progress only; no append-only per-object telemetry.
            print(json.dumps({'seconds':now-began,'progress':engine.progress()}),flush=True)
    try:
        verify_worker_inputs({'workerFiles':{dest:plan['inputs'][name] for name,dest in plan['mounts'].items()}})
        memory_guard();tmp=os.statvfs('/builder/tmp' if stage=='build' else '/tmp')
        require(tmp.f_blocks*tmp.f_frsize==CAPS['tmpBytes'] and resource.getrlimit(resource.RLIMIT_FSIZE)==(CAPS['fileBytes'],CAPS['fileBytes']),'Topology hard tmp/file limits')
        bounded_save(root,'metrics-start.json',resource_metrics())
        if stage=='build':
            root.chmod(0o777)
            for source,dest in (('coarse_osm_topology_source_v1.cpp','country-screen.cpp'),('coarse_osm_delta_v1.cpp','delta.cpp'),('coarse_osm_topology_kernel_v1.cpp','topology-kernel.cpp'),('coarse_osm_window_cells_v1.cpp','window-cells.cpp'),('coarse_osm_window_masks_v1.cpp','window-masks.cpp'),('coarse_osm_window_cells_v2.cpp','window-cells-v2.cpp')):
                shutil.copyfile('/code/'+source,root/dest)
            import qualified_asset_contents
            for name,pin in plan['headers'].items():require(qualified_asset_contents.snapshot('/builder/inputs/'+name)==pin['portable'],'Topology header contents')
            tool(root,'compiler-version',[COMPILER,'--version'],check);tool(root,'compile',[COMPILER,*FLAGS],check)
            elf=tool(root,'elf',['/usr/bin/readelf','-h','-d','-V','-Ws','/work/country-screen.so'],check)
            import re
            needed=re.findall(r'\(NEEDED\).*?\[([^\]]+)\]',elf)
            require('AArch64' in elf and 'little endian' in elf and 'GLIBCXX_' not in elf and all(name in elf for name in ('gp_country_screen_abi','gp_country_screen_frames','gp_country_screen_pbf','gp_delta_decode','gp_topology_abi','gp_topology_sort_refs','gp_topology_sort_ids','gp_topology_count_files')),'Topology ELF machine/ABI/static runtime')
            require(set(needed)<={'libz.so.1','libm.so.6','libc.so.6','libpthread.so.0','libdl.so.2','librt.so.1','ld-linux-aarch64.so.1'},'Topology dependencies')
            bounded_save(root,'result.json',{'status':'compiled_controls_pending','artifactSha256':sha(root/'country-screen.so'),'artifactBytes':(root/'country-screen.so').stat().st_size,'needed':needed,'elfSha256':sha(root/'elf.log')})
            return 0
        require(sha('/artifacts/country-screen.so')==plan['artifact']['sha256'],'Topology compiled artifact drift')
        from coarse_osm_topology_source_v1 import NativeScreen
        from coarse_osm_topology_kernel_v1 import Kernel
        from coarse_osm_topology_stream_v1 import Streams,CAPS as STREAM_CAPS
        kernel=Kernel("/artifacts/country-screen.so",plan["artifact"]["sha256"])
        if stage=='controls':
            import coarse_osm_topology_source_v1_test as source_tests
            import coarse_osm_topology_kernel_v1_test as kernel_tests
            import coarse_osm_topology_stream_v1_test as stream_tests
            artifact=('/artifacts/country-screen.so',plan['artifact']['sha256'])
            suite=unittest.TestSuite()
            for tests in (source_tests,kernel_tests,stream_tests):
                tests.ARTIFACT=artifact;suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(tests))
            result=unittest.TextTestRunner(verbosity=2).run(suite)
            controls={'tests':result.testsRun,'successful':result.wasSuccessful(),'skips':len(result.skipped),'errors':len(result.errors),'failures':len(result.failures)}
            bounded_save(root,'controls.json',controls)
            require(result.wasSuccessful() and result.testsRun==39 and not result.skipped,'Topology target controls')
            from coarse_osm_country_wire_v4 import framed_records
            from coarse_osm_native_smoke import STATE
            from coarse_osm_footprint_summary_v1 import MAJOR
            rows=source_tests.prior.fixture();ways=[r for r in rows if r['type']=='way' and r['tags'].get('highway') in MAJOR]
            caps=dict(STREAM_CAPS,references=sum(len(r['nodes']) for r in ways),ways=len(ways),taggedNodes=sum(r['type']=='node' and bool(r['tags']) for r in rows),
                relationNodes=sum(m['type']=='node' for r in rows if r['type']=='relation' for m in r['members']),relationWays=sum(m['type']=='way' for r in rows if r['type']=='relation' for m in r['members']),presenceMaxNodeID=4,chunkReferences=100,fileBytes=67108864,ownedBytes=67108864)
            streams=Streams(root/'streams',kernel,caps,check);engine=NativeScreen(*artifact)
            receipt=engine.validate_frames(framed_records(rows),STATE,dict(SCAN,scanNodesPerPass=10000,scanWaysPerPass=10000,scanRelationsPerPass=10000,scanObjectVisitsTotal=100000),check=check,on_topology=streams.accept,presence_max_node_id=4)
            bounded_save(root,'fixture.json',rows);bounded_save(root,'receipt.json',receipt)
        else:
            source=Path('/inputs/country.pbf');require(source.stat().st_size==SOURCE['bytes'],'Topology source exact size')
            require(plan['topologyCaps']==STREAM_CAPS,'Topology fixed source-derived stream bounds')
            streams=Streams(root/'streams',kernel,STREAM_CAPS,check)
            engine=NativeScreen('/artifacts/country-screen.so',plan['artifact']['sha256'],aggregate_visits=1770542426)
            receipt=engine.scan(source,SOURCE['state'],SCAN,source=SOURCE,check=check,on_topology=streams.accept,presence_max_node_id=STREAM_CAPS['presenceMaxNodeID'])
            bounded_save(root,'receipt.json',receipt)
            prior=strict_json(Path('/'+PRIOR).read_bytes())['receipt']
            require(receipt['counts']==dict(zip(('node','way','relation'),SOURCE_COUNTS)) and receipt['semanticSha256']==SOURCE['semanticSha256'] and receipt['nativeEof'],'Topology original whole-source seals')
            require(receipt['metadata']==prior['metadata'],'Topology original source metadata')
            for key in ('references','members','tags','tagUtf8Bytes','maxReferences','maxMembers','maxTags','highwayWays','examinedHighwayReferences'):
                require(receipt[key]==prior[key],'Topology original source counter: '+key)
            census=strict_json(Path('/inputs/footprint-receipt.json').read_bytes())
            require(receipt['histogram']==census['histogram'] and receipt['topologyReferences']==STREAM_CAPS['references'] and receipt['topologyWays']==STREAM_CAPS['ways'],'Topology exact profile/census binding')
            require(receipt['pythonProjectionFrames']==0,'Topology no ordinary Python object projections')
        topology=streams.finish();streams.close();bounded_save(root,'topology.json',topology)
        check();bounded_save(root,'result.json',{'status':'passed_streaming_topology_census','stage':stage,'receiptSha256':sha(root/'receipt.json'),'topologySha256':sha(root/'topology.json'),'secondsIncludingWorkerBindingsScanAndOutput':time.monotonic()-began,'modelChanged':False,'graphAllocated':False,'etaQualified':False,'vercelQualified':False})
        return 0
    except BaseException as error:
        if engine is not None and engine.last is not None and not (root/'partial-receipt.json').exists():bounded_save(root,'partial-receipt.json',engine.last)
        bounded_save(root,'worker-failure.json',{'errorType':type(error).__name__,'error':str(error)[:2000],'modelChanged':False});return 2
    finally:
        if streams is not None:streams.close()
        bounded_save(root,'metrics-end.json',resource_metrics())
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


def isolation(observed,stage):
    host=observed['HostConfig'];tmp='/builder/tmp' if stage=='build' else '/tmp'
    expected={'NetworkMode':'none','Memory':CAPS['memoryBytes'],'MemorySwap':CAPS['memoryBytes'],'ReadonlyRootfs':True,'NanoCpus':2000000000,'PidsLimit':64,'Tmpfs':{tmp:'rw,size=256m'}}
    require(observed['Image']==IMAGE and all(host[k]==v for k,v in expected.items()),'Topology observed isolation')
    require({c.removeprefix('CAP_') for c in host.get('CapAdd') or []}==({'SYS_CHROOT'} if stage=='build' else set()) and {c.removeprefix('CAP_') for c in host['CapDrop']}=={'ALL'} and 'no-new-privileges' in host['SecurityOpt'],'Topology capabilities')
    require(all(not m['RW'] for m in observed['Mounts'] if m['Destination'] not in ('/work','/builder/work')),'Topology readonly inputs')
    require({u['Name']:(u['Soft'],u['Hard']) for u in host['Ulimits']}=={'core':(0,0),'fsize':(CAPS['fileBytes'],CAPS['fileBytes'])},'Topology hard file/core')


def driver(plan,recipe):
    repo=Path(__file__).resolve().parents[1];stage=plan['stage'];root=repo/OUTPUTS[stage]
    require(not root.exists(),'Topology fresh output required');root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json')
    began=time.monotonic();owner=uuid.uuid4().hex;name='geo-planner-topology-'+stage+'-'+owner[:12];identity=child=None;code=2
    bounded_save(root,'owner.json',{'name':name,'label':owner,'image':IMAGE})
    def check():
        require(time.monotonic()-began<CAPS['hostSeconds'][stage]-15,'Topology host deadline')
        usage=owned_usage(root);require(usage['conservativeAllocatedBytes']<=CAPS['ownedBytes'][stage] and usage['entries']<=CAPS['entries'],'Topology host allocation/namespace')
        require(shutil.disk_usage(root).free>=1073741824,'Topology disk headroom')
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=10)
    try:
        for name_input,pin in plan['inputs'].items():check();require(sha(repo/name_input)==pin,'Topology host input drift: '+name_input)
        if stage=='build':
            spec=importlib.util.spec_from_file_location('qualified_asset_contents',repo/plan['assetProof']);assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)
            require(assets.snapshot(repo/ASSET_ROOT)==plan['rootfs']['portable'],'Topology cached compiler contents')
            for pin in plan['headers'].values():require(assets.snapshot(repo/pin['path'])==pin['portable'],'Topology cached header contents')
        else:require(sha(repo/plan['artifact']['path'])==plan['artifact']['sha256'],'Topology host artifact drift')
        # The country file is not read here: the bounded worker authenticates it
        # while framing and again after the native pass, avoiding an extra host scan.
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--tmpfs',('/builder/tmp' if stage=='build' else '/tmp')+':rw,size=256m','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864','--env','PYTHONPATH=/code:/tools/site','--env','LD_LIBRARY_PATH=/tools/runtime','--env','OSMIUM_MAX_INPUT_QUEUE_SIZE=2','--env','OSMIUM_MAX_OSMDATA_QUEUE_SIZE=2']
        if stage=='build':
            args+=['--cap-add=SYS_CHROOT','--mount',f'type=bind,src={repo/ASSET_ROOT},dst=/builder,readonly','--mount',f'type=bind,src={root},dst=/builder/work']
            for key,path in HEADERS.items():args+=['--mount',f'type=bind,src={repo/path},dst=/builder/inputs/{key},readonly']
        else:args+=['--mount',f'type=bind,src={repo/OUTPUTS["build"]},dst=/artifacts,readonly']
        if stage=='run':args+=['--mount',f'type=bind,src={repo/SOURCE["path"]},dst=/inputs/country.pbf,readonly']
        # All mounted files are exactly checksum-bound, including cached site files.
        for source,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_topology_v1.py','/inputs/recipe.json',sha(recipe),'--worker']
        created=call(args);require(created.returncode==0,created.stderr);identity=created.stdout.strip();require(len(identity)==64,'Topology owned identity')
        initial=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(initial,stage)
        bounded_save(root,'container-initial.json',{'Image':initial['Image'],'HostConfig':initial['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in initial['Mounts']]})
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:check();require((root/'worker.log').stat().st_size<=2097152,'Topology log cap');time.sleep(.5)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0];bounded_save(root,'container-result.json',{'State':final['State'],'clientExitCode':child.returncode})
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Topology worker failed/OOM');code=0
    except BaseException as error:bounded_save(root,'driver-failure.json',{'errorType':type(error).__name__,'error':str(error)[:2000]})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        if not (root/'container-result.json').exists():settle_error(call,identity,name,owner,root,child.returncode if child is not None else None)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    bounded_save(root,'run-summary.json',{'exitCode':code,'hostSecondsIncludingBindingsWorkerCleanup':time.monotonic()-began,'stage':stage,'networkRequests':0,'modelChanged':False});return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    recipe=Path(args.recipe).resolve();require(sha(recipe)==args.sha256,'Topology recipe binding');plan=strict_json(recipe.read_bytes());validate(plan)
    raise SystemExit(worker(plan) if args.worker else driver(plan,recipe))
