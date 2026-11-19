import unittest

from analyze_osm_blocked_node_causes_v2 import closing_node_members


class NodeClosureContributorTests(unittest.TestCase):
    def test_via_nodes_in_way_relations_do_not_create_independent_node_blocks(self):
        relation = {'id':1,'tags':{'type':'restriction','restriction:conditional':'no_left_turn @ (wet)'},
                    'members':[{'type':'way','ref':10,'role':'from'},
                               {'type':'node','ref':20,'role':'via'},
                               {'type':'way','ref':30,'role':'to'}]}
        self.assertEqual(closing_node_members(relation),[])

    def test_node_only_unsupported_relations_preserve_every_node_contribution(self):
        relation = {'id':1,'tags':{'type':'restriction','restriction':'no_left_turn'},
                    'members':[{'type':'node','ref':20,'role':'via'},
                               {'type':'node','ref':30,'role':'to'}]}
        self.assertEqual(closing_node_members(relation),[20,30])

    def test_non_car_relations_are_not_reinterpreted_as_current_closure_records(self):
        relation = {'id':1,'tags':{'type':'restriction:hgv','restriction':'no_u_turn'},
                    'members':[{'type':'node','ref':20,'role':'via'}]}
        with self.assertRaises(AssertionError):
            closing_node_members(relation)


if __name__ == '__main__':
    unittest.main()
