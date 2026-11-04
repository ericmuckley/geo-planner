"""Native car-capacity qualification, typed partition derivation and guarded country counters."""
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
from run_osm_country_screen_v15 import ASSET_ROOT, HEADERS
from coarse_osm_car_policy_v1 import POLICY

FLAGS=['-std=c++17','-O2','-fPIC','-shared','-fvisibility=hidden','-static-libstdc++','-static-libgcc',
       '-pthread','-I/inputs/libosmium/include','-I/inputs/protozero/include',
       '/work/coarse_osm_car_capacity_v1.cpp','/work/coarse_osm_car_partition_v1.cpp',
       '/work/coarse_osm_car_native_policy_v1.cpp','/work/coarse_osm_delta_v1.cpp',
       '-Wl,-z,defs','-Wl,--exclude-libs,ALL','-Wl,-Bsymbolic-functions','-lz','-o','/work/car-capacity.so']
OUTPUTS={stage:'data/coarse-quality/us-osm-car-capacity-'+stage+'-v1' for stage in ('build','controls','derive','run')}
CAPS={'memoryBytes':4294967296,'tmpBytes':268435456,'fileBytes':67108864,
      'ownedBytes':{'build':67108864,'controls':67108864,'derive':67108864,'run':268435456},'entries':1024,
      'priorRetainedReserveBytes':64500000000,'overallRetainedBytes':68719476736,
      'workerSeconds':{'build':150,'controls':180,'derive':600,'run':3600},
      'hostSeconds':{'build':180,'controls':210,'derive':660,'run':3900}}
TESTS=67
SOURCE={'path':'data/coarse-quality/us-osm-input-v3/download/http/001.bin','bytes':12229320016,
        'sha256':'1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff','md5':'c5abaec55e724255277f22fb97941e5a',
        'state':'2026-10-25T21:21:21Z','semanticSha256':'209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16'}
SCAN={'singleNormalizedElementBytes':4194304,'scanNodesPerPass':1606229364,'scanWaysPerPass':162688797,
      'scanRelationsPerPass':1624265,'scanObjectVisitsTotal':1770542426,
      'pbfHeaderBytesExclusiveMaximum':65536,'pbfUncompressedBlobBytesExclusiveMaximum':33554432}
PROPOSAL='docs/evidence/coarse-osm-offline-plan-2026-10-26/proposal.json'
PRIOR='docs/evidence/coarse-osm-country-exec-2026-10-30/screen-raw-v4/screen/pass-b/summary.json'


def validate(plan):
    stage=plan['stage'];require(stage in OUTPUTS and plan['phase']=='native_car_capacity_v1','Car capacity phase')
    require(plan['caps']==CAPS and plan['source']==SOURCE and plan['scanCaps']==SCAN and plan['image']==IMAGE and plan['flags']==FLAGS and plan['policy']==POLICY,'Car capacity frozen parameters')
    require(plan['output']==OUTPUTS[stage] and plan['network']=='none' and plan['imagePull']=='never','Car capacity fresh output/network')
    require(set(plan['mounts'])==set(plan['inputs']) and plan['tests']==TESTS,'Car capacity exact input roster/tests')
    for path,dest in plan['mounts'].items():
        require(not Path(path).is_absolute() and '..' not in Path(path).parts and dest.startswith(('/code/','/reference/','/tools/','/inputs/','/docs/')),'Car capacity readonly input scope')
        require(path!=SOURCE['path'] and 'primary-index' not in path,'Car capacity country source only through guarded run mount')
    require(plan['rootfs']['path']==ASSET_ROOT and {k:v['path'] for k,v in plan['headers'].items()}==HEADERS,'Car capacity cached build assets')
    require(CAPS['priorRetainedReserveBytes']+sum(plan['newClosedAllocations'].values())+sum(CAPS['ownedBytes'].values())+CAPS['tmpBytes']<CAPS['overallRetainedBytes'],'Car capacity overall retained envelope')
    if stage!='build':require(plan['artifact']['path']==OUTPUTS['build']+'/car-capacity.so','Car capacity artifact identity')
    if stage in ('derive','run'):require(plan['admission']['tests']==TESTS and plan['admission']['successful'] and plan['admission']['skips']==0,'Car capacity controls before data')
    if stage=='run':require(plan['partition']['qualified'] and plan['partition']['path']==OUTPUTS['derive']+'/splits.u64','Car capacity exact partition input')


def bounded_save(root,name,value):
    path=root/name;raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    require(path.parent==root and not path.exists() and not path.is_symlink() and len(raw)<=2097152,'Topology exclusive bounded record')
    with path.open('xb') as stream:stream.write(raw)


def worker(plan):
    from array import array
    from coarse_osm_data import verify_worker_inputs,memory_guard
    root=Path('/work');stage=plan['stage'];began=time.monotonic();last_check=last_progress=0.;engine=None
    timer=start_watchdog(CAPS['workerSeconds'][stage])
    def check():
        nonlocal last_check,last_progress
        now=time.monotonic();require(now-began<CAPS['workerSeconds'][stage]-5,'Car capacity worker deadline')
        if now-last_check>=1:
            last_check=now;usage=owned_usage(root)
            require(usage['conservativeAllocatedBytes']<=CAPS['ownedBytes'][stage] and usage['entries']<=CAPS['entries'],'Car capacity allocation/namespace')
        if engine is not None and now-last_progress>=15:
            last_progress=now;print(json.dumps({'seconds':now-began,'sourceProgress':engine.progress()}),flush=True)
    try:
        verify_worker_inputs({'workerFiles':{dest:plan['inputs'][name] for name,dest in plan['mounts'].items()}})
        memory_guard();tmp=os.statvfs('/builder/tmp' if stage=='build' else '/tmp')
        require(tmp.f_blocks*tmp.f_frsize==CAPS['tmpBytes'] and resource.getrlimit(resource.RLIMIT_FSIZE)==(CAPS['fileBytes'],CAPS['fileBytes']),'Car capacity tmp/file guards')
        bounded_save(root,'metrics-start.json',resource_metrics())
        if stage=='build':
            root.chmod(0o777)
            for name in ('coarse_osm_car_capacity_v1.cpp','coarse_osm_topology_source_v1.cpp','coarse_osm_car_partition_v1.cpp',
                         'coarse_osm_topology_kernel_v1.cpp','coarse_osm_car_native_policy_v1.cpp','coarse_osm_car_native_policy_v1.hpp','coarse_osm_delta_v1.cpp'):
                shutil.copyfile('/code/'+name,root/name)
            import qualified_asset_contents
            for name,pin in plan['headers'].items():require(qualified_asset_contents.snapshot('/builder/inputs/'+name)==pin['portable'],'Car capacity header contents')
            tool(root,'compiler-version',[COMPILER,'--version'],check);tool(root,'compile',[COMPILER,*FLAGS],check)
            elf=tool(root,'elf',['/usr/bin/readelf','-h','-d','-V','-Ws','/work/car-capacity.so'],check)
            import re
            needed=re.findall(r'\(NEEDED\).*?\[([^\]]+)\]',elf)
            require('AArch64' in elf and 'little endian' in elf and 'GLIBCXX_' not in elf and all(name in elf for name in ('gp_country_screen_abi','gp_country_screen_frames','gp_country_screen_pbf','gp_car_capacity_abi','gp_car_capacity_begin','gp_car_capacity_frames','gp_car_capacity_pbf','gp_car_capacity_finish','gp_car_partition_splits','gp_car_policy_frame')),'Car capacity ELF/ABI')
            require(set(needed)<={'libz.so.1','libm.so.6','libc.so.6','libpthread.so.0','libdl.so.2','librt.so.1','ld-linux-aarch64.so.1'},'Car capacity dependencies')
            bounded_save(root,'result.json',{'status':'compiled_controls_pending','artifactSha256':sha(root/'car-capacity.so'),'artifactBytes':(root/'car-capacity.so').stat().st_size,'needed':needed});return 0
        artifact=('/artifacts/car-capacity.so',plan['artifact']['sha256']);require(sha(artifact[0])==artifact[1],'Car capacity artifact drift')
        if stage=='controls':
            import coarse_osm_topology_source_v1_test as source_tests
            import coarse_osm_topology_kernel_v1_test as kernel_tests
            import coarse_osm_car_native_policy_v1_test as policy_tests
            import coarse_osm_car_partition_v1_test as partition_tests
            import coarse_osm_car_capacity_v1_test as capacity_tests
            suite=unittest.TestSuite()
            for tests in (source_tests,kernel_tests,policy_tests,partition_tests,capacity_tests):
                tests.ARTIFACT=artifact;suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(tests))
            tested=unittest.TextTestRunner(verbosity=2).run(suite)
            result={'tests':tested.testsRun,'successful':tested.wasSuccessful(),'skips':len(tested.skipped),'errors':len(tested.errors),'failures':len(tested.failures)}
            bounded_save(root,'controls.json',result);require(tested.wasSuccessful() and tested.testsRun==TESTS and not tested.skipped,'Car capacity controls')
        elif stage=='derive':
            from coarse_osm_car_partition_v1 import Partitions
            topology=strict_json(Path('/inputs/topology/topology.json').read_bytes());roster=topology['artifacts'];base=Path('/inputs/topology/streams')
            refs=[base/n for n in sorted(roster) if n.startswith('refs-')];tags=[base/n for n in sorted(roster) if n.startswith('tagged-')]
            nodes=array('Q');nodes.frombytes((base/'sorted-relation-nodes-0000.bin').read_bytes())
            require(len(nodes)==1201443,'Car capacity relation-node denominator')
            result=Partitions(*artifact).derive(refs,tags,nodes,root/'splits.u64',reference_count=48163649,way_count=4227238,tag_count=48142518,maximum_splits=2447509)
            require(result['anchors']==5731903 and result['contractedEdges']==6674747 and result['internalSplitOccurrences']==2447509 and result['uniqueNodes']==42993567,'Car capacity original lineage counts')
            result.update({'status':'passed_native_way_partition_derivation','splitSha256':sha(root/'splits.u64'),'splitBytes':(root/'splits.u64').stat().st_size,'countryPbfReads':0,'modelChanged':False,'nationalGraphBuilt':False})
        else:
            from coarse_osm_car_capacity_v1 import Capacity
            source=Path('/inputs/country.pbf');require(source.stat().st_size==SOURCE['bytes'],'Car capacity exact country source length')
            split_path=Path('/inputs/splits.u64');require(sha(split_path)==plan['partition']['sha256'] and split_path.stat().st_size==19580072,'Car capacity partition binding')
            splits=array('Q');splits.frombytes(split_path.read_bytes());facts=root/'way-facts';facts.mkdir()
            engine=Capacity(*artifact,aggregate_visits=1770542426);engine.begin(splits,14319708500,facts)
            receipt=engine.scan(source,SOURCE['state'],SCAN,source=SOURCE,check=check)
            bounded_save(root,'receipt.json',receipt)
            prior=strict_json(Path('/'+PRIOR).read_bytes())['receipt'];census=strict_json(Path('/inputs/footprint-receipt.json').read_bytes())
            require(receipt['counts']==dict(zip(('node','way','relation'),SOURCE_COUNTS)) and receipt['semanticSha256']==SOURCE['semanticSha256'] and receipt['nativeEof'],'Car capacity complete source seals')
            require(receipt['metadata']==prior['metadata'] and receipt['histogram']==census['histogram'],'Car capacity exact complete source metadata/histogram')
            for key in ('references','members','tags','tagUtf8Bytes','maxReferences','maxMembers','maxTags','highwayWays','examinedHighwayReferences'):
                require(receipt[key]==prior[key],'Car capacity source counter: '+key)
            require(receipt['pythonProjectionFrames']==0,'Car capacity no ordinary Python source objects')
            result=engine.finish()
            require(result['majorWays']==4227238 and result['majorReferences']==48163649 and result['primitiveEdges']==43936411 and result['lineageSegmentsIncludingZero']==6674747 and result['partitionSplitsConsumed']==2447509,'Car capacity exact whole profile')
            result['status']='passed_guarded_national_car_capacity_census'
            result['routingBaseBytesPreClosures']=13*5731903+7*result['preClosureArcs']+4
            result['routingBaseBytesAfterLocatableClosures']=13*5731903+7*result['postLocatableClosureArcs']+4
            result['capacityScope']='Coordinates/CSR/u16cost/reverse-u8/nodeflags arithmetic only. Costs/overflow/turns/snap/geography/decoding/search/JS/package remain unqualified; unlocatable restrictions block policy admission.'
            result.update({'nationalGraphBuilt':False,'etaQualified':False,'vercelQualified':False,'modelChanged':False,'networkRequests':0,'applicationDbReads':0})
            artifacts={}
            for path in sorted(facts.iterdir()):artifacts[str(path.relative_to(root))]={'bytes':path.stat().st_size,'sha256':sha(path)}
            bounded_save(root,'artifacts.json',artifacts)
        check();bounded_save(root,'result.json',result|{'secondsIncludingWorkerBindingsAndOutput':time.monotonic()-began});return 0
    except BaseException as error:
        if engine is not None and engine.last is not None and not (root/'partial-receipt.json').exists():bounded_save(root,'partial-receipt.json',engine.last)
        bounded_save(root,'worker-failure.json',{'errorType':type(error).__name__,'error':str(error)[:2000],'modelChanged':False});return 2
    finally:
        if engine is not None:engine.release()
        bounded_save(root,'metrics-end.json',resource_metrics())
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)

def isolation(observed,stage):
    host=observed['HostConfig'];tmp='/builder/tmp' if stage=='build' else '/tmp'
    expected={'NetworkMode':'none','Memory':CAPS['memoryBytes'],'MemorySwap':CAPS['memoryBytes'],'ReadonlyRootfs':True,'NanoCpus':2000000000,'PidsLimit':64,'Tmpfs':{tmp:'rw,size=256m'}}
    require(observed['Image']==IMAGE and all(host[k]==v for k,v in expected.items()),'Car capacity observed isolation')
    require({c.removeprefix('CAP_') for c in host.get('CapAdd') or []}==({'SYS_CHROOT'} if stage=='build' else set()) and {c.removeprefix('CAP_') for c in host['CapDrop']}=={'ALL'} and 'no-new-privileges' in host['SecurityOpt'],'Car capacity capabilities')
    require(all(not m['RW'] for m in observed['Mounts'] if m['Destination'] not in ('/work','/builder/work')),'Car capacity readonly inputs')
    require({u['Name']:(u['Soft'],u['Hard']) for u in host['Ulimits']}=={'core':(0,0),'fsize':(CAPS['fileBytes'],CAPS['fileBytes'])},'Car capacity hard file/core')


def driver(plan,recipe):
    repo=Path(__file__).resolve().parents[1];stage=plan['stage'];root=repo/OUTPUTS[stage]
    require(not root.exists(),'Car capacity fresh output required');root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json')
    began=time.monotonic();owner=uuid.uuid4().hex;name='geo-planner-car-capacity-'+stage+'-'+owner[:12];identity=child=None;code=2
    bounded_save(root,'owner.json',{'name':name,'label':owner,'image':IMAGE})
    def check():
        require(time.monotonic()-began<CAPS['hostSeconds'][stage]-15,'Car capacity host deadline')
        usage=owned_usage(root);require(usage['conservativeAllocatedBytes']<=CAPS['ownedBytes'][stage] and usage['entries']<=CAPS['entries'],'Car capacity host allocation/namespace')
        require(shutil.disk_usage(root).free>=1073741824,'Car capacity disk headroom')
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=10)
    try:
        for name_input,pin in plan['inputs'].items():check();require(sha(repo/name_input)==pin,'Car capacity host input drift: '+name_input)
        if stage=='build':
            spec=importlib.util.spec_from_file_location('qualified_asset_contents',repo/plan['assetProof']);assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)
            require(assets.snapshot(repo/ASSET_ROOT)==plan['rootfs']['portable'],'Car capacity cached compiler contents')
            for pin in plan['headers'].values():require(assets.snapshot(repo/pin['path'])==pin['portable'],'Car capacity cached header contents')
        else:require(sha(repo/plan['artifact']['path'])==plan['artifact']['sha256'],'Car capacity host artifact drift')
        # The country file is not read here: the bounded worker authenticates it
        # while framing and again after the native pass, avoiding an extra host scan.
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--tmpfs',('/builder/tmp' if stage=='build' else '/tmp')+':rw,size=256m','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864','--env','PYTHONPATH=/code:/tools/site:/reference','--env','LD_LIBRARY_PATH=/tools/runtime','--env','OSMIUM_MAX_INPUT_QUEUE_SIZE=2','--env','OSMIUM_MAX_OSMDATA_QUEUE_SIZE=2']
        if stage=='build':
            args+=['--cap-add=SYS_CHROOT','--mount',f'type=bind,src={repo/ASSET_ROOT},dst=/builder,readonly','--mount',f'type=bind,src={root},dst=/builder/work']
            for key,path in HEADERS.items():args+=['--mount',f'type=bind,src={repo/path},dst=/builder/inputs/{key},readonly']
        else:args+=['--mount',f'type=bind,src={repo/OUTPUTS["build"]},dst=/artifacts,readonly']
        if stage=='run':args+=['--mount',f'type=bind,src={repo/SOURCE["path"]},dst=/inputs/country.pbf,readonly']
        # All mounted files are exactly checksum-bound, including cached site files.
        for source,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_car_capacity_v1.py','/inputs/recipe.json',sha(recipe),'--worker']
        created=call(args);require(created.returncode==0,created.stderr);identity=created.stdout.strip();require(len(identity)==64,'Car capacity owned identity')
        initial=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(initial,stage)
        bounded_save(root,'container-initial.json',{'Image':initial['Image'],'HostConfig':initial['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in initial['Mounts']]})
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:check();require((root/'worker.log').stat().st_size<=2097152,'Car capacity log cap');time.sleep(.5)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0];bounded_save(root,'container-result.json',{'State':final['State'],'clientExitCode':child.returncode})
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Car capacity worker failed/OOM');code=0
    except BaseException as error:bounded_save(root,'driver-failure.json',{'errorType':type(error).__name__,'error':str(error)[:2000]})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        if not (root/'container-result.json').exists():settle_error(call,identity,name,owner,root,child.returncode if child is not None else None)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    bounded_save(root,'run-summary.json',{'exitCode':code,'hostSecondsIncludingBindingsWorkerCleanup':time.monotonic()-began,'stage':stage,'networkRequests':0,'modelChanged':False});return code


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    recipe=Path(args.recipe).resolve();require(sha(recipe)==args.sha256,'Car capacity recipe binding');plan=strict_json(recipe.read_bytes());validate(plan)
    raise SystemExit(worker(plan) if args.worker else driver(plan,recipe))
