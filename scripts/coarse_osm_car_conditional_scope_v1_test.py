"""Non-car keys cannot relax car conditions or erase source tag protection."""
import copy
import unittest
from dataclasses import asdict
import coarse_osm_car_policy_v2 as old
import coarse_osm_car_conditional_scope_v1 as new


class ConditionalScopeTests(unittest.TestCase):
    def test_documented_non_car_forms_preserve_base_prices_and_directions(self):
        base={'highway':'secondary','maxspeed':'50','oneway':'yes'}
        for mode in ['foot','bicycle','hgv']:
            for prefix in ['', 'maxspeed:', 'oneway:']:
                for direction in ['',':forward',':backward']:
                    key=f'{prefix}{mode}{direction}:conditional'
                    with self.subTest(key=key):
                        tags=base|{key:('30 @ wet' if prefix=='maxspeed:' else 'no @ (Mo-Fr 08:00-10:00)')}
                        self.assertEqual(old.way_policy(tags).reason,'conditional-or-way-restriction')
                        self.assertEqual(asdict(new.way_policy(tags)),asdict(old.way_policy(base)))
                        self.assertIsNone(new.way_policy(tags).backward)

    def test_car_unknown_lane_and_malformed_forms_keep_legacy_handling(self):
        keys=['access:conditional','vehicle:conditional','motor_vehicle:conditional','motorcar:conditional','maxspeed:conditional','oneway:conditional','bus:conditional','access:hgv:conditional','hgv:lanes:conditional','foo:hgv:conditional','maxspeed:hgv:motorcar:conditional','maxspeed:hgv:sideways:conditional','foot:conditional:forward','foot:Conditional']
        for key in keys:
            with self.subTest(key=key):
                tags={'highway':'primary',key:'no @ night'}
                self.assertFalse(new.ignored_conditional_key(key))
                self.assertEqual(asdict(new.way_policy(tags)),asdict(old.way_policy(tags)))

    def test_mixed_modes_and_other_exclusion_reasons_remain_closed(self):
        for extra in [{'motorcar:conditional':'no @ night'},{'access':'private'},{'barrier':'wall','access':'no'},{'access:lanes':'no|yes'},{'oneway':'unknown'},{'maxspeed':'invalid'},{'route':'ferry'}]:
            tags={'highway':'primary','hgv:conditional':'no @ night'}|extra
            with self.subTest(extra=extra):self.assertIsNotNone(new.way_policy(tags).reason)

    def test_node_tag_and_signal_protection_survives_filtering(self):
        tags={'hgv:conditional':'no @ night'}
        self.assertEqual(new.node_policy(tags),{'blocked':False,'signal':False,'tagged':True,'barrier':None})
        self.assertTrue(old.node_policy(tags)['blocked'])
        tags['highway']='traffic_signals'
        self.assertEqual(new.node_policy(tags),{'blocked':False,'signal':True,'tagged':True,'barrier':None})

    def test_node_car_barrier_and_unknown_conditions_stay_blocked(self):
        for tags in [{'access':'no'},{'motor_vehicle:conditional':'no @ night'},{'maxspeed:conditional':'20 @ wet'},{'barrier':'bollard'},{'bus:conditional':'yes @ night'}]:
            tags=tags|{'hgv:conditional':'no @ night'}
            with self.subTest(tags=tags):self.assertTrue(new.node_policy(tags)['blocked'])

    def test_source_inputs_and_relation_classifier_are_unchanged(self):
        tags={'highway':'tertiary','maxspeed':'35 mph','oneway':'-1','maxspeed:hgv:conditional':'20 @ wet'}
        before=copy.deepcopy(tags);new.way_policy(tags);new.node_policy(tags)
        self.assertEqual(tags,before)
        self.assertIs(new.restriction_policy,old.restriction_policy)
        for plain in [{'highway':'motorway'},{'highway':'primary','maxspeed':'30','oneway':'-1'},{}]:
            self.assertEqual(asdict(new.way_policy(plain)),asdict(old.way_policy(plain)))
            self.assertEqual(new.node_policy(plain),old.node_policy(plain))


if __name__=='__main__':unittest.main()
