import unittest
from coarse_osm_conditional_entry_baseline_v1 import baseline


class Tests(unittest.TestCase):
    def test_blocked_and_retained_insertions_join_source_native_way_ids(self):
        r=baseline([(10,),(20,),(30,)], [20], [(0,0,0,2),(1,3,5,4),(2,10,16,1)],10,8,17)
        self.assertEqual(r,{'originalPostArcs':8,'addedPreClosureArcs':7,'addedArcsOutsideOriginalClosures':3,'addedArcsInsideOriginalClosures':4,'newPostUnderOriginalClosures':11,'insertionGroups':3})

    def test_adjacent_restored_ways_can_share_an_old_insertion_position(self):
        r=baseline([(10,),(20,)],[],[(0,3,3,2),(1,3,5,4)],10,8,16)
        self.assertEqual(r['newPostUnderOriginalClosures'],14)

    def test_reordered_forged_duplicate_or_missing_source_counts_rejected(self):
        ways=[(10,),(20,)]
        for entries,new_pre in [([(0,0,1,2)],12), ([(0,0,0,2),(0,0,2,1)],13), ([(1,1,1,2),(0,2,4,1)],13), ([(0,0,0,2)],13), ([(2,0,0,2)],12)]:
            with self.assertRaises(AssertionError):baseline(ways,[],entries,10,8,new_pre)

    def test_unmodified_source_has_zero_delta_and_exact_original_count(self):
        r=baseline([(10,)],[],[],10,8,10);self.assertEqual(r['newPostUnderOriginalClosures'],8)
