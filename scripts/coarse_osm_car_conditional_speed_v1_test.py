"""Conditional speeds cannot relax access or alter an existing positive price."""
import copy
from dataclasses import asdict
import unittest
import coarse_osm_car_conditional_scope_v1 as scope
import coarse_osm_car_conditional_speed_v1 as new


class ConditionalSpeedTests(unittest.TestCase):
    def test_units_and_nested_condition_separators(self):
        self.assertEqual(new.conditional_speeds('30 @ (Mo-Fr 07:00-09:00; Sa 10:00-12:00); 50 kph @ wet'),(30,50))
        self.assertAlmostEqual(new.conditional_speeds('20 mph @ snow')[0],32.18688)

    def test_general_minimum_preserves_source_and_ignores_condition_state(self):
        tags={'highway':'primary','maxspeed':'70','maxspeed:conditional':'50 @ wet; 30 @ (Mo-Fr 07:00-09:00)'};before=copy.deepcopy(tags)
        result=new.way_policy(tags)
        self.assertIsNone(result.reason);self.assertEqual((result.forward,result.backward),(30,30));self.assertFalse(result.forward_default)
        self.assertEqual(tags,before)

    def test_common_and_directional_limits_share_the_conservative_minimum(self):
        tags={'highway':'primary','maxspeed':'80','maxspeed:forward':'60','maxspeed:backward':'100','maxspeed:conditional':'50 @ wet','maxspeed:forward:conditional':'35 @ snow','maxspeed:backward:conditional':'20 @ night'}
        result=new.way_policy(tags);self.assertEqual((result.forward,result.backward),(35,20))

    def test_default_provenance_changes_only_when_conditional_limit_binds(self):
        base={'highway':'tertiary'}
        result=new.way_policy(base|{'maxspeed:conditional':'60 @ wet'})
        self.assertEqual((result.forward,result.forward_default),(40,True))
        result=new.way_policy(base|{'maxspeed:forward:conditional':'20 @ wet'})
        self.assertEqual((result.forward,result.backward),(20,40));self.assertFalse(result.forward_default);self.assertTrue(result.backward_default)

    def test_oneway_and_directional_access_are_not_relaxed(self):
        result=new.way_policy({'highway':'secondary','oneway':'yes','maxspeed:conditional':'20 @ wet'})
        self.assertEqual(result.forward,20);self.assertIsNone(result.backward)
        result=new.way_policy({'highway':'secondary','motor_vehicle:forward':'no','maxspeed:conditional':'20 @ wet'})
        self.assertIsNone(result.forward);self.assertEqual(result.backward,20)

    def test_other_car_unknown_lane_and_ferry_constraints_stay_closed(self):
        for extra in [{'motorcar:conditional':'no @ night'},{'oneway:conditional':'-1 @ night'},{'maxspeed:motorcar:conditional':'10 @ wet'},{'access':'private'},{'access:lanes':'no|yes'},{'route':'ferry'}]:
            tags={'highway':'primary','maxspeed:conditional':'20 @ wet'}|extra
            with self.subTest(extra=extra):self.assertIsNotNone(new.way_policy(tags).reason)

    def test_unsupported_values_and_structurally_bad_conditions_stay_closed(self):
        values=['0 @ wet','200 @ wet','none @ night','signals @ wet','walk @ wet','20','20 @ ','20 @ ()','20 @ (wet','20 @ wet); 30 @ night','20 @ wet;','20 @ wet @ night','20 @ "wet"',';20 @ wet']
        for value in values:
            with self.subTest(value=value):
                self.assertIsNone(new.conditional_speeds(value))
                self.assertIsNotNone(new.way_policy({'highway':'primary','maxspeed:conditional':value}).reason)

    def test_node_relation_and_all_previously_eligible_ways_keep_scope_behavior(self):
        self.assertIs(new.node_policy,scope.node_policy);self.assertIs(new.restriction_policy,scope.restriction_policy)
        for tags in [{'highway':'motorway'},{'highway':'secondary','oneway':'-1','maxspeed':'35 mph'},{'highway':'primary','hgv:conditional':'no @ night'}]:
            self.assertEqual(asdict(new.way_policy(tags)),asdict(scope.way_policy(tags)))
        self.assertTrue(new.node_policy({'maxspeed:conditional':'20 @ wet'})['blocked'])

    def test_parser_work_bounds_are_explicit(self):
        self.assertIsNotNone(new.conditional_speeds(';'.join(['20 @ wet']*64)))
        self.assertIsNone(new.conditional_speeds(';'.join(['20 @ wet']*65)))
        self.assertIsNone(new.conditional_speeds('20 @ '+'('*9+'wet'+')'*9))
        self.assertIsNone(new.conditional_speeds('20 @ '+'x'*65536))


if __name__=='__main__':unittest.main()
