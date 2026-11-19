"""Collect original tags for every current winner source way; change no model costs."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from coarse_osm_current_way_tag_audit_v1 import audit
from coarse_osm_selected_way_tags_v1 import SelectedWayTags
from coarse_osm_country_screen_v1 import owned_usage, resource_metrics
from coarse_osm_data import verify_worker_inputs
from coarse_timing_input import require, start_watchdog
from run_osm_explicit_lane_source_v1 import IMAGE, sha, save
from run_osm_topology_v1 import SOURCE, SCAN

PREFIX = 'data/coarse-quality/us-osm-current-way-tags-source-'


def inputs(plan):
    if plan['operation'] == 'run':
        raw = gzip.decompress(Path('/inputs/current-source-inputs.json.gz').read_bytes())
        require(len(raw) <= 8388608, 'Current source inputs raw bound')
        encoded = json.loads(raw)
        selected = {int(k): v for k, v in encoded['selectedRoles'].items()}
        cached = {int(k): v for k, v in encoded['cachedTags'].items()}
        require(len(selected) == 33427 and len(cached) == 1084, 'Complete frozen current source inputs')
        return selected, cached, None
    report = json.loads(Path('/inputs/current-attributes-report.json').read_bytes())
    asset = report['artifact']
    packed = Path('/inputs/current-attributes.json.gz').read_bytes()
    require(len(packed) == asset['bytes'] and hashlib.sha256(packed).hexdigest() == asset['sha256'], 'Exact current source attributes')
    raw = gzip.decompress(packed)
    require(len(raw) == asset['rawBytes'] <= 50331648 and hashlib.sha256(raw).hexdigest() == asset['rawSha256'], 'Exact current raw attributes')
    attributes = json.loads(raw)
    require(len(attributes) == report['selectedArcs'] == 43910, 'Every current selected arc')
    selected = {}
    for row in attributes.values():
        identity, role = row['sourceWay'], row['role']
        require(identity not in selected or selected[identity] == role, 'Current way consistent source role')
        selected[identity] = role
    require(len(selected) == 33427, 'Every current used source way')
    db = sqlite3.connect('file:/inputs/source-cache.sqlite?mode=ro&immutable=1', uri=True)
    db.execute('PRAGMA query_only=ON')
    db.execute('PRAGMA cache_size=-16384')
    records = []
    try:
        for identity in sorted(selected):
            found = db.execute("SELECT id,raw FROM objects WHERE kind='way' AND id=?", (identity,)).fetchone()
            if found is None:
                continue
            require(int(found[0]) == identity and len(found[1]) <= 4194304, 'Bound cached current original way')
            record = json.loads(found[1])
            require(record['id'] == identity and record['tags'].get('highway') == selected[identity], 'Cached current raw source role')
            records.append(record)
    finally:
        db.close()
    require(len(records) == 1084, 'All known current raw originals retained')
    return selected, {r['id']: r['tags'] for r in records}, records


def worker(plan):
    root = Path('/work')
    operation = plan['operation']
    began = time.monotonic()
    timer = start_watchdog(180 if operation == 'capture' else 2700)
    engine = None
    last_storage = last_progress = -1.
    def check():
        nonlocal last_storage, last_progress
        elapsed = time.monotonic()-began
        require(elapsed < (180 if operation == 'capture' else 2700), 'Current way source worker deadline')
        if elapsed-last_storage >= 1:
            last_storage = elapsed
            require(owned_usage(root)['conservativeAllocatedBytes'] <= 67108864, 'Current way source owned cap')
        if engine is not None and elapsed-last_progress >= 15:
            last_progress = elapsed
            print(json.dumps({'workerSeconds': elapsed, 'nativeProgress': engine.progress()}), flush=True)
    try:
        c = Path('/sys/fs/cgroup')
        require((c/'memory.max').read_text().strip() == str(4*1024**3) and (c/'memory.swap.max').read_text().strip() == '0', 'Current source memory/swap')
        verify_worker_inputs({'workerFiles': {dest: plan['inputs'][name] for name, dest in plan['mounts'].items()}})
        selected, cached, records = inputs(plan)
        if operation == 'capture':
            import unittest
            import coarse_osm_current_way_tag_audit_v1_test as tests
            tested = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
            controls = dict(tests=tested.testsRun, successful=tested.wasSuccessful(), failures=len(tested.failures), errors=len(tested.errors), skips=len(tested.skipped))
            save(root, 'audit-controls.json', controls)
            require(controls == dict(tests=10, successful=True, failures=0, errors=0, skips=0), 'Current output audit actual Linux qualification')
            raw = json.dumps({'selectedRoles': selected, 'cachedTags': cached}, sort_keys=True, separators=(',', ':')).encode()
            require(len(raw) <= 8388608, 'Current source input metadata bound')
            packed = gzip.compress(raw, mtime=0)
            require(len(packed) <= 2097152, 'Current source input compressed bound')
            with (root/'source-inputs.json.gz').open('xb') as stream:
                stream.write(packed)
            save(root, 'source-inputs-manifest.json', dict(bytes=len(packed), sha256=hashlib.sha256(packed).hexdigest(), rawBytes=len(raw), rawSha256=hashlib.sha256(raw).hexdigest()))
        engine = SelectedWayTags('/artifacts/selected-way-tags.so', plan['artifact']['sha256'], aggregate_visits=1770542426)
        output = root/'original-way-tags.bin'
        requested = {i: selected[i] for i in sorted(cached)} if operation == 'capture' else selected
        engine.begin(output, sorted(requested), output_bytes=40*1048576)
        phase = time.monotonic()
        try:
            if operation == 'capture':
                from coarse_osm_country_wire_v4 import framed_records
                from coarse_osm_projector_v1 import reference_seal
                from coarse_osm_conditional_census_v1_test import CAPS
                receipt = engine.validate_frames(framed_records(records), SOURCE['state'], CAPS, check=check)
                require(receipt['counts'] == {'way': 1084} and receipt['semanticSha256'] == reference_seal(records), 'All cached source fields/semantic parity')
            else:
                require(operation == 'run', 'Current source operation')
                receipt = engine.scan(Path('/source.pbf'), SOURCE['state'], SCAN, source=SOURCE, check=check)
                require(receipt['counts'] == {'node': 1606229364, 'way': 162688797, 'relation': 1624265}, 'Complete national original source counts')
                require(receipt['semanticSha256'] == SOURCE['semanticSha256'], 'Exact national original semantic seal')
            require(receipt['nativeEof'] and receipt['pythonProjectionFrames'] == 0, 'Source EOF and zero ordinary Python projections')
            counters = engine.finish()
        finally:
            engine.release()
        source_seconds = time.monotonic()-phase
        # Persist completed validator/native receipts before any output interpretation.
        save(root, 'receipt.json', receipt)
        save(root, 'native-counters.json', counters)
        save(root, 'source-complete.json', dict(sourceValidationAndNativeCollectionSeconds=source_seconds, ordinaryPythonProjections=0))
        independent = audit(output, counters, requested, cached, check)
        tags = independent.pop('wayTags')
        raw = (json.dumps(tags, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
        require(len(raw) <= 40*1048576, 'Current raw tag metadata bound')
        packed = gzip.compress(raw, mtime=0)
        require(len(packed) <= 12*1048576, 'Current compressed tag metadata bound')
        with (root/'way-tags.json.gz').open('xb') as stream:
            stream.write(packed)
        artifact = dict(bytes=len(packed), sha256=hashlib.sha256(packed).hexdigest(), rawBytes=len(raw), rawSha256=hashlib.sha256(raw).hexdigest())
        save(root, 'report.json', dict(status='complete_current_way_tags_'+operation, allCurrentSelectedWays=len(selected), cachedOriginalWays=len(cached),
             selectedTags=counters, independentTagAudit=independent, tagArtifact=artifact, allCachedOriginalTagsExact=True,
             sourceValidationAndNativeCollectionSeconds=source_seconds, workerSecondsIncludingBindingsCollectionAndIndependentAudit=time.monotonic()-began,
             sourcePbfScans=int(operation == 'run'), sourceConstructorExecutions=0, routingQueries=0, providerRequests=0, applicationDbReads=0,
             sourcePermissionsOrPricesChanged=False, appActivated=False,
             scope='Original raw tags for every current winner source-way ID, never a selected-place or error subset. Metadata only, no inferred permissions/price change or model query. Captured known originals remain exact; complete full-source guards retain. Current IDs/roles come from all43910audited source arcs. Native/source receipts persist before independent output audit; stable metadata excludes atime but retains identity/size/mtime/ctime and two content hashes. Offline duration includes bindings/source/IO/audit, not routing/cloud time.'))
        check()
        return 0
    except BaseException as error:
        save(root, 'failure.json', dict(status='current_way_tags_stopped', error=repr(error), workerSeconds=time.monotonic()-began))
        raise
    finally:
        save(root, 'metrics.json', resource_metrics())
        if timer.poll() is None:
            timer.terminate()
        timer.wait(timeout=5)


def driver(recipe,pin):
    # Keep the established isolated source driver; change only stage admission and worker.
    import json
    import subprocess
    import uuid
    from prepare_osm_native_lock_v1 import cleanup_owned,settle_error
    from run_osm_country_screen_v1 import isolation
    repo=Path(__file__).resolve().parents[1];recipe=Path(recipe).resolve()
    require(recipe.is_relative_to(repo/'docs/evidence') and sha(recipe)==pin,'Selected-node tags recipe binding')
    plan=json.loads(recipe.read_bytes());operation=plan['operation']
    require(operation in ('capture','run') and plan['output']==PREFIX+operation+'-v1','Selected-node tags exact namespace')
    require(plan['priorReserveBytes']+plan['newClosedAllocationBytes']+plan['metadataScratchReserveBytes']+67108864+268435456<72*1024**3,'Selected-node tags aggregate reservation')
    require(set(plan['inputs'])==set(plan['mounts']),'Complete selected-tag input roster')
    for name,dest in plan['mounts'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and dest.startswith(('/code/','/reference/','/facts/','/inputs/','/artifacts/','/tools/')),'Selected-node tags input scope')
        require(not name.endswith(('.pbf','/001.bin')) and sha(repo/name)==plan['inputs'][name],'Selected-node tags input SHA/no ordinary source mount')
    require(plan['source']==SOURCE and plan['scanCaps']==SCAN,'Unchanged original source/scan guards')
    require(plan['nativeAdmission']=={'tests':35,'successful':True,'failures':0,'errors':0,'skips':0},'Selected-node tags actual native qualification')
    if operation=='run':
        require(plan['capturedAdmission']=={'selectedWays':1084,'allOriginalTagsExact':True,'allCurrentSourceRolesExact':True,'auditControls':10},'Complete captured qualification before source')
        original=repo/SOURCE['path']
        require(original.is_file() and not original.is_symlink() and original.stat().st_size==SOURCE['bytes'],'Exact readonly cached source')
    root=repo/plan['output'];root.mkdir();(root/'execution-plan.json').write_bytes(recipe.read_bytes())
    owner=uuid.uuid4().hex;name='geo-planner-current-way-tags-source-'+owner[:12]
    save(root,'owner.json',{'name':name,'label':owner,'image':IMAGE})
    began=time.monotonic();identity=child=None;code=2
    def call(args):return subprocess.run(args,capture_output=True,text=True,timeout=15)
    try:
        command=['docker','create','--pull=never','--init','--name',name,'--label','geo-planner.stream-owner='+owner,
                 '--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=4g','--memory-swap=4g','--cpus=2','--pids-limit=64',
                 '--tmpfs','/tmp:rw,size=256m','--ulimit','core=0:0','--ulimit','fsize=67108864:67108864','--env','PYTHONPATH=/code:/tools/site:/reference','--env','LD_LIBRARY_PATH=/tools/runtime','--env','OSMIUM_MAX_INPUT_QUEUE_SIZE=2','--env','OSMIUM_MAX_OSMDATA_QUEUE_SIZE=2']
        for source,dest in plan['mounts'].items():command+=['--mount',f'type=bind,src={repo/source},dst={dest},readonly']
        if operation=='run':command+=['--mount',f'type=bind,src={repo/SOURCE["path"]},dst=/source.pbf,readonly']
        command+=['--mount',f'type=bind,src={root},dst=/work','--mount',f'type=bind,src={recipe},dst=/inputs/recipe.json,readonly','--entrypoint=python3',IMAGE,'-B','/code/run_osm_current_way_tags_source_v1.py','/inputs/recipe.json',pin,'--worker']
        created=call(command);require(created.returncode==0,created.stderr);identity=created.stdout.strip();require(len(identity)==64,'Selected-node tags exact owner')
        observed=json.loads(call(['docker','inspect',identity]).stdout)[0];isolation(observed,'controls');save(root,'container-initial.json',observed)
        with (root/'worker.log').open('xb') as log:
            child=subprocess.Popen(['docker','start','-a',identity],stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:
                require(time.monotonic()-began<(240 if operation=='capture' else 3000) and owned_usage(root)['conservativeAllocatedBytes']<=67108864,'Selected-node tags host deadline/allocation')
                time.sleep(.5)
        observed=json.loads(call(['docker','inspect',identity]).stdout)[0];save(root,'container-result.json',{'State':observed['State'],'clientExitCode':child.returncode})
        require(child.returncode==observed['State']['ExitCode']==0 and not observed['State']['OOMKilled'],'Selected-node tags worker exit/OOM');code=0
    except BaseException as error:save(root,'driver-failure.json',{'error':repr(error),'hostSeconds':time.monotonic()-began})
    finally:
        if child and child.poll() is None:child.kill();child.wait(timeout=5)
        if not (root/'container-result.json').exists():settle_error(call,identity,name,owner,root,child.returncode if child else None)
        cleanup_owned(call,identity,name,owner,IMAGE,root)
    save(root,'run-summary.json',{'exitCode':code,'hostSecondsIncludingCleanup':time.monotonic()-began,'sourcePbfScanIntended':operation=='run'})
    return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe')
    parser.add_argument('pin')
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    require(sha(args.recipe) == args.pin, 'Current source recipe SHA')
    raise SystemExit(worker(json.loads(Path(args.recipe).read_bytes())) if args.worker else driver(args.recipe, args.pin))
