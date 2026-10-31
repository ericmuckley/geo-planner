"""Bounded compact-bank capacity census; never captures roads or changes the app."""
import argparse
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
from coarse_osm_cell_resources_v2 import CellResources,CellStorage,OWNED,RETAINED,FILE,TMP
from coarse_osm_country_screen_v1 import XY
from coarse_osm_country_screen_v6 import NativeScreen
from coarse_osm_data import memory_guard,verify_worker_inputs
from coarse_osm_full_monitor_v1 import owned_usage
from coarse_osm_records import canonical,strict_json
from coarse_osm_revalidated_index_v1 import SourceIndex
from coarse_osm_window_bank_v2 import Writer,Bank
from coarse_osm_window_cells_v1 import Cells
from coarse_osm_window_codec_v2 import Codec
from coarse_timing_input import require,start_watchdog
from prepare_osm_input_v3 import capacity
from prepare_osm_native_lock_v1 import cleanup_owned,settle_error
from run_osm_country_screen_v4 import IMAGE,SOURCE,SITE,RUNTIME,isolation
from run_osm_full_extract_v2 import source_binding

REPORT='docs/evidence/coarse-osm-extraction-2026-10-30'
ARTIFACT='data/coarse-quality/us-osm-country-controls-v13/build/country-screen.so'
ARTIFACT_SHA='e82ccc44579ded7e7a6fcae5cdd3a6267250f3f3e00968195e45e567f1c0138e'
FIXTURE='data/coarse-quality/us-osm-country-controls-v12/controls'
FINE='data/coarse-quality/us-osm-full-extract-run-v2/extract/primary-index'
CATALOG='docs/evidence/coarse-osm-country-exec-2026-10-30/screen-raw-v4/screen/pass-b/global-catalog.json'
SEMANTIC='209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16'
PROPOSAL='docs/evidence/coarse-osm-offline-plan-2026-10-26/proposal.json'
OUTPUTS={stage:f'data/coarse-quality/us-osm-cell-census-{stage}-v2' for stage in ('controls','run')}
RUN_CAPS={'hostSeconds':14400,'hostWorkSeconds':14340,'workerSeconds':13800,'passSeconds':6900,'hashSeconds':240,
          'requiredInitialFreeBytes':32*1024**3,'bankBytes':2*1024**3,'fineIndexBytes':24*1024**3,
          'fineVerificationBytesPerView':64*1024**3,'fineCodecRows':8000000000,'fineCodecCalls':2000000,
          'cellCodecRows':32000000000,'cellCodecCalls':12000000}
CONTROL_CAPS=RUN_CAPS|{'hostSeconds':600,'hostWorkSeconds':570,'workerSeconds':300,'passSeconds':90,'hashSeconds':30,
                      'requiredInitialFreeBytes':3*1024**3,'bankBytes':4*1024**2,'fineIndexBytes':4*1024**2,
                      'fineVerificationBytesPerView':64*1024**2,'fineCodecRows':2000000,'fineCodecCalls':100000,
                      'cellCodecRows':2000000,'cellCodecCalls':100000}


def queries(manifest):return sorted({value for part in manifest['shards'] for value in (part['first'],part['last'])})


def validate(plan):
    stage=plan['stage'];require(stage in OUTPUTS and plan['phase']=='window_cell_capacity_v2','Cell census stage')
    require(plan['caps']==(RUN_CAPS if stage=='run' else CONTROL_CAPS),'Cell census exact caps')
    require(plan['output']==OUTPUTS[stage] and plan['imageId']==IMAGE and plan['network']=='none','Cell census image/output/network')
    require(plan['artifact']=={'path':ARTIFACT,'sha256':ARTIFACT_SHA} and plan['site']==SITE and plan['runtime']==RUNTIME,'Cell census qualified tools')
    require(plan['retainedReservationBytes']==RETAINED and plan['ownedWorkLimitBytes']==OWNED,'Cell census retained accounting')
    require(plan['parentQualification']=={'recipe':REPORT+'/qualification-plan-v13.json','sha256':'e3c3f12d84f0bb0eea3629da292dd6187cf587925eb420c110ca53939ccc2237','tests':65,'skips':0},'Cell census read-only admission')
    if stage=='run':
        require(plan['source']==SOURCE and plan['fineInput']==FINE and plan['catalog']==CATALOG and plan['semantic']==SEMANTIC and plan['highwayWays']==52053199,'Cell census pinned national inputs')
        require(plan['prefixAdmission']['verified'] and plan['prefixAdmission']['recipeSha256']=='5f69fbf52a9d0ec879402c318ce27c7b0e43b848790e9a8e5ed0a56ff46eaee7','Cell census lossless prefix admission')
        require(len(plan['windows'])==21 and plan['controllerAdmission']['qualified'] and plan['controllerAdmission']['tests']>=10,'Cell census national admission')
        require(all(plan['inputs'].get(name)==pin for name,pin in plan['controllerAdmission']['producers'].items()),'Cell census controller drift')
        require(plan['mounts'][PROPOSAL]=='/inputs/proposal.json','Cell census original-window binding')
    else:
        require(plan['source']['path']==FIXTURE+'/full-fixture.pbf' and plan['source']['counts']=={'node':4,'way':3,'relation':2},'Cell census tiny source only')
        require(plan['highwayWays']==2,'Cell census tiny highway count')
        require(plan['fineInput']==FIXTURE+'/full-prototype/audit-index' and plan['catalog']==plan['fineInput']+'/index.json','Cell census tiny fine input')
        require(plan['windows']==[{'id':'a','bbox':[0,0,1,1]},{'id':'b','bbox':[.25,.25,.75,.75]}],'Cell census tiny windows')
    Cells(plan['windows'])
    require(plan['source']['path'] not in plan['inputs'] and 0<len(plan['queryIDs'])<=65536 and all(type(v) is int and 0<v<2**63 for v in plan['queryIDs']) and plan['queryIDs']==sorted(set(plan['queryIDs'])),'Cell census source hash scope/query order')
    require(plan['workerFiles']['/artifacts/helper.so']==plan['inputs'][ARTIFACT]==ARTIFACT_SHA,'Cell census artifact binding')
    for name,destination in plan['mounts'].items():
        require('..' not in Path(name).parts and name.startswith(('scripts/','docs/evidence/',plan['fineInput']+'/')),'Cell census code/evidence mount')
        require(destination.startswith(('/code/','/inputs/')) and plan['inputs'][name]==plan['workerFiles'][destination],'Cell census mounted binding')
    require(plan['mounts'][plan['catalog']]=='/inputs/catalog.json','Cell census required source catalog')
    for name in plan['inputs']:
        require('..' not in Path(name).parts and (name.startswith(('scripts/','docs/evidence/',SITE+'/',plan['fineInput']+'/')) or name in RUNTIME.values() or name==ARTIFACT),'Cell census input closure')


def check_windows(plan,proposal):
    if plan['stage']=='run':require(plan['windows']==proposal['windows'],'Cell census original21window drift')


def check_receipt(receipt,plan):
    counts=plan['source']['counts']
    require(receipt['nativeEof'] and {kind:receipt['counts'].get(kind,0) for kind in counts}==counts and receipt['visits']==sum(counts.values()),'Cell census full source EOF/counts')
    require(receipt['semanticSha256']==plan['semantic'] and receipt['sourceIdentity']['sourceSha256']==plan['source']['sha256'] and receipt['sourceIdentity']['sourceMd5']==plan['source']['md5'],'Cell census whole-source fields/identity')
    require(receipt['sourceIdentity']['publisherStateUtc']==plan['source']['publisherState'] and receipt['postSourceHashBytes']==plan['source']['bytes'] and receipt['knownGuardReadBytes']==2*plan['source']['bytes'],'Cell census source-state/hash-read closure')
    require(receipt['highwayWays']==plan['highwayWays'],'Cell census highway metadata count')
    require(receipt['pythonProjectionFrames']==receipt['batchWays']==receipt['selectedNodeProjections']==receipt['restrictionProjections']==0,'Cell census unexpected ordinary projection')
    require(receipt['witnessRows']==len(plan['queryIDs']),'Cell census complete fixed source witnesses')


def run_pass(plan,root,engine,codec,resources,storage,check,previous=None):
    root=Path(root);root.mkdir();caps=plan['caps'];started=time.monotonic();view=bank=None;witness=bytearray()
    watchdog=start_watchdog(caps['passSeconds'])
    try:
        manifest=strict_json(Path('/inputs/catalog.json').read_bytes());require(queries(manifest)==plan['queryIDs'],'Cell census frozen source-derived queries')
        view=SourceIndex('/fine-index',engine.codec,manifest,index_limit=caps['fineIndexBytes'],read_limit=caps['fineVerificationBytesPerView'],check=check)
        writer=Writer(root/'bank',storage,plan['windows'],plan['source']['counts']['node'],limit=caps['bankBytes'])
        from coarse_osm_projector_v1 import BLOCK_EVENT
        def block(event):
            view.append_encoded(event,engine.codec);count,first,last,size=BLOCK_EVENT.unpack_from(event)
            writer.append(codec.encode(event[BLOCK_EVENT.size:],count,first,last),codec)
        def receive_witness(raw):
            require(len(witness)+len(raw)<=len(plan['queryIDs'])*XY.size,'Cell census witness byte cap');witness.extend(raw)
        counts=plan['source']['counts'];scan_caps={'singleNormalizedElementBytes':4194304,'scanNodesPerPass':max(1,counts['node']),
            'scanWaysPerPass':max(1,counts['way']),'scanRelationsPerPass':max(1,counts['relation']),
            'scanObjectVisitsTotal':sum(counts.values()),'pbfHeaderBytesExclusiveMaximum':65536,'pbfUncompressedBlobBytesExclusiveMaximum':33554432}
        receipt=engine.scan('/source.pbf',plan['source']['publisherState'],scan_caps,source=plan['source'],on_block=block,
                            selected=plan['queryIDs'],on_witness=receive_witness,check=check)
        check_receipt(receipt,plan);view.finish();view.verify_files();writer.finish()
        resources.write(root/'source-receipt.json',receipt);resources.write(root/'fine-revalidation.json',view.report())
        require(len(witness)==len(plan['queryIDs'])*XY.size,'Cell census witness closure')
        source_rows=list(XY.iter_unpack(witness));require([row[0] for row in source_rows]==plan['queryIDs'],'Cell census source witness order')
        expected={identity:codec.cells.cell(x,y) for identity,x,y in source_rows}
        before=time.monotonic();bank=Bank(writer.root,codec,plan['windows'],expected_rows=counts['node'],limit=caps['bankBytes']);load_seconds=time.monotonic()-before
        ordered=list(reversed(plan['queryIDs']))+plan['queryIDs'][:2]+plan['queryIDs'][:1]
        before=time.monotonic();actual=bank.lookup(ordered);lookup_seconds=time.monotonic()-before
        require(actual==[expected[key] for key in ordered],'Cell census independent source coordinates/membership')
        bank.verify_files();catalog=(writer.root/'index.json').read_bytes();directory=(writer.root/'directory.bin').read_bytes()
        identity={'catalogSha256':hashlib.sha256(catalog).hexdigest(),'directorySha256':hashlib.sha256(directory).hexdigest(),
                  'partSha256':[part['sha256'] for part in bank.manifest['parts']]}
        require(previous is None or identity==previous,'Cell census independent source rebuild drift')
        resources.write(root/'witness-proof.json',{'sourceRows':[list(row) for row in source_rows],'queries':ordered,'cells':actual,
            'bankBytes':writer.stored_bytes,'snapshotBytes':bank.loaded_bytes,'bankBlocks':writer.blocks,'bankParts':len(bank.parts),
            'snapshotLoadSeconds':load_seconds,'lookupSeconds':lookup_seconds,'cellCodecRowsCumulative':codec.rows,'cellCodecCallsCumulative':codec.calls,
            'scope':'Immutable compact cell lookup against fresh native source coordinates; no road geometry, routing or driving-time measurement.'})
        resources.write(root/'result.json',{'status':'passed_cell_bank_capacity_pass','identity':identity,'protectedPassSeconds':time.monotonic()-started,
            'nodeRows':writer.rows,'bankBytes':writer.stored_bytes,'nationalPass':plan['stage']=='run','wholeTwoPassBankCapacityQualified':False,
            'wholeRoadCaptureQualified':False,'sourceSuitabilityQualified':False,'modelChanged':False})
        return identity
    except BaseException as error:
        try:fine_report=view.report() if view else None
        except Exception as report_error:fine_report={'unavailable':str(report_error)[:1000]}
        resources.write(root/'failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:3000],
            'lastNativeReceipt':engine.last,'fineView':fine_report,'cellCodecRows':codec.rows,'cellCodecCalls':codec.calls,
            'bankQualified':False,'wholeRoadCaptureQualified':False,'modelChanged':False})
        raise
    finally:
        if bank is not None:bank.close()
        if view is not None:view.close()
        if watchdog.poll() is None:watchdog.terminate()
        watchdog.wait(timeout=5)


def worker(plan,root):
    root=Path(root);caps=plan['caps'];resources=CellResources(root,seconds=caps['workerSeconds']);watchdog=start_watchdog(caps['workerSeconds'])
    engine=None;last=0.;sequence=0;label='binding'
    def check():
        nonlocal last,sequence
        resources.check()
        if engine is not None and time.monotonic()-last>=60:
            last=time.monotonic();sequence+=1
            resources.write(root/f'progress-{sequence:04d}.json',{'stage':label,'seconds':time.monotonic()-resources.began,'native':engine.progress(),
                'fineCodecRows':engine.codec.decoded_rows,'fineCodecCalls':engine.codec.calls})
    try:
        began=time.monotonic();verify_worker_inputs(plan)
        if plan['stage']=='run':check_windows(plan,strict_json(Path('/inputs/proposal.json').read_bytes()))
        resources.write(root/'input-binding.json',{'seconds':time.monotonic()-began,'scope':'Code/tools and every read-only fine file hashed; national PBF has separately metered host/framing/native/posthash phases.'})
        require(resource.getrlimit(resource.RLIMIT_FSIZE)==(FILE,FILE),'Cell census process file limit')
        disk=os.statvfs('/tmp');require(disk.f_blocks*disk.f_frsize==TMP,'Cell census tmpfs limit')
        resources.write(root/'guards.json',{'memory':memory_guard(),'fileBytes':FILE,'tmpBytes':TMP,'retainedReservationBytes':RETAINED,'ownedLimitBytes':OWNED})
        if plan['stage']=='controls':
            suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in ['coarse_osm_cell_resources_v2_test','coarse_osm_cell_census_v2_test'])
            result=unittest.TextTestRunner(verbosity=2).run(suite)
            resources.write(root/'controls.json',{'tests':result.testsRun,'successful':result.wasSuccessful(),'skips':len(result.skipped),'failures':len(result.failures),'errors':len(result.errors)})
            require(result.wasSuccessful() and not result.skipped and result.testsRun>=10,'Cell census controller qualification')
        total=sum(plan['source']['counts'].values())
        engine=NativeScreen('/artifacts/helper.so',ARTIFACT_SHA,aggregate_visits=2*total,codec_rows=caps['fineCodecRows'],codec_calls=caps['fineCodecCalls'])
        codec=Codec('/artifacts/helper.so',ARTIFACT_SHA,Cells(plan['windows']),row_budget=caps['cellCodecRows'],call_budget=caps['cellCodecCalls'])
        storage=CellStorage(root,resources);identity=None
        for label in ['pass-a','pass-b']:identity=run_pass(plan,root/label,engine,codec,resources,storage,check,identity)
        require(engine.visits==2*total,'Cell census total source receipt closure')
        resources.write(root/'result.json',{'status':'passed_cell_bank_capacity_census','sourcePasses':2,'sourceObjects':engine.visits,
            'identity':identity,'fineCodecRows':engine.codec.decoded_rows,'fineCodecCalls':engine.codec.calls,'cellCodecRows':codec.rows,'cellCodecCalls':codec.calls,
            'nationalBankCapacityQualified':plan['stage']=='run','readOnlyFineInputRevalidatedForThisStage':True,
            'oldFailedEvidenceChanged':False,'wholeRoadCaptureQualified':False,'sourceSuitabilityQualified':False,'modelChanged':False})
        return 0
    except BaseException as error:
        resources.write(root/'worker-failure.json',{'status':'stopped','stage':label,'errorType':type(error).__name__,'error':str(error)[:3000],
            'lastNativeReceipt':engine.last if engine else None,'bankCapacityQualified':False,'wholeRoadCaptureQualified':False,'modelChanged':False})
        return 2
    finally:
        try:resources.write(root/'metrics-end.json',resources.result())
        finally:
            if watchdog.poll() is None:watchdog.terminate()
            watchdog.wait(timeout=5)


def driver(recipe,pin):
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==pin,'Cell census recipe path/hash')
    plan=strict_json(recipe.read_bytes());validate(plan);caps=plan['caps'];root=repo/plan['output']
    require(not root.exists(),'Cell census fresh output required');root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json')
    began=time.monotonic();owner=uuid.uuid4().hex;name='geo-planner-cell-census-'+owner[:12];identity=child=None;success=False
    def save(filename,value):(root/filename).write_bytes(canonical(value)+b'\n')
    def check():
        require(time.monotonic()-began<caps['hostWorkSeconds'],'Cell census host deadline')
        require(owned_usage(root)['conservativeAllocatedBytes']<OWNED,'Cell census host storage cap')
        require(shutil.disk_usage(root).free>=2*1024**3,'Cell census disk headroom')
        require(not (root/'worker.log').exists() or (root/'worker.log').stat().st_size<=2*1024**2,'Cell census log cap')
    def call(args):check();return subprocess.run(args,capture_output=True,text=True,timeout=15)
    save('owner.json',{'name':name,'label':owner,'image':IMAGE,'labelKey':'geo-planner.stream-owner'})
    try:
        if plan['stage']=='run':check_windows(plan,strict_json((repo/PROPOSAL).read_bytes()))
        for input_path,pin_value in plan['inputs'].items():
            check();path=repo/input_path
            require(path.is_file() and not path.is_symlink() and path.stat().st_nlink==1,'Cell census input file kind')
            require(sha(path)==pin_value,'Cell census input drift: '+input_path)
        require({str(p.relative_to(repo)) for p in (repo/plan['fineInput']).iterdir()}=={name for name in plan['inputs'] if name.startswith(plan['fineInput']+'/')},'Cell census fine input roster')
        current=capacity(repo)
        require(current['hostDiskAvailableBytes']>=caps['requiredInitialFreeBytes'] and current['hostMemoryBytes']>=8589934592 and current['dockerMemoryBytes']>=6442450944 and min(current['hostCpuCount'],current['dockerCpuCount'])>=2,'Cell census starting capacity')
        save('capacity-at-start.json',current)
        source=repo/plan['source']['path'];save('host-source-binding.json',source_binding(source,plan['source'],check,caps['hashSeconds']))
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL',
              '--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--ulimit','core=0:0','--ulimit',f'fsize={FILE}:{FILE}',
              '--tmpfs','/tmp:rw,size=256m','--env','LD_LIBRARY_PATH=/tools/runtime','--env','PYTHONPATH=/code:/tools/site',
              '--env','OSMIUM_MAX_INPUT_QUEUE_SIZE=2','--env','OSMIUM_MAX_OSMDATA_QUEUE_SIZE=2']
        for input_path,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/input_path},dst={destination},readonly']
        for filename,input_path in RUNTIME.items():args+=['--mount',f'type=bind,src={repo/input_path},dst=/tools/runtime/{filename},readonly']
        args+=['--mount',f'type=bind,src={repo/SITE},dst=/tools/site,readonly','--mount',f'type=bind,src={repo/ARTIFACT},dst=/artifacts/helper.so,readonly',
               '--mount',f'type=bind,src={source},dst=/source.pbf,readonly','--mount',f'type=bind,src={repo/plan["fineInput"]},dst=/fine-index,readonly',
               '--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly',
               '--entrypoint=python3',IMAGE,'-B','/code/run_osm_cell_census_v2.py','/inputs/recipe.json',pin,'--worker']
        result=call(args);require(result.returncode==0,result.stderr);identity=result.stdout.strip();require(len(identity)==64,'Cell census owned worker identity')
        initial=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(initial,'controls')
        save('container-initial.json',{'Image':initial['Image'],'HostConfig':initial['HostConfig'],'Mounts':[{'Destination':m['Destination'],'RW':m['RW']} for m in initial['Mounts']]})
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:check();time.sleep(.5)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0];save('container-result.json',{'State':final['State'],'clientExitCode':child.returncode})
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Cell census worker exit/OOM');success=True
    except BaseException as error:save('driver-failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:3000]})
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        def cleanup_call(args):return subprocess.run(args,capture_output=True,text=True,timeout=15)
        if not (root/'container-result.json').exists():settle_error(cleanup_call,identity,name,owner,root,child.returncode if child else None)
        cleanup_owned(cleanup_call,identity,name,owner,IMAGE,root)
    require(time.monotonic()-began<caps['hostSeconds'],'Cell census final deadline')
    save('run-summary.json',{'status':'passed_cell_bank_capacity_census' if success else 'stopped','hostSecondsIncludingBindingsAndCleanup':time.monotonic()-began,'networkRequests':0,'modelChanged':False})
    return 0 if success else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    require(sha(args.recipe)==args.sha256,'Cell census recipe binding');plan=strict_json(Path(args.recipe).read_bytes());validate(plan)
    raise SystemExit(worker(plan,'/work') if args.worker else driver(args.recipe,args.sha256))
