import unittest
from coarse_osm_source_gap_way_causes_v1 import way_cause
from coarse_timing_input import PilotError


def row(eligible=False,closed=False):return {'sourceWay':10,'storedSourceFlags':1280,'baseEligible':eligible,'finalFallbackClosed':closed}


class Tests(unittest.TestCase):
    def test_missing_raw_way_never_infers_a_current_reason(self):
        got=way_cause(row(),None)
        self.assertFalse(got['rawWayKnown']);self.assertIsNone(got['currentRawPolicy'])

    def test_stored_old_reason_is_not_current_raw_rejection_and_closure_stays_separate(self):
        tags={'highway':'primary','motor_vehicle:lanes':'|yes','lanes':'2','oneway':'yes'}
        got=way_cause(row(),{'type':'way','id':10,'tags':tags})
        self.assertEqual(got['storedSourceFlags']>>8,5)
        self.assertEqual(got['currentRawPolicy']['reason'],'lane-access')
        got=way_cause(row(True,True),{'type':'way','id':10,'tags':{'highway':'primary'}})
        self.assertTrue(got['finalFallbackClosed']);self.assertIsNone(got['currentRawPolicy']['reason'])

    def test_forged_identity_or_eligibility_rejected(self):
        for raw in ({'type':'way','id':11,'tags':{}},{'type':'way','id':10,'tags':{'highway':'primary'}}):
            with self.assertRaises(PilotError):way_cause(row(),raw)
