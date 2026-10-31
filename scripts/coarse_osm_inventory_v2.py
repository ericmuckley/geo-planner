"""Inventory-only row-budget revision; original full-import limits remain held."""
from copy import deepcopy
import os
from pathlib import Path
import resource
import time
import unittest

from coarse_osm_inventory import CAPS as ORIGINAL_CAPS, KINDS, project, scan, compare_sample, decision
from coarse_osm_data import memory_guard, verify_worker_inputs
from coarse_osm_bulk_pbf import framing
from coarse_osm_profile import copy_prefix, save
from coarse_timing_input import require, start_watchdog

CAPS = dict(ORIGINAL_CAPS, nodeLimit=1500000000, visitLimit=1610000000)


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
        suite = unittest.defaultTestLoader.loadTestsFromNames(['coarse_osm_inventory_test','coarse_osm_inventory_driver_v2_test','coarse_osm_validation_v4_test'])
        controls = unittest.TextTestRunner(verbosity=1).run(suite)
        save(root/'controls.json',{'tests':controls.testsRun,'successful':controls.wasSuccessful(),'failures':len(controls.failures),'errors':len(controls.errors),'skipped':len(controls.skipped)})
        require(controls.wasSuccessful() and not controls.skipped, 'Inventory Linux controls')
        header = root/'header.osm.pbf'
        copied = copy_prefix('/inputs/source.pbf',header,frames=1,byte_limit=CAPS['headerBytes'])
        identity = framing(header,plan['extractConfig']['proposedCaps'],plan['source']['publisherStateUtc'])
        save(root/'header.json',{'prefix':copied,'identity':identity,'scope':'Header only, against the already hash-bound complete source.'})
        inventory = scan('/inputs/source.pbf',root/'scan',caps=CAPS)
        samples = compare_sample(root/'scan/samples.jsonl',inventory,plan['extractConfig'],root)
        selected = decision(inventory,samples,plan['forecastInputs'])
        selected['originalFullImportRowCeilings'] = dict(zip(KINDS,[ORIGINAL_CAPS[k+'Limit'] for k in KINDS]))
        selected['originalFullImportRowCeilingsExceeded'] = any(inventory['counts'][k] > ORIGINAL_CAPS[k+'Limit'] for k in KINDS)
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
