import itertools
import random
import unittest

from coarse_osm_car_conditional_scope_v1 import node_policy as previous
from coarse_osm_car_passable_barriers_v1 import PASSABLE_BARRIERS,graph_node_decision,node_policy


class Tests(unittest.TestCase):
    def test_documented_feature_defaults_only_and_raw_tags_unchanged(self):
        for barrier in PASSABLE_BARRIERS:
            tags={'barrier':barrier};snapshot=dict(tags)
            got=node_policy(tags)
            self.assertTrue(previous(tags)['blocked'])
            self.assertFalse(got['blocked'])
            self.assertIsNone(got['barrier']['accessKey'])
            self.assertEqual(tags,snapshot)

    def test_every_existing_guard_and_ambiguous_form_retains_closure(self):
        guards=({'motorcar':'no'},{'access':'private'},{'vehicle':'destination'}, {'motor_vehicle':''},
                {'access':'designated'},{'access:conditional':'yes @ night'},{'motor_vehicle:conditional':'yes @ day'},
                {'snowmobile:conditional':'yes @ snow'}, {'oneway':'yes'},{'motorcar:forward':'yes'},
                {'maxwidth':'2'},{'width':'3'},{'maxweight:hgv':'5'},{'locked':'yes'},{'locked':''},
                {'opening_hours':'Mo-Fr 08:00-18:00'},{'opening_hours':''})
        for barrier,extra in itertools.product(PASSABLE_BARRIERS,guards):
            tags={'barrier':barrier}|extra
            self.assertEqual(node_policy(tags),previous(tags),(barrier,extra))
            self.assertTrue(node_policy(tags)['blocked'])

    def test_specific_mode_precedence_and_accepted_permissions(self):
        for barrier in PASSABLE_BARRIERS:
            for key in ('motorcar','motor_vehicle','vehicle','access'):
                tags={'barrier':barrier,key:'yes'}
                self.assertFalse(node_policy(tags)['blocked'])
            self.assertFalse(node_policy({'barrier':barrier,'motorcar':'yes','access':'no'})['blocked'])
            self.assertTrue(node_policy({'barrier':barrier,'motorcar':'no','access':'yes'})['blocked'])

    def test_gate_and_lift_gate_and_unknown_features_unchanged(self):
        for barrier in ('gate','lift_gate','border_control','bollard','block','chain','sally_port','unknown','','CATTLE_GRID'):
            for extra in ({},{'motorcar':'yes'},{'motorcar':'no'},{'locked':'yes'}):
                tags={'barrier':barrier}|extra
                self.assertEqual(node_policy(tags),previous(tags))

    def test_only_existing_noncar_scope_is_ignored(self):
        for key in ('hgv:conditional','foot:conditional','bicycle:conditional'):
            tags={'barrier':'entrance',key:'no @ night'}
            self.assertFalse(node_policy(tags)['blocked'])
            self.assertEqual(node_policy(tags)['tagged'],True)
        self.assertTrue(node_policy({'barrier':'entrance','bus:conditional':'no @ night'})['blocked'])

    def test_signals_tagged_flags_and_all_original_positives_preserved(self):
        rng=random.Random(20261107)
        for _ in range(2000):
            tags={}
            for key,values in (('barrier',('gate','cattle_grid','entrance','toll_booth','bollard')),
                               ('motorcar',('yes','no','permissive','private','designated','')),
                               ('highway',('traffic_signals','stop')),('locked',('no','yes'))):
                if rng.random()<.5:tags[key]=rng.choice(values)
            old,new=previous(tags),node_policy(tags)
            self.assertEqual((old['signal'],old['tagged']),(new['signal'],new['tagged']))
            if not old['blocked']:self.assertEqual(old,new)
            if old['blocked'] and not new['blocked']:self.assertIn(tags['barrier'],PASSABLE_BARRIERS)

    def test_independent_node_only_restriction_still_blocks(self):
        tags={'barrier':'cattle_grid'}
        self.assertFalse(graph_node_decision(tags,[])['blocked'])
        guarded=graph_node_decision(tags,[90])
        self.assertTrue(guarded['blocked'])
        self.assertFalse(guarded['base']['blocked'])
        self.assertEqual(tags,{'barrier':'cattle_grid'})
