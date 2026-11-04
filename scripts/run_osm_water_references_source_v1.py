"""Separately frozen tiny pipeline and one national lossless water reference capture and audit."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from coarse_timing_input import require, start_watchdog
from run_osm_topology_v1 import SOURCE, SCAN

IMAGE = 'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402'
PREFIX = 'data/coarse-quality/us-osm-water-references-source-'
OWNED={'controls':67108864,'run':872415232}
COMPRESSED={'controls':16777216,'run':838860800}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(root, name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 1048576, 'Water source record cap')
    with (root/name).open('xb') as stream:
        stream.write(raw)


def worker(plan):
    from array import array
    from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
    from coarse_osm_data import verify_worker_inputs
    from coarse_osm_water_references_v1 import WaterReferences, audit_store
    from coarse_osm_water_reference_store_v1 import ReferenceStore
    from coarse_osm_water_scan_v1 import collect
    root=Path('/work');operation=plan['operation'];began=time.monotonic()
    limit=120 if operation=='controls' else 2700;timer=start_watchdog(limit)
    engine=None;last_progress=0.;last_storage=-1.
    def check():
        nonlocal last_progress,last_storage
        elapsed=time.monotonic()-began
        require(elapsed<limit,'Water reference worker deadline')
        if elapsed-last_storage>=1:
            last_storage=elapsed
            require(owned_usage(root)['conservativeAllocatedBytes']<=OWNED[operation],'Water reference owned cap')
        if engine is not None and elapsed-last_progress>=15:
            last_progress=elapsed;print(json.dumps({'workerSeconds':elapsed,'nativeProgress':engine.progress()}),flush=True)
    try:
        c=Path('/sys/fs/cgroup')
        require((c/'memory.max').read_text().strip()==str(4*1024**3) and (c/'memory.swap.max').read_text().strip()=='0','Water reference memory/swap')
        quota,period=map(int,(c/'cpu.max').read_text().split())
        require(quota==2*period and int((c/'pids.max').read_text())==64,'Water reference CPU/PIDs')
        verify_worker_inputs({'workerFiles':{destination:plan['inputs'][name] for name,destination in plan['mounts'].items()}})
        artifact=('/artifacts/water-references.so',plan['artifact']['sha256'])
        if operation=='controls':
            import osmium
            from coarse_osm_native_smoke import fixture_records,write_xml,STATE
            from coarse_osm_country_wire_v4 import framed_records,reference_seal
            from coarse_osm_water_union_v1_test import oracle
            from coarse_osm_water_references_v1_test import selected
            from coarse_osm_water_census_v2_test import CAPS
            require(not Path('/source.pbf').exists(),'Water reference controls do not mount national source')
            rows=fixture_records();rows[4]['tags']['natural']='water';rows[7]['tags']['natural']='water'
            ids=sorted([rows[4]['id'],rows[6]['id'],rows[6]['id']+1]);expected=oracle(rows,ids)
            raw_bytes=len(framed_records(selected(rows,ids)))
            xml,pbf=root/'tiny.osm',root/'tiny.pbf';write_xml(xml,rows)
            header=osmium.io.Header();header.set('osmosis_replication_timestamp',STATE)
            with osmium.SimpleWriter(str(pbf),header=header,bufsz=65536) as writer:
                for obj in osmium.FileProcessor(str(xml)):writer.add(obj)
            raw=pbf.read_bytes();source={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'md5':hashlib.md5(raw).hexdigest()}
            with ReferenceStore(root,raw_way_bytes=raw_bytes,reference_count=expected['unionReferences'],budget=COMPRESSED[operation]) as store:
                engine=WaterReferences(*artifact,store=store,member_ids=ids,expected_ways=expected['unionWays'],expected_references=expected['unionReferences'],check=check)
                measured=collect(engine,pbf,STATE,CAPS,source,{'node':4,'way':3,'relation':2},reference_seal(rows),check)
                require(measured['water']['union']==expected and not engine.begun and not engine.active,'Water reference tiny exact union and released capture')
                audited=audit_store(engine,root,measured['water']['referenceStore'],measured['water']['referenceCapture'],measured['water']['union'],ids,check)
            rejected=root/'wrong-source';rejected.mkdir();refused=False
            with ReferenceStore(rejected,raw_way_bytes=raw_bytes,reference_count=expected['unionReferences'],budget=COMPRESSED[operation]) as store:
                engine=WaterReferences(*artifact,store=store,member_ids=ids,expected_ways=expected['unionWays'],expected_references=expected['unionReferences'],check=check)
                try:collect(engine,pbf,STATE,CAPS,source|{'sha256':'0'*64},{'node':4,'way':3,'relation':2},reference_seal(rows),check)
                except Exception as error:
                    require('source identity' in str(error),'Water reference wrong-source rejection boundary');refused=True
            require(refused,'Water reference wrong-source must be rejected')
            save(root,'report.json',{'status':'water_reference_controller_pipeline_passed','checks':{'positivePipeline':True,'wrongSourceRejected':True,'nationalSourceMounted':False,'memberWayUnionExact':True,'referenceBytesAndUniqueIdsExact':True,'producerBuffersReleasedBeforeAudit':True},'tiny':measured,'independentAudit':audited})
            return 0
        require(operation=='run','Water reference operation')
        member_raw=Path('/inputs/closure-member-way-ids.u64').read_bytes()
        require(len(member_raw)==3666040,'Water reference exact source-derived member input')
        ids=array('Q');ids.frombytes(member_raw);require(len(ids)==458255 and ids.itemsize==8,'Water reference complete member count/platform')
        prior=json.loads(Path('/inputs/water-union-report.json').read_bytes())
        expected=prior['water']['union']
        require(expected['unionWays']==2829193 and expected['unionReferences']==104806243 and expected['unionEncodedBytes']==1197794328,'Water reference exact frozen source union dimensions')
        with ReferenceStore(root,raw_way_bytes=1209111100,reference_count=104806243,budget=COMPRESSED[operation]) as store:
            engine=WaterReferences(*artifact,store=store,member_ids=ids,expected_ways=2829193,expected_references=104806243,check=check,aggregate_visits=1770542426)
            source_start=time.monotonic()
            measured=collect(engine,Path('/source.pbf'),SOURCE['state'],SCAN,SOURCE,{'node':1606229364,'way':162688797,'relation':1624265},SOURCE['semanticSha256'],check)
            source_seconds=time.monotonic()-source_start
            water=measured['water'];require({k:water[k] for k in prior['water']}==prior['water'],'Water reference exact all40 water/all20 union counters')
            require(not engine.active and not engine.begun,'Water reference producer buffers released before audit')
            audit_start=time.monotonic()
            audited=audit_store(engine,root,water['referenceStore'],water['referenceCapture'],water['union'],ids,check)
            audit_seconds=time.monotonic()-audit_start
        missing=water.pop('missingMemberWayIds')
        with (root/'missing-member-way-ids.u64').open('xb') as stream:array('Q',missing).tofile(stream)
        require(len(missing)==17 and sha(root/'missing-member-way-ids.u64')==prior['missingMemberWayIds']['sha256'],'Water reference exact missing source way IDs')
        check();save(root,'receipt.json',measured['receipt'])
        save(root,'report.json',{'status':'national_water_exact_references_and_unique_ids_audited','water':water,'independentAudit':audited,
                                 'missingMemberWayIds':prior['missingMemberWayIds'],'sourceAndCaptureSecondsIncludingProtectedValidationSortCompressionRelease':source_seconds,
                                 'independentSavedReferenceAuditSeconds':audit_seconds,'workerSecondsIncludingBindingsSourceCaptureAudit':time.monotonic()-began,
                                 'producerBuffersReleasedBeforeAudit':True,'sourcePbfScans':1,'sourceConstructorExecutions':0,'routingQueries':0,'providerRequests':0,
                                 'coordinatesOrGeometryRetained':False,'maskOrModelChanged':False,'appActivated':False,
                                 'scope':'Exact selected normalized GPF metadata/references and unique native node IDs only, every saved field/reference/index independently checked. Missing17 ways/one nested relation remain. No coordinates, rings, polygon/shore/input/ETA/app admission.'})
        return 0
    except BaseException as error:
        save(root,'failure.json',{'status':'water_references_stopped','error':repr(error),'workerSeconds':time.monotonic()-began});raise
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
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+OWNED[operation]+268435456 < 64*1024**3, 'Water source aggregate reservation')
    require(set(plan['mounts']) == set(plan['inputs']), 'Water source complete input bindings')
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/', '/tools/')), 'Water source input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Water source input SHA/no PBF')
    require(plan['source'] == SOURCE and plan['scanCaps'] == SCAN, 'Water exact original source/scan guards')
    require(operation == 'controls' or plan['nativeAdmission'] == {'tests':62,'successful':True,'failures':0,'errors':0,'skips':0} and plan['controllerAdmission'] == {'positivePipeline':True,'wrongSourceRejected':True,'nationalSourceMounted':False,'memberWayUnionExact':True,'referenceBytesAndUniqueIdsExact':True,'producerBuffersReleasedBeforeAudit':True}, 'Water source qualification admission')
    if operation == 'run':
        original = repo/SOURCE['path']
        require(original.is_file() and not original.is_symlink() and original.stat().st_size == SOURCE['bytes'], 'Water exact read-only cached source')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-water-references-source-'+owner[:12]
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
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_water_references_source_v1.py', '/inputs/recipe.json', pin, '--worker']
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
