"""Generic paid-source overlay controls; optional unchanged native cost artifact."""
import copy
import math
import random
import unittest

from coarse_osm_car_cost_math_v1 import NativeCosts
from coarse_osm_car_explicit_lanes_v1 import POLICY
from coarse_osm_conditional_overlay_v1_test import ReferenceCosts
from coarse_osm_explicit_lane_census_v1_test import lane
from coarse_osm_explicit_lane_overlay_v1 import prepare
from import_roads import distance_m

ARTIFACT=None


def fixture(**extra):
    tags=lane(highway='primary',**extra);role=POLICY['roles'].index('primary')
    source=[[100,200,300],[0,0,10000,0,20000,0],[0,2],[0,1,2],[(10,0.,0.,(6<<8)|(role<<4),3)],[]]
    return source,[{'type':'way','id':10,'tags':tags}]


class Tests(unittest.TestCase):
    def kernel(self):return NativeCosts(*ARTIFACT) if ARTIFACT else ReferenceCosts()
    def run_case(self,args,records):return prepare(*args,records,self.kernel())

    def test_explicit_lane_normalizes_direction_default_reason_and_role_flags(self):
        args,records=fixture();r=self.run_case(args,records)
        self.assertEqual(r['wayRows'][0],(10,55,0,1|12|(4<<4),3))
        self.assertEqual(len(r['arcs']),1);self.assertEqual(r['nodeFlags'],{})

    def test_every_primitive_is_paid_and_all_source_anchor_cuts_retained(self):
        args,records=fixture();args[2]=[0,1,2]
        r=self.run_case(args,records);ms=math.ceil(distance_m([0,0],[.001,0])*3600/55)
        self.assertEqual(r['arcs'],[(0,1,0,0,1,1,ms),(1,2,0,1,2,1,ms)])

    def test_reverse_oneway_source_speed_and_conditional_fallback_remain(self):
        args,records=fixture(oneway='-1',maxspeed='80')
        r=self.run_case(args,records);self.assertEqual(len(r['arcs']),1)
        self.assertEqual(r['arcs'][0][:2],(1,0));self.assertEqual(r['arcs'][0][5],-1)
        self.assertEqual(r['wayRows'][0][1:3],(0,80));self.assertEqual(r['wayRows'][0][3]&3,2)
        # The frozen lane prototype only changes an existing lane-access reason.
        # A conditional-speed way still rejected before that point stays closed.
        args,records=fixture(**{'maxspeed:conditional':'20 @ wet'})
        with self.assertRaises(AssertionError):self.run_case(args,records)

    def test_repeated_native_span_is_not_a_free_added_arc(self):
        args,records=fixture();args[3]=[0,0,2]
        r=self.run_case(args,records);self.assertEqual(len(r['arcs']),1);self.assertGreater(r['arcs'][0][-1],0)

    def test_old_source_rows_geometry_and_arcs_are_unchanged(self):
        args,records=fixture();args[3].extend([0,2]);args[4].append((20,40.,40.,67,5));args[5].append((0,1,1,0,1,1,1000))
        before=copy.deepcopy((args,records));r=self.run_case(args,records)
        self.assertEqual((args,records),before);self.assertEqual(set(r['wayRows']),{0});self.assertTrue(all(a[2]==0 for a in r['arcs']))

    def test_unchanged_ambiguous_restricted_missing_or_duplicate_records_rejected(self):
        for extra in ({'oneway':'no'},{'motor_vehicle:lanes':'|yes|yes'},{'access':'private'},{'maxspeed':'bad'}):
            args,records=fixture(**extra)
            with self.assertRaises(AssertionError):self.run_case(args,records)
        args,records=fixture()
        with self.assertRaises(AssertionError):self.run_case(args,records+records)
        records[0]['id']=999
        with self.assertRaises(AssertionError):self.run_case(args,records)
        records[0]['id']=10;records[0]['type']='node'
        with self.assertRaises(AssertionError):self.run_case(args,records)

    def test_existing_preclosure_arcs_and_wrong_source_flags_are_refused(self):
        args,records=fixture();args[5]=[(0,1,0,0,2,1,1000)]
        with self.assertRaises(AssertionError):self.run_case(args,records)
        args,records=fixture();args[4][0]=(10,0.,0.,5<<8,3)
        with self.assertRaises(AssertionError):self.run_case(args,records)

    def test_generated_geometry_and_direction_prices_match_independent_oracle(self):
        rng=random.Random(20261106)
        for _ in range(100):
            args,records=fixture(oneway=rng.choice(['yes','-1']),maxspeed=str(rng.choice([20,30,55,80])))
            args[1]=[0,0,rng.randrange(1,50000),rng.randrange(1,50000),rng.randrange(50001,100000),rng.randrange(50001,100000)]
            self.assertEqual(self.run_case(args,records),prepare(*args,records,ReferenceCosts()))

    def test_cancellation_callback_runs_before_any_source_update(self):
        args,records=fixture();before=copy.deepcopy(args)
        def cancel():raise RuntimeError('cancel lane overlay')
        with self.assertRaisesRegex(RuntimeError,'cancel lane overlay'):prepare(*args,records,self.kernel(),cancel)
        self.assertEqual(args,before)
