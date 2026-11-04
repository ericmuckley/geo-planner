"""Native formatter qualification against bounded independent Python encoding."""
from pathlib import Path
import random
import struct
import tempfile
import unittest

from coarse_osm_car_packed_native_v1 import NativePacked
from coarse_osm_packed_capture_v1 import encode

ARTIFACT = None


class NativePackedTests(unittest.TestCase):
    def setUp(self):
        if ARTIFACT is None:self.skipTest('Explicit qualified native artifact required')
        self.native = NativePacked(*ARTIFACT)
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name);self.source = self.root/'facts';self.source.mkdir()
        self.output = self.root/'routing';self.output.mkdir()

    def facts(self, ids, anchors, flags, ways, arcs, closures=(), turns=(), xy=None):
        def save(prefix, fmt, values):
            if values:(self.source/(prefix+'-0000.bin')).write_bytes(b''.join(struct.pack(fmt, *row) for row in values))
        save('ids', '<Q', [(n,) for n in ids]);save('anchors', '<I', [(n,) for n in anchors])
        save('flags', '<B', [(n,) for n in flags]);save('xy', '<ii', xy or [(0, 0)]*len(ids))
        save('ways', '<QddII', ways);save('arcs', '<IIIIIb3xQ', arcs)
        save('closures', '<Q', [(n,) for n in sorted(closures)]);save('turns', '<QQQQB7x', turns)
        return [len(ids), len(anchors), len(ways), len(arcs), sum(ways[row[2]][0] not in closures for row in arcs), len(turns)]

    def test_small_full_fields_match_separate_formatter(self):
        ids = [11, 12, 13];anchors = [0, 2];flags = b'\4\6';ways = [(10, 100., 100., 3, 3)]
        arcs = [(0, 1, 0, 0, 2, 1, 2), (1, 0, 0, 0, 2, -1, 2)]
        expected = self.facts(ids, anchors, flags, ways, arcs)
        result = self.native.encode(self.source,self.output,expected)
        fields, _, _ = encode(ids, [0]*6, anchors, flags, [0, 1, 2], ways, arcs, set(), [], [])
        self.assertEqual(result['payloadBytes'], sum(map(len, fields.values())))
        for name, raw in fields.items():self.assertEqual((self.output/name).read_bytes(), raw, name)

    def test_cost_overflow_and_closed_physical_pairs(self):
        ways = [(10, 100., 100., 3, 2), (20, 100., 100., 3, 4)]
        arcs = [(0, 1, 0, 0, 1, 1, 65535*125), (1, 0, 0, 0, 1, -1, 65534*125),
                (0, 1, 1, 0, 1, 1, 1), (1, 0, 1, 0, 1, -1, 1)]
        result = self.native.encode(self.source,self.output,self.facts([11,12],[0,1],b'\4\4',ways,arcs,{20}))
        self.assertEqual(result['postClosureArcs'], 2)
        self.assertEqual(result['costOverflowEntries'], 1)
        self.assertEqual((self.output/'cost-overflow-ticks.u32').read_bytes(),struct.pack('<I',65535))
        self.assertEqual((self.output/'reverse.u8').read_bytes(),b'\0\0')

    def test_only_to_unselected_way_blocks_all_retained_choices(self):
        ways = [(10,100.,0.,1,2),(20,100.,0.,1,4)]
        arcs = [(0,1,0,0,1,1,1),(1,2,1,0,1,1,1)]
        result = self.native.encode(self.source,self.output,self.facts([11,12,13],[0,1,2],b'\4'*3,ways,arcs,turns=[(100,10,12,999,6)]))
        self.assertEqual(result['forbiddenTurnPairs'],1)
        self.assertEqual((self.output/'forbidden-turns.u24').read_bytes(),b'\0\0\0\1\0\0')

    def test_same_way_only_u_turn_keeps_exact_physical_reverse(self):
        ways=[(10,100.,100.,3,3)]
        arcs=[(0,1,0,0,1,1,1),(1,0,0,0,1,-1,1),(1,2,0,1,2,1,1),(2,1,0,1,2,-1,1)]
        result=self.native.encode(self.source,self.output,self.facts([11,12,13],[0,1,2],b'\4'*3,ways,arcs,turns=[(100,10,12,10,9)]))
        self.assertEqual(result['forbiddenTurnPairs'],2)
        self.assertEqual((self.output/'forbidden-turns.u24').read_bytes(),b'\0\0\0\2\0\0\3\0\0\1\0\0')

    def test_reverse_overflow_ordinal_is_not_no_reverse(self):
        ways=[(i+10,100.,100.,3,2*(i+1)) for i in range(256)]
        arcs=[]
        for i in range(256):arcs.extend([(0,1,i,0,1,1,1),(1,0,i,0,1,-1,1)])
        result=self.native.encode(self.source,self.output,self.facts([11,12],[0,1],b'\4\4',ways,arcs))
        self.assertEqual(result['reverseOverflowEntries'],4)
        self.assertEqual((self.output/'reverse.u8').read_bytes()[254:256],b'\xfe\xfe')

    def test_refuses_bad_counts_padding_order_and_truncation(self):
        ways=[(10,100.,0.,1,2)];arcs=[(0,1,0,0,1,1,1)]
        expected=self.facts([11,12],[0,1],b'\4\4',ways,arcs)
        raw=(self.source/'arcs-0000.bin').read_bytes()
        for invalid in [raw[:-1],raw[:21]+b'\1'+raw[22:],raw+raw]:
            (self.source/'arcs-0000.bin').write_bytes(invalid)
            with self.assertRaises(ValueError):self.native.encode(self.source,self.output,expected)
        (self.source/'arcs-0000.bin').write_bytes(raw)
        with self.assertRaises(ValueError):self.native.encode(self.source,self.output,[2,2,1,1,2,0])

    def test_fresh_outputs_and_symlink_inputs_refused(self):
        expected=self.facts([11,12],[0,1],b'\4\4',[(10,100.,0.,1,2)],[(0,1,0,0,1,1,1)])
        path=self.source/'ids-0000.bin';path.rename(self.root/'ids');path.symlink_to(self.root/'ids')
        with self.assertRaises(ValueError):self.native.encode(self.source,self.output,expected)
        path.unlink();path.write_bytes((self.root/'ids').read_bytes())
        (self.output/'existing').write_bytes(b'preserve')
        with self.assertRaises(ValueError):self.native.encode(self.source,self.output,expected)
        self.assertEqual((self.output/'existing').read_bytes(),b'preserve')

    def test_seeded_parallel_directed_graphs_match_all_independent_wire_bytes(self):
        randomizer = random.Random(20261102)
        for trial in range(100):
            self.source=self.root/f'facts-{trial}';self.source.mkdir()
            self.output=self.root/f'routing-{trial}';self.output.mkdir()
            ids=list(range(11,19));anchors=list(range(8));flags=bytes(randomizer.randrange(8) for _ in ids)
            ways=[];arcs=[];geometry=[];closures=set();turns=[]
            for way in range(20):
                tail,head=randomizer.sample(range(8),2);geometry.extend((tail,head));directions=randomizer.randrange(4)
                ways.append((100+way,100. if directions&1 else 0.,100. if directions&2 else 0.,directions,len(geometry)))
                if directions&1:arcs.append((tail,head,way,0,1,1,1))
                if directions&2:arcs.append((head,tail,way,0,1,-1,1))
                if randomizer.randrange(8)==0:closures.add(100+way)
            for relation in range(15):
                source,target=randomizer.randrange(100,120),randomizer.randrange(100,123);kind=randomizer.randrange(10)
                if source==target and kind not in (2,3,8,9):kind=9
                turns.append((relation+1000,source,randomizer.choice(ids),target,kind))
            expected=self.facts(ids,anchors,flags,ways,arcs,closures,turns)
            self.native.encode(self.source,self.output,expected)
            fields,_,_=encode(ids,[0]*16,anchors,flags,geometry,ways,arcs,closures,turns,[])
            for name,raw in fields.items():self.assertEqual((self.output/name).read_bytes(),raw,(trial,name))


if __name__ == '__main__':unittest.main()
