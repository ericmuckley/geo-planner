"""Protected native lane parity, including every preceding policy control."""
from dataclasses import asdict
import itertools
import random
import unittest

import coarse_osm_car_native_policy_v3_test as previous
from coarse_osm_car_explicit_lanes_v1 import way_policy
from coarse_osm_car_native_policy_v4 import NativePolicy

ARTIFACT=None
WireTests=previous.WireTests


class NativeTests(previous.NativeTests):
    @classmethod
    def setUpClass(cls):
        if ARTIFACT is None:raise unittest.SkipTest('Run with the protected compiled V4 artifact')
        cls.native=NativePolicy(*ARTIFACT)

    def way(self,props):self.assertEqual(self.native.classify('way',props),asdict(way_policy(props)),props)

    def test_all_known_two_lane_permission_columns(self):
        for a,b,c,d in itertools.product(('yes','no','designated','psv'),('yes','no','designated','psv'),('yes','no','designated'),('yes','no','designated')):
            self.way({'highway':'motorway','oneway':'yes','lanes':'2','motor_vehicle:lanes':a+'|'+b,'hov:lanes':c+'|'+d})

    def test_lane_bounds_direction_overrides_and_ambiguous_forms(self):
        base={'highway':'primary','oneway':'yes','lanes':'3','access:lanes':'yes|psv|yes','hov:lanes':'yes|designated|yes'}
        for key,values in {'lanes':('','0','03','33','٣','1'*10000,'32'),
                           'access:lanes':('','yes||yes','no|no|no','yes|unknown|yes','yes| yes|yes'),
                           'hov:lanes':('designated||','yes|psv|yes'),
                           'oneway':('no','-1','reversible'),
                           'oneway:motorcar':('yes','no','-1'),
                           'oneway:bus':('yes','no'),
                           'hov':('yes','designated'),
                           'lanes:backward':('0','1'),
                           'hov:conditional':('designated @ night',),
                           'access:lanes:forward':('yes|yes|yes',),
                           'maxspeed:conditional':('20 @ wet','bad'),
                           'motorcar:conditional':('no @ night',)}.items():
            for value in values:self.way(base|{key:value})
        self.way({'highway':'motorway','lanes':'32','motor_vehicle:lanes':'|'.join(['no']*31+['yes'])})
        self.way(base|{'lanes':'2','access:lanes':'yes|yes','hov:lanes':'yes|yes','motorcar:lanes':'no|yes'})

    def test_seeded_lane_policy_combinations(self):
        rng=random.Random(20261105)
        fields={'highway':('motorway','primary','residential'),'oneway':('yes','no','-1'),
                'lanes':('1','2','3','4','03'),'motor_vehicle:lanes':('no|yes|yes','|yes','yes|yes'),
                'access:lanes':('yes|psv|yes','no|no','yes|yes'),'hov:lanes':('designated|yes|yes','|yes','yes|yes'),
                'maxspeed':('35 mph','60','bad'),'motorcar':('yes','no','destination'),
                'oneway:motorcar':('yes','-1'),'hov:minimum':('2',),'hgv:conditional':('no @ night',)}
        for _ in range(4000):
            self.way({'highway':'primary'}|{key:rng.choice(values) for key,values in fields.items() if rng.randrange(3)==0})
