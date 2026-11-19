import unittest

from coarse_osm_blocked_node_causes_v1 import node_cause


class BlockedNodeCausesTests(unittest.TestCase):
    def test_benign_raw_tags_do_not_discard_an_independent_relation_contribution(self):
        result = node_cause(10,7,{'type':'node','id':10,'tags':{'highway':'traffic_signals'}},[99,99])
        self.assertFalse(result['rawBaseBlocked'])
        self.assertEqual(result['cause'],'restriction-only')
        self.assertEqual(result['restrictionContributorIds'],[99])
        self.assertTrue(result['sourceBlockingReconciled'])
        self.assertTrue(result['sourceSignalReconciled'])

    def test_base_and_relation_contributions_and_unknown_raw_nodes_remain_separate(self):
        result = node_cause(10,5,{'type':'node','id':10,'tags':{'motor_vehicle':'no'}},[99])
        self.assertEqual(result['cause'],'base-and-restriction')
        self.assertTrue(result['rawBaseBlocked'])
        unknown = node_cause(20,5,None,[101])
        self.assertIsNone(unknown['rawBaseBlocked'])
        self.assertIsNone(unknown['sourceBlockingReconciled'])
        self.assertEqual(unknown['restrictionContributorIds'],[101])

    def test_source_mismatch_is_explicit_and_native_id_mismatch_refuses(self):
        result = node_cause(10,5,{'type':'node','id':10,'tags':{}},[])
        self.assertEqual(result['cause'],'unexplained-stored-block')
        self.assertFalse(result['sourceBlockingReconciled'])
        with self.assertRaises(AssertionError):
            node_cause(10,5,{'type':'node','id':11,'tags':{}},[])


if __name__ == '__main__':
    unittest.main()
