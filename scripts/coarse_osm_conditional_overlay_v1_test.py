"""Generic overlay qualification; native cost artifact supplied explicitly."""
from array import array
import copy
import math
import random
import unittest
from coarse_osm_conditional_overlay_v1 import closed_relation_nodes,prepare
from coarse_osm_car_cost_math_v1 import NativeCosts
from import_roads import distance_m

ARTIFACT=None


class ReferenceCosts:
    def costs(self,xy,speeds,same):
        return array('Q',(0 if same[i] else max(1,math.ceil(distance_m([xy[4*i]/1e7,xy[4*i+1]/1e7],[xy[4*i+2]/1e7,xy[4*i+3]/1e7])*3600/speed)) for i,speed in enumerate(speeds)))
    def sum(self,values):
        ms=sum(values);return ms,(ms+124)//125


def fixture(tags=None):
    source=[[100,200,300],[0,0,10000,0,20000,0],[0,2],[4,4],[0,1,2],[(10,0.,0.,(5<<8)|(4<<4),3)],[]]
    return source,[{'type':'way','id':10,'tags':{'highway':'primary','maxspeed:conditional':'20 @ wet'}|(tags or {})}]


class Tests(unittest.TestCase):
    def kernel(self):return NativeCosts(*ARTIFACT) if ARTIFACT else ReferenceCosts()
    def run_case(self,args,records,closed=()):return prepare(*args,records,set(closed),self.kernel())

    def test_new_way_normalized_flags_reason_directions_and_speed(self):
        args,records=fixture();r=self.run_case(args,records)
        self.assertEqual(r['wayRows'][0],(10,20,20,(4<<4)|3,3));self.assertEqual(len(r['arcs']),2)
        self.assertEqual(r['counts']['changedGraphWays'],1)

    def test_native_primitive_prices_and_source_anchor_cuts(self):
        args,records=fixture();args[2]=[0,1,2];args[3]=[4,4,4]
        r=self.run_case(args,records);ms=math.ceil(distance_m([0,0],[.001,0])*3600/20)
        self.assertEqual(r['arcs'],[(0,1,0,0,1,1,ms),(1,0,0,0,1,-1,ms),(1,2,0,1,2,1,ms),(2,1,0,1,2,-1,ms)])

    def test_zero_repeated_native_span_is_not_an_added_arc(self):
        args,records=fixture();args[4]=[0,0,2];args[2]=[0,2]
        r=self.run_case(args,records);self.assertEqual(len(r['arcs']),2)
        self.assertTrue(all(a[-1]>0 for a in r['arcs']))

    def test_oneway_and_directional_speed_default_masks(self):
        args,records=fixture({'oneway':'-1','maxspeed:backward:conditional':'10 @ snow'})
        r=self.run_case(args,records);self.assertEqual(len(r['arcs']),1);self.assertEqual(r['arcs'][0][5],-1)
        self.assertEqual(r['wayRows'][0][3]&3,2);self.assertEqual(r['wayRows'][0][2],10)
        args,records=fixture({'maxspeed:conditional':'60 @ wet'})
        r=self.run_case(args,records);self.assertEqual(r['wayRows'][0][1:3],(55,55));self.assertEqual(r['wayRows'][0][3]&15,15)

    def test_node_flags_open_only_selected_anchor_source_bit(self):
        args,_=fixture();args[3]=[7,4]
        records=[{'type':'node','id':100,'tags':{'highway':'traffic_signals','hgv:conditional':'no @ night'}}]
        r=self.run_case(args,records);self.assertEqual(r['nodeFlags'],{0:6})
        records[0]['id']=999;r=self.run_case(args,records);self.assertEqual(r['nodeFlags'],{});self.assertEqual(r['counts']['changedNodesOutsideSelectedGraph'],1)

    def test_relation_closed_node_is_never_reopened(self):
        args,_=fixture();args[3]=[5,4]
        records=[{'type':'node','id':100,'tags':{'hgv:conditional':'no @ night'}}]
        r=self.run_case(args,records,[100]);self.assertEqual(r['nodeFlags'],{});self.assertEqual(r['counts']['changedNodesKeptClosedByRelation'],1)

    def test_complete_relation_closure_union_uses_only_node_only_fallbacks(self):
        def relation(i,members):return {'id':i,'tags':{'type':'restriction','restriction':'unknown'},'members':members}
        member=lambda typ,ref:{'type':typ,'ref':ref,'role':'via'}
        elements=[relation(1,[member('node',100)]),relation(2,[member('way',10),member('node',200)])]
        result,count=closed_relation_nodes(elements);self.assertEqual(result,{100});self.assertEqual(count,2)
        with self.assertRaises(AssertionError):closed_relation_nodes(elements[::-1])

    def test_source_rows_arrays_and_old_arc_bytes_unchanged(self):
        args,records=fixture();args[4].extend([0,2]);args[5].append((20,40,40,67,5));args[6].append((0,1,1,0,1,1,1000))
        before=copy.deepcopy((args,records));r=self.run_case(args,records)
        self.assertEqual((args,records),before);self.assertNotIn(1,r['wayRows']);self.assertTrue(all(a[2]==0 for a in r['arcs']))

    def test_forged_unchanged_unknown_and_duplicate_records_rejected(self):
        for tags in ({'maxspeed:conditional':'none @ wet'},{'access':'private'}):
            args,records=fixture(tags)
            with self.assertRaises(AssertionError):self.run_case(args,records)
        args,records=fixture()
        with self.assertRaises(AssertionError):self.run_case(args,records+records)
        records[0]['id']=20
        with self.assertRaises(AssertionError):self.run_case(args,records)

    def test_existing_preclosure_arc_and_bad_source_policy_flags_rejected(self):
        args,records=fixture();args[6]=[(0,1,0,0,2,1,1000)]
        with self.assertRaises(AssertionError):self.run_case(args,records)
        args,records=fixture();args[5][0]=(10,0.,0.,4<<4,3)
        with self.assertRaises(AssertionError):self.run_case(args,records)

    def test_tagged_selected_node_requires_original_anchor_and_flags(self):
        args,_=fixture();records=[{'type':'node','id':200,'tags':{'hgv:conditional':'no @ night'}}]
        with self.assertRaises(AssertionError):self.run_case(args,records)
        records[0]['id']=100
        with self.assertRaises(AssertionError):self.run_case(args,records)

    def test_generated_source_geometry_costs_and_reverse_directions(self):
        rng=random.Random(20261106)
        for _ in range(50):
            args,records=fixture({'oneway':rng.choice(['yes','no','-1']),'maxspeed:conditional':str(rng.choice([10,20,30]))+' @ wet'})
            args[1]=[0,0,rng.randrange(1,50000),rng.randrange(1,50000),rng.randrange(50001,100000),rng.randrange(50001,100000)]
            actual=self.run_case(args,records)
            reference=prepare(*args,records,set(),ReferenceCosts())
            self.assertEqual(actual,reference)
