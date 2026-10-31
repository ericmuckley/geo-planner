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
OUTPUT='data/coarse-quality/us-osm-country-controls-v7'
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
           'coarse_osm_sample_v2_test', 'coarse_osm_country_screen_v1_test', 'coarse_osm_country_screen_v2_test', 'coarse_osm_country_screen_v4_test', 'coarse_osm_country_screen_v5_test', 'coarse_osm_country_screen_v6_test', 'coarse_osm_lookup_v3_test', 'coarse_osm_full_extract_v2_test']
LEGACY = {'path':'data/coarse-quality/us-osm-projector-v1/build/projector.so',
          'sha256':'9227bc577f3592f167d614329ecc25311c4f8505aa854d3121f9837073f75f26'}

OLD_RECIPE='docs/evidence/coarse-osm-country-helper-2026-10-30/qualification-plan.json'
LEGACY_COUNTRY={'path':'data/coarse-quality/us-osm-country-controls-v1/build/country-screen.so',
                'sha256':'0b3d2d9e609350252fb9850a2342215c6fae3172b03b76fc65350b55c66b9a53'}

V5_ARTIFACT='data/coarse-quality/us-osm-country-controls-v5/build/country-screen.so'
V4_ARTIFACT='data/coarse-quality/us-osm-country-controls-v4/build/country-screen.so'
V2_ARTIFACT='data/coarse-quality/us-osm-country-controls-v2/build/country-screen.so'

REUSED_BUILD='data/coarse-quality/us-osm-country-controls-v6/build'
REUSED_SHA='1084fc1b6e9b1a627b52180fd91df0b46e01a967fbd399c2bad672a4f675f48a'


def validate(plan):
    require(plan['phase']=='offline_native_country_screen_v7' and plan['caps']==CAPS, 'Country screen phase/caps drift')
    require(plan['imageId']==IMAGE and plan['imagePull']=='never' and plan['output']==OUTPUT, 'Country screen image/output drift')
    require(plan['phases']==['controls'] and plan['network']=='none' and plan['flags']==FLAGS, 'Country screen stages/network/flags drift')
    require(plan['reusedBuild']=={'path':REUSED_BUILD,'sha256':REUSED_SHA},'Exact unchanged V6 build required')
    require(plan['modules']==MODULES and plan['legacyArtifact']==LEGACY, 'Country screen retained controls/artifact')
    require(plan['mounts'].get(PROPOSAL)=='/'+PROPOSAL and plan['mounts'].get('scripts/coarse_osm_delta_v1.cpp')=='/code/coarse_osm_delta_v1.cpp', 'Country screen proposal/codec binding')
    require(plan['rootfs']['path']==ASSET_ROOT and plan['rootfs']['portable']['portableTreeSha256']=='a64ef22d93c8b49689ccfefe09c67a62e67422cb84c6edb86089533fb33ebd72', 'Country screen rootfs drift')
    require({name:pin['path'] for name,pin in plan['headers'].items()}==HEADERS, 'Country screen header paths')
    for source,destination in plan['mounts'].items():
        require(source.startswith('scripts/') and source.endswith(('.py','.cpp')) and '..' not in Path(source).parts or source in (ASSET_PROOF,PROPOSAL,OLD_RECIPE,'docs/evidence/coarse-osm-country-exec-2026-10-30/member-diagnostic-regression.json','docs/evidence/coarse-osm-country-exec-2026-10-30/screen-raw-v4/screen/pass-b/global-catalog.json','docs/evidence/coarse-osm-country-exec-2026-10-30/screen-raw-v4/screen/pass-b/global-directory.bin'), 'Country screen refuses real source mounts')
        require(destination.startswith('/code/') or source==PROPOSAL and destination=='/'+PROPOSAL or source==OLD_RECIPE and destination=='/inputs/recipe.json' or source.endswith('/member-diagnostic-regression.json') and destination=='/inputs/member-regression.json' or source in ('docs/evidence/coarse-osm-country-exec-2026-10-30/screen-raw-v4/screen/pass-b/global-catalog.json', 'docs/evidence/coarse-osm-country-exec-2026-10-30/screen-raw-v4/screen/pass-b/global-directory.bin') and destination.startswith('/inputs/global/'), 'Country screen mount destination')
        require(plan['inputs'][source]==plan['workerFiles'][destination], 'Country screen mount checksum')
    for name in plan['inputs']:
        require('..' not in Path(name).parts and (name.startswith(('scripts/','docs/evidence/',plan['site']+'/'))
                or name in plan['runtime'].values() or name in (LEGACY['path'],LEGACY_COUNTRY['path'],V2_ARTIFACT,V4_ARTIFACT,V5_ARTIFACT,REUSED_BUILD+'/country-screen.so',REUSED_BUILD+'/result.json','data/coarse-quality/us-osm-native-lock-v1/acquire/http/001.bin')), 'Country screen refuses source/other asset hashes')
    require(plan['workerFiles']['/legacy/projector.so']==plan['inputs'][LEGACY['path']]==LEGACY['sha256'], 'Country screen prior artifact binding')
    require(plan['workerFiles']['/legacy-country/country-screen.so']==plan['inputs'][LEGACY_COUNTRY['path']]==LEGACY_COUNTRY['sha256'], 'Country screen prior country artifact binding')
    require(plan['wholeSourceOrSavedPbfReads']==0 and plan['capturedRelationFixtures']==2 and plan['aggregateSourceReceipts']==2000000, 'Country screen synthetic-only bounds')


def guards(root,phase):
    disk=os.statvfs('/builder/tmp' if phase=='build' else '/tmp')
    require(disk.f_blocks*disk.f_frsize==CAPS['tmpBytes'],'Country screen tmp guard')
    require(resource.getrlimit(resource.RLIMIT_FSIZE)==(CAPS['fileBytes'],CAPS['fileBytes']),'Country screen file guard')
    save(root/'resource-guards.json',{'memory':memory_guard(),'tmpBytes':CAPS['tmpBytes'],'fileBytes':CAPS['fileBytes'],
        'phase':phase,'watchdogSeconds':CAPS['workerSeconds'],'sysChrootCapability':phase=='build'})


def worker(plan,root,phase):
    root=Path(root);watchdog=start_watchdog(CAPS['workerSeconds']);began=time.monotonic()
    from coarse_osm_country_screen_v6 import resource_metrics, owned_usage
    def check():
        require(time.monotonic()-began<CAPS['workerSeconds'], 'Country screen worker deadline')
        usage=owned_usage(root)
        require(usage['conservativeAllocatedBytes']<CAPS['workingBytesIncludingTmp']-CAPS['tmpBytes'] and usage['entries']<=1024, 'Country screen allocated working/namespace cap')
    try:
        verify_worker_inputs(plan);guards(root,phase)
        save(root/'metrics-start.json',resource_metrics())
        if phase=='build':
            root.chmod(0o777)
            shutil.copyfile('/code/coarse_osm_country_screen_v6.cpp',root/'country-screen.cpp')
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
        import coarse_osm_country_screen_v2_test as v2_tests
        import coarse_osm_country_screen_v4_test as v4_tests
        import coarse_osm_country_screen_v5_test as v5_tests
        import coarse_osm_full_extract_v2_test as full_tests
        import coarse_osm_country_screen_v6_test as tests
        artifact=strict_json(Path('/artifacts/result.json').read_bytes())
        for module in (delta,prior):module.configure_native('/legacy/projector.so',LEGACY['sha256'])
        country_prior.configure_native('/legacy-country/country-screen.so',LEGACY_COUNTRY['sha256'])
        v2_tests.configure_native('/legacy-v2/country-screen.so','56cb0ae4020e9ea04586ea72e1f71a2f6a943d83222dfa42d40a0a4f65a42c9a')
        v4_tests.configure_native('/legacy-v4/country-screen.so','bc9f5bee468c483af8069db74d6bc8682384b4052b396cb8a45e8f274274145b')
        v5_tests.configure_native('/legacy-v5/country-screen.so','9c81c86e3605738430b1c8f9f762bce71830740e5c46737485371ef8c0561166')
        tests.configure_native('/artifacts/country-screen.so',artifact['artifactSha256'])
        full_tests.configure_native('/artifacts/country-screen.so',artifact['artifactSha256'])
        def flatten(suite):
            for item in suite:
                if isinstance(item,unittest.TestSuite):yield from flatten(item)
                else:yield item.id()
        suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in MODULES)
        require(sorted(flatten(suite))==plan['testIds'], 'Country screen test roster drift')
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        cpp_receipts=sum(engine.visits for engine in tests.ENGINES)+sum(engine.visits for engine in v2_tests.ENGINES)+sum(engine.visits for engine in v4_tests.ENGINES)+sum(engine.visits for engine in v5_tests.ENGINES)+sum(engine.visits for engine in full_tests.ENGINES)+sum(engine.visits for engine in country_prior.ENGINES)+sum(engine.visits for engine in prior.ENGINES)
        require(cpp_receipts<=2000000, 'Country screen aggregate synthetic received objects')
        controls={'tests':result.testsRun,'successful':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
                  'newHelperSourceReceipts':sum(engine.visits for engine in tests.ENGINES+full_tests.ENGINES),'retainedHelperSourceReceipts':sum(engine.visits for engine in v2_tests.ENGINES)+sum(engine.visits for engine in v4_tests.ENGINES)+sum(engine.visits for engine in v5_tests.ENGINES)+sum(engine.visits for engine in country_prior.ENGINES)+sum(engine.visits for engine in prior.ENGINES),
                  'sourceReceiptScope':'Recognized C++ source objects including rejected/cap+1; retained Python-reference and old codec scopes keep their own finite test bounds.',
                  'newHelperCodecRows':sum(engine.source_codec_rows for engine in tests.ENGINES+full_tests.ENGINES),'newHelperCodecCalls':sum(engine.source_codec_calls for engine in tests.ENGINES+full_tests.ENGINES)}
        save(root/'controls.json',controls)
        if not result.wasSuccessful() or result.skipped:return 2
        from coarse_osm_country_screen_v6 import NativeScreen,run_pair
        from coarse_osm_country_wire_v4 import reference_seal
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
        # Independent source-field oracle plus the frozen authenticated reader.
        from coarse_osm_delta_v2 import Reader,ReferenceCodec
        import hashlib,struct
        reader=Reader(root/'two-pass/pass-b/probe',ReferenceCodec())
        batch_fields=[];batch_lookups=[]
        expected_xy={row['id']:(row['lon'],row['lat']) for row in reference if row['type']=='node'}
        def receive_batch(batch):
            keys=[identity for row in batch for identity in row['nodes']]
            coordinates=reader.points(keys)
            expected=[expected_xy[identity] for identity in keys]
            bits=b''.join(struct.pack('<dd',*point) for point in coordinates)
            require(bits==b''.join(struct.pack('<dd',*point) for point in expected),'Way batch coordinate order/duplicates/bits')
            batch_fields.extend(batch);batch_lookups.append({'ways':len(batch),'references':len(keys),'coordinateBitsSha256':hashlib.sha256(bits).hexdigest()})
        try:
            batch_proof=engine.scan(pbf,STATE,caps,on_way_batch=receive_batch,check=check)
            require(batch_fields==[row for row in reference if row['type']=='way'],'Way batch complete independent field oracle')
            require(batch_proof['semanticSha256']==proof['semanticSha256'] and batch_proof['batchWays']==200 and batch_proof['batchReferences']==400,'Way batch whole-source seal/counts')
            save(root/'batch-fields.json',batch_fields);save(root/'batch-proof.json',batch_proof);save(root/'batch-lookups.json',batch_lookups)
        finally:reader.close()
        from coarse_osm_full_extract_v1 import extract as full_extract
        from coarse_osm_bulk import extract as four_pass
        base_rows=fixture_records();full_xml=root/'full-fixture.osm';full_pbf=root/'full-fixture.pbf';write_xml(full_xml,base_rows)
        with osmium.SimpleWriter(str(full_pbf),header=header,bufsz=65536) as writer:
            for obj in osmium.FileProcessor(str(full_xml)):writer.add(obj);views+=1
        proposal=deepcopy(strict_json(Path('/'+PROPOSAL).read_bytes()))
        proposal['source']['proposedPublisherReplicationStateUtc']=STATE
        proposal['windows']=[{'id':'a','bbox':[0,0,1,1]},{'id':'b','bbox':[.25,.25,.75,.75]}]
        proposal['proposedCaps'].update(sqliteIndexBytesEach=1048576,sqliteMaxPagesEach=256,sqliteCacheBytesEach=8192,
            workingBytesIncludingTmp=33554432,tmpBytes=65536,pythonSelectionStateBytes=4194304,retainedNativeObjectBytes=1048576,
            normalizedExtractBytes=1048576,scanNodesPerPass=10000,scanWaysPerPass=10000,scanRelationsPerPass=10000,scanObjectVisitsTotal=100000,wallSeconds=30)
        new_root=root/'full-prototype';new_root.mkdir();old_root=root/'four-pass-reference';old_root.mkdir();reference_views=0
        def reference_reader():
            nonlocal reference_views
            for row in deepcopy(base_rows):reference_views+=1;yield row
        old=four_pass(reference_reader,proposal,old_root,source_identity={'publisherStateUtc':STATE})
        new=full_extract(full_pbf,proposal,new_root,engine=engine,check=check)
        require(old['status']=='extracted_publisher_file_analysis_pending' and new['status']=='passed_all_highway_extraction_prototype','Complete synthetic extraction status')
        require((new_root/'elements.jsonl').read_bytes()==(old_root/'elements.jsonl').read_bytes(),'Complete source/metadata/dependency/window output differs from four-pass reference')
        save(root/'full-prototype-proof.json',{'proposal':proposal,'newState':new,'referenceState':old,'fourPassReferenceViews':reference_views,
             'outputBytes':(new_root/'elements.jsonl').stat().st_size,'outputSha256':sha(new_root/'elements.jsonl')})
        cpp_receipts=sum(e.visits for e in tests.ENGINES)+sum(e.visits for e in v2_tests.ENGINES)+sum(e.visits for e in v4_tests.ENGINES)+sum(e.visits for e in v5_tests.ENGINES)+sum(e.visits for e in full_tests.ENGINES)+sum(e.visits for e in country_prior.ENGINES)+sum(e.visits for e in prior.ENGINES)
        require(cpp_receipts+views+len(reference)+reference_views<=2000000, 'Country screen complete measured synthetic receipts')
        save(root/'result.json',{'status':'passed_country_screen_synthetic_qualification','controls':controls,'proof':proof,
             'positivePipelineStatus':positive['status'],'positivePipelineReceipts':positive['objectReceipts'],
             'aggregateCppSourceReceipts':cpp_receipts,'encodingNativeViews':views,'independentReferenceViews':len(reference),'fourPassReferenceViews':reference_views,
             'scope':'Synthetic full-extraction/summary/census/probe/ABI controls plus two decoded relation fixtures and saved national catalog metadata. No national file or saved PBF read, no full import.',
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
        p=root/phase;p.mkdir();identity=child=None;name='geo-planner-country-screen-v7-'+phase+'-'+owner[:12]
        save(p/'owner.json',{'name':name,'label':owner})
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
            '--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--ulimit','core=0:0','--ulimit',f'fsize={CAPS["fileBytes"]}:{CAPS["fileBytes"]}',
            '--tmpfs',('/builder/tmp' if phase=='build' else '/tmp')+':rw,size=256m','--env','LD_LIBRARY_PATH=/tools/runtime']
        if phase=='build':args+=['--cap-add=SYS_CHROOT','--mount',f'type=bind,src={repo/ASSET_ROOT},dst=/builder,readonly','--mount',f'type=bind,src={p},dst=/builder/work']
        if phase=='build':
            for header_name,path in HEADERS.items():args+=['--mount',f'type=bind,src={repo/path},dst=/builder/inputs/{header_name},readonly']
        else:args+=['--mount',f'type=bind,src={repo/REUSED_BUILD},dst=/artifacts,readonly']
        args+=['--mount',f'type=bind,src={repo/LEGACY["path"]},dst=/legacy/projector.so,readonly',
               '--mount',f'type=bind,src={repo/LEGACY_COUNTRY["path"]},dst=/legacy-country/country-screen.so,readonly']
        args+=['--mount',f'type=bind,src={repo / V5_ARTIFACT},dst=/legacy-v5/country-screen.so,readonly']
        args+=['--mount',f'type=bind,src={repo / V4_ARTIFACT},dst=/legacy-v4/country-screen.so,readonly']
        args+=['--mount',f'type=bind,src={repo / V2_ARTIFACT},dst=/legacy-v2/country-screen.so,readonly']
        args+=['--env','PYTHONPATH=/code:/tools/site','--env','OSMIUM_MAX_INPUT_QUEUE_SIZE=2','--env','OSMIUM_MAX_OSMDATA_QUEUE_SIZE=2']
        for source,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/source},dst={destination},readonly']
        args+=['--mount',f'type=bind,src={repo/plan["site"]},dst=/tools/site,readonly']
        for filename,source in plan['runtime'].items():args+=['--mount',f'type=bind,src={repo/source},dst=/tools/runtime/{filename},readonly']
        args+=['--mount',f'type=bind,src={p},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe-v7.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_country_screen_v7.py','--qualify','/inputs/recipe-v7.json',expected,'/work','--worker','--phase',phase]
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
        'hostSecondsIncludingInputAssetHashesBuildControlsCleanup':time.monotonic()-began,'networkRequests':0,'wholeSourceOrSavedPbfReads':0,'capturedRelationFixtures':2,
        'nativeSummaryAndBoundedProbeImplemented':True,'fullImportAdmitted':False,'modelChanged':False})
    return 0 if success else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--qualify',action='store_true',required=True)
    parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('output');parser.add_argument('--worker',action='store_true');parser.add_argument('--phase',choices=['build','controls'])
    args=parser.parse_args()
    if args.worker:
        require(sha(args.recipe)==args.sha256,'Batch qualification worker recipe binding');plan=strict_json(Path(args.recipe).read_bytes());sys.path.insert(0,'/tools/site')
        validate(plan);require(args.phase in plan['phases'],'Batch qualification phase');raise SystemExit(worker(plan,args.output,args.phase))
    raise SystemExit(driver(args.recipe,args.sha256,args.output))
