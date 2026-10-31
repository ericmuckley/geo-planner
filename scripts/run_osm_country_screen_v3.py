"""One frozen offline country-summary qualification, synthetic inputs only."""
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
OUTPUT='data/coarse-quality/us-osm-country-controls-v3'
ASSET_ROOT='data/coarse-quality/us-osm-native-build-v1/prepare/rootfs'
ASSET_PROOF='docs/evidence/coarse-osm-native-build-2026-10-27/asset_contents.py'
PROPOSAL='docs/evidence/coarse-osm-offline-plan-2026-10-26/proposal.json'
HEADERS={'libosmium':'data/coarse-quality/us-osm-native-build-v1/prepare/source-1',
    'protozero':'data/coarse-quality/us-osm-native-build-v1/prepare/source-2'}
FLAGS=['-std=c++17','-O2','-fPIC','-shared','-fvisibility=hidden','-static-libstdc++','-static-libgcc',
    '-pthread','-I/inputs/libosmium/include','-I/inputs/protozero/include','/work/country-screen.cpp','/work/delta.cpp',
    '-Wl,-z,defs','-Wl,--exclude-libs,ALL','-Wl,-Bsymbolic-functions','-lz','-o','/work/country-screen.so']


MODULES = ['coarse_osm_stream_v1_test', 'coarse_osm_stream_driver_v1_test', 'coarse_osm_validation_v4_test',
           'coarse_osm_delta_v2_test', 'coarse_osm_projector_v1_test', 'coarse_osm_sample_v1_test',
           'coarse_osm_sample_v2_test', 'coarse_osm_country_screen_v1_test', 'coarse_osm_country_screen_v2_test', 'coarse_osm_country_runner_v3_test']
LEGACY = {'path':'data/coarse-quality/us-osm-projector-v1/build/projector.so',
          'sha256':'9227bc577f3592f167d614329ecc25311c4f8505aa854d3121f9837073f75f26'}

OLD_RECIPE='docs/evidence/coarse-osm-country-helper-2026-10-30/qualification-plan.json'
LEGACY_COUNTRY={'path':'data/coarse-quality/us-osm-country-controls-v1/build/country-screen.so',
                'sha256':'0b3d2d9e609350252fb9850a2342215c6fae3172b03b76fc65350b55c66b9a53'}


def validate(plan):
    require(plan['phase']=='offline_native_country_screen_v3' and plan['caps']==CAPS, 'Country screen phase/caps drift')
    require(plan['imageId']==IMAGE and plan['imagePull']=='never' and plan['output']==OUTPUT, 'Country screen image/output drift')
    require(plan['phases']==['controls'] and plan['network']=='none' and plan['flags']==FLAGS, 'Country screen stages/network/flags drift')
    require(plan['modules']==MODULES and plan['legacyArtifact']==LEGACY, 'Country screen retained controls/artifact')
    require(plan['reusedBuild']=={'path':BUILD_ROOT,'sha256':'56cb0ae4020e9ea04586ea72e1f71a2f6a943d83222dfa42d40a0a4f65a42c9a'}, 'Country exact reused V2 build')
    require(plan['mounts'].get(PROPOSAL)=='/'+PROPOSAL and plan['mounts'].get('scripts/coarse_osm_delta_v1.cpp')=='/code/coarse_osm_delta_v1.cpp', 'Country screen proposal/codec binding')
    require(plan['rootfs']['path']==ASSET_ROOT and plan['rootfs']['portable']['portableTreeSha256']=='a64ef22d93c8b49689ccfefe09c67a62e67422cb84c6edb86089533fb33ebd72', 'Country screen rootfs drift')
    require({name:pin['path'] for name,pin in plan['headers'].items()}==HEADERS, 'Country screen header paths')
    for source,destination in plan['mounts'].items():
        require(source.startswith('scripts/') and source.endswith(('.py','.cpp')) and '..' not in Path(source).parts or source in (ASSET_PROOF,PROPOSAL,OLD_RECIPE), 'Country screen refuses real source mounts')
        require(destination.startswith('/code/') or source==PROPOSAL and destination=='/'+PROPOSAL or source==OLD_RECIPE and destination=='/inputs/recipe.json', 'Country screen mount destination')
        require(plan['inputs'][source]==plan['workerFiles'][destination], 'Country screen mount checksum')
    for name in plan['inputs']:
        require('..' not in Path(name).parts and (name.startswith(('scripts/','docs/evidence/',plan['site']+'/'))
                or name in plan['runtime'].values() or name in (LEGACY['path'],LEGACY_COUNTRY['path'],ARTIFACT_PATH,BUILD_ROOT+'/result.json','data/coarse-quality/us-osm-native-lock-v1/acquire/http/001.bin')), 'Country screen refuses source/other asset hashes')
    require(plan['workerFiles']['/legacy/projector.so']==plan['inputs'][LEGACY['path']]==LEGACY['sha256'], 'Country screen prior artifact binding')
    require(plan['workerFiles']['/legacy-country/country-screen.so']==plan['inputs'][LEGACY_COUNTRY['path']]==LEGACY_COUNTRY['sha256'], 'Country screen prior country artifact binding')
    require(plan['sourceOrSavedSampleReads']==0 and plan['aggregateSourceReceipts']==2000000, 'Country screen synthetic-only bounds')


def guards(root,phase):
    disk=os.statvfs('/builder/tmp' if phase=='build' else '/tmp')
    require(disk.f_blocks*disk.f_frsize==CAPS['tmpBytes'],'Country screen tmp guard')
    require(resource.getrlimit(resource.RLIMIT_FSIZE)==(CAPS['fileBytes'],CAPS['fileBytes']),'Country screen file guard')
    save(root/'resource-guards.json',{'memory':memory_guard(),'tmpBytes':CAPS['tmpBytes'],'fileBytes':CAPS['fileBytes'],
        'phase':phase,'watchdogSeconds':CAPS['workerSeconds'],'sysChrootCapability':phase=='build'})


def worker(plan,root,phase):
    root=Path(root);watchdog=start_watchdog(CAPS['workerSeconds']);began=time.monotonic()
    from coarse_osm_country_screen_v2 import resource_metrics, owned_usage
    def check():
        require(time.monotonic()-began<CAPS['workerSeconds'], 'Country screen worker deadline')
        usage=owned_usage(root)
        require(usage['conservativeAllocatedBytes']<CAPS['workingBytesIncludingTmp']-CAPS['tmpBytes'] and usage['entries']<=1024, 'Country screen allocated working/namespace cap')
    try:
        verify_worker_inputs(plan);guards(root,phase)
        save(root/'metrics-start.json',resource_metrics())
        if phase=='build':
            root.chmod(0o777)
            shutil.copyfile('/code/coarse_osm_country_screen_v2.cpp',root/'country-screen.cpp')
            shutil.copyfile('/code/coarse_osm_delta_v1.cpp',root/'delta.cpp')
            import qualified_asset_contents
            for name,pin in plan['headers'].items():require(qualified_asset_contents.snapshot('/builder/inputs/'+name)==pin['portable'], 'Country screen header drift')
            tool(root,'compiler-version',[COMPILER,'--version'],check)
            tool(root,'compile',[COMPILER,*FLAGS],check)
            elf=tool(root,'elf',['/usr/bin/readelf','-h','-d','-V','-Ws','/work/country-screen.so'],check)
            exports=['gp_delta_abi','gp_delta_decode','gp_country_screen_abi','gp_country_screen_frames','gp_country_screen_pbf',
                     'gp_country_screen_add','gp_country_screen_priority','gp_country_screen_stratum']
            require('AArch64' in elf and 'little endian' in elf and all(name in elf for name in exports) and 'GLIBCXX_' not in elf, 'Country screen ELF/ABI/runtime')
            import re
            needed=re.findall(r'\(NEEDED\).*?\[([^\]]+)\]',elf)
            require(set(needed)<={'libz.so.1','libm.so.6','libc.so.6','libpthread.so.0','libdl.so.2','librt.so.1','ld-linux-aarch64.so.1'}, 'Country screen dynamic dependency')
            artifact=root/'country-screen.so'
            save(root/'result.json',{'status':'compiled_country_screen_controls_pending','artifactSha256':sha(artifact),'artifactBytes':artifact.stat().st_size,
                'sourceSha256':sha(root/'country-screen.cpp'),'deltaSourceSha256':sha(root/'delta.cpp'),'flags':FLAGS,'needed':needed,'exports':exports,'elfSha256':sha(root/'elf.log')})
            return 0
        import coarse_osm_delta_v2_test as delta
        import coarse_osm_projector_v1_test as prior
        import coarse_osm_country_screen_v1_test as country_prior
        import coarse_osm_country_screen_v2_test as tests
        artifact=strict_json(Path('/artifacts/result.json').read_bytes())
        require(sha(Path('/artifacts/country-screen.so'))==artifact['artifactSha256']==plan['reusedBuild']['sha256'], 'Country reused compiled artifact drift')
        for module in (delta,prior):module.configure_native('/legacy/projector.so',LEGACY['sha256'])
        country_prior.configure_native('/legacy-country/country-screen.so',LEGACY_COUNTRY['sha256'])
        tests.configure_native('/artifacts/country-screen.so',artifact['artifactSha256'])
        def flatten(suite):
            for item in suite:
                if isinstance(item,unittest.TestSuite):yield from flatten(item)
                else:yield item.id()
        suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in MODULES)
        require(sorted(flatten(suite))==plan['testIds'], 'Country screen test roster drift')
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        cpp_receipts=sum(engine.visits for engine in tests.ENGINES)+sum(engine.visits for engine in country_prior.ENGINES)+sum(engine.visits for engine in prior.ENGINES)
        require(cpp_receipts<=2000000, 'Country screen aggregate synthetic received objects')
        controls={'tests':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
                  'newHelperSourceReceipts':sum(engine.visits for engine in tests.ENGINES),'retainedHelperSourceReceipts':sum(engine.visits for engine in country_prior.ENGINES)+sum(engine.visits for engine in prior.ENGINES),
                  'sourceReceiptScope':'Recognized C++ source objects including rejected/cap+1; retained Python-reference and old codec scopes keep their own finite test bounds.',
                  'newHelperCodecRows':sum(engine.source_codec_rows for engine in tests.ENGINES),'newHelperCodecCalls':sum(engine.source_codec_calls for engine in tests.ENGINES)}
        save(root/'controls.json',controls)
        if not result.wasSuccessful() or result.skipped:return 2
        from coarse_osm_country_screen_v2 import NativeScreen,run_pair
        from coarse_osm_projector_v1 import reference_seal
        from coarse_osm_native_smoke import fixture_records,write_xml,STATE
        from coarse_osm_bulk_pbf import native_records
        from coarse_osm_country_screen_v1_test import binding
        import osmium
        base=fixture_records()
        rows=[dict(base[0],id=i+1,tags={}) for i in range(300)]
        rows += [dict(base[4],id=i+1,tags={'highway':'primary'},nodes=[i%299+1,i%299+2]) for i in range(200)]
        xml=root/'fixture.osm';pbf=root/'fixture.pbf';write_xml(xml,rows)
        header=osmium.io.Header();header.set('osmosis_replication_timestamp',STATE)
        views=0
        with osmium.SimpleWriter(str(pbf),header=header,bufsz=65536) as writer:
            for obj in osmium.FileProcessor(str(xml)):writer.add(obj);views+=1
        reference=list(native_records(pbf,1048576));save(root/'reference-fields.json',reference)
        engine=NativeScreen('/artifacts/country-screen.so',artifact['artifactSha256']);tests.ENGINES.append(engine)
        caps=deepcopy(strict_json(Path('/'+PROPOSAL).read_bytes())['proposedCaps'])
        caps.update(scanNodesPerPass=10000,scanWaysPerPass=10000,scanRelationsPerPass=10000,scanObjectVisitsTotal=100000)
        actual=[];proof=engine.scan(pbf,STATE,caps,proof=True,on_record=actual.append,check=check)
        require(actual==reference and proof['semanticSha256']==reference_seal(reference), 'Country screen full fields/semantic oracle')
        save(root/'projected-fields.json',actual);save(root/'proof-receipt.json',proof)
        positive=run_pair(pbf,{'node':300,'way':200,'relation':0},caps,STATE,root/'two-pass',engine,binding(pbf),check=check)
        cpp_receipts=sum(e.visits for e in tests.ENGINES)+sum(e.visits for e in country_prior.ENGINES)+sum(e.visits for e in prior.ENGINES)
        require(cpp_receipts+views+len(reference)<=2000000, 'Country screen complete measured synthetic receipts')
        save(root/'result.json',{'status':'passed_country_screen_synthetic_qualification','controls':controls,'proof':proof,
             'positivePipelineStatus':positive['status'],'positivePipelineReceipts':positive['objectReceipts'],
             'aggregateCppSourceReceipts':cpp_receipts,'encodingNativeViews':views,'independentReferenceViews':len(reference),
             'scope':'Synthetic summary/census/probe/ABI controls only. No national file, saved sample or full import.',
             'nationalExecutionAdmitted':False,'modelChanged':False})
        return 0
    except BaseException as error:
        save(root/'worker-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:1000],'fullImportAdmitted':False})
        return 2
    finally:
        try:save(root/'metrics-end.json',resource_metrics())
        except Exception as error:save(root/'metrics-unavailable.json',{'error':str(error)[:1000]})
        finally:
            if watchdog.poll() is None:watchdog.terminate()
            watchdog.wait(timeout=5)


def isolation(observed,phase):
    tmp='/builder/tmp' if phase=='build' else '/tmp'
    expected={'NetworkMode':'none','Memory':4294967296,'MemorySwap':4294967296,'ReadonlyRootfs':True,'NanoCpus':2000000000,'PidsLimit':64,'Tmpfs':{tmp:'rw,size=256m'}}
    require(observed['Image']==IMAGE and all(observed['HostConfig'][k]==v for k,v in expected.items()),'Country screen isolation drift')
    allowed={'/work','/builder/work'} if phase=='build' else {'/work'}
    require(all(not m['RW'] for m in observed['Mounts'] if m['Destination'] not in allowed),'Country screen writable input')
    require({c.removeprefix('CAP_') for c in observed['HostConfig'].get('CapAdd') or []}==({'SYS_CHROOT'} if phase=='build' else set()),'Country screen added capability drift')
    require({c.removeprefix('CAP_') for c in observed['HostConfig'].get('CapDrop') or []}=={'ALL'} and 'no-new-privileges' in observed['HostConfig']['SecurityOpt'],'Country screen capability/security drift')
    require({u['Name']:(u['Soft'],u['Hard']) for u in observed['HostConfig']['Ulimits']}=={'core':(0,0),'fsize':(CAPS['fileBytes'],CAPS['fileBytes'])},'Country screen file/core limits')


def driver(recipe,expected,output):
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==expected,'Country screen recipe path/hash')
    plan=strict_json(recipe.read_bytes());validate(plan)
    root=(repo/output).resolve();require(root==repo/OUTPUT and not root.exists(),'Country screen fresh exact output required')
    root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json')
    began=time.monotonic();deadline=began+CAPS['workSeconds'];hard=began+CAPS['hostSeconds'];owner=uuid.uuid4().hex
    save(root/'owner.json',{'label':owner,'image':IMAGE,'labelKey':'geo-planner.stream-owner'});codes={};success=False
    def check():
        require(time.monotonic()<deadline,'Country screen shared host deadline')
        require(tree_bytes(root)<=CAPS['workingBytesIncludingTmp']-CAPS['tmpBytes'],'Country screen owned storage cap')
        require(shutil.disk_usage(root).free>=2147483648,'Country screen disk headroom')
    def call(args,**kwargs):
        check();return subprocess.run(args,capture_output=True,text=True,timeout=min(15,max(.01,deadline-time.monotonic())),**kwargs)
    def run_phase(phase):
        p=root/phase;p.mkdir();identity=child=None;name='geo-planner-country-screen-v2-'+phase+'-'+owner[:12]
        save(p/'owner.json',{'name':name,'label':owner})
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
            '--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--ulimit','core=0:0','--ulimit',f'fsize={CAPS["fileBytes"]}:{CAPS["fileBytes"]}',
            '--tmpfs',('/builder/tmp' if phase=='build' else '/tmp')+':rw,size=256m','--env','LD_LIBRARY_PATH=/tools/runtime']
        if phase=='build':args+=['--cap-add=SYS_CHROOT','--mount',f'type=bind,src={repo/ASSET_ROOT},dst=/builder,readonly','--mount',f'type=bind,src={p},dst=/builder/work']
        if phase=='build':
            for header_name,path in HEADERS.items():args+=['--mount',f'type=bind,src={repo/path},dst=/builder/inputs/{header_name},readonly']
        else:args+=['--mount',f'type=bind,src={repo/BUILD_ROOT},dst=/artifacts,readonly']
        args+=['--mount',f'type=bind,src={repo/LEGACY["path"]},dst=/legacy/projector.so,readonly',
               '--mount',f'type=bind,src={repo/LEGACY_COUNTRY["path"]},dst=/legacy-country/country-screen.so,readonly']
        args+=['--env','PYTHONPATH=/code:/tools/site','--env','OSMIUM_MAX_INPUT_QUEUE_SIZE=2','--env','OSMIUM_MAX_OSMDATA_QUEUE_SIZE=2']
        for source,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={repo/plan["site"]},dst=/tools/site,readonly']
        for filename,source in plan['runtime'].items():args+=['--mount',f'type=bind,src={repo/source},dst=/tools/runtime/{filename},readonly']
        args+=['--mount',f'type=bind,src={p},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe-v2.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_country_screen_v3.py','--qualify','/inputs/recipe-v2.json',expected,'/work','--worker','--phase',phase]
        try:
            identity=call(args,check=True).stdout.strip();require(len(identity)==64,'Country screen owned container ID')
            initial=json.loads(call(['docker','inspect',identity],check=True).stdout)[0];isolation(initial,phase)
            save(p/'container-initial.json',{'Image':initial['Image'],'HostConfig':initial['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in initial['Mounts']]})
            with (p/'worker.log').open('xb') as log:
                child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
                while child.poll() is None:
                    check();require((p/'worker.log').stat().st_size<=CAPS['reportBytes'],'Country screen worker log cap');time.sleep(.25)
            final=json.loads(call(['docker','inspect',identity],check=True).stdout)[0]
            save(p/'container-result.json',{'Image':final['Image'],'State':final['State'],'clientExitCode':child.returncode})
            require(final['State']['ExitCode']==child.returncode and not final['State']['OOMKilled'],'Country screen worker exit/OOM')
            return child.returncode
        finally:
            if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
            def cleanup_call(args):return subprocess.run(args,capture_output=True,text=True,timeout=max(1,min(15,hard-time.monotonic())))
            try:
                if not (p/'container-result.json').exists():settle_error(cleanup_call,identity,name,owner,p,child.returncode if child is not None else None)
            finally:cleanup_owned(cleanup_call,identity,name,owner,IMAGE,p)
    try:
        for name,pin in plan['inputs'].items():check();require(sha(repo/name)==pin,'Country screen input drift: '+name)
        observed=capacity(repo)
        require(observed['hostDiskAvailableBytes']>=3221225472 and observed['hostMemoryBytes']>=8589934592 and observed['dockerMemoryBytes']>=6442450944,'Country screen starting capacity')
        save(root/'capacity-at-start.json',observed)
        import importlib.util
        spec=importlib.util.spec_from_file_location('qualified_asset_contents',repo/ASSET_PROOF);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        require(module.snapshot(repo/ASSET_ROOT)==plan['rootfs']['portable'],'Country screen qualified compiler contents drift')
        for name,pin in plan['headers'].items():require(module.snapshot(repo/pin['path'])==pin['portable'],'Country screen saved headers drift')
        check();save(root/'asset-verification.json',{'portableRootfsVerified':True,'scope':'File content/path/link hashes only; original Linux permission seal remains in the parent proof.'})
        for phase in plan['phases']:
            codes[phase]=run_phase(phase);require(codes[phase]==0,'Country screen phase stopped: '+phase)
        success=True
    except (Exception,KeyboardInterrupt) as error:
        save(root/'driver-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:1000],'fullImportAdmitted':False})
    require(time.monotonic()-began<CAPS['hostSeconds'],'Country screen final host deadline')
    save(root/'run-summary.json',{'status':'country_screen_synthetic_qualified' if success else 'stopped','phaseClientExitCodes':codes,
        'hostSecondsIncludingInputAssetHashesBuildControlsCleanup':time.monotonic()-began,'networkRequests':0,'sourceOrSavedSampleReads':0,
        'nativeSummaryAndBoundedProbeImplemented':True,'fullImportAdmitted':False,'modelChanged':False})
    return 0 if success else 2


SOURCE={'path':'data/coarse-quality/us-osm-input-v3/download/http/001.bin','bytes':12229320016,
        'sha256':'1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff',
        'md5':'c5abaec55e724255277f22fb97941e5a','publisherState':'2026-10-25T21:21:21Z',
        'counts':{'node':1606229364,'way':162688797,'relation':1624265}}
SCREEN_CAPS={'hostSeconds':7800,'workSeconds':7740,'workerSeconds':7200,'hostHashSeconds':240,
             'passSeconds':3000,'lookupSeconds':300,'memoryBytes':4294967296,'tmpBytes':268435456,
             'workingBytesIncludingTmp':1073741824,'fileBytes':67108864,'reportBytes':2097152,
             'probeIndexBytes':402653184,'lookupShardBytes':4294967296,'lookupCodecRows':256000000}
SCREEN_OUTPUT='data/coarse-quality/us-osm-country-screen-v3'
ADMISSION='docs/evidence/coarse-osm-country-exec-2026-10-30/admission.json'
BUILD_ROOT='data/coarse-quality/us-osm-country-controls-v2/build'
ARTIFACT_PATH=BUILD_ROOT+'/country-screen.so'
QUAL_RECIPE='docs/evidence/coarse-osm-country-exec-2026-10-30/qualification-plan-v3.json'
SITE='data/coarse-quality/us-osm-tools-v3/offline/site'
RUNTIME={'libexpat.so.1':'data/coarse-quality/us-osm-tools-v3/prepare/runtime/libexpat.so.1','copyright':'data/coarse-quality/us-osm-tools-v3/prepare/runtime/copyright'}


def validate_screen(plan):
    require(plan['phase']=='country_screen_execution_v3' and plan['caps']==SCREEN_CAPS and plan['source']==SOURCE, 'Country execution phase/source/caps')
    require(plan['output']==SCREEN_OUTPUT and plan['network']=='none' and plan['imageId']==IMAGE and plan['imagePull']=='never', 'Country execution output/image/network')
    require(plan['artifact']['path']==ARTIFACT_PATH and plan['admission']==ADMISSION, 'Country execution qualified artifact/admission')
    require(plan['site']==SITE and plan['runtime']==RUNTIME, 'Country execution qualified tool paths')
    for source,destination in plan['mounts'].items():
        require('..' not in Path(source).parts and (source.startswith('scripts/') and source.endswith(('.py','.cpp')) or source.startswith('docs/evidence/')), 'Country execution code/evidence mounts')
        require(destination.startswith(('/code/','/docs/evidence/')) or destination in ('/inputs/admission.json','/inputs/recipe.json'), 'Country execution code destination')
        require(plan['inputs'][source]==plan['workerFiles'][destination], 'Country execution code binding')
    require(plan['mounts'].get(ADMISSION)=='/inputs/admission.json', 'Country admission mount')
    require(plan['workerFiles']['/artifacts/country-screen.so']==plan['inputs'][ARTIFACT_PATH]==plan['artifact']['sha256'], 'Country artifact binding')
    for name in plan['inputs']:
        require('..' not in Path(name).parts and (name.startswith(('scripts/','docs/evidence/',plan['site']+'/'))
                or name in plan['runtime'].values() or name in (ARTIFACT_PATH,LEGACY['path'],LEGACY_COUNTRY['path'],'data/coarse-quality/us-osm-native-lock-v1/acquire/http/001.bin')), 'Country execution input closure')
    require(SOURCE['path'] not in plan['inputs'], 'Country source hash must use its bounded host phase')


def verify_admission(plan, admission):
    require(admission['qualified'] and admission['linuxSkips']==0 and admission['tests']>=103 and admission['abi']=='0x00020000', 'Country execution controls admission')
    require(admission['artifactSha256']==plan['artifact']['sha256'], 'Country admission artifact drift')
    required={'scripts/coarse_osm_country_screen_v2.cpp','scripts/coarse_osm_country_screen_v2.py',
              'scripts/coarse_osm_country_screen_v2_test.py','scripts/run_osm_country_screen_v3.py','scripts/coarse_osm_country_runner_v3_test.py'}
    require(set(admission['producerFiles'])==required, 'Country admission complete producer binding')
    require(admission['qualificationRecipeSha256']==plan['inputs'][QUAL_RECIPE], 'Country admission qualification recipe drift')
    require(all(plan['inputs'].get(name)==pin for name,pin in admission['producerFiles'].items()), 'Country admitted producer drift')
    require(admission['ownedWorkersAbsent'] and admission['independentProofPassed'], 'Country independent admission incomplete')


def screen_worker(plan,root):
    from coarse_osm_country_screen_v2 import NativeScreen,Resources,run_pair
    from coarse_osm_data import memory_guard
    root=Path(root);watchdog=start_watchdog(SCREEN_CAPS['workerSeconds'])
    resources=Resources(root,seconds=SCREEN_CAPS['workerSeconds'])
    engine=None;last_progress=0.;sequence=0
    def check():
        nonlocal last_progress,sequence
        resources.check()
        now=time.monotonic()
        if engine is not None and now-last_progress>=60:
            last_progress=now;sequence+=1
            resources.write(root/f'progress-{sequence:04d}.json',{'seconds':now-resources.began,'completedSourceReceipts':engine.visits,
                             'nativeProgress':engine.progress(),'aggregateCounters':engine.totals})
    try:
        verify_worker_inputs(plan);resources.check(force=True)
        admission=strict_json(Path('/inputs/admission.json').read_bytes());verify_admission(plan,admission)
        import resource
        require(resource.getrlimit(resource.RLIMIT_FSIZE)==(67108864,67108864), 'Country file limit')
        tmp=os.statvfs('/tmp');require(tmp.f_blocks*tmp.f_frsize==268435456, 'Country tmp limit')
        resources.write(root/'resource-guards.json',{'memory':memory_guard(),'fileBytes':67108864,'tmpBytes':268435456,
                                                  'workerSeconds':7200,'sourcePassSeconds':3000,'scope':'Actual worker guards; no import forecast'})
        engine=NativeScreen('/artifacts/country-screen.so',plan['artifact']['sha256'],aggregate_visits=3541084852,codec_rows=64000000)
        caps={'singleNormalizedElementBytes':1048576,'scanNodesPerPass':1606229364,'scanWaysPerPass':162688797,
              'scanRelationsPerPass':1624265,'scanObjectVisitsTotal':1770542426,'pbfHeaderBytesExclusiveMaximum':65536,
              'pbfUncompressedBlobBytesExclusiveMaximum':33554432}
        result=run_pair('/source.osm.pbf',SOURCE['counts'],caps,SOURCE['publisherState'],root/'screen',engine,SOURCE,
                        resources=resources,check=check,pass_seconds=3000,lookup_seconds=300,
                        probe_limit=402653184,lookup_rows=256000000,lookup_io=4294967296)
        require(engine.visits==3541084852 and len(result['passes'])==2, 'Country aggregate complete EOF receipts')
        require(result['passes'][1]['globalManifest']['blocks']==392146 and len(result['passes'][1]['mapping'])==8, 'Country complete census shape')
        resources.write(root/'result.json',{'status':'country_screen_passed','sourceReceipts':engine.visits,'aggregateCounters':engine.totals,
                                          'pipelineStatus':result['status'],'storageDecision':result['storageDecision'],
                                          'nationalPhysicalIndexAllocated':False,'wholeRoadExtractionQualified':False,'modelChanged':False})
        return 0
    except BaseException as error:
        save(root/'worker-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:1000],
                                      'lastNativeReceipt':engine.last if engine else None,'receivedSourceObjects':engine.visits if engine else 0,
                                      'wholeSourceEof':False,'indexesTrusted':False,'modelChanged':False})
        return 2
    finally:
        try:save(root/'metrics-end.json',resources.result())
        except Exception as error:save(root/'metrics-unavailable.json',{'error':str(error)[:1000]})
        if watchdog.poll() is None:watchdog.terminate()
        watchdog.wait(timeout=5)


def screen_driver(recipe,expected,output):
    import hashlib
    from coarse_osm_bulk_pbf import stat_key
    from coarse_osm_country_screen_v1 import owned_usage
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==expected, 'Country execution recipe hash/path')
    plan=strict_json(recipe.read_bytes());validate_screen(plan)
    root=(repo/output).resolve();require(root==repo/SCREEN_OUTPUT and not root.exists(), 'Country execution new exact output required')
    root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json')
    began=time.monotonic();deadline=began+7740;hard=began+7800;owner=uuid.uuid4().hex
    name='geo-planner-country-v2-'+owner[:12];identity=child=None;success=False
    save(root/'owner.json',{'name':name,'label':owner,'image':IMAGE,'labelKey':'geo-planner.stream-owner'})
    def check():
        require(time.monotonic()<deadline, 'Country host work deadline')
        require(owned_usage(root)['conservativeAllocatedBytes']<768*1024**2, 'Country host owned allocation cap')
        require(shutil.disk_usage(root).free>=2147483648, 'Country host free-space headroom')
    def call(args,**kwargs):
        check();return subprocess.run(args,capture_output=True,text=True,timeout=min(15,max(.01,deadline-time.monotonic())),**kwargs)
    try:
        for path,pin in plan['inputs'].items():check();require(sha(repo/path)==pin,'Country execution input drift: '+path)
        verify_admission(plan,strict_json((repo/ADMISSION).read_bytes()))
        observed=capacity(repo)
        require(observed['hostDiskAvailableBytes']>=3221225472 and observed['dockerMemoryBytes']>=6442450944 and observed['hostMemoryBytes']>=8589934592
                and observed['hostCpuCount']>=2 and observed['dockerCpuCount']>=2, 'Country host/Docker capacity')
        save(root/'capacity-at-start.json',observed)
        source=repo/SOURCE['path'];require(not source.is_symlink() and source.is_file() and source.stat().st_size==SOURCE['bytes'], 'Country saved source type/length')
        before=stat_key(source);hashed=hashlib.sha256();md5=hashlib.md5();read=0;start=time.monotonic()
        with source.open('rb') as stream:
            while body:=stream.read(8*1024**2):
                require(time.monotonic()-start<240, 'Country host source binding deadline');check()
                read+=len(body);require(read<=SOURCE['bytes'], 'Country host source byte cap');hashed.update(body);md5.update(body)
        require(read==SOURCE['bytes'] and hashed.hexdigest()==SOURCE['sha256'] and md5.hexdigest()==SOURCE['md5'] and before==stat_key(source), 'Country saved source binding/stability')
        save(root/'host-source-binding.json',{'bytesRead':read,'seconds':time.monotonic()-start,'sha256':hashed.hexdigest(),'md5':md5.hexdigest(),'scope':'Host binding pass only; worker framing/pre-post/native reads are separate'})
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL',
              '--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864',
              '--tmpfs','/tmp:rw,size=256m','--env','LD_LIBRARY_PATH=/tools/runtime','--env','PYTHONPATH=/code:/tools/site',
              '--env','OSMIUM_MAX_INPUT_QUEUE_SIZE=2','--env','OSMIUM_MAX_OSMDATA_QUEUE_SIZE=2']
        for source_path,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source_path},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={repo/plan["site"]},dst=/tools/site,readonly']
        for filename,path in plan['runtime'].items():args+=['--mount',f'type=bind,src={repo/path},dst=/tools/runtime/{filename},readonly']
        args+=['--mount',f'type=bind,src={repo/ARTIFACT_PATH},dst=/artifacts/country-screen.so,readonly',
               '--mount',f'type=bind,src={source},dst=/source.osm.pbf,readonly','--mount',f'type=bind,src={root},dst=/work',
               '--mount',f'type=bind,src={recipe},dst=/inputs/screen-recipe.json,readonly','--entrypoint=python3',IMAGE,
               '-B','/code/run_osm_country_screen_v3.py','--screen','/inputs/screen-recipe.json',expected,'/work','--worker']
        identity=call(args,check=True).stdout.strip();require(len(identity)==64,'Country worker identity')
        initial=json.loads(call(['docker','inspect',identity],check=True).stdout)[0];isolation(initial,'controls')
        save(root/'container-initial.json',{'Image':initial['Image'],'HostConfig':initial['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in initial['Mounts']]})
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:
                check();require((root/'worker.log').stat().st_size<=2097152,'Country worker log cap');time.sleep(1)
        final=json.loads(call(['docker','inspect',identity],check=True).stdout)[0]
        save(root/'container-result.json',{'Image':final['Image'],'State':final['State'],'clientExitCode':child.returncode})
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'], 'Country worker exit/OOM')
        success=True
    except (Exception,KeyboardInterrupt) as error:
        save(root/'driver-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:1000],'modelChanged':False})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        def cleanup_call(args):return subprocess.run(args,capture_output=True,text=True,timeout=max(1,min(15,hard-time.monotonic())))
        try:
            if not (root/'container-result.json').exists():settle_error(cleanup_call,identity,name,owner,root,child.returncode if child else None)
        finally:cleanup_owned(cleanup_call,identity,name,owner,IMAGE,root)
    save(root/'run-summary.json',{'status':'country_screen_passed' if success else 'stopped','hostSecondsIncludingBindingsWorkerCleanup':time.monotonic()-began,
                                'networkRequests':0,'nationalSourceMounted':identity is not None,'fullImportAdmitted':False,'modelChanged':False})
    return 0 if success else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--qualify',action='store_true');mode.add_argument('--screen',action='store_true')
    parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('output');parser.add_argument('--worker',action='store_true');parser.add_argument('--phase',choices=['build','controls'])
    args=parser.parse_args()
    if args.worker:
        require(sha(args.recipe)==args.sha256,'Country V2 worker recipe binding');plan=strict_json(Path(args.recipe).read_bytes());sys.path.insert(0,'/tools/site')
        if args.screen:validate_screen(plan);raise SystemExit(screen_worker(plan,args.output))
        validate(plan);require(args.phase is not None,'Country V2 qualification phase');raise SystemExit(worker(plan,args.output,args.phase))
    raise SystemExit(screen_driver(args.recipe,args.sha256,args.output) if args.screen else driver(args.recipe,args.sha256,args.output))
