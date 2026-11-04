"""Hand-encoded source/packet controls independent of the native producer."""
import math
from pathlib import Path
import struct
import tempfile
import unittest

from coarse_osm_car_paid_geometry_audit_v1 import FILES,audit,curve_packet,varint
from import_roads import distance_m


def words(values,width):return b''.join(value.to_bytes(width,'little') for value in values)


def encode(value):
    raw=bytearray()
    while value>=128:raw.append((value&127)|128);value>>=7
    raw.append(value);return raw


class PaidAuditTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)

    def fixture(self,points,kept,forward=100.,backward=80.,reverse=True,closed=False,references=None):
        source=self.root/'facts';source.mkdir();out=self.root/'geometry';out.mkdir()
        refs=list(range(len(points))) if references is None else references
        def write(prefix,shape,rows):
            (source/(prefix+'-0000.bin')).write_bytes(b''.join(struct.pack(shape,*row) for row in rows))
        write('xy','<ii',points);write('anchors','<I',[(refs[0],),(refs[-1],)])
        write('geometry','<I',[(ref,) for ref in refs])
        write('ways','<QddII',[(10,forward,backward,int(forward>0)+2*int(backward>0),len(refs))])
        prefixes=[];length=0.
        for speed in (forward,backward):
            prefix=[0]
            for first,last in zip(refs,refs[1:]):
                d=distance_m([v/1e7 for v in points[first]],[v/1e7 for v in points[last]])
                prefix.append(prefix[-1]+(0 if not speed or first==last else max(1,math.ceil(d*3600/speed))))
            prefixes.append(prefix)
        length=sum(distance_m([v/1e7 for v in points[a]],[v/1e7 for v in points[b]]) for a,b in zip(refs,refs[1:]))
        arcs=[]
        if forward:arcs.append((0,1,0,0,len(refs)-1,1,prefixes[0][-1]))
        if backward:arcs.append((1,0,0,0,len(refs)-1,-1,prefixes[1][-1]))
        write('arcs','<IIIIIb3xQ',arcs)
        if closed:write('closures','<Q',[(10,)])
        degree=[0,0]
        if not closed:
            for arc in arcs:degree[arc[0]]+=1
        offsets=self.root/'offsets';offsets.write_bytes(words([0,degree[0],sum(degree)],3))
        mapping=list(range(sum(degree)))
        if reverse:mapping.reverse()
        arc_map=self.root/'map';arc_map.write_bytes(words(mapping,4))
        direction=-1 if backward and (not forward or reverse) else 1
        positions=kept if direction==1 else kept[::-1];packet=bytearray();old=points[refs[0 if direction==1 else -1]]
        for pos in positions:
            point=points[refs[pos]]
            for value,previous in zip(point,old):
                delta=(value-previous)&0xffffffff;packet.extend(encode(((delta<<1)^(0xffffffff if delta>=2**31 else 0))&0xffffffff))
            lanes=[]
            for prefix in prefixes if direction==1 else prefixes[::-1]:
                value=prefix[pos] if direction==1 else prefix[-1]-prefix[pos]
                lanes.append(0 if prefix[-1]==0 else (value*65535+prefix[-1]//2)//prefix[-1])
            packet.extend(struct.pack('<HH',*lanes));old=point
        provenance=struct.pack('<IIIb3x',0,0,len(refs)-1,direction)
        for name in FILES:(out/name).write_bytes(b'')
        if kept and not closed:
            (out/'curve-keys.u24').write_bytes(words([0],3));(out/'curve-packets.u8').write_bytes(packet)
            (out/'curve-source.bin').write_bytes(provenance);(out/'curve-source-positions.u32').write_bytes(words(positions,4))
        (out/'curve-offsets.u32').write_bytes(words([0,len(packet)] if kept and not closed else [0],4))
        if length>1000 and not closed:
            units=math.ceil(length/8)+1
            (out/'long-keys.u24').write_bytes(words([0],3));(out/'long-lengths.u16').write_bytes(words([min(units,65535)],2))
            (out/'long-source.bin').write_bytes(provenance)
            if units>=65535:
                (out/'long-overflow-keys.u24').write_bytes(words([0],3));(out/'long-overflow-units.u32').write_bytes(words([units],4))
        return source,offsets,arc_map,out,[len(points),2,1,len(refs),len(arcs),sum(degree)]

    def test_reverse_packet_asymmetric_prefix_and_long_length(self):
        result=audit(*self.fixture([(0,0),(2500000,100000),(10000000,0)],[1]))
        self.assertEqual((result['physicalSpansChecked'],result['interiorPositionsChecked'],result['longSpansChecked']),(1,1,1))

    def test_forward_only_short_straight_simplification(self):
        result=audit(*self.fixture([(0,0),(100,0),(200,0)],[],backward=0,reverse=False))
        self.assertEqual(result['curvedSpansChecked'],0)

    def test_backward_only_repeated_native_and_coincident_distinct_nodes(self):
        result=audit(*self.fixture([(0,0),(0,0),(1000,0)],[1,2],forward=0,references=[0,0,1,2]))
        self.assertEqual(result['directedSourceCostsChecked'],1)

    def test_closed_source_has_no_geometry(self):
        self.assertEqual(audit(*self.fixture([(0,0),(5000000,100000),(10000000,0)],[1],closed=True))['physicalSpansChecked'],0)

    def test_backtracking_without_paid_vertices_refused(self):
        args=self.fixture([(0,0),(10000000,0),(0,0),(10000000,0)],[])
        with self.assertRaises(AssertionError):audit(*args)

    def test_long_overflow(self):
        result=audit(*self.fixture([(i%2*10000000,0) for i in range(100)],list(range(1,99)),backward=0,reverse=False))
        self.assertEqual(result['lengthOverflowsChecked'],1)

    def test_prefix_source_position_coordinate_and_length_corruption_refused(self):
        args=self.fixture([(0,0),(2500000,100000),(10000000,0)],[1]);out=args[3]
        for name,offset in [('curve-packets.u8',-1),('curve-packets.u8',0),('curve-source-positions.u32',0),('long-lengths.u16',0),('curve-source.bin',12)]:
            original=(out/name).read_bytes();bad=bytearray(original);bad[offset]^=1;(out/name).write_bytes(bad)
            with self.assertRaises(AssertionError):audit(*args)
            (out/name).write_bytes(original)

    def test_wrong_arc_map_or_source_cost_refused(self):
        args=self.fixture([(0,0),(2500000,100000),(10000000,0)],[1]);original=args[2].read_bytes()
        args[2].write_bytes(words([0,0],4))
        with self.assertRaises(AssertionError):audit(*args)
        args[2].write_bytes(original);path=args[0]/'arcs-0000.bin';bad=bytearray(path.read_bytes());bad[24]^=1;path.write_bytes(bad)
        with self.assertRaises(AssertionError):audit(*args)

    def test_noncanonical_overflowing_truncated_varints_refused(self):
        for raw in (b'\x80\0',b'\xff\xff\xff\xff\x10',b'\x80'):
            with self.assertRaises(AssertionError):varint(raw,0,len(raw))
        with self.assertRaises(AssertionError):curve_packet(b'\0\0\0',0,3,(0,0))


if __name__=='__main__':unittest.main()
