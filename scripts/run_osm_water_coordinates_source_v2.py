"""Separately frozen tiny pipeline and one national exact E7 coordinate closure and independent source-shadow audit."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import time
import uuid

from coarse_timing_input import require, start_watchdog
from run_osm_topology_v1 import SOURCE, SCAN

IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
PREFIX = 'data/coarse-quality/us-osm-water-coordinates-source-v2-'
OWNED={'controls':67108864,'run':2415919104}
ENCODED={'controls':8388608,'run':2147483648}
MISSING={'controls':8388608,'run':1073741824}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(root, name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 1048576, 'Water source record cap')
    with (root/name).open('xb') as stream:
        stream.write(raw)


def worker(plan):
    import struct
    from coarse_osm_country_screen_v1 import owned_usage,resource_metrics
    from coarse_osm_data import verify_worker_inputs
    from coarse_osm_water_coordinates_v1 import WaterCoordinates,audit_store
    from coarse_osm_water_coordinate_store_v1 import CoordinateStore
    from coarse_osm_water_coordinate_scan_v1 import collect
    from coarse_osm_water_reference_store_v1 import Reader
    root=Path('/work');operation=plan['operation'];began=time.monotonic()
    limit=120 if operation=='controls' else 2700;timer=start_watchdog(limit)
    engine=None;phase='bindings';last_progress=0.;last_storage=-1.
    def check():
        nonlocal last_progress,last_storage
        elapsed=time.monotonic()-began
        require(elapsed<limit,'Water coordinate worker deadline')
        if elapsed-last_storage>=1:
            last_storage=elapsed
            require(owned_usage(root)['conservativeAllocatedBytes']<=OWNED[operation],'Water coordinate owned cap')
        if engine is not None and elapsed-last_progress>=15:
            last_progress=elapsed;print(json.dumps({'workerSeconds':elapsed,'phase':phase,'nativeProgress':engine.progress()}),flush=True)
    try:
        c=Path('/sys/fs/cgroup')
        require((c/'memory.max').read_text().strip()==str(4*1024**3) and (c/'memory.swap.max').read_text().strip()=='0','Water coordinate memory/swap')
        quota,period=map(int,(c/'cpu.max').read_text().split())
        require(quota==2*period and int((c/'pids.max').read_text())==64,'Water coordinate CPU/PIDs')
        verify_worker_inputs({'workerFiles':{destination:plan['inputs'][name] for name,destination in plan['mounts'].items()}})
        artifact=('/artifacts/water-coordinates.so',plan['artifact']['sha256'])
        if operation=='controls':
            import osmium
            from coarse_osm_native_smoke import fixture_records,write_xml,STATE
            from coarse_osm_country_wire_v4 import field_frame,reference_seal
            from coarse_osm_water_census_v2_test import CAPS
            require(not Path('/source.pbf').exists() and not Path('/inputs/node-index').exists(),'Water coordinate controls must not mount national source/index')
            rows=fixture_records();ids=sorted([r['id'] for r in rows if r['type']=='node']+[99])
            id_raw=b''.join(struct.pack('<Q',i) for i in ids)
            id_chunks=lambda:iter([id_raw])
            canonical=b''.join(struct.pack('<Q',r['id'])+field_frame(r)[-8:] for r in rows if r['type']=='node')
            xml,pbf=root/'tiny.osm',root/'tiny.pbf';write_xml(xml,rows)
            header=osmium.io.Header();header.set('osmosis_replication_timestamp',STATE)
            with osmium.SimpleWriter(str(pbf),header=header,bufsz=65536) as writer:
                for obj in osmium.FileProcessor(str(xml)):writer.add(obj)
            raw=pbf.read_bytes();source={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'md5':hashlib.md5(raw).hexdigest()}
            with CoordinateStore(root,len(ids),encoded_budget=ENCODED[operation],missing_budget=MISSING[operation]) as store:
                engine=WaterCoordinates(*artifact,requested=len(ids),id_chunks=id_chunks,store=store,check=check)
                measured=collect(engine,pbf,STATE,CAPS,source,{'node':4,'way':3,'relation':2},reference_seal(rows),check)
                require(not engine.begun and not engine.active,'Water coordinate producer ID buffers released')
                result=measured['coordinates']
                require(result['stored']['sourceShadow']=={'bytes':len(canonical),'sha256':hashlib.sha256(canonical).hexdigest()},'Water coordinate tiny independent canonical source bytes')
                audited=audit_store(engine,root,result['stored'],result['capture'],check)
                require(audited['requestedIdsIndependentlyPartitioned']==5 and audited['presentCoordinatesIndependentlyDecoded']==4 and audited['missingIdsIndependentlyCompared']==1,'Water coordinate tiny exact partition')
            rejected=root/'wrong-source';rejected.mkdir();refused=False
            with CoordinateStore(rejected,len(ids),encoded_budget=ENCODED[operation],missing_budget=MISSING[operation]) as store:
                engine=WaterCoordinates(*artifact,requested=len(ids),id_chunks=id_chunks,store=store,check=check)
                try:collect(engine,pbf,STATE,CAPS,source|{'sha256':'0'*64},{'node':4,'way':3,'relation':2},reference_seal(rows),check)
                except Exception as error:
                    require('source identity' in str(error),'Water coordinate wrong-source rejection boundary');refused=True
            require(refused,'Water coordinate wrong-source must be rejected')
            save(root,'report.json',{'status':'water_coordinate_controller_pipeline_passed','checks':{'positivePipeline':True,'wrongSourceRejected':True,'nationalSourceMounted':False,'nationalIndexMounted':False,'sourceCoordinateShadowExact':True,'completeRequestedIdPartition':True,'producerBuffersReleasedBeforeAudit':True},'tiny':measured,'independentAudit':audited})
            return 0
        require(operation=='run','Water coordinate operation')
        prior=json.loads(Path('/inputs/water-references-report.json').read_bytes())
        index=prior['water']['referenceStore']['nodes']
        require(prior['status']=='national_water_exact_references_and_unique_ids_audited' and
                prior['independentAudit']['allUniqueNodeIdsIndependentlyCompared']==101738006 and index['rawBytes']==813904048 and
                index['rawSha256']=='587da8a37ae28bfaae38709faf3f016cc03383b61dfef56e06d8be8428c988fd','Water coordinate exact independently audited requested index')
        def id_chunks():
            with Reader('/inputs/node-index',index) as reader:
                while raw:=reader.read(1048576):yield raw
                require(reader.finished,'Water coordinate complete index EOF')
        with CoordinateStore(root,101738006,encoded_budget=ENCODED[operation],missing_budget=MISSING[operation]) as store:
            engine=WaterCoordinates(*artifact,requested=101738006,id_chunks=id_chunks,store=store,check=check,aggregate_visits=1770542426)
            phase='source-coordinate-capture';source_start=time.monotonic()
            measured=collect(engine,Path('/source.pbf'),SOURCE['state'],SCAN,SOURCE,{'node':1606229364,'way':162688797,'relation':1624265},SOURCE['semanticSha256'],check)
            source_seconds=time.monotonic()-source_start
            require(not engine.active and not engine.begun,'Water coordinate producer buffers released before audit reload')
            result=measured['coordinates'];phase='independent-coordinate-audit';audit_start=time.monotonic()
            audited=audit_store(engine,root,result['stored'],result['capture'],check)
            audit_seconds=time.monotonic()-audit_start
        check();save(root,'receipt.json',measured['receipt'])
        save(root,'report.json',{'status':'national_water_exact_coordinate_closure_and_source_shadow_audited','coordinates':result,'independentAudit':audited,
                                 'sourceAndCoordinateCaptureSecondsIncludingIndexLoadProtectedValidationCompressionRelease':source_seconds,
                                 'independentCoordinateDecodeSourceShadowPartitionAuditSeconds':audit_seconds,
                                 'workerSecondsIncludingBindingsIndexSourceCaptureAudit':time.monotonic()-began,
                                 'producerBuffersReleasedBeforeAudit':True,'sourcePbfScans':1,'roadGraphConstructorExecutions':0,'routingQueries':0,'providerRequests':0,
                                 'priorMissingWayMembers':17,'priorSourceAbsentNestedRelations':1,
                                 'coordinatesRetained':True,'ringsOrPolygonsConstructed':False,'maskOrModelChanged':False,'appActivated':False,
                                 'scope':'Exact existing source E7 coordinates and explicit missing IDs for every independently audited requested node. All canonical source ID/X/Y shadow bytes and full requested-ID partition independently reproduce. No new rounding/rings/polygon/shore/input/ETA/app admission. Existing source gaps remain explicit.'})
        return 0
    except BaseException as error:
        save(root,'failure.json',{'status':'water_coordinate_closure_stopped','error':repr(error),'workerSeconds':time.monotonic()-began,'phase':phase});raise
    finally:
        save(root,'metrics.json',resource_metrics())
        if timer.poll() is None:timer.terminate()
        timer.wait(timeout=5)


def driver(recipe, pin):
    from coarse_osm_full_monitor_v1 import owned_usage
    from prepare_osm_native_lock_v1 import cleanup_owned, settle_error
    from run_osm_country_screen_v1 import isolation
    repo = Path(__file__).resolve().parents[1]
    recipe = Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe) == pin, 'Water source recipe binding')
    plan = json.loads(recipe.read_bytes())
    operation = plan['operation']
    require(operation in ('controls', 'run') and plan['output'] == PREFIX+operation+'-v1', 'Water source exact namespace')
    require(plan['retainedBytes']==72*1024**3 and plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+OWNED[operation]+268435456 < plan['retainedBytes'], 'Water source aggregate reservation')
    require(set(plan['mounts']) == set(plan['inputs']), 'Water source complete input bindings')
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/', '/tools/')), 'Water source input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Water source input SHA/no PBF')
    require(plan['source'] == SOURCE and plan['scanCaps'] == SCAN, 'Water exact original source/scan guards')
    require(operation == 'controls' or plan['nativeAdmission'] == {'tests':55,'successful':True,'failures':0,'errors':0,'skips':0} and plan['controllerAdmission'] == {'positivePipeline':True,'wrongSourceRejected':True,'nationalSourceMounted':False,'nationalIndexMounted':False,'sourceCoordinateShadowExact':True,'completeRequestedIdPartition':True,'producerBuffersReleasedBeforeAudit':True}, 'Water source qualification admission')
    if operation == 'run':
        original = repo/SOURCE['path']
        require(original.is_file() and not original.is_symlink() and original.stat().st_size == SOURCE['bytes'], 'Water exact read-only cached source')
    require(shutil.disk_usage(repo).free>=88*1024**3,'Water coordinate V2 initial host free headroom')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-water-coordinates-source-v2-'+owner[:12]
    save(root, 'owner.json', {'name': name, 'label': owner, 'image': IMAGE})
    began = time.monotonic()
    identity = child = None
    code = 2
    def call(args):
        return subprocess.run(args, capture_output=True, text=True, timeout=15)
    try:
        command = ['docker', 'create', '--pull=never', '--init', '--name', name, '--label', 'geo-planner.stream-owner='+owner,
                   '--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=4g', '--memory-swap=4g', '--cpus=2', '--pids-limit=64',
                   '--tmpfs', '/tmp:rw,size=256m', '--ulimit', 'core=0:0', '--ulimit', 'fsize=67108864:67108864', '--env', 'PYTHONPATH=/code:/tools/site:/reference', '--env', 'LD_LIBRARY_PATH=/tools/runtime', '--env', 'OSMIUM_MAX_INPUT_QUEUE_SIZE=2', '--env', 'OSMIUM_MAX_OSMDATA_QUEUE_SIZE=2']
        for source, destination in plan['mounts'].items():
            command += ['--mount', f'type=bind,src={repo/source},dst={destination},readonly']
        if operation == 'run':
            command += ['--mount', f'type=bind,src={repo/SOURCE["path"]},dst=/source.pbf,readonly']
        command += ['--mount', f'type=bind,src={root},dst=/work', '--mount', f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly',
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_water_coordinates_source_v2.py', '/inputs/recipe.json', pin, '--worker']
        created = call(command)
        require(created.returncode == 0, created.stderr)
        identity = created.stdout.strip()
        require(len(identity) == 64, 'Water source exact owned ID')
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        isolation(observed, 'controls')
        save(root, 'container-initial.json', observed)
        with (root/'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(shutil.disk_usage(root).free>=16*1024**3,'Water coordinate V2 during-run host headroom')
                require(time.monotonic()-began < (180 if operation=='controls' else 3000) and owned_usage(root)['conservativeAllocatedBytes'] <= OWNED[operation], 'Water source host deadline/owned cap')
                time.sleep(.5)
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        save(root, 'container-result.json', {'State': observed['State'], 'clientExitCode': child.returncode})
        require(child.returncode == observed['State']['ExitCode'] == 0 and not observed['State']['OOMKilled'], 'Water source worker exit/OOM')
        code = 0
    except BaseException as error:
        save(root, 'driver-failure.json', {'error': repr(error), 'hostSeconds': time.monotonic()-began})
    finally:
        if child and child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        if not (root/'container-result.json').exists():
            settle_error(call, identity, name, owner, root, child.returncode if child else None)
        cleanup_owned(call, identity, name, owner, IMAGE, root)
    save(root, 'run-summary.json', {'exitCode': code, 'hostSecondsIncludingCleanup': time.monotonic()-began, 'sourcePbfReads': 0})
    return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe')
    parser.add_argument('pin')
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    require(sha(args.recipe) == args.pin, 'Water source recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe, args.pin))
