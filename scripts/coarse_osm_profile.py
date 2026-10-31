"""Bounded offline PBF-prefix profiling. No source acquisition or model output."""
from collections import Counter
from copy import deepcopy
import cProfile
import hashlib
import math
import os
from pathlib import Path
import pstats
import resource
import statistics
import struct
import time
import unittest

from coarse_osm_bulk import Coordinates, Run, checked_records as reference
from coarse_osm_bulk_pbf import framing, singular, stat_key, native_records
from coarse_osm_data import memory_guard, verify_worker_inputs
from coarse_osm_input import absolute_timeout
from coarse_osm_records import canonical
from coarse_osm_validation_v4 import checked_records as candidate
from coarse_timing_input import digest, json_bytes, require, start_watchdog


CAPS = {'hostSeconds': 600, 'hostWorkSeconds': 570, 'workerSeconds': 300, 'caseSeconds': 60,
    'sourcePrefixBytes': 2097152, 'sampleFrames': 9, 'objectsPerCase': 200000, 'totalNativeObjects': 2000000,
    'workingBytesIncludingTmp': 1073741824, 'tmpBytes': 268435456, 'sqliteIndexBytesEach': 33554432,
    'sqliteCacheBytesEach': 8388608, 'fileBytes': 67108864, 'reportBytes': 1048576,
    'memoryBytes': 4294967296, 'cpus': 2, 'pids': 64, 'minimumMedianSpeedup': 1.25}
CASES = [('projection', 'projection', 'reference', True), ('validation', 'validation', 'reference', True),
    ('reference-profile', 'index', 'reference', True), ('candidate-profile', 'index', 'candidate', True),
    ('pair-0-reference', 'index', 'reference', False), ('pair-0-candidate', 'index', 'candidate', False),
    ('pair-1-candidate', 'index', 'candidate', False), ('pair-1-reference', 'index', 'reference', False),
    ('pair-2-reference', 'index', 'reference', False), ('pair-2-candidate', 'index', 'candidate', False)]


def save(path, value):
    raw = json_bytes(value)
    require(len(raw) <= CAPS['reportBytes'] and not path.exists(), 'Profile report cap/reuse')
    path.write_bytes(raw)


def copy_prefix(source, target, *, frames=9, byte_limit=2097152):
    before = stat_key(source)
    total = 0
    with Path(source).open('rb') as stream, Path(target).open('xb') as output:
        for number in range(frames):
            require(total + 4 <= byte_limit, 'Profile source-read byte cap')
            prefix = stream.read(4); total += len(prefix)
            require(len(prefix) == 4, 'Truncated profile frame length')
            size = struct.unpack('!I', prefix)[0]
            require(0 < size < 65536 and total + size <= byte_limit, 'Profile frame header bound')
            raw = stream.read(size); total += len(raw)
            require(len(raw) == size, 'Truncated profile frame header')
            header = singular(raw)
            require(header.get(1) == (2, b'OSMHeader' if number == 0 else b'OSMData') and header.get(3, (None,))[0] == 0, 'Profile frame type/order')
            length = header[3][1]
            require(0 < length and total + length <= byte_limit, 'Profile source-read byte cap')
            blob = stream.read(length); total += len(blob)
            require(len(blob) == length, 'Truncated profile frame blob')
            output.write(prefix + raw + blob)
    require(before == stat_key(source), 'Profile source changed')
    return {'sourcePrefixBytesRead': total, 'sampleBytes': Path(target).stat().st_size,
        'frames': frames, 'sampleSha256': digest(target), 'wholePublisherFileEof': False}


def profile_rows(profiler):
    stats = pstats.Stats(profiler)
    rows = [{'file': name, 'line': line, 'function': function, 'calls': values[1],
        'selfSeconds': values[2], 'cumulativeSeconds': values[3]}
        for (name, line, function), values in stats.stats.items()]
    return {'instrumentedTotalSeconds': stats.total_tt,
        'topCumulative': sorted(rows, key=lambda r: r['cumulativeSeconds'], reverse=True)[:40],
        'topSelf': sorted(rows, key=lambda r: r['selfSeconds'], reverse=True)[:30]}


def benchmark(sample, config, folder, case, account):
    name, mode, implementation, profiled = case
    folder.mkdir()
    run = Run(folder, config)
    index = Coordinates(folder / 'nodes.sqlite', run.caps) if mode == 'index' else None
    output_hash = hashlib.sha256()
    counts = Counter()
    def reader():
        for raw in native_records(sample, config['proposedCaps']['singleNormalizedElementBytes']):
            account()
            yield raw
    def work():
        rows = reader() if mode == 'projection' else (candidate if implementation == 'candidate' else reference)(
            reader, run, config['source']['proposedPublisherReplicationStateUtc'], 'profile-index')
        for raw in rows:
            counts[raw['type']] += 1
            require(sum(counts.values()) <= CAPS['objectsPerCase'], 'Profile per-case object cap')
            output_hash.update(canonical(raw) + b'\n')
            if index is not None and raw['type'] == 'node':
                index.add(raw)
        if index is not None:
            index.finish()
    profiler = cProfile.Profile() if profiled else None
    began = time.monotonic()
    try:
        with absolute_timeout(CAPS['caseSeconds']):
            if profiler is None:
                work()
            else:
                profiler.runcall(work)
    finally:
        if index is not None:
            index.close()
    elapsed = time.monotonic() - began
    result = {'name': name, 'mode': mode, 'implementation': implementation, 'profiled': profiled,
        'secondsIncludingProjectionValidationHashAndIndexAsApplicable': elapsed, 'counts': dict(counts),
        'projectedRecordsSha256': output_hash.hexdigest(), 'passes': run.state['passes'],
        'indexBytes': (folder / 'nodes.sqlite').stat().st_size if index is not None else 0,
        'indexSha256': digest(folder / 'nodes.sqlite') if index is not None else None,
        'scope': 'Complete deterministic prefix only, not whole-source EOF, extraction, routing latency or national throughput.'}
    if profiler is not None:
        save(folder / 'profile.json', profile_rows(profiler))
    save(folder / 'result.json', result)
    return result


def reconcile(cases):
    require(len(cases) == len(CASES) and [r['name'] for r in cases] == [c[0] for c in CASES], 'Profile fixed case sequence')
    require(all((row['mode'], row['implementation'], row['profiled']) == case[1:] for row, case in zip(cases, CASES)), 'Profile fixed case semantics')
    require(sum(cases[0]['counts'].values()) > 0, 'Empty profile sample')
    require(all(r['counts'] == cases[0]['counts'] and r['projectedRecordsSha256'] == cases[0]['projectedRecordsSha256'] for r in cases), 'Profile projected output/count drift')
    indexes = [r for r in cases if r['mode'] == 'index']
    require(all(r['indexSha256'] == indexes[0]['indexSha256'] and r['indexBytes'] == indexes[0]['indexBytes'] for r in indexes), 'Profile coordinate index drift')
    require(all(len(r['passes']) == 1 and r['passes'][0]['status'] == 'eof' and r['passes'][0]['counts'] == r['counts'] for r in cases if r['mode'] != 'projection'), 'Profile prefix stream EOF/counters')
    times = {kind: [r['secondsIncludingProjectionValidationHashAndIndexAsApplicable'] for r in cases if r['implementation'] == kind and not r['profiled']] for kind in ('reference', 'candidate')}
    require(all(len(v) == 3 and all(math.isfinite(t) and t > 0 for t in v) for v in times.values()), 'Profile paired timing roster')
    medians = {kind: statistics.median(values) for kind, values in times.items()}
    ratio = medians['reference'] / medians['candidate']
    return {'equivalentPrefixRecordsAndIndexes': True, 'medianIndexSeconds': medians, 'medianSpeedup': ratio,
        'minimumMedianSpeedup': CAPS['minimumMedianSpeedup'], 'performanceGatePassed': ratio >= CAPS['minimumMedianSpeedup']}


def worker(plan, root):
    root = Path(root)
    began = time.monotonic()
    watchdog = start_watchdog(CAPS['workerSeconds'])
    try:
        verify_worker_inputs(plan)
        memory = memory_guard()
        disk = os.statvfs('/tmp')
        require(disk.f_blocks * disk.f_frsize == CAPS['tmpBytes'], 'Profile tmp guard')
        require(resource.getrlimit(resource.RLIMIT_FSIZE) == (CAPS['fileBytes'], CAPS['fileBytes']), 'Profile file guard')
        save(root / 'resource-guards.json', {'memory': memory, 'tmpBytes': disk.f_blocks * disk.f_frsize,
            'fileBytes': resource.getrlimit(resource.RLIMIT_FSIZE)[0], 'workerSeconds': CAPS['workerSeconds']})
        suite = unittest.defaultTestLoader.loadTestsFromNames(['coarse_osm_validation_v4_test', 'coarse_osm_profile_test', 'coarse_osm_profile_driver_test'])
        controls = unittest.TextTestRunner(verbosity=1).run(suite)
        save(root / 'controls.json', {'tests': controls.testsRun, 'successful': controls.wasSuccessful(), 'failures': len(controls.failures), 'errors': len(controls.errors)})
        require(controls.wasSuccessful(), 'Profile synthetic controls failed')
        sample = root / 'prefix.osm.pbf'
        identity = copy_prefix('/inputs/source.pbf', sample, frames=CAPS['sampleFrames'], byte_limit=CAPS['sourcePrefixBytes'])
        framed = framing(sample, plan['extractConfig']['proposedCaps'], plan['source']['publisherStateUtc'])
        require(framed['frames'] == CAPS['sampleFrames'] and framed['sourceSha256'] == identity['sampleSha256'], 'Profile copied-prefix framing drift')
        save(root / 'sample.json', {**identity, 'framing': framed, 'sourceBytes': plan['source']['bytes'], 'sourceSha256': plan['source']['sha256'], 'scope': 'Leading complete frames; publisher file is larger and no whole-source EOF is claimed.'})
        config = deepcopy(plan['extractConfig']); caps = config['proposedCaps']
        caps.update(wallSeconds=CAPS['caseSeconds'], workingBytesIncludingTmp=CAPS['workingBytesIncludingTmp'], tmpBytes=CAPS['tmpBytes'],
            sqliteIndexBytesEach=CAPS['sqliteIndexBytesEach'], sqliteMaxPagesEach=CAPS['sqliteIndexBytesEach']//caps['sqlitePageBytes'], sqliteCacheBytesEach=CAPS['sqliteCacheBytesEach'],
            scanNodesPerPass=CAPS['objectsPerCase'], scanWaysPerPass=CAPS['objectsPerCase'], scanRelationsPerPass=CAPS['objectsPerCase'], scanObjectVisitsTotal=CAPS['objectsPerCase'])
        visits = 0
        def account():
            nonlocal visits
            visits += 1
            require(visits <= CAPS['totalNativeObjects'] and time.monotonic() - began < CAPS['workerSeconds'] - 5, 'Profile aggregate object/time cap')
        cases = []
        for case in CASES:
            cases.append(benchmark(sample, config, root / case[0], case, account))
        result = reconcile(cases)
        save(root / 'result.json', {**result, 'status': 'passed_bounded_profile' if result['performanceGatePassed'] else 'equivalent_but_performance_gate_failed',
            'cases': cases, 'nativeObjectVisits': visits, 'workerSecondsBeforeSummary': time.monotonic() - began,
            'observedProcessMaxRssKiB': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'wholeSourceEof': False, 'wholeExtractionQualified': False, 'sourceFeasibilityQualified': False,
            'usableAttributesQualified': False, 'modelChanged': False, 'networkRequests': 0})
        return 0 if result['performanceGatePassed'] else 2
    except Exception as error:
        save(root / 'failure.json', {'status': 'stopped', 'errorType': type(error).__name__, 'error': str(error)[:2000],
            'wholeSourceEof': False, 'wholeExtractionQualified': False, 'partialIndexesTrusted': False,
            'windows': [{'id': w['id'], 'status': 'unqualified_diagnostic_only'} for w in plan['extractConfig']['windows']]})
        return 2
    finally:
        if watchdog.poll() is None:
            watchdog.terminate()
        watchdog.wait(timeout=5)
