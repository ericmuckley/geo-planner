import unittest

from coarse_osm_current_way_exclusions_v1 import classify_inventory, reconcile_closures


def row(identity, reason=None, old_closed=True):
    return dict(sourceWay=identity,rawWayKnown=True,rawTags={'highway':'primary'},currentRawPolicy={'reason':reason},
                baseEligible=reason is None,finalFallbackClosed=old_closed,laneStatus='unchanged')


class Tests(unittest.TestCase):
    def test_shared_independent_closure_stays(self):
        self.assertEqual(reconcile_closures({'1':[10,20],'2':[10]}, {10}, {1}), {'1':[20]})
    def test_extra_missing_or_malformed_current_union_rejected(self):
        for current in ({1,2},set()):
            with self.assertRaises(AssertionError):reconcile_closures({'1':[10,20],'2':[10]},{10},current)
        with self.assertRaises(AssertionError):reconcile_closures({'1':[20,10]},{10},{1})
    def test_base_access_and_relation_fallback_both_preserved(self):
        evidence={'1':row(1,'access',False),'2':row(2),'3':row(3)}
        result,counts,reasons,_=classify_inventory(evidence,{1,2},{'1':[10],'2':[10]},{10:dict(closureKind='constant-conditional',closedWays=['1','2'])})
        self.assertTrue(result['1']['currentExcluded']);self.assertTrue(result['1']['currentFallbackClosed'])
        self.assertFalse(result['3']['currentExcluded'])
        self.assertEqual(counts,{'base-ineligible':1,'base-eligible-fallback-closed':1,'retained-now':1});self.assertEqual(reasons,{'access':1})
    def test_missing_relation_or_forged_base_eligibility_rejected(self):
        with self.assertRaises(AssertionError):classify_inventory({'1':row(1)},{1},{},{})
        fake=row(1);fake['baseEligible']=False
        with self.assertRaises(AssertionError):classify_inventory({'1':fake},set(),{},{})
    def test_newly_retained_record_requires_original_fallback(self):
        with self.assertRaises(AssertionError):classify_inventory({'1':row(1,old_closed=False)},set(),{},{})
    def test_lane_shape_is_observation_not_permission(self):
        r=row(1,'lane-access',False);r['rawTags']['oneway:lanes']='yes|yes'
        out,_,_,shapes=classify_inventory({'1':r},set(),{},{})
        self.assertEqual(shapes,{'only-oneway-vectors':1});self.assertTrue(out['1']['currentExcluded'])
    def test_large_integer_source_id_stays_exact(self):
        i=2**53+1;out,_,_,_=classify_inventory({str(i):row(i)},set(),{},{})
        self.assertEqual(out[str(i)]['sourceWay'],i)


if __name__=='__main__':unittest.main()
