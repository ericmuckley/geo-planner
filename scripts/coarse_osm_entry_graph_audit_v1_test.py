from pathlib import Path
import struct
import tempfile
import unittest

from coarse_osm_entry_graph_audit_v1 import audit
from coarse_osm_packed_capture_v1 import pack24


class Controls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.original, self.view, self.routing = (root/n for n in ('original', 'view', 'routing'))
        for path in (self.original, self.view, self.routing):
            path.mkdir()
        def field(prefix, fmt, values):
            raw = b''.join(struct.pack(fmt, *row) for row in values)
            for source in (self.original, self.view):
                (source/(prefix+'-0000.bin')).write_bytes(raw)
        field('ids', '<Q', [(n,) for n in range(11, 16)])
        field('anchors', '<I', [(n,) for n in range(5)])
        field('xy', '<ii', [(0, 0)]*5)
        field('flags', '<B', [(4,)]*5)
        field('ways', '<QddII', [(n, 40, 0, 1, 2*(i+1)) for i, n in enumerate((10, 20, 30, 40))])
        field('arcs', '<IIIIIb3xQ', [(0, 1, 0, 0, 1, 1, 1250), (1, 2, 1, 0, 1, 1, 1250), (2, 3, 2, 0, 1, 1, 1250), (4, 1, 3, 0, 1, 1, 1250)])
        field('turns', '<QQQQB7x', [(100, 40, 12, 20, 0)])
        (self.original/'closures-0000.bin').write_bytes(struct.pack('<QQQ', 10, 20, 30))
        (self.view/'closures-0000.bin').write_bytes(b'')
        fields = {'xy.i32': bytes(40), 'offsets.u24': pack24([0, 1, 2, 3, 3, 4]),
                  'targets.u24': pack24([1, 2, 3, 1]), 'costs.u16': struct.pack('<HHHH', 10, 10, 10, 10),
                  'cost-overflow-arcs.u24': b'', 'cost-overflow-ticks.u32': b'', 'reverse.u8': b'\xff'*4,
                  'reverse-overflow-arcs.u24': b'', 'reverse-overflow-targets.u24': b'',
                  'node-flags.u8': b'\4'*5, 'forbidden-turns.u24': pack24([3, 1])}
        for name, raw in fields.items():
            (self.routing/name).write_bytes(raw)
        self.extra, self.final = root/'pre.u32', root/'final.u24'
        self.extra.write_bytes(struct.pack('<II', 0, 1))
        self.final.write_bytes(pack24([0, 1, 3, 1]))
        self.dims, self.counts = [5, 5, 4, 4, 4, 1], [1, 1, 1, 0, 2, 4]

    def run_audit(self):
        return audit(self.original, self.view, self.routing, self.extra, self.final, self.dims, self.counts, baseline_post=1)

    def test_complete_fields_pairs_and_old_transition_superset(self):
        result = self.run_audit()
        self.assertEqual(result['reopenedDirectedArcs'], 3)
        self.assertTrue(result['oldAllowedTransitionsPreserved'])
        self.assertEqual(result['baseFields']['directedCostsAndPhysicalReversesChecked'], 4)
        self.assertEqual(result['nativeLibraryExecutions'], 0)

    def test_missing_or_surplus_entry_pair_fails(self):
        for values in ([3, 1], [0, 1, 1, 2, 3, 1]):
            self.final.write_bytes(pack24(values))
            with self.assertRaises(AssertionError):
                self.run_audit()

    def test_supported_turn_must_remain(self):
        self.final.write_bytes(pack24([0, 1]))
        with self.assertRaises(AssertionError):
            self.run_audit()

    def test_added_prohibition_cannot_touch_originally_open_road(self):
        self.extra.write_bytes(struct.pack('<II', 3, 1))
        self.final.write_bytes(pack24([3, 1]))
        with self.assertRaises(AssertionError):
            self.run_audit()

    def test_nonjoining_source_pair_fails(self):
        self.extra.write_bytes(struct.pack('<II', 0, 2))
        with self.assertRaises(AssertionError):
            self.run_audit()

    def test_duplicate_or_partial_pairs_fail(self):
        self.extra.write_bytes(self.extra.read_bytes()*2)
        with self.assertRaises(AssertionError):
            self.run_audit()
        self.extra.write_bytes(b'x')
        with self.assertRaises(AssertionError):
            self.run_audit()

    def test_wrong_source_cost_and_native_count_fail(self):
        self.counts[-1] = 3
        with self.assertRaises(AssertionError):
            self.run_audit()
        self.counts[-1] = 4
        (self.routing/'costs.u16').write_bytes(struct.pack('<HHHH', 9, 10, 10, 10))
        with self.assertRaises(AssertionError):
            self.run_audit()

    def test_source_closure_subset_and_base_turn_rules_fail_closed(self):
        (self.original/'closures-0000.bin').write_bytes(b'')
        (self.view/'closures-0000.bin').write_bytes(struct.pack('<Q', 999))
        with self.assertRaises(AssertionError):
            self.run_audit()
        (self.view/'closures-0000.bin').write_bytes(b'')
        (self.routing/'forbidden-turns.u24').write_bytes(b'')
        with self.assertRaises(AssertionError):
            self.run_audit()

    def test_overlapping_fallback_drops_entry_but_keeps_source_closure(self):
        (self.view/'closures-0000.bin').write_bytes(struct.pack('<Q', 20))
        changed = {'offsets.u24': pack24([0, 1, 1, 2, 2, 3]), 'targets.u24': pack24([1, 3, 1]),
                   'costs.u16': struct.pack('<HHH', 10, 10, 10), 'reverse.u8': b'\xff'*3,
                   'forbidden-turns.u24': b''}
        for name, raw in changed.items():
            (self.routing/name).write_bytes(raw)
        self.final.write_bytes(b'')
        self.dims[-2], self.counts = 3, [1, 0, 0, 1, 0, 3]
        result = self.run_audit()
        self.assertEqual(result['augmentationCounts'][3], 1)


if __name__ == '__main__':
    unittest.main()
