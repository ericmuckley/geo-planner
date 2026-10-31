"""Regression for rejected reference receipts; V1 remains frozen unchanged."""
import json
from pathlib import Path
import unittest

import coarse_osm_projector_v1_test as prior
from coarse_osm_native_smoke import fixture_records
from coarse_osm_sample_v1 import run_case as old_case,Visits as OldVisits
from coarse_osm_sample_v2 import run_case,Visits
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    setUp=prior.Tests.setUp
    directory=prior.Tests.directory
    pbf=prior.Tests.pbf
    engine=prior.Tests.engine

    def test_budget_preserves_over_limit_receipt_sentinel(self):
        budget=Visits(1);budget.add()
        with self.assertRaises(PilotError):budget.add()
        self.assertEqual(budget.total,2)

    def test_rejected_object_and_quota_receipts_match_both_paths(self):
        engine=self.engine();row=dict(fixture_records()[0],version=0);path=self.pbf([row])
        folder=self.directory()/'old';old_budget=OldVisits()
        with self.assertRaises(PilotError):old_case(path,self.config,folder,engine=engine,budget=old_budget,mode='python')
        self.assertEqual(json.loads((folder/'partial-result.json').read_text())['counts'],{})
        self.assertEqual(old_budget.total,0)
        for mode in ('python','native'):
            folder=self.directory()/'fixed';budget=Visits()
            with self.assertRaises(PilotError):run_case(path,self.config,folder,engine=engine,budget=budget,mode=mode)
            state=json.loads((folder/'partial-result.json').read_text())
            self.assertEqual(state['counts'],{'node':1});self.assertEqual(budget.total,1)
            self.assertFalse(state['eof']);self.assertFalse(state['indexesTrusted'])
        path=self.pbf(fixture_records()[:4])
        for mode in ('python','native'):
            folder=self.directory()/'quota';budget=Visits(1)
            with self.assertRaises(PilotError):run_case(path,self.config,folder,engine=engine,budget=budget,mode=mode)
            state=json.loads((folder/'partial-result.json').read_text())
            self.assertEqual(state['counts'],{'node':2});self.assertEqual(budget.total,2)
            self.assertFalse(state['eof'])

    def test_valid_pairs_keep_exact_source_io_fields_and_lookup_bits(self):
        engine=self.engine();path=self.pbf(fixture_records()[:4]);budget=Visits();results=[]
        for mode in ('python','native'):
            folder=self.directory()/'pair'
            results.append(run_case(path,self.config,folder,engine=engine,budget=budget,mode=mode,proof=True,queries=[4,1,1]))
        self.assertEqual(budget.total,8)
        for key in ('counts','canonicalSha256','semanticSha256','indexManifestSha256','indexBytes','coordinateRowsProved'):
            self.assertEqual(results[0][key],results[1][key],key)
        self.assertEqual({r['coordinateBitsSha256'] for p in results for r in p['lookup']},{results[0]['lookup'][0]['coordinateBitsSha256']})
        self.assertTrue(all(p['knownGuardReadBytes']==2*path.stat().st_size for p in results))


if __name__=='__main__':unittest.main()
