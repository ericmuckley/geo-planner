import unittest

from analyze_osm_blocked_node_tags_v1 import exposures
from coarse_osm_blocked_node_causes_v1 import node_cause


class Tests(unittest.TestCase):
    def test_tag_inventory_preserves_raw_barrier_and_independent_restriction(self):
        row=node_cause(10,5,{'type':'node','id':10,'tags':{'barrier':'cattle_grid'}},[90])
        got=exposures(row)
        self.assertEqual(got['barrier'],'cattle_grid')
        self.assertEqual(got['barrierReason'],'unsupported-barrier')
        self.assertEqual(got['restrictionContributorCount'],1)
        self.assertTrue(got['baseBlocked'])

    def test_unknown_mode_qualifiers_retained_and_only_existing_scope_ignored(self):
        row=node_cause(10,5,{'type':'node','id':10,'tags':{'vehicle:conditional':'no @ night','hgv:conditional':'no @ night'}},[])
        got=exposures(row)
        self.assertEqual(got['retainedConditionalKeys'],['vehicle:conditional'])
        self.assertEqual(got['ignoredConditionalKeys'],['hgv:conditional'])

    def test_more_specific_access_and_mismatched_recorded_policy(self):
        row=node_cause(10,5,{'type':'node','id':10,'tags':{'motorcar':'no','access':'yes'}},[])
        got=exposures(row)
        self.assertEqual((got['effectiveAccessKey'],got['effectiveAccessValue']),('motorcar','no'))
        self.assertFalse(got['accessAllowed'])
        row['rawBaseDecision']={}
        with self.assertRaises(Exception):exposures(row)
