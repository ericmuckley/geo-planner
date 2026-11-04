"""Synthetic native resolver/CSR controls; real inputs belong to a later recipe."""
from pathlib import Path
import shutil
import struct
import tempfile
import unittest

from coarse_osm_car_entry_native_v1 import NativeEntries
from coarse_osm_car_packed_native_v1 import NativePacked

ENGINE = PACKED = None


def configure_native(path, pin):
    global ENGINE, PACKED
    ENGINE, PACKED = NativeEntries(path, pin), NativePacked(path, pin)


def a(tail, head, way, first=0, direction=1):
    return {'tail': tail, 'head': head, 'way': way, 'first': first, 'last': first+1, 'direction': direction, 'ms': 1250}


class Controls(unittest.TestCase):
    def setUp(self):
        if ENGINE is None:
            self.skipTest('Configure the qualified native artifact explicitly')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def facts(self, arcs=None, closed=(10, 20, 30), turns=()):
        arcs = arcs or [a(0, 1, 10), a(1, 2, 20), a(2, 3, 30), a(4, 1, 40)]
        source = self.root/'facts'
        source.mkdir()
        ways = sorted({x['way'] for x in arcs})
        vertices = max(max(x['tail'], x['head']) for x in arcs)+1
        arcs = sorted(arcs, key=lambda x: (ways.index(x['way']), x['first'], x['last'], -x['direction']))
        records = [(x['tail'], x['head'], ways.index(x['way']), x['first'], x['last'], x['direction'], x['ms']) for x in arcs]
        fields = {'ids': b''.join(struct.pack('<Q', 100+i) for i in range(vertices)),
                  'xy': b''.join(struct.pack('<ii', i*10000, 0) for i in range(vertices)),
                  'anchors': b''.join(struct.pack('<I', i) for i in range(vertices)), 'flags': bytes([4]*vertices),
                  'ways': b''.join(struct.pack('<QddII', w, 40, 40, 3, 2*(i+1)) for i, w in enumerate(ways)),
                  'arcs': b''.join(struct.pack('<IIIIIb3xQ', *r) for r in records),
                  'closures': b''.join(struct.pack('<Q', w) for w in sorted(closed)),
                  'turns': b''.join(struct.pack('<QQQQB7x', *r) for r in turns)}
        for name, body in fields.items():
            (source/(name+'-0000.bin')).write_bytes(body)
        self.source, self.arcs, self.records = source, arcs, records
        self.ways, self.vertices, self.turns = ways, vertices, turns
        return source

    def resolve(self, rules=((1, 10, 20, 30),), fallback=(), dims=None):
        rules_path, fallback_path = self.root/'rules.bin', self.root/'fallback.u64'
        rules_path.write_bytes(b''.join(struct.pack('<QQQQ', *r) for r in rules))
        fallback_path.write_bytes(b''.join(struct.pack('<Q', n) for n in fallback))
        out = self.root/'resolved'
        out.mkdir()
        result = ENGINE.resolve(self.source, rules_path, fallback_path, out,
                                dims or [len(self.ways), self.vertices, len(self.arcs), len(rules), len(fallback)])
        self.resolved = out
        return result

    def base(self):
        view, routing = self.root/'view', self.root/'routing'
        view.mkdir()
        routing.mkdir()
        for f in self.source.iterdir():
            if not f.name.startswith('closures-'):
                shutil.copyfile(f, view/f.name)
        shutil.copyfile(self.resolved/'closures-0000.bin', view/'closures-0000.bin')
        closed = {row[0] for row in struct.iter_unpack('<Q', (view/'closures-0000.bin').read_bytes())}
        post = sum(a['way'] not in closed for a in self.arcs)
        PACKED.encode(view, routing, [self.vertices, self.vertices, len(self.ways), len(self.arcs), post, len(self.turns)])
        self.routing, self.post = routing, post
        return routing

    def augment(self):
        output = self.root/'augmented.u24'
        result = ENGINE.augment(self.source, self.resolved/'closures-0000.bin', self.resolved/'entry-pairs-pre.u32', self.routing, output,
                                [len(self.ways), self.vertices, len(self.arcs), self.post])
        return result, output.read_bytes()

    def test_actual_shared_node_resolution_and_original_source_unchanged(self):
        self.facts()
        before = (self.source/'closures-0000.bin').read_bytes()
        self.assertEqual(self.resolve(), [1, 1, 0, 0, 3, 0, 1, 4, 4])
        self.assertEqual((self.resolved/'entry-pairs-pre.u32').read_bytes(), struct.pack('<II', 0, 1))
        self.base()
        self.assertEqual((self.source/'closures-0000.bin').read_bytes(), before)

    def test_missing_member_retains_full_fallback(self):
        self.facts(closed=(10, 20, 99))
        result = self.resolve(rules=((1, 10, 20, 99),))
        self.assertEqual(result[1:4], [0, 1, 0])
        self.assertEqual([r[0] for r in struct.iter_unpack('<Q', (self.resolved/'closures-0000.bin').read_bytes())], [10, 20, 99])

    def test_no_shared_source_node_retains_full_fallback(self):
        self.facts([a(0, 1, 10), a(2, 3, 20), a(3, 4, 30)])
        result = self.resolve()
        self.assertEqual(result[1:4], [0, 0, 1])
        self.assertEqual(result[-1], 0)

    def test_other_relation_fallback_is_not_subtracted(self):
        self.facts()
        self.resolve(fallback=(20,))
        self.assertEqual((self.resolved/'closures-0000.bin').read_bytes(), struct.pack('<Q', 20))
        self.base()
        counts, raw = self.augment()
        self.assertEqual(counts[2:4], [0, 1])
        self.assertEqual(raw, b'')

    def test_parallel_arcs_and_multiple_junctions_all_get_entry_pairs(self):
        self.facts([a(0, 1, 10), a(4, 1, 10, 1), a(5, 2, 10, 2),
                    a(1, 2, 20), a(1, 3, 20, 1), a(2, 4, 20, 2), a(4, 6, 30)])
        self.resolve()
        pairs = list(struct.iter_unpack('<II', (self.resolved/'entry-pairs-pre.u32').read_bytes()))
        self.assertEqual(pairs, [(0, 3), (0, 4), (1, 3), (1, 4), (2, 5)])

    def test_same_from_to_way_is_supported(self):
        self.facts([a(0, 1, 10), a(2, 3, 10, 1), a(1, 2, 20)], closed=(10, 20))
        self.assertEqual(self.resolve(rules=((1, 10, 20, 10),))[1], 1)

    def test_typed_shape_count_and_fallback_subset_guards(self):
        self.facts()
        with self.assertRaises(ValueError):
            self.resolve(rules=((1, 10, 10, 30),))
        shutil.rmtree(self.root/'resolved')
        with self.assertRaises(ValueError):
            self.resolve(fallback=(99,))
        shutil.rmtree(self.root/'resolved')
        with self.assertRaises(ValueError):
            self.resolve(dims=[4, 5, 4, 2, 0])

    def test_actual_source_to_csr_mapping_and_extra_pairs(self):
        self.facts([a(4, 1, 10), a(1, 2, 20), a(2, 3, 30), a(0, 1, 40)])
        self.resolve()
        self.base()
        counts, raw = self.augment()
        pairs = [tuple(int.from_bytes(raw[i+j:i+j+3], 'little') for j in (0, 3)) for i in range(0, len(raw), 6)]
        self.assertEqual(pairs, [(3, 1)])
        self.assertEqual(counts, [1, 0, 1, 0, 1, 4])

    def test_existing_pairs_are_preserved_and_duplicate_extra_input_fails(self):
        self.facts()
        self.resolve()
        self.base()
        (self.routing/'forbidden-turns.u24').write_bytes(b'\x00\x00\x00\x01\x00\x00')
        counts, raw = self.augment()
        self.assertEqual(counts[1:3], [1, 1])
        self.assertEqual(len(raw), 6)
        (self.root/'augmented.u24').unlink()
        p = self.resolved/'entry-pairs-pre.u32'
        p.write_bytes(p.read_bytes()*2)
        with self.assertRaises(ValueError):
            self.augment()

    def test_pair_on_a_previously_open_road_is_rejected(self):
        self.facts()
        self.resolve()
        self.base()
        (self.resolved/'entry-pairs-pre.u32').write_bytes(struct.pack('<II', 3, 1))
        with self.assertRaises(ValueError):
            self.augment()

    def test_wrong_actual_csr_correspondence_is_rejected(self):
        self.facts()
        self.resolve()
        self.base()
        p = self.routing/'targets.u24'
        raw = bytearray(p.read_bytes())
        raw[0:3] = b'\x02\x00\x00'
        p.write_bytes(raw)
        with self.assertRaises(ValueError):
            self.augment()

    def test_vertex_arrays_larger_than_a_fact_chunk_are_supported(self):
        self.facts([a(0, 1, 10), a(1, 2, 20), a(2, 3, 30), a(3, 1, 40)])
        self.resolve()
        self.base()
        vertices = 5592406
        with (self.routing/'offsets.u24').open('wb') as stream:
            stream.write(b''.join(i.to_bytes(3, 'little') for i in range(5)))
            count = vertices-4
            block = b'\x04\x00\x00'*65536
            while count:
                n = min(count, 65536)
                stream.write(block[:3*n])
                count -= n
        output = self.root/'large-augmented.u24'
        result = ENGINE.augment(self.source, self.resolved/'closures-0000.bin', self.resolved/'entry-pairs-pre.u32', self.routing, output,
                                [len(self.ways), vertices, len(self.arcs), self.post])
        self.assertEqual(result[-1], 4)
        self.assertGreater((self.routing/'offsets.u24').stat().st_size, 16777216)
