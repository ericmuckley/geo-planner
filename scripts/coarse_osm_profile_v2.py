"""V2 worker changes only the portable fake-host control suite; profiling is shared."""
from copy import deepcopy
import os
from pathlib import Path
import resource
import time
import unittest

from coarse_osm_profile import CAPS, CASES, copy_prefix, benchmark, reconcile, save
from coarse_osm_data import memory_guard, verify_worker_inputs
from coarse_osm_bulk_pbf import framing
from coarse_timing_input import require, start_watchdog


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
        suite = unittest.defaultTestLoader.loadTestsFromNames(['coarse_osm_validation_v4_test', 'coarse_osm_profile_test', 'coarse_osm_profile_driver_v2_test'])
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
