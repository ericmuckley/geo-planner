import unittest
from analyze_osm_source_gap_closures_v1 import contribution


def relation(kind,via=(2,)):
    return {'type':'relation','id':99,'tags':{'type':'restriction','restriction':kind},'members':[{'type':'way','ref':1,'role':'from'},*[{'type':'way','ref':v,'role':'via'} for v in via],{'type':'way','ref':4,'role':'to'}]}


class Tests(unittest.TestCase):
    def test_single_and_multi_decisions_close_only_failed_complete_joins(self):
        for status in (0,2,3):
            self.assertEqual(bool(contribution(relation('no_left_turn'),{99:status},{})[0]),status==2)
            self.assertEqual(bool(contribution(relation('no_left_turn',(2,3)),{},{99:status})[0]),status==2)

    def test_only_and_conditional_and_independent_contributors_remain(self):
        got=contribution(relation('only_straight_on'),{},{})
        self.assertEqual((set(got[0]),got[1]),({1,2,4},'constant-static-only'))
        element=relation('no_left_turn');element['tags']['restriction:conditional']='no_left_turn @ night'
        self.assertEqual(contribution(element,{},{})[1],'constant-conditional')

    def test_node_only_relations_do_not_create_whole_way_contributions(self):
        element=relation('no_left_turn');element['members']=[{'type':'node','ref':2,'role':'via'}]
        self.assertEqual(contribution(element,{},{})[0],[])
