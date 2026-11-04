"""Independent all-native-point distances, source metadata and lineage controls."""
from copy import deepcopy
import math
import unittest

from coarse_osm_lineage_v1 import prepare,Access,query,build,CAPS,csr
from coarse_osm_backbone_v1_test import fixture as source_fixture,factory,WINDOWS,STATE,distance,floyd
from coarse_osm_backbone_v1 import build as old_build,MAJOR
from coarse_timing_input import PilotError

LIMITS=CAPS|{'nodeCanonicalBytes':1048576}

def fixture():return source_fixture(relations=[(1,[{'type':'way','ref':1,'role':'via'}])])
def baseline(rows):return old_build(factory(rows),snapshot=STATE,windows=WINDOWS,caps=LIMITS)['profiles'][1]
def run(rows=None):
    rows=fixture() if rows is None else rows;output={}
    def emit(name,raw):
        assert name not in output;output[name]=bytes(raw)
    return build(factory(rows),snapshot=STATE,windows=WINDOWS,baseline=baseline(rows),caps=LIMITS,writer=emit),output

def verify_all_points(rows):
    nodes,g,*_=prepare(factory(rows),snapshot=STATE,windows=WINDOWS,caps=LIMITS)
    access=Access(g,nodes);graph=csr(len(g.vertices),g.starts,g.ends,g.meters);active=[i for i,d in enumerate(g.degree) if d]
    points={r['element']['id']:[r['element']['lon'],r['element']['lat']] for r in rows if r['element']['type']=='node'};edges=[]
    for r in rows:
        e=r['element']
        if e['type']=='way' and e['tags'].get('highway') in MAJOR:
            edges.extend((a,b,distance(points[a],points[b])) for a,b in zip(e['nodes'],e['nodes'][1:]))
    expected=floyd([nodes.ids[i] for i in active],edges);work=[0]
    for a in active:
        for b in active:
            actual,_,_=query(g,access,graph,a,b,work,LIMITS,lambda:None);wanted=expected[nodes.ids[a],nodes.ids[b]]
            if math.isinf(wanted):assert actual is None
            else:assert actual is not None and math.isclose(actual,wanted,rel_tol=1e-10,abs_tol=1e-6),(a,b,actual,wanted)
    return nodes,g,access


class Tests(unittest.TestCase):
    def test_way_relation_metadata_moves_to_full_chain_lineage(self):
        report,out=run();self.assertEqual((report['oldAnchors'],report['anchors'],report['contractedEdges']),(3,2,1))
        self.assertEqual(report['geometryNodeOccurrences'],3);self.assertEqual(report['relationContext']['relations'],1)
        self.assertGreater(report['internalNativePoints'],0);self.assertIn('provenance/alias-prefix.f64',out)
        verify_all_points(fixture())
    def test_every_explicit_relation_node_and_tag_stays_an_anchor(self):
        for rows in (source_fixture(relations=[(1,[{'type':'node','ref':2,'role':'via'}])]),source_fixture(node_tags={2:{'custom':'unknown'}})):
            report,_=run(rows);self.assertEqual(report['anchors'],3);verify_all_points(rows)
    def test_way_end_attribute_boundaries_and_real_junctions_survive(self):
        for ways in ([(1,[1,2],{'highway':'primary'}),(2,[2,3],{'highway':'primary','oneway':'-1'})],[(1,[1,2,3],{'highway':'primary'}),(2,[2,3],{'highway':'primary','access':'private'})]):
            verify_all_points(source_fixture(ways=ways))
    def test_closed_parallel_repeated_and_zero_length_paths_preserve_all_points(self):
        for ways in ([(1,[1,2,3,1],{'highway':'primary'})],[(1,[1,2,3],{'highway':'primary'}),(2,[1,3],{'highway':'primary'})],[(1,[1,1],{'highway':'primary'})],[(1,[1,2,2,3],{'highway':'primary'})]):
            verify_all_points(source_fixture(ways=ways,relations=[(1,[{'type':'way','ref':1,'role':'via'}])]))
    def test_coincident_coordinates_do_not_join_distinct_native_components(self):
        verify_all_points(source_fixture(points={1:[0,0],2:[.001,0],3:[.001,0],4:[.002,0]},ways=[(1,[1,2],{'highway':'primary'}),(2,[3,4],{'highway':'primary'})]))
    def test_internal_point_queries_on_same_and_different_chains(self):
        points={i:[i/1000,0] for i in range(1,12)};ways=[(1,list(range(1,7)),{'highway':'primary'}),(2,list(range(6,12)),{'highway':'secondary'})]
        verify_all_points(source_fixture(points,ways,relations=[(1,[{'type':'way','ref':1,'role':'from'},{'type':'way','ref':2,'role':'to'}])]))
    def test_original_frozen_pairs_are_not_resampled(self):
        rows=fixture();old=baseline(rows);report,_=run(rows)
        self.assertEqual([(q['windowId'],q['sourceNodeIds']) for q in report['queries']],[(q['windowId'],q['sourceNodeIds']) for q in old['queries']])
        self.assertEqual([q['lineageMeters'] for q in report['queries']],[q['rawMeters'] for q in old['queries']])
    def test_input_digest_drift_missing_nodes_and_caps_fail(self):
        rows=fixture();rows[0]['element']['tags']['changed']='yes'
        with self.assertRaises(PilotError):prepare(factory(rows),snapshot=STATE,windows=WINDOWS,caps=LIMITS)
        with self.assertRaises(PilotError):prepare(factory(source_fixture()),snapshot=STATE,windows=WINDOWS,caps=LIMITS|{'geometryReferences':1})
    def test_unselected_native_points_reject_instead_of_coordinate_joining(self):
        rows=source_fixture(points={1:[0,0],2:[.001,0],3:[.002,0],4:[0,0]},ways=[(1,[1,2,3],{'highway':'primary'}),(2,[4,4],{'highway':'service'})])
        nodes,g,access=verify_all_points(rows)
        with self.assertRaises(PilotError):query(g,access,csr(len(g.vertices),g.starts,g.ends,g.meters),3,3,[0],LIMITS,lambda:None)
    def test_all_native_id_bits_boundary_metadata_and_false_admissions(self):
        rows=source_fixture(points={1:[0,0],2:[.001,0],2**63-1:[.002,0]},ways=[(1,[1,2,2**63-1],{'highway':'primary'})],relations=[(1,[{'type':'way','ref':1,'role':'via'}])]);verify_all_points(rows)
        report,_=run()
        for key in ('carPolicyReviewed','etaQualified','nationalArtifactBuilt','vercelQualified','modelChanged'):self.assertFalse(report[key])

    def test_validation_pair_selection_cannot_change_graph_artifacts(self):
        rows=fixture();old=baseline(rows);outputs=[]
        for cases in (old['queries'],[]):
            out={};build(factory(rows),snapshot=STATE,windows=WINDOWS,baseline=old|{'queries':cases},caps=LIMITS,writer=lambda k,v:out.update({k:bytes(v)}));outputs.append(out)
        self.assertEqual(outputs[0],outputs[1])
    def test_original_window_cuts_and_outside_nodes_remain_anchors(self):
        rows=source_fixture(points={1:[-.003,0],2:[-.002,0],3:[0,0],4:[.002,0],5:[.003,0]},ways=[(1,[1,2,3,4,5],{'highway':'primary'})],relations=[(1,[{'type':'way','ref':1,'role':'via'}])])
        nodes,g,*_=prepare(factory(rows),snapshot=STATE,windows=[{'id':'a','bbox':[-.001,-.001,.001,.001]}],caps=LIMITS)
        self.assertEqual(len(g.vertices),5);self.assertEqual(len(g.starts),4)
