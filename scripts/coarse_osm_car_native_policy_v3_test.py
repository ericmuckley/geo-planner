"""Protected native parity for the static conditional-speed prototype."""
from dataclasses import asdict
import random
import unittest
import coarse_osm_car_native_policy_v2_test as legacy
from coarse_osm_car_native_policy_v3 import NativePolicy
from coarse_osm_car_conditional_speed_v1 import node_policy,way_policy

ARTIFACT=None
WireTests=legacy.WireTests


class NativeTests(legacy.NativeTests):
    @classmethod
    def setUpClass(cls):
        if ARTIFACT is None:raise unittest.SkipTest('Run with the protected compiled V3 artifact')
        cls.native=NativePolicy(*ARTIFACT)

    def way(self,props):self.assertEqual(self.native.classify('way',props),asdict(way_policy(props)),props)

    def node(self,props):
        expected=node_policy(props)
        self.assertEqual(self.native.classify('node',props),{k:expected[k] for k in ('blocked','signal','tagged')},props)

    def test_conditional_mode_key_grammar_and_tagged_nodes(self):
        for mode in ('foot','bicycle','hgv','bus','motorcar','hgv_articulated',''):
            for prefix in ('','maxspeed:','oneway:','restriction:','access:'):
                for direction in ('',':forward',':backward',':lanes',':forward:forward'):
                    tags={prefix+mode+direction+':conditional':'no @ night'}
                    self.way({'highway':'primary'}|tags);self.node(tags)
                    self.node({'barrier':'gate','motorcar':'yes'}|tags)

    def test_conditional_values_units_and_nested_clauses(self):
        for value in ('25 mph @ children_present','20 mph @ (Mo-Fr 07:00-17:00)',
                      '30 @ (Mo-Fr 07:00-09:00; Sa 10:00-12:00); 50 kph @ wet',
                      '40 @ wet; 30 mph @ snow','\u200330\u00a0mph @ (wet)','20 @ ()wet',
                      '0.000000000000000000000000001 @ wet','0'*8192+'55 @ wet'):
            for key in ('maxspeed:conditional','maxspeed:forward:conditional','maxspeed:backward:conditional'):
                self.way({'highway':'secondary',key:value})

    def test_conditional_direction_base_access_and_other_constraints(self):
        base={'highway':'secondary','maxspeed':'80','maxspeed:conditional':'50 @ wet','maxspeed:forward:conditional':'25 @ snow','maxspeed:backward:conditional':'35 @ night'}
        for extra in ({},{'oneway':'-1'},{'oneway':'yes'},{'motorcar:forward':'no'},{'access':'private'},
                      {'motorcar:conditional':'no @ night'},{'oneway:conditional':'no @ night'},
                      {'maxspeed:motorcar:conditional':'30 @ wet'},{'maxspeed:forward':'20'},
                      {'access:lanes':'yes|no'},{'hgv:conditional':'no @ night'},{'route':'ferry'}):self.way(base|extra)

    def test_bad_conditional_values_and_structures(self):
        for value in ('','25 mph','0 @ wet','200 @ wet','none @ night','signals @ wet','walk @ wet','20 @ ',
                      '20 @ ()','20 @ (wet','20 @ wet);30 @ night','20 @ wet;','20 @ wet @ night',
                      '20 @ "wet"',"20 @ 'wet'",';20 @ wet','５０ @ wet','1'*8192+' @ wet','20\x00 @ wet'):
            self.way({'highway':'primary','maxspeed:conditional':value})

    def test_conditional_parser_exact_work_bounds_and_unicode_length(self):
        for value in (';'.join(['20 @ wet']*64),';'.join(['20 @ wet']*65),
                      '20 @ '+'('*8+'wet'+')'*8,'20 @ '+'('*9+'wet'+')'*9,
                      '20 @ '+'x'*65531,'20 @ '+'x'*65532,'20 @ '+'雪'*65531,'20 @ '+'雪'*65532):
            self.way({'highway':'primary','maxspeed:conditional':value})

    def test_seeded_conditional_combinations(self):
        rng=random.Random(20261104)
        fields={'highway':('primary','secondary','motorway','residential'), 'maxspeed':('60','30 mph','bad'),
                'maxspeed:conditional':('20 @ wet','40 @ wet; 30 @ snow','none @ wet','25 mph @ children_present'),
                'maxspeed:forward:conditional':('15 @ night','60 @ wet','20'),
                'oneway':('yes','no','-1'),'hgv:conditional':('no @ night',),
                'motorcar:conditional':('no @ night',),'motor_vehicle:backward':('no','yes')}
        for _ in range(2000):
            props={'highway':'primary'}|{k:rng.choice(v) for k,v in fields.items() if rng.randrange(3)==0}
            self.way(props)
