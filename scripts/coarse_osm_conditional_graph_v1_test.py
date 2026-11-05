"""Captured graph changes must follow generic source policy and paid geometry."""
import copy
from dataclasses import asdict
import math
import unittest
from coarse_osm_car_conditional_speed_v1 import way_policy
from coarse_osm_car_policy_v2 import way_policy as old
from coarse_osm_conditional_graph_v1 import augment
from evaluate_osm_entry_capture_v1 import SourceReplay
from import_roads import distance_m


def record(tags,identity=10):
    before,after=asdict(old(tags)),asdict(way_policy(tags))
    return {'kind':'way','id':identity,'tags':tags,'before':before,'after':after,'eligibilityGained':before['reason'] is not None and after['reason'] is None,'conditionalSpeedStatus':'static-minimum'}


def fixture():return [[100,200,300],[0,0,10000,0,20000,0],[0,2],[0,1,2],[(10,0.0,0.0,0,3)],[]]


class Controls(unittest.TestCase):
    def test_numeric_policy_prices_every_primitive_and_independent_source_witness(self):
        args=fixture();r=record({'highway':'primary','maxspeed':'80','maxspeed:conditional':'20 @ wet'})
        ways,arcs,changed=augment(*args,[r]);self.assertEqual(len(arcs),2)
        ms=2*math.ceil(distance_m([0,0],[.001,0])*3600/20)
        self.assertEqual(arcs[0],(0,1,0,0,2,1,ms));self.assertEqual(arcs[1][-1],ms)
        replay=SourceReplay(args[0],args[1],args[2],args[3],ways,arcs,[],set(),[])
        ticks=(ms+124)//125
        witness=replay.audit({'sourceNodeIds':[100,300]},{'ticks':ticks,'steps':[{'arc':0,'kind':'full','ticks':ticks}]},[4,4])
        self.assertEqual(witness['nativeNodeIds'],[100,200,300]);self.assertEqual(changed[0]['newPreClosureArcs'],2)

    def test_directional_permission_and_restriction_closure_are_not_relaxed(self):
        from coarse_osm_packed_capture_v1 import encode
        args=fixture();r=record({'highway':'primary','oneway':'-1','maxspeed:conditional':'20 @ wet'})
        ways,arcs,_=augment(*args,[r]);self.assertEqual(len(arcs),1);self.assertEqual(arcs[0][5],-1)
        fields,_,counts=encode(args[0],args[1],args[2],[4,4],args[3],ways,arcs,{10},[],[])
        self.assertEqual(counts['arcs'],0);self.assertEqual(fields['targets.u24'],b'')

    def test_all_cuts_and_old_data_preserved_without_source_mutation(self):
        args=fixture();args[2]=[0,1,2]
        r=record({'highway':'primary','maxspeed:conditional':'20 @ wet'});original=copy.deepcopy((args,r))
        _,arcs,_=augment(*args,[r]);self.assertEqual(len(arcs),4)
        self.assertEqual({a[3:5] for a in arcs},{(0,1),(1,2)})
        self.assertEqual((args,r),original)
        args[4].append((20,40,40,0,5));args[3].extend([0,2]);args[5]=[(0,2,1,0,1,1,1000)]
        ways,arcs,_=augment(*args,[r]);self.assertEqual(ways[1],args[4][1]);self.assertEqual(arcs[0],args[5][0])

    def test_access_unknown_values_and_malformed_source_records_never_open(self):
        for extra in ({'motorcar:conditional':'no @ night'},{'access':'private'},{'maxspeed:conditional':'25 mph'}):
            args=fixture();r=record({'highway':'primary','maxspeed:conditional':'20 @ wet'}|extra)
            self.assertEqual(augment(*args,[r])[1],[])
        r=record({'highway':'primary','maxspeed:conditional':'20 @ wet'});r['after']['forward']=30
        with self.assertRaises(AssertionError):augment(*fixture(),[r])

    def test_duplicate_candidates_and_existing_arcs_refused(self):
        r=record({'highway':'primary','maxspeed:conditional':'20 @ wet'})
        with self.assertRaises(AssertionError):augment(*fixture(),[r,r])
        args=fixture();args[-1]=[(0,1,0,0,2,1,1000)]
        with self.assertRaises(AssertionError):augment(*args,[r])


if __name__=='__main__':unittest.main()
