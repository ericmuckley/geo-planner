from pathlib import Path
import struct
import tempfile
import unittest

from coarse_osm_entry_attributes_v1 import annotate, summarize
from coarse_osm_packed_capture_v1 import pack24


class Controls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ways = [(10, 40, 50, 3 | 4 | (4 << 4), 2), (20, 60, 0, 1 | (2 << 4), 4)]
        self.arcs = [(0, 1, 0, 0, 1, 1, 1250), (1, 0, 0, 0, 1, -1, 2500), (1, 2, 1, 0, 1, 1, 3750)]
        self.write()
        (self.root/'closures-0000.bin').write_bytes(b'')
        self.offsets, self.mapping = self.root/'offsets.u24', self.root/'map.u32'
        self.offsets.write_bytes(pack24([0, 1, 3, 3]))
        self.mapping.write_bytes(struct.pack('<III', 2, 0, 1))

    def write(self):
        (self.root/'ways-0000.bin').write_bytes(b''.join(struct.pack('<QddII', *r) for r in self.ways))
        (self.root/'arcs-0000.bin').write_bytes(b''.join(struct.pack('<IIIIIb3xQ', *r) for r in self.arcs))

    def run_annotation(self, selected=None, dims=None):
        return annotate(self.root, self.offsets, self.mapping, {0, 1, 2} if selected is None else selected, dims or [2, 3, 3, 3])

    def test_direction_default_mask_role_and_permutation(self):
        out = self.run_annotation()
        self.assertEqual(out[2]['sourceWay'], 10)
        self.assertEqual(out[2]['role'], 'primary')
        self.assertTrue(out[2]['defaultSpeed'])
        self.assertFalse(out[0]['defaultSpeed'])
        self.assertEqual(out[0]['sourceSpeedKph'], 50)
        self.assertEqual(out[1]['sourceFullCostTicks'], 30)

    def test_partial_and_full_step_totals_match_original_road_component(self):
        record = {'sample': {'id': 'test'}, 'road': {'steps': [{'arc': 2, 'ticks': 4, 'portion': 'source-suffix'}, {'arc': 0, 'ticks': 20, 'portion': 'full'}]}, 'components': {'roadTravelTicks': 24}}
        result = summarize(record, self.run_annotation())
        self.assertEqual((result['defaultTicks'], result['taggedTicks']), (4, 20))
        record['road']['steps'][1]['ticks'] = 19
        with self.assertRaises(AssertionError):
            summarize(record, self.run_annotation())

    def test_closure_and_source_counts_are_complete(self):
        (self.root/'closures-0000.bin').write_bytes(struct.pack('<Q', 10))
        self.offsets.write_bytes(pack24([0, 0, 1, 1]))
        self.mapping.write_bytes(struct.pack('<I', 0))
        out = self.run_annotation({0}, [2, 3, 3, 1])
        self.assertEqual(out[0]['sourceWay'], 20)
        with self.assertRaises(AssertionError):
            self.run_annotation({0}, [2, 3, 4, 1])

    def test_duplicate_wrong_or_partial_permutation_refused(self):
        for raw in (struct.pack('<III', 0, 0, 2), struct.pack('<III', 0, 1, 3), b'x'):
            self.mapping.write_bytes(raw)
            with self.assertRaises((AssertionError, ValueError)):
                self.run_annotation()

    def test_bad_flags_speed_or_source_arc_refused(self):
        self.ways[0] = (10, 0, 50, 3, 2)
        self.write()
        with self.assertRaises(AssertionError):
            self.run_annotation()
        self.ways[0] = (10, 40, 50, 3, 2)
        self.arcs[0] = (0, 1, 0, 0, 1, 1, 0)
        self.write()
        with self.assertRaises(AssertionError):
            self.run_annotation()

    def test_out_of_domain_selection_dimensions_and_csr_refused(self):
        with self.assertRaises(AssertionError):
            self.run_annotation({3})
        with self.assertRaises(AssertionError):
            self.run_annotation(dims=[8000001, 3, 3, 3])
        self.offsets.write_bytes(pack24([0, 0, 3, 3]))
        with self.assertRaises(AssertionError):
            self.run_annotation()

    def test_empty_bounded_selection_keeps_complete_source_checks(self):
        self.assertEqual(self.run_annotation(set()), {})


if __name__ == '__main__':
    unittest.main()
