from pathlib import Path
import struct
import tempfile
import unittest

from coarse_osm_entry_resolution_audit_v1 import audit


class Controls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source, self.output = self.root/'source', self.root/'output'
        self.source.mkdir()
        self.output.mkdir()
        self.arcs = [(0, 1, 0, 0, 1, 1, 1250), (1, 2, 1, 0, 1, 1, 1250),
                     (2, 3, 2, 0, 1, 1, 1250), (4, 1, 3, 0, 1, 1, 1250)]
        self.write_arcs()
        (self.source/'ways-0000.bin').write_bytes(b''.join(struct.pack('<QddII', n, 40, 40, 3, 2*(i+1)) for i, n in enumerate((10, 20, 30, 40))))
        (self.source/'closures-0000.bin').write_bytes(struct.pack('<QQQ', 10, 20, 30))
        self.rules, self.fallback = self.root/'rules.bin', self.root/'fallback.u64'
        self.rules.write_bytes(struct.pack('<QQQQ', 1, 10, 20, 30))
        self.fallback.write_bytes(b'')
        self.set_output([], [(0, 1)], (1, 0, 1))
        self.dims, self.counts, self.old_post = [4, 5, 4, 1, 0], [1, 1, 0, 0, 3, 0, 1, 4, 4], 1

    def write_arcs(self):
        (self.source/'arcs-0000.bin').write_bytes(b''.join(struct.pack('<IIIIIb3xQ', *r) for r in self.arcs))

    def set_output(self, closed, pairs, decision):
        (self.output/'closures-0000.bin').write_bytes(b''.join(struct.pack('<Q', n) for n in closed))
        (self.output/'entry-pairs-pre.u32').write_bytes(b''.join(struct.pack('<II', *p) for p in pairs))
        (self.output/'decisions.bin').write_bytes(struct.pack('<QII', *decision))

    def run_audit(self):
        return audit(self.source, self.rules, self.fallback, self.output, self.dims, self.counts, baseline_post=self.old_post)

    def test_complete_source_decision_pair_closure_and_count_audit(self):
        result = self.run_audit()
        self.assertEqual(result['preArcsChecked'], 4)
        self.assertTrue(result['fallbackUnionExact'])
        self.assertEqual(result['nativeLibraryExecutions'], 0)

    def test_missing_member_keeps_full_source_fallback(self):
        self.rules.write_bytes(struct.pack('<QQQQ', 1, 10, 20, 99))
        (self.source/'closures-0000.bin').write_bytes(struct.pack('<QQQ', 10, 20, 99))
        self.set_output([10, 20, 99], [], (1, 1, 0))
        self.counts, self.old_post = [1, 0, 1, 0, 3, 3, 0, 4, 2], 2
        self.assertEqual(self.run_audit()['candidatePostArcs'], 2)

    def test_no_actual_source_junction_keeps_full_fallback(self):
        self.arcs[1] = (2, 3, 1, 0, 1, 1, 1250)
        self.arcs[2] = (3, 4, 2, 0, 1, 1, 1250)
        self.write_arcs()
        self.set_output([10, 20, 30], [], (1, 2, 0))
        self.counts = [1, 0, 0, 1, 3, 3, 0, 4, 1]
        self.assertEqual(self.run_audit()['candidatePostArcs'], 1)

    def test_other_fallback_closure_must_remain_even_for_converted_relation(self):
        self.fallback.write_bytes(struct.pack('<Q', 20))
        self.set_output([20], [(0, 1)], (1, 0, 1))
        self.dims[-1], self.counts = 1, [1, 1, 0, 0, 3, 1, 1, 4, 3]
        self.assertEqual(self.run_audit()['overrideClosureIdsChecked'], 1)
        (self.output/'closures-0000.bin').write_bytes(b'')
        with self.assertRaises(AssertionError):
            self.run_audit()

    def test_forged_pair_and_missing_decision_cannot_pass(self):
        (self.output/'entry-pairs-pre.u32').write_bytes(struct.pack('<II', 3, 1))
        with self.assertRaises(AssertionError):
            self.run_audit()
        (self.output/'entry-pairs-pre.u32').write_bytes(struct.pack('<II', 0, 1))
        (self.output/'decisions.bin').write_bytes(b'')
        with self.assertRaises(AssertionError):
            self.run_audit()

    def test_original_and_new_arc_counts_must_both_reconcile(self):
        self.counts[-1] = 3
        with self.assertRaises(AssertionError):
            self.run_audit()
        self.counts[-1], self.old_post = 4, 2
        with self.assertRaises(AssertionError):
            self.run_audit()

    def test_malformed_source_arc_cost_order_and_dimensions_fail(self):
        self.arcs[0] = (*self.arcs[0][:-1], 0)
        self.write_arcs()
        with self.assertRaises(AssertionError):
            self.run_audit()
        self.dims[0] = 8000001
        with self.assertRaises(AssertionError):
            self.run_audit()

    def test_duplicate_candidate_identity_and_partial_binary_fail(self):
        self.rules.write_bytes(self.rules.read_bytes()*2)
        self.dims[3] = 2
        (self.output/'decisions.bin').write_bytes(struct.pack('<QII', 1, 0, 1)*2)
        with self.assertRaises(AssertionError):
            self.run_audit()
        self.rules.write_bytes(b'X')
        with self.assertRaises(AssertionError):
            self.run_audit()


if __name__ == '__main__':
    unittest.main()
