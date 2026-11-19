import unittest
from coarse_osm_conditional_entry_preservation_v1 import ArcMap,audit


class Tests(unittest.TestCase):
    def test_forward_and_inverse_around_all_insertion_boundaries(self):
        m=ArcMap([(1,0,0,2),(2,3,5,2),(3,5,9,1)],5,10)
        self.assertEqual([m.forward(i) for i in range(5)],[2,3,4,7,8])
        self.assertEqual([m.backward(i) for i in range(10)],[None,None,0,1,2,None,None,3,4,None])

    def test_adjacent_insertions_with_same_old_position_and_empty_map(self):
        m=ArcMap([(1,0,0,2),(2,0,2,1)],2,5)
        self.assertEqual([m.forward(i) for i in range(2)],[3,4]);self.assertEqual(m.backward(2),None)
        self.assertEqual(ArcMap([],2,2).forward(1),1)

    def test_all_old_pairs_mapped_and_only_new_arc_restriction_allowed(self):
        r=audit({20},{20},{(0,1)},{(1,2),(0,1)},[(0,0,0,1)],2,3,lambda i:10)
        self.assertTrue(r['allOldAllowedSourceTransitionsRetained']);self.assertEqual(r['pairsTouchingNewArcs'],1)

    def test_pair_on_formerly_closed_way_can_be_added_without_losing_old_path(self):
        r=audit({20},set(),set(),{(0,1)},[],2,2,lambda i:20 if i==0 else 10)
        self.assertEqual(r['pairsTouchingOldClosedWays'],1)

    def test_new_closure_or_old_active_pair_or_missing_old_pair_refused(self):
        for args in [({20},{30},set(),set()),(set(),set(),set(),{(0,1)}),(set(),set(),{(0,1)},set())]:
            with self.assertRaises(AssertionError):audit(*args,[],2,2,lambda i:10)

    def test_invalid_source_mapping_count_and_reordered_records_refused(self):
        for entries,old,new in [([(1,0,1,1)],2,3), ([(1,0,0,1),(0,1,2,1)],2,4), ([],2,3)]:
            with self.assertRaises(AssertionError):ArcMap(entries,old,new)
