import unittest
from coarse_osm_conditional_node_inventory_v1 import closure_unions
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    def test_shared_member_ways_keep_every_unconverted_contributor(self):
        rows=[{'sourceRelation':1,'closedWays':['10','20']},{'sourceRelation':2,'closedWays':['20','30']}]
        self.assertEqual(closure_unions(rows,{1}),({10,20,30},{20,30}))
        self.assertEqual(closure_unions(rows,set()),({10,20,30},{10,20,30}))
        self.assertEqual(closure_unions(rows,{1,2}),({10,20,30},set()))

    def test_forged_candidate_or_duplicate_contributor_refused(self):
        rows=[{'sourceRelation':1,'closedWays':['10']}]
        with self.assertRaises(PilotError):closure_unions(rows,{2})
        with self.assertRaises(PilotError):closure_unions(rows+rows,{1})

    def test_all_other_closures_remain_even_when_one_has_multiple_members(self):
        rows=[{'sourceRelation':1,'closedWays':['10','20','30']},{'sourceRelation':2,'closedWays':['20']},{'sourceRelation':3,'closedWays':['40']}]
        self.assertEqual(closure_unions(rows,{1})[1],{20,40})
