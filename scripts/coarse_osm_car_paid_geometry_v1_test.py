"""Independent small source-cost/packet/provenance expectations for paid geometry."""
import math
from pathlib import Path
import random
import struct
import tempfile
import unittest

from coarse_osm_car_paid_geometry_v1 import NativePaidGeometry
from coarse_osm_packed_capture_v1 import pack24
from coarse_osm_paid_projection_v1 import R,angle,frame,project
from import_roads import distance_m

ARTIFACT=None


def ms(a,b,speed):
    return max(1,math.ceil(distance_m([v/1e7 for v in a],[v/1e7 for v in b])*3600/speed))


def decode_packet(raw,start):
    cursor=0;x,y=start;points=[]
    def word():
        nonlocal cursor
        value=0
        for i in range(5):
            byte=raw[cursor];cursor+=1;value|=(byte&127)<<(7*i)
            if byte<128:return value
        raise ValueError('Fixture varint overflow')
    def signed(value):return value-2**32 if value>=2**31 else value
    while cursor<len(raw):
        a,b=word(),word();x=signed((x+((a>>1)^-(a&1)))&0xffffffff);y=signed((y+((b>>1)^-(b&1)))&0xffffffff)
        f,b=struct.unpack_from('<HH',raw,cursor);cursor+=4;points.append((x,y,f,b))
    return points


class PaidGeometryTests(unittest.TestCase):
    def setUp(self):
        if ARTIFACT is None:self.skipTest('Explicit paid-geometry native artifact required')
        self.native=NativePaidGeometry(*ARTIFACT);self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def fixture(self,points,forward=100.,backward=80.,closed=False,reverse_map=True):
        source=self.root/'facts';source.mkdir();out=self.root/'out';out.mkdir()
        def save(prefix,fmt,rows):(source/(prefix+'-0000.bin')).write_bytes(b''.join(struct.pack(fmt,*row) for row in rows))
        save('xy','<ii',points);save('geometry','<I',[(i,) for i in range(len(points))]);save('anchors','<I',[(0,),(len(points)-1,)])
        save('ways','<QddII',[(10,forward,backward,int(forward>0)|2*int(backward>0),len(points))])
        f=sum(ms(a,b,forward) for a,b in zip(points,points[1:])) if forward else 0
        b=sum(ms(a,b,backward) for a,b in zip(points,points[1:])) if backward else 0
        arcs=[]
        if forward:arcs.append((0,1,0,0,len(points)-1,1,f))
        if backward:arcs.append((1,0,0,0,len(points)-1,-1,b))
        save('arcs','<IIIIIb3xQ',arcs)
        if closed:save('closures','<Q',[(10,)])
        degree=[0,0]
        if not closed:
            for arc in arcs:degree[arc[0]]+=1
        offsets=self.root/'offsets';offsets.write_bytes(pack24([0,degree[0],sum(degree)]))
        arc_map=self.root/'map';mapping=list(range(sum(degree)))
        if reverse_map:mapping.reverse()
        arc_map.write_bytes(b''.join(struct.pack('<I',v) for v in mapping))
        return source,offsets,arc_map,out,[len(points),2,1,len(points),len(arcs),sum(degree)]

    def test_straight_time_progress_simplifies(self):
        result=self.native.simplify([(0,0),(5000000,0),(10000000,0)],[0,2000000,4000000],[0,3000000,6000000])
        self.assertEqual(result['kept'],[0,2]);self.assertLessEqual(result['maximumDiscardedTimeErrorMs'],10000)

    def test_two_thousand_independent_projections_and_short_global_wraps(self):
        randomizer=random.Random(20261102)
        cases=[((1,0),(0,0),(2,0)),((1800000000,0),(1799999999,0),(-1799999999,0)),
               ((450000000,899999999),(0,899999998),(900000000,899999998))]
        for _ in range(2000):
            x=randomizer.uniform(-180,180);y=randomizer.uniform(-80,80)
            def p(dx,dy):return round(((x+dx+180)%360-180)*1e7),round((y+dy)*1e7)
            cases.append((p(randomizer.uniform(-2,2),randomizer.uniform(-2,2)),p(0,0),p(randomizer.uniform(-2,2),randomizer.uniform(-2,2))))
        for p,a,b in cases:
            actual=self.native.project(p,a,b);expected=project(p,frame(a,b))
            self.assertAlmostEqual(actual[0],expected[0],delta=.001)
            self.assertLessEqual(abs(actual[1]-expected[1])*R*angle(a,b),.001)
            self.assertLessEqual(abs(actual[1]-expected[1]),1e-6)

    def test_backtracking_time_progress_not_erased_by_collinear_shape(self):
        result=self.native.simplify([(0,0),(10000000,0),(0,0),(10000000,0)],[0,4000000,8000000,12000000],[0,5000000,10000000,15000000])
        self.assertEqual(result['kept'],[0,1,2,3])

    def test_canonical_reverse_prefixes_exact_source_positions_and_length(self):
        points=[(0,0),(5000000,100000),(10000000,0)]
        args=self.fixture(points);result=self.native.build(*args)
        self.assertEqual((result['curvedSpans'],result['interiorPoints'],result['longSpans']),(1,1,1))
        out=args[3];self.assertEqual((out/'curve-keys.u24').read_bytes(),pack24([0]))
        self.assertEqual(decode_packet((out/'curve-packets.u8').read_bytes(),points[-1]),[(5000000,100000,32768,32768)])
        self.assertEqual((out/'curve-source.bin').read_bytes(),struct.pack('<IIIb3x',0,0,2,-1))
        self.assertEqual((out/'curve-source-positions.u32').read_bytes(),struct.pack('<I',1))
        length=sum(distance_m([v/1e7 for v in a],[v/1e7 for v in b]) for a,b in zip(points,points[1:]))
        self.assertEqual(struct.unpack('<H',(out/'long-lengths.u16').read_bytes())[0],math.ceil(length/8)+1)
        self.assertEqual(result['totalOutputBytes'],sum(p.stat().st_size for p in out.iterdir()))

    def test_closure_removes_both_directions_without_creating_geometry(self):
        args=self.fixture([(0,0),(5000000,100000),(10000000,0)],closed=True);result=self.native.build(*args)
        self.assertEqual((result['physicalSpans'],result['runtimeBytes']),(0,4))
        self.assertEqual((args[3]/'curve-offsets.u32').read_bytes(),b'\0'*4)

    def test_long_length_overflow_and_paid_backtracking(self):
        points=[(i%2*10000000,0) for i in range(100)]
        args=self.fixture(points,backward=0,reverse_map=False);result=self.native.build(*args)
        self.assertEqual(result['lengthOverflows'],1);self.assertEqual(result['interiorPoints'],98)
        self.assertEqual((args[3]/'long-lengths.u16').read_bytes(),b'\xff\xff')
        value=struct.unpack('<I',(args[3]/'long-overflow-units.u32').read_bytes())[0];self.assertGreaterEqual(value,65535)

    def test_whole_source_cost_mismatch_refused_before_writes(self):
        args=self.fixture([(0,0),(5000000,100000),(10000000,0)])
        path=args[0]/'arcs-0000.bin';raw=bytearray(path.read_bytes());raw[24]^=1;path.write_bytes(raw)
        with self.assertRaises(ValueError):self.native.build(*args)
        self.assertEqual(list(args[3].iterdir()),[])

    def test_bad_bijection_csr_and_existing_output_refused(self):
        args=self.fixture([(0,0),(5000000,100000),(10000000,0)])
        args[2].write_bytes(struct.pack('<II',0,0))
        with self.assertRaises(ValueError):self.native.build(*args)
        args[2].write_bytes(struct.pack('<II',1,0));args[1].write_bytes(pack24([0,2,2]))
        with self.assertRaises(ValueError):self.native.build(*args)
        (args[3]/'preserve').write_bytes(b'keep')
        with self.assertRaises(ValueError):self.native.build(*args)

    def test_invalid_prefix_or_coordinate_refused(self):
        for points,f,b in [([(0,0),(1,1),(2,2)],[0,2,1],[0,1,2]), ([(0,0),(0,900000001)],[0,1],[0,1])]:
            with self.assertRaises(ValueError):self.native.simplify(points,f,b)

    def test_generated_packets_pass_independent_source_audit(self):
        from coarse_osm_car_paid_geometry_audit_v1 import audit
        randomizer=random.Random(20261103)
        for case in range(50):
            child=self.root/str(case);child.mkdir();previous=self.root;self.root=child
            x=randomizer.randrange(-1700000000,1700000000);y=randomizer.randrange(-700000000,700000000)
            points=[(x,y)]
            for _ in range(randomizer.randrange(2,80)):
                x+=randomizer.randrange(-100000,100000);y+=randomizer.randrange(-100000,100000);points.append((x,y))
            args=self.fixture(points,forward=0 if case%3==0 else 100.,backward=0 if case%3==1 else 80.,closed=case%7==0,reverse_map=case%2==0)
            actual=self.native.build(*args);checked=audit(*args)
            self.assertEqual(actual['physicalSpans'],checked['physicalSpansChecked'])
            self.assertEqual(actual['runtimeBytes'],checked['runtimeBytes']);self.root=previous


if __name__=='__main__':unittest.main()
