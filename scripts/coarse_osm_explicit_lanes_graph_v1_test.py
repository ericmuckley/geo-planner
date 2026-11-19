import copy
from dataclasses import asdict
import unittest

from coarse_osm_car_conditional_speed_v1 import way_policy as previous
from coarse_osm_car_explicit_lanes_v1 import POLICY, classify_way
from coarse_osm_explicit_lanes_graph_v1 import augment
from coarse_osm_packed_capture_v1 import encode
from evaluate_osm_conditional_capture_v1 import SourceReplay


def fixture():
    role=POLICY['roles'].index('primary')
    return [[100,200,300],[0,0,10000,0,20000,0],[0,2],[0,1,2],[(10,0.,0.,(6<<8)|(role<<4),3)],[]]


def record(**extra):
    tags={'highway':'primary','oneway':'yes','lanes':'2','access:lanes':'psv|yes'}|extra
    result=classify_way(tags);before=asdict(previous(tags));after=asdict(result.pop('policy'))
    return {'kind':'way','id':10,'tags':tags,'before':before,'after':after,'eligibilityGained':before!=after,**result}


class Controls(unittest.TestCase):
    def test_source_default_flags_and_every_primitive_price_independently_replay(self):
        args=fixture();r=record();ways,arcs,changed=augment(*args,[r])
        self.assertEqual(len(arcs),1);self.assertEqual(arcs[0][3:6],(0,2,1))
        role=POLICY['roles'].index('primary');self.assertEqual(ways[0][3],1|12|(role<<4))
        replay=SourceReplay(args[0],args[1],args[2],args[3],ways,arcs,[],set(),[])
        ticks=(arcs[0][-1]+124)//125
        witness=replay.audit({'sourceNodeIds':[100,300]},{'ticks':ticks,'steps':[{'arc':0,'kind':'full','ticks':ticks}]},[4,4])
        self.assertEqual(witness['nativeNodeIds'],[100,200,300]);self.assertEqual(changed[0]['newPreClosureArcs'],1)

    def test_reverse_direction_and_explicit_speed_flags(self):
        args=fixture();ways,arcs,_=augment(*args,[record(oneway='-1',maxspeed='35 mph')])
        self.assertEqual(arcs[0][:2],(1,0));self.assertEqual(arcs[0][5],-1)
        self.assertEqual(ways[0][3]&15,2);self.assertEqual(ways[0][1],0.)
        self.assertAlmostEqual(ways[0][2],35*1.609344)

    def test_all_anchor_cuts_old_arcs_and_inputs_preserved(self):
        args=fixture();args[2]=[0,1,2]
        args[3].extend([0,2]);args[4].append((20,40.,40.,3,5));args[5].append((0,2,1,0,1,1,1000))
        r=record();saved=copy.deepcopy((args,r));ways,arcs,_=augment(*args,[r])
        self.assertEqual((args,r),saved);self.assertEqual(ways[1],args[4][1]);self.assertEqual(arcs[0],args[5][0])
        self.assertEqual({a[3:5] for a in arcs[1:]},{(0,1),(1,2)})

    def test_source_relation_closures_and_ambiguous_lane_fallback_stay(self):
        args=fixture();ways,arcs,_=augment(*args,[record()])
        _,_,counts=encode(args[0],args[1],args[2],[4,4],args[3],ways,arcs,{10},[],[])
        self.assertEqual(counts['arcs'],0)
        for extra in [{'oneway':'no'},{'access:lanes':'|yes'},{'motorcar':'private'}]:
            self.assertEqual(augment(*fixture(),[record(**extra)])[1],[])

    def test_forged_flags_records_and_duplicate_or_existing_way_refused(self):
        r=record();r['after']['forward']=30
        with self.assertRaises(AssertionError):augment(*fixture(),[r])
        r=record();r['explicitOrdinaryLaneIndices']=[0]
        with self.assertRaises(AssertionError):augment(*fixture(),[r])
        r=record()
        with self.assertRaises(AssertionError):augment(*fixture(),[r,r])
        args=fixture();args[4][0]=(10,0.,0.,0,3)
        with self.assertRaises(AssertionError):augment(*args,[r])
        args=fixture();args[5]=[(0,1,0,0,2,1,1000)]
        with self.assertRaises(AssertionError):augment(*args,[r])


if __name__=='__main__':unittest.main()
