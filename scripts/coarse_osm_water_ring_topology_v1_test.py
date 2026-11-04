import unittest

from coarse_osm_water_ring_topology_v1 import join_degree_two


class Controls(unittest.TestCase):
    def test_reversed_ways_join_by_native_ids_and_use_every_member_once(self):
        result=join_degree_two([(10,1,2,3),(20,3,2,4),(30,3,1,3)])
        self.assertTrue(result['allMembersJoined'])
        self.assertEqual(result['closedChains'],[[[10,1],[20,-1],[30,1]]])
        self.assertFalse(result['polygonValidityEstablished'])

    def test_disconnected_rings_and_closed_members_remain_separate(self):
        result=join_degree_two([(10,1,2,2),(20,2,1,3),(30,8,8,4),(40,9,10,2),(50,10,9,4)])
        self.assertTrue(result['allMembersJoined']);self.assertEqual(len(result['closedChains']),3)
        self.assertEqual(sorted(i for ring in result['closedChains'] for i,_ in ring),[10,20,30,40,50])

    def test_missing_endpoint_chain_is_preserved(self):
        result=join_degree_two([(10,1,2,3),(20,2,3,4)])
        self.assertFalse(result['allMembersJoined']);self.assertEqual(result['unjoinedOpenWayIds'],[10,20])
        self.assertEqual(result['endpointDegreesNeedingGeometryOrMissingClosure'],[[1,1],[3,1]])

    def test_touching_branch_is_not_guessed_from_member_order(self):
        result=join_degree_two([(10,1,2,3),(20,2,1,3),(30,1,3,3),(40,3,1,3)])
        self.assertFalse(result['allMembersJoined'])
        self.assertEqual(result['endpointDegreesNeedingGeometryOrMissingClosure'],[[1,4]])

    def test_different_native_ids_never_join_by_implied_coordinate_coincidence(self):
        result=join_degree_two([(10,1,2,2),(20,3,4,2)])
        self.assertFalse(result['allMembersJoined']);self.assertEqual(len(result['endpointDegreesNeedingGeometryOrMissingClosure']),4)

    def test_duplicate_members_short_closed_ways_and_bad_fields_preserved_or_rejected(self):
        with self.assertRaises(Exception):join_degree_two([(10,1,2,2),(10,2,1,2)])
        for segment in ((10,0,1,2),(10,1,1,1),(True,1,2,3)):
            with self.assertRaises(Exception):join_degree_two([segment])
        result=join_degree_two([(10,1,1,3)])
        self.assertFalse(result['allMembersJoined']);self.assertEqual(result['shortClosedMemberWayIds'],[10])

    def test_empty_member_list_is_not_polygon_validity(self):
        result=join_degree_two([])
        self.assertTrue(result['allMembersJoined']);self.assertEqual(result['closedChains'],[])
        self.assertFalse(result['polygonValidityEstablished'])


if __name__=='__main__':unittest.main()
