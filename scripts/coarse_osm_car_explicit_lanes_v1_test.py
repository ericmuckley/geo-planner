import copy
from dataclasses import asdict
import itertools
import unittest

from coarse_osm_car_conditional_speed_v1 import way_policy as previous
from coarse_osm_car_explicit_lanes_v1 import classify_way, way_policy


def tags(**extra):
    return {'highway':'motorway','oneway':'yes','lanes':'3','maxspeed':'65 mph',
            'motor_vehicle:lanes':'no|yes|yes','hov:lanes':'designated|yes|yes','hov:minimum':'2'}|extra


class ExplicitLanes(unittest.TestCase):
    def test_documented_mixed_hov_keeps_ordinary_lane_and_source_price(self):
        raw=tags();before=copy.deepcopy(raw);result=classify_way(raw)
        self.assertEqual(result['explicitOrdinaryLaneIndices'],(1,2))
        self.assertEqual(result['policy'],previous({k:v for k,v in raw.items() if k!='motor_vehicle:lanes'}))
        self.assertEqual(result['policy'].backward,None)
        self.assertEqual(raw,before)

    def test_intersection_is_conservative_without_mode_precedence_inference(self):
        raw=tags(**{'motorcar:lanes':'yes|no|yes','access:lanes':'yes|yes|no'})
        self.assertEqual(classify_way(raw)['explicitOrdinaryLaneIndices'],())
        self.assertEqual(way_policy(raw),previous(raw))
        raw['access:lanes']='yes|yes|yes'
        self.assertEqual(classify_way(raw)['explicitOrdinaryLaneIndices'],(2,))

    def test_no_restricted_or_inherited_hov_lane_is_admitted(self):
        for changes in [{'motor_vehicle:lanes':'no|no|no'},{'motor_vehicle:lanes':'|yes|yes'},
                        {'hov:lanes':'designated|designated|designated'},{'hov':'designated'},
                        {'hov:lanes':'designated||'},{'hov:lanes:forward':'yes|yes|yes'}]:
            raw=tags(**changes);self.assertEqual(way_policy(raw),previous(raw))

    def test_unknown_keys_tokens_counts_and_two_way_keep_fallback(self):
        for changes in [{'lanes':'0'},{'lanes':'03'},{'lanes':'33'},{'lanes':'3.0'},{'lanes':'٣'},{'lanes':'1'*10000},
                        {'motor_vehicle:lanes':'no|yes'},{'motor_vehicle:lanes':'no|unknown|yes'},
                        {'motor_vehicle:lanes':'no| yes|yes'},{'access:lanes:forward':'yes|yes|yes'},
                        {'oneway:lanes':'yes|yes|yes'},{'oneway':'no'},{'oneway':'reversible'}]:
            raw=tags(**changes);self.assertEqual(way_policy(raw),previous(raw))

    def test_all_other_access_and_conditional_constraints_stay(self):
        for changes in [{'motorcar':'no'},{'access':'private'},{'motor_vehicle':'destination'},
                        {'motor_vehicle:conditional':'no @ (Mo-Fr)'},{'motor_vehicle:lanes:conditional':'yes|no|no @ (Mo-Fr)'},
                        {'hov:conditional':'designated @ (Mo-Fr)'},{'ford':'yes'},{'access:lanes:unknown':'yes|yes|yes'}]:
            raw=tags(**changes);self.assertEqual(way_policy(raw),previous(raw))

    def test_reverse_oneway_and_motorcar_direction_priority_are_unchanged(self):
        raw=tags(oneway='-1');result=way_policy(raw)
        self.assertIsNone(result.forward);self.assertIsNotNone(result.backward)
        self.assertEqual(result.backward,previous({k:v for k,v in raw.items() if k!='motor_vehicle:lanes'}).backward)
        raw=tags(**{'oneway':'no','oneway:motorcar':'yes'})
        self.assertIsNotNone(way_policy(raw).forward);self.assertIsNone(way_policy(raw).backward)

    def test_all_existing_eligible_policies_retain_exact_decisions_and_costs(self):
        for role,oneway,speed in itertools.product(('motorway','primary','secondary'),('yes','no','-1'),('50','65 mph',None)):
            raw={'highway':role,'oneway':oneway}
            if speed is not None:raw['maxspeed']=speed
            self.assertEqual(asdict(way_policy(raw)),asdict(previous(raw)))

    def test_exhaustive_explicit_lane_intersection_matches_independent_column_oracle(self):
        values=('yes','no','designated','psv')
        for a,b,c,d in itertools.product(values,values,('yes','no','designated'),('yes','no','designated')):
            raw={'highway':'motorway','oneway':'yes','lanes':'2','motor_vehicle:lanes':a+'|'+b,'hov:lanes':c+'|'+d}
            possible=(a=='yes' and c=='yes') or (b=='yes' and d=='yes')
            self.assertEqual(way_policy(raw).reason is None,possible)

    def test_ambiguous_lane_direction_and_hov_metadata_stay_closed(self):
        for changes in [{'lanes:backward':'1'},{'lanes:forward':'2'},{'lanes:both_ways':'1'},
                        {'oneway:bus':'no'},{'hov:lanes':'yes|psv|yes'},{'hov:lanes:conditional':'yes|yes|yes @ (Mo-Fr)'}]:
            raw=tags(**changes);self.assertEqual(way_policy(raw),previous(raw))


if __name__=='__main__':unittest.main()
