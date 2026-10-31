"""Short fixed-sample profile; this module cannot acquire or import national data."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import resource
import statistics
import time
import unittest

from coarse_osm_bulk import Coordinates, Run
from coarse_osm_bulk_pbf import native_records
from coarse_osm_compact_v1 import Index, Storage
from coarse_osm_data import memory_guard, verify_worker_inputs
from coarse_osm_input import absolute_timeout
from coarse_osm_native_smoke import write_xml
from coarse_osm_profile import save
from coarse_osm_records import canonical, strict_json
from coarse_osm_stream_v1 import NativeValidator, native_scan
from coarse_osm_validation_v4 import checked_records
from coarse_timing_input import digest, require, start_watchdog

CAPS = {'hostSeconds': 600, 'hostWorkSeconds': 570, 'workerSeconds': 300, 'caseSeconds': 60,
    'objectsPerCase': 200000, 'totalNativeObjects': 2000000, 'workingBytesIncludingTmp': 1073741824,
    'tmpBytes': 268435456, 'indexBytes': 33554432, 'fileBytes': 67108864, 'reportBytes': 1048576,
    'memoryBytes': 4294967296, 'cpus': 2, 'pids': 64, 'minimumMedianSpeedup': 1.25,
    'maximumSampleIndexFraction': .75, 'forecastTimeMargin': 2., 'forecastStorageMargin': 1.5}
CASES = [('projection', 'projection'), ('fused-validation', 'validation'),
    ('pair-0-v4', 'v4'), ('pair-0-compact', 'compact'), ('pair-1-compact', 'compact'),
    ('pair-1-v4', 'v4'), ('pair-2-v4', 'v4'), ('pair-2-compact', 'compact')]


def benchmark(path, config, folder, mode, account):
    folder.mkdir()
    run = Run(folder, config)
    index = None
    if mode == 'v4':
        index = Coordinates(folder / 'nodes.sqlite', run.caps)
    elif mode == 'compact':
        index = Index(folder / 'nodes', Storage(CAPS['indexBytes'], CAPS['fileBytes']))
    hashed, counts, ids = hashlib.sha256(), Counter(), []
    def consume(raw, line):
        account()
        counts[raw['type']] += 1
        require(sum(counts.values()) <= CAPS['objectsPerCase'], 'Stream per-case callback cap')
        hashed.update(line)
        if raw['type'] == 'node':
            if len(ids) < 1024:
                ids.append(raw['id'])
            if index is not None:
                index.add(raw)
    began = time.monotonic()
    native = None
    lookup_seconds = 0
    lookup_hash = None
    try:
        with absolute_timeout(CAPS['caseSeconds']):
            if mode in ('compact', 'validation'):
                native = NativeValidator(config['source']['proposedPublisherReplicationStateUtc'], run.caps['singleNormalizedElementBytes'], run.caps, consume)
                native_scan(path, native)
            else:
                reader = lambda: native_records(path, run.caps['singleNormalizedElementBytes'])
                rows = reader() if mode == 'projection' else checked_records(reader, run, config['source']['proposedPublisherReplicationStateUtc'], 'v4-prefix')
                for raw in rows:
                    consume(raw, canonical(raw) + b'\n')
            if index is not None:
                index.finish()
            seconds = time.monotonic() - began
            if index is not None:
                lookup_began = time.monotonic()
                points = index.points(list(reversed(ids)) + ids[:128])
                lookup_hash = hashlib.sha256(canonical(points)).hexdigest()
                lookup_seconds = time.monotonic() - lookup_began
    except Exception as error:
        save(folder / 'partial-result.json', {'counts': dict(counts), 'nativeDeliveredCounts': dict(native.counts) if native is not None else None,
            'returnedRecordsSha256': hashed.hexdigest(), 'nativePrefixEof': False, 'indexesTrusted': False,
            'errorType': type(error).__name__, 'error': str(error)[:2000]})
        raise
    finally:
        if index is not None:
            index.close()
    index_bytes = sum(p.stat().st_size for p in folder.rglob('*') if p.is_file() and (p.suffix in ('.bin', '.sqlite') or p.name == 'index.json'))
    result = {'mode': mode, 'indexLoopSeconds': seconds, 'lookupSeconds': lookup_seconds,
        'lookupQueries': len(ids) + min(128, len(ids)) if index is not None else 0,
        'lookupCoordinateSha256': lookup_hash, 'counts': dict(counts), 'projectedSha256': hashed.hexdigest(),
        'indexBytes': index_bytes, 'nativePrefixEof': native.eof if native is not None else True,
        'passes': run.state['passes'], 'scope': 'Fixed node prefix or explicitly re-encoded mixed fixture; not national import throughput.'}
    save(folder / 'result.json', result)
    return result


def mixed_fixture(path, target, account):
    import osmium
    require(path.stat().st_size == 3304488, 'Mixed sample size')
    rows = []
    with path.open('rb') as stream:
        while line := stream.readline(1048578):
            require(line.endswith(b'\n') and len(line) <= 1048577 and len(rows) < 3000, 'Mixed sample record bound')
            rows.append(strict_json(line))
    require(Counter(r['type'] for r in rows) == {'node': 1000, 'way': 1000, 'relation': 1000}, 'Mixed sample counts')
    xml = target.with_suffix('.osm')
    write_xml(xml, rows)
    require(xml.stat().st_size <= CAPS['fileBytes'], 'Re-encoded XML byte cap')
    with osmium.SimpleWriter(str(target), bufsz=65536) as writer:
        for obj in osmium.FileProcessor(str(xml)):
            account()
            writer.add(obj)
    return {'records': len(rows), 'xmlBytes': xml.stat().st_size, 'pbfBytes': target.stat().st_size,
        'pbfSha256': digest(target), 'scope': 'Re-encoded saved real records; not original publisher PBF bytes or dependency-complete ways.'}


def worker(plan, root):
    root = Path(root)
    began = time.monotonic()
    watchdog = start_watchdog(CAPS['workerSeconds'])
    try:
        verify_worker_inputs(plan)
        memory = memory_guard()
        disk = os.statvfs('/tmp')
        require(disk.f_blocks * disk.f_frsize == CAPS['tmpBytes'], 'Stream tmp guard')
        require(resource.getrlimit(resource.RLIMIT_FSIZE) == (CAPS['fileBytes'], CAPS['fileBytes']), 'Stream file guard')
        save(root / 'resource-guards.json', {'memory': memory, 'tmpBytes': CAPS['tmpBytes'], 'fileBytes': CAPS['fileBytes']})
        tests = unittest.defaultTestLoader.loadTestsFromNames(['coarse_osm_stream_v1_test', 'coarse_osm_stream_driver_v1_test', 'coarse_osm_validation_v4_test'])
        controls = unittest.TextTestRunner().run(tests)
        save(root / 'controls.json', {'tests': controls.testsRun, 'successful': controls.wasSuccessful(), 'failures': len(controls.failures), 'errors': len(controls.errors), 'skipped': len(controls.skipped)})
        require(controls.wasSuccessful() and not controls.skipped, 'Stream controls failed')
        config = deepcopy(plan['extractConfig'])
        config['proposedCaps'].update(wallSeconds=CAPS['caseSeconds'], workingBytesIncludingTmp=CAPS['workingBytesIncludingTmp'], tmpBytes=CAPS['tmpBytes'],
            sqliteIndexBytesEach=CAPS['indexBytes'], sqliteMaxPagesEach=CAPS['indexBytes']//4096, sqliteCacheBytesEach=8388608,
            scanNodesPerPass=CAPS['objectsPerCase'], scanWaysPerPass=CAPS['objectsPerCase'], scanRelationsPerPass=CAPS['objectsPerCase'], scanObjectVisitsTotal=CAPS['objectsPerCase'])
        visits = 0
        def account():
            nonlocal visits
            visits += 1
            require(visits <= CAPS['totalNativeObjects'] and time.monotonic() - began < CAPS['workerSeconds'] - 5, 'Stream total visit/time cap')
        cases = []
        for name, mode in CASES:
            cases.append(dict(name=name, **benchmark('/inputs/prefix.pbf', config, root / name, mode, account)))
        fixture = mixed_fixture(Path('/inputs/mixed.jsonl'), root / 'mixed.pbf', account)
        save(root / 'mixed-fixture.json', fixture)
        mixed = [benchmark(root / 'mixed.pbf', config, root / ('mixed-' + mode), mode, account) for mode in ('v4', 'validation')]
        require(all(r['counts'] == {'node': 64000} and r['projectedSha256'] == cases[0]['projectedSha256'] and r['nativePrefixEof'] for r in cases), 'Stream prefix equivalence')
        require(mixed[0]['counts'] == mixed[1]['counts'] == {'node': 1000, 'way': 1000, 'relation': 1000}, 'Stream mixed counts')
        require(mixed[0]['projectedSha256'] == mixed[1]['projectedSha256'] == plan['mixed']['sha256'], 'Re-encoded mixed projection differs')
        indexed = [r for r in cases if r['mode'] in ('v4', 'compact')]
        require(len({r['lookupCoordinateSha256'] for r in indexed}) == 1, 'Stream index coordinate mismatch')
        medians = {mode: statistics.median(r['indexLoopSeconds'] for r in indexed if r['mode'] == mode) for mode in ('v4', 'compact')}
        speedup = medians['v4'] / medians['compact']
        fraction = next(r['indexBytes'] for r in indexed if r['mode'] == 'compact') / next(r['indexBytes'] for r in indexed if r['mode'] == 'v4')
        passed = speedup >= CAPS['minimumMedianSpeedup'] and fraction <= CAPS['maximumSampleIndexFraction']
        save(root / 'result.json', {'status': 'passed_sample_screen' if passed else 'equivalent_but_sample_gate_failed',
            'cases': cases, 'mixed': mixed, 'equivalentSamplesAndCoordinates': True, 'medianIndexSeconds': medians,
            'medianSpeedup': speedup, 'indexByteFraction': fraction, 'sampleGatesPassed': passed,
            'nativeObjectVisits': visits, 'workerSecondsBeforeSummary': time.monotonic() - began,
            'observedProcessMaxRssKiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'wholeSourceEof': False, 'wholeExtractionQualified': False, 'modelChanged': False, 'networkRequests': 0})
        return 0 if passed else 2
    except Exception as error:
        save(root / 'failure.json', {'status': 'stopped', 'errorType': type(error).__name__, 'error': str(error)[:2000],
            'wholeExtractionQualified': False, 'modelChanged': False})
        return 2
    finally:
        if watchdog.poll() is None:
            watchdog.terminate()
        watchdog.wait(timeout=5)
