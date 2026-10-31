"""One frozen source/probe batching measurement, with a separate tiny qualification."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import unittest
import uuid

from coarse_osm_build_v1 import sha
from coarse_osm_bulk_pbf import stat_key
from coarse_osm_country_screen_v1 import BoundedCodec, ProbeReader, owned_usage
from coarse_osm_country_screen_v4 import Resources, CheckedStorage
from coarse_osm_country_screen_v5 import NativeScreen
from coarse_osm_data import verify_worker_inputs
from coarse_osm_delta_v1 import ReferenceCodec
from coarse_osm_records import canonical
from coarse_timing_input import require, start_watchdog
from prepare_osm_input_v3 import capacity
from prepare_osm_native_lock_v1 import cleanup_owned, settle_error
from run_osm_country_screen_v4 import IMAGE, SOURCE, SITE, RUNTIME, isolation

REPORT = 'docs/evidence/coarse-osm-way-batch-2026-10-30'
ARTIFACT = 'data/coarse-quality/us-osm-country-controls-v5/build/country-screen.so'
ARTIFACT_SHA = '9c81c86e3605738430b1c8f9f762bce71830740e5c46737485371ef8c0561166'
PROBE = 'data/coarse-quality/us-osm-country-screen-v4/screen/pass-b/probe'
FIXTURE = 'data/coarse-quality/us-osm-country-controls-v5/controls'
PARENT_SEAL = '3cf6a309323e830fb0227e092e8d332e44684bdf8ddae250e485dc4bf827ad69'
OUTPUTS = {stage: f'data/coarse-quality/us-osm-way-batch-{stage}-v2' for stage in ('controls', 'run')}
RUN_CAPS = dict(hostSeconds=4800, hostWorkSeconds=4740, workerSeconds=4200, caseSeconds=3000,
                auditSeconds=900, hashSeconds=240, references=8000000, batches=512,
                lookupBytes=32*1024**3, lookupRows=1024000000, codecCalls=250000)
CONTROL_CAPS = RUN_CAPS | dict(hostSeconds=600, hostWorkSeconds=570, workerSeconds=300,
                             caseSeconds=90, auditSeconds=60, references=1000, batches=4,
                             lookupBytes=64*1024**2, lookupRows=2000000, codecCalls=10000)
WITNESS = struct.Struct('<qdd')


def validate(plan):
    stage = plan['stage']
    require(stage in OUTPUTS and plan['phase'] == 'bounded_way_batch_v2', 'Batch phase/stage')
    require(plan['caps'] == (RUN_CAPS if stage == 'run' else CONTROL_CAPS), 'Batch exact caps')
    require(plan['output'] == OUTPUTS[stage] and plan['imageId'] == IMAGE and plan['network'] == 'none', 'Batch image/output/network')
    require(plan['artifact'] == {'path': ARTIFACT, 'sha256': ARTIFACT_SHA}, 'Batch qualified artifact')
    require(plan['site'] == SITE and plan['runtime'] == RUNTIME and plan['parentSeal'] == PARENT_SEAL, 'Batch tool/source admission')
    require(plan['helperQualificationTests'] == 206 and plan['helperQualificationSkips'] == 0, 'Batch helper tests')
    if stage == 'run':
        require(plan['source'] == SOURCE and plan['probe'] == PROBE and plan['expectedWays'] == 274570, 'Batch frozen national workload')
        require(plan['expectedSemantic'] == '209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16', 'Batch national field seal')
        require(plan['controllerAdmission']['qualified'] and plan['controllerAdmission']['tests'] >= 6, 'Batch controller qualification')
    else:
        require(plan['source']['path'] == FIXTURE+'/fixture.pbf' and plan['probe'] == FIXTURE+'/two-pass/pass-b/probe', 'Batch tiny qualification only')
        require(plan['source']['counts'] == {'node':300, 'way':200, 'relation':0} and plan['expectedWays'] == 200, 'Batch tiny counts')
    require(plan['source']['path'] not in plan['inputs'], 'Batch source has separate bounded identity phase')
    require(plan['workerFiles']['/artifacts/helper.so'] == plan['inputs'][ARTIFACT] == ARTIFACT_SHA, 'Batch artifact binding')
    for name, destination in plan['mounts'].items():
        require('..' not in Path(name).parts and (name.startswith('scripts/') or name.startswith('docs/evidence/')), 'Batch code/evidence mount')
        require(destination.startswith(('/code/', '/inputs/', '/docs/')), 'Batch code destination')
        require(plan['inputs'][name] == plan['workerFiles'][destination], 'Batch mounted code binding')
    for name in plan['inputs']:
        require('..' not in Path(name).parts and (name.startswith(('scripts/', 'docs/evidence/', SITE+'/', plan['probe']+'/')) or name in RUNTIME.values() or name == ARTIFACT), 'Batch input closure')
    if stage == 'run':
        admission=plan['controllerAdmission']
        require(all(plan['inputs'].get(name)==pin for name,pin in admission['producers'].items()), 'Batch qualified controller drift')


class BatchSink:
    def __init__(self, reader, root, storage, check, caps):
        self.reader, self.root, self.storage, self.check, self.caps = reader, Path(root), storage, check, caps
        self.root.mkdir()
        self.ledger = []
        self.ways = self.references = 0
        self.fields = hashlib.sha256()

    def receive(self, rows):
        self.check()
        keys = [identity for row in rows for identity in row['nodes']]
        self.ways += len(rows); self.references += len(keys)
        require(len(self.ledger) < self.caps['batches'] and self.references <= self.caps['references'], 'Batch sink aggregate cap')
        before = self.reader.loaded_bytes
        started = time.monotonic(); points = self.reader.points(keys); elapsed = time.monotonic()-started
        require(len(points) == len(keys), 'Batch lookup returned occurrence count')
        witness = b''.join(WITNESS.pack(identity, *point) for identity,point in zip(keys,points))
        for row in rows:self.fields.update(canonical(row)+b'\n')
        name = f'{len(self.ledger):04d}.bin'
        self.storage.write(self.root/name, witness)
        self.ledger.append(dict(file=name, ways=len(rows), references=len(keys), firstWay=rows[0]['id'], lastWay=rows[-1]['id'],
                                witnessSha256=hashlib.sha256(witness).hexdigest(), lookupSeconds=elapsed,
                                authenticatedShardBytes=self.reader.loaded_bytes-before))


class AuditCodec(ReferenceCodec):
    def __init__(self, caps):self.caps=caps;self.rows=self.calls=0
    def decode(self, payload, count, first, last):
        require(self.calls < self.caps['codecCalls'] and self.rows+count <= self.caps['lookupRows'], 'Batch independent decode cap')
        self.calls+=1;self.rows+=count
        return super().decode(payload,count,first,last)


def audit_witnesses(root, ledger, reader, check):
    references=0;digest=hashlib.sha256()
    for row in ledger:
        check();raw=(Path(root)/row['file']).read_bytes()
        require(len(raw)==row['references']*WITNESS.size and hashlib.sha256(raw).hexdigest()==row['witnessSha256'], 'Batch witness identity/size')
        entries=list(WITNESS.iter_unpack(raw));keys=[entry[0] for entry in entries]
        points=reader.points(keys)
        require(len(points)==len(keys), 'Batch independent returned count')
        for (identity,x,y),point in zip(entries,points):
            require(struct.pack('<dd',x,y)==struct.pack('<dd',*point), 'Batch independent ordered coordinate bits')
        references+=len(entries);digest.update(raw)
    return dict(references=references, orderedWitnessSha256=digest.hexdigest())


def worker(plan, root):
    caps=plan['caps'];root=Path(root);resources=Resources(root,seconds=caps['workerSeconds'])
    watchdog=start_watchdog(caps['workerSeconds']);engine=reader=reference=None;sink=None;sequence=0;last=0.
    def check():
        nonlocal sequence,last
        resources.check()
        if engine is not None and time.monotonic()-last>=60:
            last=time.monotonic();sequence+=1
            resources.write(root/f'progress-{sequence:04d}.json',{'seconds':time.monotonic()-resources.began,'native':engine.progress(),
                            'batchWays':sink.ways if sink else 0,'batchReferences':sink.references if sink else 0})
    try:
        verify_worker_inputs(plan)
        if plan['stage']=='controls':
            suite=unittest.defaultTestLoader.loadTestsFromName('coarse_osm_way_batch_v2_test')
            result=unittest.TextTestRunner(verbosity=2).run(suite)
            resources.write(root/'controls.json',dict(tests=result.testsRun,successful=result.wasSuccessful(),skips=len(result.skipped)))
            require(result.wasSuccessful() and not result.skipped and result.testsRun>=6,'Batch controller controls')
        import resource
        require(resource.getrlimit(resource.RLIMIT_FSIZE)==(67108864,67108864),'Batch file limit')
        disk=os.statvfs('/tmp');require(disk.f_blocks*disk.f_frsize==268435456,'Batch tmp limit')
        source=plan['source'];counts=source['counts'];total=sum(counts.values())
        case_started=time.monotonic();case_watchdog=start_watchdog(caps['caseSeconds'])
        try:
            codec=BoundedCodec('/artifacts/helper.so',ARTIFACT_SHA,row_budget=caps['lookupRows'],calls=caps['codecCalls'])
            reader=ProbeReader('/probe',codec,index_limit=384*1024**2,catalog_limit=4*1024**2,read_limit=caps['lookupBytes'])
            storage=CheckedStorage(root,resources);sink=BatchSink(reader,root/'witness',storage,check,caps)
            engine=NativeScreen('/artifacts/helper.so',ARTIFACT_SHA,aggregate_visits=total,codec_rows=1)
            scan_caps={'singleNormalizedElementBytes':4194304,'scanNodesPerPass':max(1,counts['node']),
                       'scanWaysPerPass':max(1,counts['way']),'scanRelationsPerPass':max(1,counts['relation']),
                       'scanObjectVisitsTotal':total,'pbfHeaderBytesExclusiveMaximum':65536,'pbfUncompressedBlobBytesExclusiveMaximum':33554432}
            receipt=engine.scan('/source.pbf',source['publisherState'],scan_caps,source=source,on_way_batch=sink.receive,check=check,
                                batch_caps={'ways':plan['expectedWays'],'references':caps['references'],'batches':caps['batches']})
            require({kind:receipt['counts'].get(kind,0) for kind in counts}==counts and receipt['nativeEof'],'Batch whole-source counts/EOF')
            require(receipt['semanticSha256']==plan['expectedSemantic'] and sink.ways==receipt['batchWays']==plan['expectedWays'], 'Batch whole-source/selected seal and count')
            require(sink.references==receipt['batchReferences'] and len(sink.ledger)==receipt['wayBatches'],'Batch delivered accounting')
            resources.write(root/'ledger.json',sink.ledger)
            resources.write(root/'source-and-lookup.json',dict(receipt=receipt, ways=sink.ways, references=sink.references,
                            selectedFieldsSha256=sink.fields.hexdigest(), authenticatedShardBytes=reader.loaded_bytes,
                            lookupSeconds=sum(row['lookupSeconds'] for row in sink.ledger), decodedRows=codec.decoded_rows,
                            codecCalls=codec.calls, catalogBytes=reader.catalog_bytes, hashAndFormatSeconds=reader.hash_seconds,
                            blockDecodeSeconds=reader.decode_seconds, caseSecondsBeforeClose=time.monotonic()-case_started,
                            scope='Native span includes batch field decoding, coordinate lookups and witness writes; lookup seconds measure points() only. OS cache uncontrolled.'))
            check();require(time.monotonic()-case_started<caps['caseSeconds'],'Batch complete case timer')
        finally:
            if case_watchdog.poll() is None:case_watchdog.terminate()
            case_watchdog.wait(timeout=5)
        audit_started=time.monotonic();audit_watchdog=start_watchdog(caps['auditSeconds'])
        try:
            independent=AuditCodec(caps)
            reference=ProbeReader('/probe',independent,index_limit=384*1024**2,catalog_limit=4*1024**2,read_limit=caps['lookupBytes'])
            proof=audit_witnesses(root/'witness',sink.ledger,reference,check)
            require(proof['references']==sink.references,'Batch complete independent reference count')
            resources.write(root/'independent-audit.json',proof | dict(seconds=time.monotonic()-audit_started,
                            authenticatedShardBytes=reference.loaded_bytes,decodedRows=independent.rows,codecCalls=independent.calls,
                            scope='Independent Python reference decoder and every ordered coordinate bit; retained probe, not a second national road-field oracle.'))
            require(time.monotonic()-audit_started<caps['auditSeconds'],'Batch independent audit timer')
        finally:
            if audit_watchdog.poll() is None:audit_watchdog.terminate()
            audit_watchdog.wait(timeout=5)
        resources.write(root/'result.json',dict(status='passed_bounded_way_batch',ways=sink.ways,references=sink.references,
                        batches=len(sink.ledger),nationalPhysicalIndexAllocated=False,wholeRoadExtractionQualified=False,modelChanged=False))
        return 0
    except BaseException as error:
        (root/'worker-failure.json').write_bytes(canonical(dict(status='stopped',error=str(error),lastNativeReceipt=engine.last if engine else None,
                                                              wholeRoadExtractionQualified=False))+b'\n')
        return 2
    finally:
        for item in (reader,reference):
            if item is not None:item.close()
        try:resources.write(root/'metrics-end.json',resources.result())
        finally:
            if watchdog.poll() is None:watchdog.terminate()
            watchdog.wait(timeout=5)


def driver(recipe,pin):
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==pin,'Batch exact recipe path/hash')
    plan=json.loads(recipe.read_text());validate(plan);caps=plan['caps'];root=repo/plan['output']
    require(not root.exists(),'Batch fresh output required');root.mkdir();shutil.copyfile(recipe,root/'execution-plan.json')
    started=time.monotonic();owner=uuid.uuid4().hex;name='geo-planner-way-batch-'+owner[:12];identity=child=None;success=False
    def save(filename,value):(root/filename).write_bytes(canonical(value)+b'\n')
    def check():
        require(time.monotonic()-started<caps['hostWorkSeconds'],'Batch host deadline')
        require(owned_usage(root)['conservativeAllocatedBytes']<768*1024**2,'Batch host allocation cap')
        require(shutil.disk_usage(root).free>=2147483648,'Batch free space')
    def call(args):check();return subprocess.run(args,capture_output=True,text=True,timeout=15)
    save('owner.json',dict(name=name,label=owner,image=IMAGE,labelKey='geo-planner.stream-owner'))
    try:
        for input_path,expected in plan['inputs'].items():check();require(sha(repo/input_path)==expected,'Batch input drift: '+input_path)
        measured=capacity(repo);require(measured['dockerMemoryBytes']>=6442450944 and measured['hostMemoryBytes']>=8589934592,'Batch starting memory')
        save('capacity-at-start.json',measured)
        source=repo/plan['source']['path'];before=stat_key(source);require(source.is_file() and not source.is_symlink() and source.stat().st_size==plan['source']['bytes'],'Batch source type/length')
        digest=hashlib.sha256();md5=hashlib.md5();count=0;hash_started=time.monotonic()
        with source.open('rb') as stream:
            while data:=stream.read(8*1024**2):
                check();require(time.monotonic()-hash_started<caps['hashSeconds'],'Batch host source hash deadline')
                count+=len(data);require(count<=plan['source']['bytes'],'Batch source byte cap');digest.update(data);md5.update(data)
        require(count==plan['source']['bytes'] and digest.hexdigest()==plan['source']['sha256'] and md5.hexdigest()==plan['source']['md5'] and stat_key(source)==before,'Batch source identity/stability')
        save('host-source-binding.json',dict(bytesRead=count,sha256=digest.hexdigest(),md5=md5.hexdigest(),seconds=time.monotonic()-hash_started))
        args=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,'--network=none','--read-only','--cap-drop=ALL',
              '--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864',
              '--tmpfs','/tmp:rw,size=256m','--env','LD_LIBRARY_PATH=/tools/runtime','--env','PYTHONPATH=/code:/tools/site',
              '--env','OSMIUM_MAX_INPUT_QUEUE_SIZE=2','--env','OSMIUM_MAX_OSMDATA_QUEUE_SIZE=2']
        for input_path,destination in plan['mounts'].items():args+=['--mount',f'type=bind,src={repo/input_path},dst={destination},readonly']
        for filename,input_path in RUNTIME.items():args+=['--mount',f'type=bind,src={repo/input_path},dst=/tools/runtime/{filename},readonly']
        args+=['--mount',f'type=bind,src={repo/SITE},dst=/tools/site,readonly','--mount',f'type=bind,src={repo/ARTIFACT},dst=/artifacts/helper.so,readonly',
               '--mount',f'type=bind,src={source},dst=/source.pbf,readonly','--mount',f'type=bind,src={repo/plan["probe"]},dst=/probe,readonly',
               '--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,
               '-B','/code/run_osm_way_batch_v2.py','/inputs/recipe.json',pin,'--worker']
        result=call(args);require(result.returncode==0,result.stderr);identity=result.stdout.strip();require(len(identity)==64,'Batch owned identity')
        initial=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(initial,'controls')
        save('container-initial.json',dict(Image=initial['Image'],HostConfig=initial['HostConfig'],Mounts=[dict(Destination=m['Destination'],RW=m['RW']) for m in initial['Mounts']]))
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:check();time.sleep(.5)
        final=json.loads(call(['docker','inspect',identity]).stdout)[0]
        save('container-result.json',dict(State=final['State'],clientExitCode=child.returncode))
        require(final['State']['ExitCode']==child.returncode==0 and not final['State']['OOMKilled'],'Batch worker exit/OOM');success=True
    except BaseException as error:save('driver-failure.json',dict(status='stopped',error=str(error)))
    finally:
        if child is not None and child.poll() is None:child.kill();child.wait(timeout=5)
        def cleanup_call(args):return subprocess.run(args,capture_output=True,text=True,timeout=15)
        if not (root/'container-result.json').exists():settle_error(cleanup_call,identity,name,owner,root,child.returncode if child else None)
        cleanup_owned(cleanup_call,identity,name,owner,IMAGE,root)
    require(time.monotonic()-started<caps['hostSeconds'],'Batch final host deadline')
    save('run-summary.json',dict(status='passed_bounded_way_batch' if success else 'stopped',hostSeconds=time.monotonic()-started,networkRequests=0,modelChanged=False))
    return 0 if success else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('recipe');parser.add_argument('sha256');parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    require(sha(args.recipe)==args.sha256,'Batch recipe hash');plan=json.loads(Path(args.recipe).read_text());validate(plan)
    raise SystemExit(worker(plan,'/work') if args.worker else driver(args.recipe,args.sha256))
