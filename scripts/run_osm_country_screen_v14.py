"""Disk-selected native bridge and extraction controls, synthetic inputs only."""
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

CAPS={'hostSeconds':1800,'workSeconds':1770,'workerSeconds':1200,'workingBytesIncludingTmp':1073741824,
    'tmpBytes':268435456,'fileBytes':2147483648,'indexBytes':33554432,'reportBytes':2097152,
    'nativeCodecRows':2000000,'cacheBlocks':64,'cachePayloadBytes':4194304}
OUTPUT='data/coarse-quality/us-osm-country-controls-v14'
ASSET_ROOT='data/coarse-quality/us-osm-native-build-v1/prepare/rootfs'
ASSET_PROOF='docs/evidence/coarse-osm-native-build-2026-10-27/asset_contents.py'
PROPOSAL='docs/evidence/coarse-osm-offline-plan-2026-10-26/proposal.json'
HEADERS={'libosmium':'data/coarse-quality/us-osm-native-build-v1/prepare/source-1',
    'protozero':'data/coarse-quality/us-osm-native-build-v1/prepare/source-2'}
FLAGS=['-std=c++17','-O2','-fPIC','-shared','-fvisibility=hidden','-static-libstdc++','-static-libgcc',
    '-pthread','-I/inputs/libosmium/include','-I/inputs/protozero/include','/work/country-screen.cpp','/work/delta.cpp','/work/window-cells.cpp','/work/window-masks.cpp','/work/window-cells-v2.cpp',
    '-Wl,-z,defs','-Wl,--exclude-libs,ALL','-Wl,-Bsymbolic-functions','-lz','-o','/work/country-screen.so']


MODULES = ['coarse_osm_selected_store_v1_test','coarse_osm_selected_audit_v1_test','coarse_osm_country_screen_v7_test','coarse_osm_filtered_extract_v3_test','coarse_osm_window_cells_v1_test','coarse_osm_window_codec_v2_test','coarse_osm_window_bank_v2_test','coarse_osm_window_masks_v1_test','coarse_osm_revalidated_index_v1_test']
LEGACY = {'path':'data/coarse-quality/us-osm-projector-v1/build/projector.so',
          'sha256':'9227bc577f3592f167d614329ecc25311c4f8505aa854d3121f9837073f75f26'}

OLD_RECIPE='docs/evidence/coarse-osm-country-helper-2026-10-30/qualification-plan.json'
LEGACY_COUNTRY={'path':'data/coarse-quality/us-osm-country-controls-v1/build/country-screen.so',
                'sha256':'0b3d2d9e609350252fb9850a2342215c6fae3172b03b76fc65350b55c66b9a53'}

V5_ARTIFACT='data/coarse-quality/us-osm-country-controls-v5/build/country-screen.so'
V4_ARTIFACT='data/coarse-quality/us-osm-country-controls-v4/build/country-screen.so'
V2_ARTIFACT='data/coarse-quality/us-osm-country-controls-v2/build/country-screen.so'

REUSED_BUILD=OUTPUT+'/build'
REUSED_SHA='1084fc1b6e9b1a627b52180fd91df0b46e01a967fbd399c2bad672a4f675f48a'


def validate(plan):
    require(plan['phase']=='offline_native_country_screen_v14' and plan['caps']==CAPS, 'Country screen phase/caps drift')
    require(plan['imageId']==IMAGE and plan['imagePull']=='never' and plan['output']==OUTPUT, 'Country screen image/output drift')
    require(plan['phases']==['build','controls'] and plan['network']=='none' and plan['flags']==FLAGS, 'Country screen stages/network/flags drift')
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
    require(plan['wholeSourceOrSavedPbfReads']==0 and plan['capturedRelationFixtures']==2 and plan['aggregateSourceReceipts']==3000000, 'Country screen synthetic-only bounds')


def guards(root,phase):
    disk=os.statvfs('/builder/tmp' if phase=='build' else '/tmp')
    require(disk.f_blocks*disk.f_frsize==CAPS['tmpBytes'],'Country screen tmp guard')
    require(resource.getrlimit(resource.RLIMIT_FSIZE)==(CAPS['fileBytes'],CAPS['fileBytes']),'Country screen file guard')
    save(root/'resource-guards.json',{'memory':memory_guard(),'tmpBytes':CAPS['tmpBytes'],'fileBytes':CAPS['fileBytes'],
        'phase':phase,'watchdogSeconds':CAPS['workerSeconds'],'sysChrootCapability':phase=='build'})


def worker(plan,root,phase):
    root=Path(root);watchdog=start_watchdog(CAPS['workerSeconds']);began=time.monotonic()
    from coarse_osm_country_screen_v6 import resource_metrics, owned_usage
    last_check=0.
    def check():
        nonlocal last_check
        require(time.monotonic()-began<CAPS['workerSeconds'], 'Country screen worker deadline')
        now=time.monotonic()
        if now-last_check<1:return
        last_check=now
        usage=owned_usage(root)
        require(usage['conservativeAllocatedBytes']<CAPS['workingBytesIncludingTmp']-CAPS['tmpBytes'] and usage['entries']<=1024, 'Country screen allocated working/namespace cap')
    try:
        verify_worker_inputs(plan);guards(root,phase)
        save(root/'metrics-start.json',resource_metrics())
        if phase=='build':
            root.chmod(0o777)
            shutil.copyfile('/code/coarse_osm_country_screen_v7.cpp',root/'country-screen.cpp')
            shutil.copyfile('/code/coarse_osm_delta_v1.cpp',root/'delta.cpp')
            shutil.copyfile('/code/coarse_osm_window_cells_v1.cpp',root/'window-cells.cpp')
            shutil.copyfile('/code/coarse_osm_window_masks_v1.cpp',root/'window-masks.cpp')
            shutil.copyfile('/code/coarse_osm_window_cells_v2.cpp',root/'window-cells-v2.cpp')
            import qualified_asset_contents
            for name,pin in plan['headers'].items():require(qualified_asset_contents.snapshot('/builder/inputs/'+name)==pin['portable'], 'Country screen header drift')
            tool(root,'compiler-version',[COMPILER,'--version'],check)
            tool(root,'compile',[COMPILER,*FLAGS],check)
            elf=tool(root,'elf',['/usr/bin/readelf','-h','-d','-V','-Ws','/work/country-screen.so'],check)
            exports=['gp_window_cells_v2_abi','gp_window_cells_v2_encode','gp_window_cells_v2_lookup','gp_window_cells_v2_from_v1','gp_window_masks_abi','gp_window_primary_masks','gp_window_audit_masks','gp_window_cells_abi','gp_window_cells_encode','gp_window_cells_lookup','gp_delta_abi','gp_delta_decode','gp_country_screen_abi','gp_country_screen_frames','gp_country_screen_pbf',
                     'gp_country_screen_add','gp_country_screen_priority','gp_country_screen_stratum']
            require('AArch64' in elf and 'little endian' in elf and all(name in elf for name in exports) and 'GLIBCXX_' not in elf, 'Country screen ELF/ABI/runtime')
            import re
            needed=re.findall(r'\(NEEDED\).*?\[([^\]]+)\]',elf)
            require(set(needed)<={'libz.so.1','libm.so.6','libc.so.6','libpthread.so.0','libdl.so.2','librt.so.1','ld-linux-aarch64.so.1'}, 'Country screen dynamic dependency')
            artifact=root/'country-screen.so'
            save(root/'result.json',{'status':'compiled_country_screen_controls_pending','artifactSha256':sha(artifact),'artifactBytes':artifact.stat().st_size,
                'sourceSha256':sha(root/'country-screen.cpp'),'deltaSourceSha256':sha(root/'delta.cpp'),'flags':FLAGS,'needed':needed,'exports':exports,'elfSha256':sha(root/'elf.log')})
            return 0
        from coarse_osm_selected_qualification_v1 import qualify
        qualify(plan,root,check)
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
        p=root/phase;p.mkdir();identity=child=None;name='geo-planner-country-screen-v14-'+phase+'-'+owner[:12]
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
        args+=['--mount',f'type=bind,src={p},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe-v14.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_country_screen_v14.py','--qualify','/inputs/recipe-v14.json',expected,'/work','--worker','--phase',phase]
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
