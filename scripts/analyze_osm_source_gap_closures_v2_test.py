import unittest
from analyze_osm_source_gap_closures_v2 import cached_closure_subsets


class Tests(unittest.TestCase):
    def test_closed_base_ineligible_way_keeps_both_independent_labels(self):
        rows=[{'sourceWay':1,'baseEligible':True,'finalFallbackClosed':True},
              {'sourceWay':2,'baseEligible':False,'finalFallbackClosed':True},
              {'sourceWay':3,'baseEligible':False,'finalFallbackClosed':False}]
        all_closed,eligible=cached_closure_subsets(rows)
        self.assertEqual(all_closed,{1,2});self.assertEqual(eligible,{1})

    def test_empty_and_no_closed_ways_remain_empty(self):
        self.assertEqual(cached_closure_subsets([]),(set(),set()))
        self.assertEqual(cached_closure_subsets([{'sourceWay':1,'baseEligible':True,'finalFallbackClosed':False}]),(set(),set()))
