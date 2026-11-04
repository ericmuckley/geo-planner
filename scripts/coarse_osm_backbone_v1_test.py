"""Native contraction invariants and independent all-pairs geometric oracle."""
from collections import defaultdict
from copy import deepcopy
import gzip
import hashlib
import io
import math
import struct
import unittest

from coarse_osm_backbone_v1 import (CAPS,EDGE,PROFILES,REL_NODE,REL_WAY,TAGGED,OUTSIDE,BOUNDARY,analyze,build,contract,point,read_nodes,selected)
from coarse_osm_records import canonical
from coarse_timing_input import PilotError

STATE='2026-10-25T21:21:21Z'
WINDOWS=[{'id':'a','bbox':[-1,-1,1,1]},{'id':'empty','bbox':[2,2,3,3]}]


def fixture(points=None,ways=None,node_tags=None,relations=None):
    points=points or {1:[0.,0.],2:[.001,0.],3:[.002,0.]};ways=ways if ways is not None else [(1,[1,2,3],{'highway':'primary','maxspeed':'55 mph','access':'private'})]
    common={'version':1,'timestamp':'2026-10-20T00:00:00Z','visible':True}
    nodes=[common|{'type':'node','id':i,'lon':p[0],'lat':p[1],'tags':(node_tags or {}).get(i,{})} for i,p in sorted(points.items())];by_id={e['id']:e for e in nodes}
    elements=[*nodes,*[common|{'type':'relation','id':i,'tags':{'type':'restriction'},'members':members} for i,members in (relations or [])],*[common|{'type':'way','id':i,'nodes':refs,'tags':tags} for i,refs,tags in ways]];rows=[]
    for e in elements:
        r={'publisherStateUtc':STATE,'element':e,'elementSha256':hashlib.sha256(canonical(e)).hexdigest(),'windowIds':['a']}
        if e['type']=='way':r['geometryDependencySha256']=hashlib.sha256(canonical([STATE,[by_id[i] for i in e['nodes']]])).hexdigest()
        rows.append(r)
    return rows


def factory(rows):
    raw=b''.join(canonical(r)+b'\n' for r in rows)
    return lambda:io.BytesIO(raw)


def run(rows=None,windows=WINDOWS,caps=None):
    output={};limits=CAPS|{'nodeCanonicalBytes':1048576}|(caps or {})
    def writer(name,raw):
        assert name not in output;output[name]=bytes(raw)
    report=build(factory(fixture() if rows is None else rows),snapshot=STATE,windows=windows,caps=limits,writer=writer)
    return report,output


def graph(rows):
    caps=CAPS|{'nodeCanonicalBytes':1048576};f=factory(rows)
    with f() as stream:nodes,receipt=read_nodes(stream,STATE,caps=caps)
    graphs,_=analyze(f,nodes,receipt,WINDOWS,PROFILES,caps,lambda:None);contract(f,nodes,receipt,graphs,caps,lambda:None)
    return nodes,graphs


def distance(a,b):
    x,y=map(math.radians,(a[1],b[1]));h=math.sin((y-x)/2)**2+math.cos(x)*math.cos(y)*math.sin(math.radians(b[0]-a[0])/2)**2
    return 12742000*math.atan2(math.sqrt(h),math.sqrt(1-h))


def floyd(vertices,edges):
    d={(a,b):0. if a==b else math.inf for a in vertices for b in vertices}
    for a,b,length in edges:d[a,b]=min(d[a,b],length);d[b,a]=min(d[b,a],length)
    for k in vertices:
        for a in vertices:
            for b in vertices:d[a,b]=min(d[a,b],d[a,k]+d[k,b])
    return d


class Tests(unittest.TestCase):
    def test_simple_chain_contracts_without_losing_geometry_or_length(self):
        report,out=run();p=report['profiles'][0]
        self.assertEqual((p['primitiveEdges'],p['contractedEdges'],p['contractedVertices']),(2,1,2));self.assertEqual(p['geometryNodeOccurrences'],3)
        self.assertAlmostEqual(p['distanceMeters'],distance([0,0],[.002,0]),delta=1e-7);self.assertFalse(report['etaModelQualified']);self.assertFalse(report['vercelPackageQualified'])
        self.assertEqual(len(out['all-highways/provenance/edges.bin']),EDGE.size)

    def test_real_junction_and_way_metadata_boundaries_are_retained(self):
        points={1:[0,0],2:[.001,0],3:[.002,0],4:[.001,.001]};ways=[(1,[1,2,3],{'highway':'primary'}),(2,[2,4],{'highway':'primary'})]
        report,_=run(fixture(points,ways));p=report['profiles'][0];self.assertEqual(p['contractedEdges'],3);self.assertGreater(p['anchorReasons']['degreeNotTwo'],0)
        report,_=run(fixture(ways=[(1,[1,2],{'highway':'primary'}),(2,[2,3],{'highway':'primary','oneway':'-1'})]));self.assertEqual(report['profiles'][0]['contractedEdges'],2)

    def test_every_tagged_node_is_an_anchor(self):
        for tags in ({'barrier':'gate'},{'highway':'traffic_signals'},{'maxspeed':'20'},{'custom':'unknown'}):
            report,_=run(fixture(node_tags={2:tags}));self.assertEqual(report['profiles'][0]['contractedEdges'],2);self.assertEqual(report['profiles'][0]['anchorReasons']['taggedNode'],1)

    def test_relation_node_and_way_context_are_never_collapsed(self):
        for members in ([{'type':'node','ref':2,'role':'via'}],[{'type':'way','ref':1,'role':'via'}]):
            report,_=run(fixture(relations=[(1,members)]));self.assertEqual(report['profiles'][0]['contractedEdges'],2);self.assertEqual(report['relationContext']['relations'],1)
        report,_=run(fixture(relations=[(1,[{'type':'way','ref':99,'role':'to'},{'type':'node','ref':999,'role':'via'},{'type':'relation','ref':99,'role':'context'}])]))
        self.assertEqual(report['relationContext']['missingMemberWayIds'],1);self.assertEqual(report['relationContext']['missingMemberNodeOccurrences'],1);self.assertEqual(report['relationContext']['missingMemberRelationIds'],1)

    def test_window_boundary_and_outside_native_nodes_are_preserved(self):
        points={1:[-.003,0],2:[-.002,0],3:[0,0],4:[.002,0],5:[.003,0]};rows=fixture(points,[(1,[1,2,3,4,5],{'highway':'primary'})]);windows=[{'id':'a','bbox':[-.001,-.001,.001,.001]}]
        report,_=run(rows,windows);p=report['profiles'][0];self.assertEqual(p['contractedEdges'],4);self.assertEqual(p['anchorReasons']['outsideArea'],4);self.assertEqual(p['anchorReasons']['areaBoundary'],3)

    def test_closed_loops_parallel_edges_and_zero_length_edges_survive(self):
        for ways,expected in [([(1,[1,2,3,1],{'highway':'primary'})],1),([(1,[1,2,3],{'highway':'primary'}),(2,[1,3],{'highway':'primary'})],2),([(1,[1,1],{'highway':'primary'})],1)]:
            report,_=run(fixture(ways=ways));self.assertEqual(report['profiles'][0]['contractedEdges'],expected);self.assertEqual(report['profiles'][0]['rawComponents']['count'],report['profiles'][0]['contractedComponents']['count'])

    def test_coincident_coordinates_with_different_ids_do_not_connect(self):
        points={1:[0,0],2:[.001,0],3:[.001,0],4:[.002,0]};report,_=run(fixture(points,[(1,[1,2],{'highway':'primary'}),(2,[3,4],{'highway':'primary'})]))
        self.assertEqual(report['profiles'][0]['rawComponents']['count'],2);self.assertEqual(report['profiles'][0]['contractedComponents']['count'],2)

    def test_profile_selection_preserves_full_input_and_empty_area_denominators(self):
        report,_=run(fixture(ways=[(1,[1,2],{'highway':'service'}),(2,[2,3],{'highway':'footway'})]));a,b=report['profiles'];self.assertEqual(a['selectedWays'],2);self.assertEqual(b['selectedWays'],0);self.assertEqual(b['contractedEdges'],0);self.assertEqual(report['captureReceipt']['types']['way'],2);self.assertEqual(a['windows']['empty']['ways'],0)

    def test_binary_counts_gzip_roundtrip_and_native_large_ids(self):
        big=2**63-1;rows=fixture(points={big-2:[0,0],big-1:[.001,0],big:[.002,0]},ways=[(big,[big-2,big-1,big],{'highway':'primary'})]);report,out=run(rows)
        self.assertEqual(EDGE.unpack(out['all-highways/provenance/edges.bin'])[0],big)
        for p in report['profiles']:
            routing=[raw for name,raw in out.items() if name.startswith(p['id']+'/routing/') and not name.endswith('.gz')]
            self.assertEqual(sum(map(len,routing)),p['routingDecodedBytes'])
        for name,raw in out.items():
            if name.endswith('.gz'):self.assertEqual(gzip.decompress(raw),out[name[:-3]])

    def test_independent_all_pairs_oracle_matches_raw_and_contracted_graphs(self):
        cases=[fixture(),fixture(ways=[(1,[1,2,3,1],{'highway':'primary'})]),fixture(ways=[(1,[1,2,3],{'highway':'primary'}),(2,[1,3],{'highway':'service'})]),fixture(points={1:[0,0],2:[.001,0],3:[.001,0],4:[.002,0]},ways=[(1,[1,2],{'highway':'primary'}),(2,[3,4],{'highway':'primary'})])]
        for rows in cases:
            nodes,graphs=graph(rows);by_id={r['element']['id']:r['element'] for r in rows if r['element']['type']=='node'}
            for g in graphs:
                primitive=[];vertices=set()
                for r in rows:
                    e=r['element']
                    if e['type']!='way' or not selected(g.profile,e):continue
                    for a,b in zip(e['nodes'],e['nodes'][1:]):vertices.update((a,b));primitive.append((a,b,distance([by_id[a]['lon'],by_id[a]['lat']],[by_id[b]['lon'],by_id[b]['lat']])))
                anchor_ids=[int(nodes.ids[i]) for i in g.vertices];compact=[(anchor_ids[a],anchor_ids[b],length) for a,b,length in zip(g.starts,g.ends,g.meters)];expected=floyd(vertices,primitive);actual=floyd(anchor_ids,compact)
                for a in anchor_ids:
                    for b in anchor_ids:
                        if math.isinf(expected[a,b]):self.assertTrue(math.isinf(actual[a,b]))
                        else:self.assertAlmostEqual(actual[a,b],expected[a,b],delta=1e-7)

    def test_source_snapshot_raw_fields_geometry_and_node_order_drift_fail(self):
        for mode in ('snapshot','field','geometry','order','missing'):
            rows=fixture()
            if mode=='snapshot':rows[0]['publisherStateUtc']='wrong'
            if mode=='field':rows[0]['elementSha256']='0'*64
            if mode=='geometry':rows[-1]['geometryDependencySha256']='0'*64
            if mode=='order':rows[0],rows[1]=rows[1],rows[0]
            if mode=='missing':rows.pop(0)
            with self.subTest(mode=mode),self.assertRaises(PilotError):run(rows)

    def test_all_input_geometry_and_search_caps_are_effective(self):
        for key in ('records','rowBytes','inputBytes','nodeCanonicalBytes','geometryReferences','edges','chainReferences','querySettles'):
            with self.subTest(cap=key),self.assertRaises(PilotError):run(fixture(node_tags={2:{'barrier':'gate'}}),caps={key:1})
        star=fixture(points={1:[0,0],2:[.001,0],3:[0,.001],4:[-.001,0]},ways=[(1,[1,2],{'highway':'primary'}),(2,[1,3],{'highway':'primary'}),(3,[1,4],{'highway':'primary'})])
        with self.assertRaises(PilotError):run(star,caps={'queryHeap':1})
        with self.assertRaises(PilotError):run(fixture(relations=[(1,[{'type':'node','ref':1,'role':'via'},{'type':'node','ref':2,'role':'via'}])]),caps={'relationReferences':1})

    def test_stream_drift_between_passes_fails_closed(self):
        count=[0];rows=fixture();raw=factory(rows)().read()
        def changed():count[0]+=1;return io.BytesIO(raw if count[0]==1 else raw+b'\n')
        with self.assertRaises((PilotError,ValueError)):build(changed,snapshot=STATE,windows=WINDOWS,caps=CAPS|{'nodeCanonicalBytes':1048576})

    def test_original_direction_and_access_do_not_become_car_permission(self):
        report,_=run();self.assertTrue(report['undirectedGeometryOnly']);self.assertFalse(report['carPermissionReviewed']);self.assertFalse(report['etaModelQualified']);self.assertFalse(report['nationalFootprintQualified']);self.assertTrue(all(not p['carPermissionReviewed'] for p in report['profiles']))

    def test_duplicate_invalid_areas_and_external_deadline_are_rejected(self):
        with self.assertRaises(PilotError):run(windows=[WINDOWS[0],WINDOWS[0]])
        with self.assertRaises(PilotError):run(windows=[{'id':'a','bbox':[0,0,0,1]}])
        def expired():raise PilotError('deadline')
        with self.assertRaisesRegex(PilotError,'deadline'):build(factory(fixture()),snapshot=STATE,windows=WINDOWS,caps=CAPS|{'nodeCanonicalBytes':1048576},check=expired)
