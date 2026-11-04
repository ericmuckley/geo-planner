"""Independent static-car state oracle and compact cost/identity controls."""
from array import array
from copy import deepcopy
import math,random,unittest
from unittest.mock import patch
import io

from import_roads import access_allowed,speed_kph,distance_m
from coverage_census import directions
from coarse_osm_car_policy_v1 import POLICY,way_policy,node_policy,restriction_policy
from coarse_osm_car_codec_v1 import Costs,Reverses,ticks,MAX_U32
from coarse_osm_car_graph_v1 import Graph,read_metadata,BLOCKED,SIGNAL,REVERSAL
from coarse_osm_car_payload_v1 import Payload,query_native
from coarse_osm_lineage_v1 import prepare
from coarse_osm_backbone_v1_test import fixture as captured_fixture,factory,STATE,WINDOWS
from coarse_osm_lineage_v1_test import LIMITS
from coarse_timing_input import PilotError


def fixture(ways=None,points=None,node_tags=None,relations=None):
    rows=captured_fixture(points,ways if ways is not None else [(1,[1,2,3],{'highway':'primary'})],node_tags,relations)
    return rows


def graphs(rows):
    f=factory(rows);nodes,g,receipt,*_=prepare(f,snapshot=STATE,windows=WINDOWS,caps=LIMITS)
    selected=array('I',(i for i,d in enumerate(g.degree) if d));mapping={v:i for i,v in enumerate(selected)}
    geom={'selected':selected,'xy':array('i',(v for i in selected for v in (nodes.x[i],nodes.y[i]))),'anchors':[mapping[v] for v in g.vertices],
        'edges':list(zip(g.ways,g.first,g.last,g.starts,g.ends,g.meters)),'offsets':g.geometry_offsets,'geometry':array('I',(mapping[i] for i in g.geometry))}
    with f() as stream:meta=read_metadata(stream,geom,receipt,STATE)
    return Graph(geom,meta,raw=True),Graph(geom,meta),geom,meta


def independent_cost(graph,source,target):
    if source==target:return 0
    arcs=graph.arcs;n=len(arcs);start=n;goal=n+1;edges=[]
    for i,a in enumerate(arcs):
        if a['tail']==source:edges.append((start,i,a['costMs']))
        if a['head']==target:edges.append((i,goal,0))
        for j,b in enumerate(arcs):
            if a['head']!=b['tail']:continue
            node=a['head'];flag=graph.metadata['flags'][node]
            reversal=a['edge']==b['edge'] and a['part']==b['part'] and a['dir']==-b['dir']
            if flag&BLOCKED or reversal and not flag&REVERSAL:continue
            applicable=[r for r in graph.metadata['rules'] if r['fromWay']==a['way'] and r['via']==graph.metadata['ids'][node]];negative=False;only=[]
            for r in applicable:
                match=b['way']==r['toWay']
                if r['fromWay']==r['toWay']:match=match and (reversal if r['kind'].endswith('u_turn') else not reversal)
                if r['kind'].startswith('only_'):only.append(match)
                elif match:negative=True
            if negative or only and not any(only):continue
            edges.append((i,j,b['costMs']+(5000 if flag&SIGNAL else 0)+(20000 if reversal else 0)))
    labels=[math.inf]*(n+2);labels[start]=0
    for _ in range(n+1):
        changed=False
        for a,b,cost in edges:
            if labels[a]+cost<labels[b]:labels[b]=labels[a]+cost;changed=True
        if not changed:break
    return None if math.isinf(labels[goal]) else labels[goal]


def verify(rows,oracle=True):
    raw,compact,_,_=graphs(rows);out={};compact.serialize(lambda k,v:out.update({k:v}));payload=Payload(out.__getitem__)
    for a in range(raw.nodes):
        for b in range(raw.nodes):
            before=raw.query(a,b);after=compact.query(a,b);encoded=compact.query(a,b,quantized=True)
            assert query_native(payload,compact,a,b)==encoded['costMs'],(a,b,'binary query mismatch')
            assert before['costMs']==after['costMs'],(a,b,before,after)
            if oracle:assert before['costMs']==independent_cost(raw,a,b),(a,b,before)
            if after['costMs'] is None:assert encoded['costMs'] is None
            else:assert after['costMs']<=encoded['costMs']<=after['costMs']+124*after['fragments']
    return raw,compact


class PolicyTests(unittest.TestCase):
    def test_direction_access_and_speed_precedence_match_existing_reference(self):
        for role in POLICY['roles']:
            for extra in ({},{'oneway':'-1'},{'oneway':'yes'},{'oneway':'no'},{'motor_vehicle:backward':'no'},{'access':'no','motorcar':'yes'},
                          {'access':'private'},{'maxspeed':'55 mph'},{'maxspeed:forward':'40','maxspeed:backward':'30 kph'},
                          {'maxspeed':'signals'},{'maxspeed:backward':'0'},{'access:conditional':'yes @ Mo'},{'motor_vehicle:lanes':'yes|no'}):
                props={'highway':role}|extra;p=way_policy(props)
                self.assertEqual(int(p.forward is not None)+int(p.backward is not None),directions(props),props)
    def test_ferries_are_excluded_without_geographic_exceptions(self):
        for role in POLICY['roles']:
            for ferry in ({'route':'ferry'},{'ferry':'primary'},{'ferry':'yes'}):self.assertEqual(way_policy({'highway':role}|ferry).reason,'vehicle-ferry')
        self.assertIsNone(way_policy({'highway':'primary','ferry':'no'}).reason)
    def test_explicit_and_missing_speed_defaults_have_clear_provenance(self):
        p=way_policy({'highway':'primary'});self.assertEqual((p.forward,p.backward),(55,55));self.assertTrue(p.forward_default)
        p=way_policy({'highway':'primary','maxspeed':'25 mph'});self.assertAlmostEqual(p.forward,40.2336);self.assertFalse(p.forward_default)
        self.assertEqual(way_policy({'highway':'primary','maxspeed':'161'}).reason,'unsupported-speed')
    def test_barriers_permissions_unknown_conditions_and_signal_flags(self):
        for props,blocked in (({'barrier':'gate'},True),({'barrier':'gate','motorcar':'yes'},False),({'barrier':'gate','motorcar':'no','access':'yes'},True),({'access:conditional':'no @ Mo'},True),({'barrier':'bollard','motorcar':'yes'},True)):
            self.assertEqual(node_policy(props)['blocked'],blocked)
        self.assertTrue(node_policy({'highway':'traffic_signals'})['signal'])
    def test_restriction_modes_exceptions_and_unsupported_closures(self):
        base={'id':1,'tags':{'type':'restriction','restriction':'no_left_turn'},'members':[{'type':'way','ref':1,'role':'from'},{'type':'node','ref':2,'role':'via'},{'type':'way','ref':3,'role':'to'}]}
        self.assertEqual(restriction_policy(base)['status'],'via-node')
        for tags in ({'except':'motorcar'},{'type':'restriction:bicycle'}):self.assertEqual(restriction_policy(base|{'tags':base['tags']|tags})['status'],'non-car')
        self.assertEqual(restriction_policy(base|{'tags':base['tags']|{'restriction:conditional':'no_left_turn @ Mo'}})['status'],'closed-unsupported')
        broken=deepcopy(base);broken['members'][1]={'type':'way','ref':2,'role':'via'};self.assertEqual(restriction_policy(broken)['reason'],'via-way')


class CodecTests(unittest.TestCase):
    def test_zero_u16_sentinel_large_ticks_and_lossless_overflow(self):
        costs=[0,1,124,125,126,65534*125,65535*125,65536*125,MAX_U32*125]
        packed=Costs(costs);self.assertEqual([packed.get(i) for i in range(len(costs))],[ticks(c) for c in costs]);self.assertEqual(len(packed.indices),3)
        self.assertEqual(packed.bytes,2*len(costs)+24)
    def test_invalid_costs_indices_and_tick_overflow_reject(self):
        for cost in (-1,True,1.5,(MAX_U32+1)*125):
            with self.assertRaises(PilotError):Costs([cost])
        p=Costs([1])
        for index in (-1,1,True):
            with self.assertRaises(PilotError):p.get(index)
    def test_reverse_ordinals_roundtrip_and_high_degree_overflow(self):
        arcs=[{'head':1,'reverse':255}]+[{'head':2,'reverse':None} for _ in range(254)]+[{'head':0,'reverse':0}]
        offsets=array('I',[0,1,256,256]);codec=Reverses(arcs,offsets,{0:0,1:1,2:2})
        self.assertEqual(codec.get(0,1,offsets),255);self.assertEqual(codec.get(255,0,offsets),0);self.assertIsNone(codec.get(1,2,offsets));self.assertEqual(len(codec.indices),1)
    def test_quantization_never_understates_or_loses_more_than124ms(self):
        rng=random.Random(20261101)
        for _ in range(10000):
            ms=rng.randrange(0,10**8);self.assertTrue(ms<=ticks(ms)*125<=ms+124)


class GraphTests(unittest.TestCase):
    def test_internal_point_source_target_and_quantized_costs(self):verify(fixture())
    def test_oneway_forward_reverse_and_directional_speeds(self):
        for extra in ({'oneway':'yes'},{'oneway':'-1'},{'maxspeed:forward':'30','maxspeed:backward':'60'}):verify(fixture(ways=[(1,[1,2,3],{'highway':'primary'}|extra)]))
    def test_signal_delay_and_control_point_permissions(self):
        for props in ({'highway':'traffic_signals'},{'barrier':'gate'},{'barrier':'gate','motorcar':'yes'}):verify(fixture(node_tags={2:props}))
    def test_no_and_only_turns_with_legal_detours(self):
        points={1:[0,0],2:[.001,0],3:[.002,0],4:[.001,.001]};ways=[(1,[1,2],{'highway':'primary'}),(2,[2,3],{'highway':'primary'}),(3,[2,4,3],{'highway':'secondary'})]
        for kind in ('no_right_turn','only_right_turn','no_u_turn','only_u_turn'):
            to=1 if 'u_turn' in kind else 2
            rows=fixture(points=points,ways=ways,relations=[(99,[{'type':'way','ref':1,'role':'from'},{'type':'node','ref':2,'role':'via'},{'type':'way','ref':to,'role':'to'}])])
            # Rebuild the relation's frozen source hash after specifying its rule.
            import hashlib
            from coarse_osm_records import canonical
            for r in rows:
                if r['element']['type']=='relation':r['element']['tags']['restriction']=kind;r['elementSha256']=hashlib.sha256(canonical(r['element'])).hexdigest()
            verify(rows)
    def test_unsupported_via_way_and_conditional_relations_close_members(self):
        verify(fixture(relations=[(1,[{'type':'way','ref':1,'role':'from'},{'type':'way','ref':99,'role':'via'},{'type':'way','ref':2,'role':'to'}])]))
    def test_closed_parallel_zero_and_repeated_native_geometry(self):
        for refs in ([1,2,3,1],[1,2,2,3],[1,1]):verify(fixture(ways=[(1,refs,{'highway':'primary'})]))
        verify(fixture(ways=[(1,[1,2,3],{'highway':'primary'}),(2,[1,3],{'highway':'secondary'})]))
    def test_coincident_native_points_do_not_connect(self):
        verify(fixture(points={1:[0,0],2:[.001,0],3:[.001,0],4:[.002,0]},ways=[(1,[1,2],{'highway':'primary'}),(2,[3,4],{'highway':'primary'})]))
    def test_private_and_ferry_ways_remain_explicit_unreachable_cases(self):
        for extra in ({'access':'private'},{'route':'ferry'}):
            raw,compact=verify(fixture(ways=[(1,[1,2,3],{'highway':'primary'}|extra)]));self.assertIsNone(compact.query(0,2)['costMs'])
    def test_serialized_arrays_decode_costs_reverse_and_sparse_rules(self):
        _,g=verify(fixture());out={};report=g.serialize(lambda k,v:out.update({k:v}))
        self.assertEqual(sum(map(len,out.values())),report['payloadBytes']);self.assertEqual(report['arcs'],2)
        self.assertEqual(list(struct_unpack(out['targets.u32'],'I')),[1,0]);self.assertEqual(out['reverse.u8'],b'\x00\x00')
    def test_seeded_graphs_match_flat_state_relaxation_and_contraction(self):
        rng=random.Random(20261102)
        for _ in range(20):
            points={i:[i/1000,(i%2)/1000] for i in range(1,7)};ways=[(i+1,[rng.randrange(1,7) for _ in range(rng.randrange(2,5))],{'highway':'primary','oneway':rng.choice(('yes','-1','no'))}) for i in range(5)]
            verify(fixture(points=points,ways=ways))


class GuardTests(unittest.TestCase):
    def test_capture_receipt_and_deadline_reject_before_admission(self):
        rows=fixture();_,_,g,m=graphs(rows)
        with factory(rows)() as stream:
            with self.assertRaises(PilotError):read_metadata(stream,g,m['receipt']|{'rows':0},STATE)
        def expired():raise PilotError('deadline')
        with factory(rows)() as stream:
            with self.assertRaisesRegex(PilotError,'deadline'):read_metadata(stream,g,m['receipt'],STATE,expired)
    def test_record_relation_way_and_reference_caps(self):
        rows=fixture(relations=[(1,[{'type':'way','ref':1,'role':'from'},{'type':'node','ref':2,'role':'via'},{'type':'way','ref':1,'role':'to'}])]);_,_,g,m=graphs(rows)
        from coarse_osm_car_graph_v1 import CAPS
        for cap in ('records','relations','ways','references'):
            with patch.dict(CAPS,{cap:0}),factory(rows)() as stream:
                with self.assertRaises(PilotError):read_metadata(stream,g,m['receipt'],STATE)
    def test_graph_arc_query_heap_and_settle_caps(self):
        raw,g,geometry,metadata=graphs(fixture());from coarse_osm_car_graph_v1 import CAPS
        with patch.dict(CAPS,{'arcs':0}):
            with self.assertRaises(PilotError):Graph(geometry,metadata)
        with patch.dict(CAPS,{'querySettles':0}):
            with self.assertRaises(PilotError):g.query(0,2)
        with patch.dict(CAPS,{'queryHeap':0}):
            with self.assertRaises(PilotError):raw.query(0,2)
    def test_binary_corruption_and_reverse_identity_fail_closed(self):
        _,g,_,_=graphs(fixture());out={};g.serialize(lambda k,v:out.update({k:v}))
        for name,data in (('reverse.u8',b'\x01\x00'),('targets.u32',array('I',[999,0]).tobytes()),('costs.u16',array('H',[65535,0]).tobytes()),('forbidden-turns.u32',array('I',[0]).tobytes())):
            with self.assertRaises(PilotError):Payload((out|{name:data}).__getitem__)
    def test_binary_overflow_cost_and_reverse_decoding(self):
        # Separate decoder checks the two independently constructed side tables.
        _,g,_,_=graphs(fixture());out={};g.serialize(lambda k,v:out.update({k:v}))
        out.update({'costs.u16':array('H',[65535,65534]).tobytes(),'cost-overflow-arcs.u32':array('I',[0]).tobytes(),'cost-overflow-ticks.u32':array('I',[MAX_U32]).tobytes(),
                    'reverse.u8':bytes([254,0]),'reverse-overflow-arcs.u32':array('I',[0]).tobytes(),'reverse-overflow-targets.u32':array('I',[1]).tobytes()})
        p=Payload(out.__getitem__);self.assertEqual(p.cost_ms(0),MAX_U32*125);self.assertEqual(p.reverse_arc(0),1)


class RunnerTests(unittest.TestCase):
    def test_exact_scope_policy_limits_and_admission_reject_drift(self):
        import run_osm_car_v1 as runner
        plan={'stage':'controls','phase':'native_road_only_car_v1','image':runner.IMAGE,'output':runner.OUTPUTS['controls'],'caps':runner.CAPS,'mounts':runner.mounts('controls'),
              'inputs':dict.fromkeys(runner.mounts('controls'),'test-pin'),'hostBindings':dict.fromkeys(runner.HOST_CODE,'test-pin'),'dataCaps':runner.DATA_CAPS,'policy':POLICY,'tests':runner.TESTS,
              'sourceSnapshotUtc':STATE,'retainedReservationBytes':64500000000,'overallEnvelopeBytes':68719476736}
        runner.validate(plan)
        for field,bad in (('policy',{}),('inputs',{}),('mounts',{}),('hostBindings',{}),('caps',{}),('dataCaps',{}),('image','other'),('output','other'),('retainedReservationBytes',0)):
            with self.assertRaises(PilotError):runner.validate(plan|{field:bad})
    def test_observed_memory_swap_network_capabilities_mounts_and_files(self):
        import run_osm_car_v1 as runner
        host={'NetworkMode':'none','Memory':runner.CAPS['memoryBytes'],'MemorySwap':runner.CAPS['memoryBytes'],'ReadonlyRootfs':True,'NanoCpus':1000000000,'PidsLimit':32,'Tmpfs':{'/tmp':'rw,size=64m'},
              'CapDrop':['ALL'],'CapAdd':None,'SecurityOpt':['no-new-privileges'],'Ulimits':[{'Name':'core','Soft':0,'Hard':0},{'Name':'fsize','Soft':runner.CAPS['fileBytes'],'Hard':runner.CAPS['fileBytes']}]}
        obj={'Image':runner.IMAGE,'HostConfig':host,'Mounts':[{'Destination':'/work','RW':True},{'Destination':'/inputs','RW':False}]};runner.isolation(obj)
        for field,bad in (('Memory',0),('MemorySwap',0),('NetworkMode','bridge'),('ReadonlyRootfs',False),('NanoCpus',2000000000),('PidsLimit',64),('CapDrop',[]),('CapAdd',['SYS_ADMIN']),('Tmpfs',{}),('Ulimits',[])):
            with self.assertRaises(PilotError):runner.isolation(obj|{'HostConfig':host|{field:bad}})
        with self.assertRaises(PilotError):runner.isolation(obj|{'Mounts':[{'Destination':'/inputs','RW':True}]})


def struct_unpack(raw,code):
    import struct
    return struct.unpack('<'+code*(len(raw)//struct.calcsize('<'+code)),raw)
