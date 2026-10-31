"""Bounded native inventory and fixed mixed-type samples, without a location index."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import resource
import time
import unittest

from coarse_osm_bulk import Run, checked_records as reference
from coarse_osm_bulk_pbf import framing, stat_key
from coarse_osm_data import memory_guard, verify_worker_inputs
from coarse_osm_input import absolute_timeout
from coarse_osm_profile import copy_prefix, save
from coarse_osm_records import canonical, strict_json, utc
from coarse_osm_validation_v4 import checked_records as candidate
from coarse_timing_input import PilotError, digest, json_bytes, require, start_watchdog


KINDS = ('node', 'way', 'relation')
CAPS = {'hostSeconds':1800, 'hostWorkSeconds':1770, 'workerSeconds':1500, 'countSeconds':1200,
    'samplePerKind':1000, 'sampleBytes':16777216, 'elementBytes':1048576, 'headerBytes':1048576,
    'nodeLimit':1000000000, 'wayLimit':100000000, 'relationLimit':10000000, 'visitLimit':1110000000,
    'checkpointEvery':1048576, 'validationSeconds':60, 'workingBytesIncludingTmp':1073741824,
    'tmpBytes':268435456, 'fileBytes':67108864, 'reportBytes':1048576,
    'memoryBytes':4294967296, 'cpus':2, 'pids':64, 'forecastTimeMargin':2.0, 'forecastStorageMargin':1.5}


def project(obj, limit):
    """Copy the frozen projector's fields while the native view is valid."""
    stamp = obj.timestamp
    require(stamp.microsecond == 0 and stamp.utcoffset() is not None and stamp.utcoffset().total_seconds() == 0, 'Unsupported native timestamp precision/zone')
    raw = {'type': {'n':'node','w':'way','r':'relation'}[obj.type_str()], 'id':int(obj.id),
        'version':int(obj.version), 'timestamp':obj.timestamp.strftime('%Y-%m-%dT%H:%M:%SZ'), 'visible':bool(obj.visible)}
    charged = 256
    tags = {}
    for tag in obj.tags:
        charged += len(tag.k.encode()) + len(tag.v.encode()) + 64
        require(charged <= limit, 'Native view tag-copy bound')
        require(str(tag.k) not in tags, 'Duplicate native tag key')
        tags[str(tag.k)] = str(tag.v)
    raw['tags'] = tags
    if raw['type'] == 'node':
        raw.update(lon=float(obj.location.lon), lat=float(obj.location.lat))
    elif raw['type'] == 'way':
        refs = []
        for node in obj.nodes:
            charged += 32
            require(charged <= limit, 'Native view reference-copy bound')
            refs.append(int(node.ref))
        raw['nodes'] = refs
    else:
        members = []
        for member in obj.members:
            charged += len(member.role.encode()) + 128
            require(charged <= limit, 'Native view member-copy bound')
            members.append({'type':{'n':'node','w':'way','r':'relation'}[member.type], 'ref':int(member.ref), 'role':str(member.role)})
        raw['members'] = members
    require(len(canonical(raw)) <= limit, 'Native copied-record bound')
    utc(raw['timestamp'])
    return raw


class Inventory:
    def __init__(self, root, caps=CAPS, *, clock=time.monotonic, projector=project):
        self.root = Path(root)
        self.caps = caps
        self.clock = clock
        self.projector = projector
        self.started = clock()
        self.counts = [0,0,0]
        self.samples = [0,0,0]
        self.visits = self.sample_bytes = 0
        self.sample_hash = hashlib.sha256()
        self.limits = [caps[k+'Limit'] for k in KINDS]
        self.stream = None
        self.eof = False
        self.error = None

    def state(self):
        return {'status':'native_eof' if self.eof else ('stopped' if self.error else 'running'),
            'counts':dict(zip(KINDS,self.counts)), 'nativeCallbackVisits':self.visits,
            'sampleCounts':dict(zip(KINDS,self.samples)), 'sampleBytes':self.sample_bytes,
            'sampleSha256':self.sample_hash.hexdigest(), 'wholeSourceNativeEof':self.eof,
            'elapsedCountSeconds':self.clock()-self.started, 'error':self.error,
            'sourceMetadataValidatedGlobally':False, 'scope':'Counts are delivered node/way/relation callbacks. Only fixed samples are projected; decoder failures may leave unknown raw-object counts.'}

    def checkpoint(self):
        raw = json_bytes(self.state())
        require(len(raw) <= self.caps['reportBytes'], 'Inventory state byte cap')
        path = self.root/'inventory-state.json.partial'
        require(not path.is_symlink(), 'Inventory state symlink')
        path.write_bytes(raw)
        path.replace(self.root/'inventory-state.json')

    def see(self, kind, obj):
        self.counts[kind] += 1
        self.visits += 1
        if self.counts[kind] > self.limits[kind] or self.visits > self.caps['visitLimit']:
            raise PilotError('Inventory native object cap')
        # Unsampled objects are count-only: no metadata/tag/coordinate copies.
        if self.counts[kind] <= self.caps['samplePerKind']:
            raw = self.projector(obj, self.caps['elementBytes'])
            require(raw['type'] == KINDS[kind], 'Inventory callback/projector type drift')
            line = canonical(raw)+b'\n'
            require(len(line) <= self.caps['elementBytes']+1 and self.sample_bytes+len(line) <= self.caps['sampleBytes'], 'Inventory sample byte cap')
            self.stream.write(line)
            self.stream.flush()
            self.sample_hash.update(line)
            self.sample_bytes += len(line)
            self.samples[kind] += 1
        if self.counts[kind] == 1 or self.visits % self.caps['checkpointEvery'] == 0:
            require(self.clock()-self.started < self.caps['countSeconds'], 'Inventory count deadline')
            self.checkpoint()


def native_apply(path, inventory):
    import osmium
    class Handler(osmium.SimpleHandler):
        def node(self, obj): inventory.see(0,obj)
        def way(self, obj): inventory.see(1,obj)
        def relation(self, obj): inventory.see(2,obj)
    Handler().apply_file(str(path), locations=False)


def scan(source, root, caps=CAPS, *, apply=native_apply, projector=project, clock=time.monotonic):
    root = Path(root)
    root.mkdir()
    inventory = Inventory(root,caps,clock=clock,projector=projector)
    before = stat_key(source)
    inventory.checkpoint()
    try:
        with (root/'samples.jsonl').open('xb') as stream:
            inventory.stream = stream
            with absolute_timeout(caps['countSeconds']):
                apply(source,inventory)
            require(before == stat_key(source), 'Inventory source changed')
            require(sum(inventory.counts) == inventory.visits, 'Inventory count sum drift')
            require(inventory.samples == [min(c,caps['samplePerKind']) for c in inventory.counts], 'Inventory fixed sample count drift')
        inventory.eof = True
    except Exception as error:
        inventory.error = {'type':type(error).__name__,'message':str(error)[:2000]}
    inventory.checkpoint()
    result = inventory.state()
    save(root/'inventory-result.json',result)
    return result


def compare_sample(path, inventory, config, root):
    require(path.stat().st_size == inventory['sampleBytes'] and digest(path) == inventory['sampleSha256'], 'Inventory sample identity drift')
    results = {}
    for name,implementation in (('reference',reference),('candidate',candidate)):
        folder = root/('validation-'+name)
        folder.mkdir()
        proposal = deepcopy(config)
        proposal['proposedCaps'].update(wallSeconds=CAPS['validationSeconds'],scanNodesPerPass=CAPS['samplePerKind'],
            scanWaysPerPass=CAPS['samplePerKind'],scanRelationsPerPass=CAPS['samplePerKind'],scanObjectVisitsTotal=3*CAPS['samplePerKind'])
        run = Run(folder,proposal)
        output = hashlib.sha256()
        returned = 0
        loaded = dict.fromkeys(KINDS,0)
        def reader():
            with path.open('rb') as stream:
                while line := stream.readline(CAPS['elementBytes']+2):
                    require(line.endswith(b'\n') and len(line) <= CAPS['elementBytes']+1, 'Inventory sample line cap/prefix')
                    raw = strict_json(line)
                    require(raw['type'] in loaded, 'Inventory sample kind')
                    loaded[raw['type']] += 1
                    yield raw
        began = time.monotonic()
        error = None
        try:
            with absolute_timeout(CAPS['validationSeconds']):
                for raw in implementation(reader,run,config['source']['proposedPublisherReplicationStateUtc'],'mixed-sample'):
                    output.update(canonical(raw)+b'\n')
                    returned += 1
            require(loaded == inventory['sampleCounts'], 'Inventory sampled-type count drift')
        except Exception as failure:
            error = {'type':type(failure).__name__,'message':str(failure)[:2000]}
        results[name] = {'accepted':error is None,'error':error,'returnedRecords':returned,'returnedSha256':output.hexdigest(),
            'loadedCounts':loaded,'passes':run.state['passes'],'visits':run.state['scanObjectVisits'],
            'secondsIncludingJsonReplayValidationHash':time.monotonic()-began}
        save(folder/'result.json',results[name])
    keys = ('accepted','returnedRecords','returnedSha256','loadedCounts','passes','visits')
    equivalent = all(results['reference'][k] == results['candidate'][k] for k in keys)
    result = {'equivalent':equivalent,'allSampleRecordsAccepted':all(r['accepted'] for r in results.values()),
        'sampleCounts':inventory['sampleCounts'],'cases':results,'wholeSourceMetadataValidation':False,
        'scope':'First fixed objects per type, replayed as JSON; no real spatial selection, dependency closure, index, source-wide metadata validation or national timing claim.'}
    save(root/'sample-comparison.json',result)
    return result


def decision(inventory, samples, forecast):
    if not inventory['wholeSourceNativeEof']:
        return {'decision':'hold_incomplete_inventory','wholeExtractionAdmitted':False,'countsComplete':False}
    if not samples['equivalent']:
        return {'decision':'reject_validator_equivalence','wholeExtractionAdmitted':False,'countsComplete':True}
    nodes = inventory['counts']['node']
    seconds = 2*nodes*forecast['candidateNodeIndexMedianSeconds']/forecast['nodeSampleCount']
    index_bytes = nodes*forecast['sampleIndexBytes']/forecast['nodeSampleCount']
    margined_index = index_bytes*CAPS['forecastStorageMargin']
    working = forecast['otherOriginalWorkingBytes']+2*margined_index
    reasons = []
    if not samples['allSampleRecordsAccepted']: reasons.append('reference_and_prototype_reject_fixed_sample')
    if seconds > forecast['workSeconds'] or seconds*CAPS['forecastTimeMargin'] > forecast['workSeconds']: reasons.append('node_index_time_screen')
    if margined_index > forecast['sqliteIndexBytesEach'] or working > forecast['workingBytes']: reasons.append('coordinate_index_storage_screen')
    follow_up = 'Prototype fused native metadata validation and batched coordinate writes, preserving exact sample projection/guards, typed identity, generic selection and independent auditing; screen again before full extraction.'
    if not samples['allSampleRecordsAccepted']:
        follow_up = 'Resolve the preserved fixed-sample compatibility rejection in a separately versioned policy before importer optimization; no resampling or silent validation weakening.'
    return {'decision':'reject_current_all_node_four_pass_strategy' if reasons else 'hold_until_versioned_full_import_controls',
        'wholeExtractionAdmitted':False,'countsComplete':True,'reasons':reasons,
        'forecast':{'optimisticTwoNodeIndexSeconds':seconds,'timeMargin':CAPS['forecastTimeMargin'],
            'marginedTwoNodeIndexSeconds':seconds*CAPS['forecastTimeMargin'],'indexBytesEachBeforeMargin':index_bytes,
            'storageMargin':CAPS['forecastStorageMargin'],'marginedIndexBytesEach':margined_index,'marginedWorkingBytes':working,
            'scope':'Extrapolation from the frozen 64,000-node prefix; excludes remaining passes, way/relation work, framing/final checks. Not measured national import time, a physical storage bound or an accuracy result.'},
        'followUp':follow_up}


def worker(plan,root):
    root = Path(root)
    began = time.monotonic()
    watchdog = start_watchdog(CAPS['workerSeconds'])
    try:
        verify_worker_inputs(plan)
        memory = memory_guard()
        tmp = os.statvfs('/tmp')
        require(tmp.f_blocks*tmp.f_frsize == CAPS['tmpBytes'], 'Inventory tmp guard')
        require(resource.getrlimit(resource.RLIMIT_FSIZE) == (CAPS['fileBytes'],CAPS['fileBytes']), 'Inventory file guard')
        save(root/'resource-guards.json',{'memory':memory,'tmpBytes':tmp.f_blocks*tmp.f_frsize,'fileBytes':CAPS['fileBytes'],'workerSeconds':CAPS['workerSeconds']})
        suite = unittest.defaultTestLoader.loadTestsFromNames(['coarse_osm_inventory_test','coarse_osm_inventory_driver_test','coarse_osm_validation_v4_test'])
        controls = unittest.TextTestRunner(verbosity=1).run(suite)
        save(root/'controls.json',{'tests':controls.testsRun,'successful':controls.wasSuccessful(),'failures':len(controls.failures),'errors':len(controls.errors),'skipped':len(controls.skipped)})
        require(controls.wasSuccessful() and not controls.skipped, 'Inventory Linux controls')
        header = root/'header.osm.pbf'
        copied = copy_prefix('/inputs/source.pbf',header,frames=1,byte_limit=CAPS['headerBytes'])
        identity = framing(header,plan['extractConfig']['proposedCaps'],plan['source']['publisherStateUtc'])
        save(root/'header.json',{'prefix':copied,'identity':identity,'scope':'Header only, against the already hash-bound complete source.'})
        inventory = scan('/inputs/source.pbf',root/'scan')
        samples = compare_sample(root/'scan/samples.jsonl',inventory,plan['extractConfig'],root)
        selected = decision(inventory,samples,plan['forecastInputs'])
        passed = inventory['wholeSourceNativeEof'] and samples['equivalent']
        save(root/'result.json',{'status':'completed_inventory_screen' if passed else 'stopped_or_equivalence_failed',
            'inventory':inventory,'sampleComparison':samples,'importerDecision':selected,
            'workerSecondsBeforeSummary':time.monotonic()-began,'observedProcessMaxRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'networkRequests':0,'wholeExtractionQualified':False,'sourceFeasibilityQualified':False,'publisherBoundaryQualified':False,
            'usableAttributesQualified':False,'modelChanged':False,'windows':[{'id':w['id'],'status':'unqualified_inventory_only'} for w in plan['extractConfig']['windows']]})
        return 0 if passed else 2
    except Exception as error:
        save(root/'failure.json',{'status':'stopped','errorType':type(error).__name__,'error':str(error)[:2000],
            'wholeExtractionQualified':False,'partialCountersMayBeUnfinalized':True})
        return 2
    finally:
        if watchdog.poll() is None: watchdog.terminate()
        watchdog.wait(timeout=5)
