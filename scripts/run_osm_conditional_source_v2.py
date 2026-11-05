"""Separately frozen tiny pipeline and one national conditional-metadata feasibility run."""
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
PREFIX = 'data/coarse-quality/us-osm-conditional-source-'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(root, name, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    require(len(raw) <= 1048576, 'Conditional source record cap')
    with (root/name).open('xb') as stream:
        stream.write(raw)


def worker(plan):
    from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
    from coarse_osm_data import verify_worker_inputs
    from coarse_osm_conditional_census_v1 import ConditionalCensus
    from coarse_osm_conditional_scan_v2 import collect
    root = Path('/work')
    operation = plan['operation']
    began = time.monotonic()
    timer = start_watchdog(120 if operation=='controls' else 2700)
    engine = None
    last_progress = 0.
    last_storage_check = -1.
    def check():
        nonlocal last_progress, last_storage_check
        elapsed = time.monotonic()-began
        require(elapsed < (120 if operation=='controls' else 2700), 'Conditional source worker deadline')
        if elapsed-last_storage_check >= 1:
            last_storage_check = elapsed
            require(owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Conditional source owned cap')
        if engine is not None and elapsed-last_progress >= 15:
            last_progress = elapsed
            print(json.dumps({'workerSeconds':elapsed,'nativeProgress':engine.progress()}),flush=True)
    try:
        cgroup = Path('/sys/fs/cgroup')
        require((cgroup/'memory.max').read_text().strip() == str(4*1024**3) and (cgroup/'memory.swap.max').read_text().strip() == '0', 'Conditional source memory/swap')
        verify_worker_inputs({'workerFiles': {destination: plan['inputs'][name] for name, destination in plan['mounts'].items()}})
        artifact = ('/artifacts/conditional-census.so', plan['artifact']['sha256'])
        if operation == 'controls':
            import osmium
            from coarse_osm_native_smoke import fixture_records, write_xml, STATE
            from coarse_osm_projector_v1 import reference_seal
            from coarse_osm_conditional_census_v1_test import CAPS
            import unittest
            import coarse_osm_conditional_scan_v2_test as audit_tests
            tested=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(audit_tests))
            unit={'tests':tested.testsRun,'successful':tested.wasSuccessful(),'failures':len(tested.failures),'errors':len(tested.errors),'skips':len(tested.skipped)}
            save(root,'audit-controls.json',unit)
            require(unit=={'tests':7,'successful':True,'failures':0,'errors':0,'skips':0},'Independent changed metadata audit controls')
            require(not Path('/source.pbf').exists(), 'Conditional pipeline controls do not mount national source')
            records = fixture_records()
            records[1]['tags']['hgv:conditional']='no @ night'
            records[4]['tags']|={'highway':'primary','access':'yes','maxspeed':'80','maxspeed:conditional':'20 @ wet'}
            records[5]['tags']|={'highway':'primary','access':'private','maxspeed:conditional':'20 @ wet'}
            xml, pbf = root/'tiny.osm', root/'tiny.pbf'
            write_xml(xml, records)
            header = osmium.io.Header()
            header.set('osmosis_replication_timestamp', STATE)
            with osmium.SimpleWriter(str(pbf), header=header, bufsz=65536) as writer:
                for obj in osmium.FileProcessor(str(xml)):
                    writer.add(obj)
            source = {'bytes':pbf.stat().st_size, 'sha256':sha(pbf), 'md5':hashlib.md5(pbf.read_bytes()).hexdigest()}
            engine = ConditionalCensus(*artifact)
            measured = collect(engine,pbf,STATE,CAPS,source,{'node':4,'way':3,'relation':2},reference_seal(records),root/'changed-tags.bin',check,lambda value:save(root,'source-census.json',value))
            require(measured['conditional']['newlyEligibleWays']==measured['conditional']['changedNodeFlags']==1 and measured['independentChangedTagAudit']['counts']['ways']==measured['independentChangedTagAudit']['counts']['nodes']==1,'Conditional tiny independent selection/audit')
            engine = ConditionalCensus(*artifact)
            refused = False
            try:
                collect(engine,pbf,STATE,CAPS,source|{'sha256':'0'*64},{'node':4,'way':3,'relation':2},reference_seal(records),root/'wrong-source-changed-tags.bin',check,lambda value:save(root,'wrong-source-census.json',value))
            except Exception as error:
                require('source identity' in str(error), 'Conditional wrong-source exact rejection boundary')
                refused = True
            require(refused,'Conditional changed source must be rejected')
            save(root,'report.json',{'status':'conditional_source_controller_pipeline_passed','checks':{'positivePipeline':True,'wrongSourceRejected':True,'nationalSourceMounted':False,'independentChangedTagAudit':True,'auditUnitTests':7},'tiny':measured})
            return 0
        require(operation == 'run','Conditional source operation')
        engine = ConditionalCensus(*artifact,aggregate_visits=1770542426)
        measured = collect(engine,Path('/source.pbf'),SOURCE['state'],SCAN,SOURCE,{'node':1606229364,'way':162688797,'relation':1624265},SOURCE['semanticSha256'],root/'changed-tags.bin',check,lambda value:save(root,'source-census.json',value))
        baseline=json.loads(Path('/facts/country-fact-summary.json').read_bytes());c=measured['conditional']
        require(c['majorWays']==baseline['majorWays'] and c['majorReferences']==baseline['majorReferences'],'Original national major profile/reference counts')
        require(c['oldEligibleWays']==baseline['wayReasons']['eligible'] and c['taggedNodes']==baseline['allTaggedNodes'] and c['signalNodes']==baseline['allSignalNodes'] and c['oldBlockedNodes']==baseline['allBlockedNodes'],'Original national policy counts')
        reasons=['eligible','outside-major-profile','vehicle-ferry','access','area-ford-driveway-parking','conditional-or-way-restriction','lane-access','unsupported-oneway','unsupported-speed','directional-access']
        require(all(c['oldWayReason'+str(i)]==baseline['wayReasons'][reason] for i,reason in enumerate(reasons)),'Every original national way reason exact')
        save(root,'receipt.json',measured['receipt'])
        save(root,'report.json',{'status':'complete_national_conditional_metadata_census_passed','conditional':c,
                                 'independentChangedTagAudit':measured['independentChangedTagAudit'],
                                 'sourceValidationAndCensusSeconds':measured['sourceValidationAndCensusSeconds'],
                                 'changedTagAuditSeconds':measured['changedTagAuditSeconds'],
                                 'workerSecondsIncludingBindingsAndProtectedSourceValidation':time.monotonic()-began,
                                 'sourcePbfScans':1,'sourceConstructorExecutions':0,'routingQueries':0,'providerRequests':0,'applicationDbReads':0,
                                 'coordinatesOrGeometryRetained':False,'maskOrModelChanged':False,'appActivated':False,
                                 'scope':'Complete changed ID/tag metadata only over every unchanged source object; original source semantic/counts/major profile/references/old-way reasons/node flags/full pre-post identity exact, all old positives retained. All changed tags independently decoded/reclassified, including unchanged signal/tagged protection. No country coordinates/reference dictionary/new source acquisition/graph/native constructor/routes/ETA/app acceptance. Timings cover source hashes/validation/census/tag audit separately, not query/cloud time.'})
        return 0
    except BaseException as error:
        save(root,'failure.json',{'status':'conditional_source_stopped','error':repr(error),'workerSeconds':time.monotonic()-began})
        raise
    finally:
        save(root,'metrics.json',resource_metrics())
        if timer.poll() is None:
            timer.terminate()
        timer.wait(timeout=5)


def driver(recipe, pin):
    from coarse_osm_full_monitor_v1 import owned_usage
    from prepare_osm_native_lock_v1 import cleanup_owned, settle_error
    from run_osm_country_screen_v1 import isolation
    repo = Path(__file__).resolve().parents[1]
    recipe = Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe) == pin, 'Conditional source recipe binding')
    plan = json.loads(recipe.read_bytes())
    operation = plan['operation']
    require(operation in ('controls', 'run') and plan['output'] == PREFIX+operation+'-v2', 'Conditional source exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+67108864+268435456 < 72*1024**3, 'Conditional source aggregate reservation')
    require(set(plan['mounts']) == set(plan['inputs']), 'Conditional source complete input bindings')
    for name, destination in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and destination.startswith(('/code/', '/reference/', '/facts/', '/inputs/', '/artifacts/', '/tools/')), 'Conditional source input scope')
        require(not name.endswith(('.pbf', '/001.bin')) and sha(repo/name) == plan['inputs'][name], 'Conditional source input SHA/no PBF')
    require(plan['source'] == SOURCE and plan['scanCaps'] == SCAN, 'Conditional exact original source/scan guards')
    require(operation == 'controls' or plan['nativeAdmission'] == {'tests':38,'successful':True,'failures':0,'errors':0,'skips':0} and plan['controllerAdmission'] == {'positivePipeline':True,'wrongSourceRejected':True,'nationalSourceMounted':False,'independentChangedTagAudit':True,'auditUnitTests':7}, 'Conditional source qualification admission')
    if operation == 'run':
        original = repo/SOURCE['path']
        require(original.is_file() and not original.is_symlink() and original.stat().st_size == SOURCE['bytes'], 'Conditional exact read-only cached source')
    root = repo/plan['output']
    root.mkdir()
    (root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner = uuid.uuid4().hex
    name = 'geo-planner-conditional-source-'+owner[:12]
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
                    '--entrypoint=python3', IMAGE, '-B', '/code/run_osm_conditional_source_v2.py', '/inputs/recipe.json', pin, '--worker']
        created = call(command)
        require(created.returncode == 0, created.stderr)
        identity = created.stdout.strip()
        require(len(identity) == 64, 'Conditional source exact owned ID')
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        isolation(observed, 'controls')
        save(root, 'container-initial.json', observed)
        with (root/'worker.log').open('xb') as log:
            child = subprocess.Popen(['docker', 'start', '-a', identity], stdout=log, stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began < (180 if operation=='controls' else 3000) and owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Conditional source host deadline/owned cap')
                time.sleep(.5)
        observed = json.loads(call(['docker', 'inspect', identity]).stdout)[0]
        save(root, 'container-result.json', {'State': observed['State'], 'clientExitCode': child.returncode})
        require(child.returncode == observed['State']['ExitCode'] == 0 and not observed['State']['OOMKilled'], 'Conditional source worker exit/OOM')
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
    save(root, 'run-summary.json', {'exitCode': code, 'hostSecondsIncludingCleanup': time.monotonic()-began, 'sourcePbfScanIntended': operation=='run'})
    return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe')
    parser.add_argument('pin')
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    require(sha(args.recipe) == args.pin, 'Conditional source recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe, args.pin))
