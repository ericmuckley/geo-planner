from pathlib import Path
import struct
import tempfile
import unittest

from coarse_osm_car_packed_audit_v1 import ARC, unpack24
from coarse_osm_context_records_v1 import build, u24, u32
from coarse_osm_context_records_audit_v1 import audit


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'source'
        self.source.mkdir()
        self.ids = [10, 20, 30, 40, 50]
        self.arcs = [(0, 1, 0), (1, 2, 1), (2, 3, 1), (3, 4, 2), (2, 5, 3), (6, 1, 4)]
        (self.source/'ways-0000.bin').write_bytes(b''.join(struct.pack('<QddII', n, 40, 0, 1, 0) for n in self.ids))
        (self.source/'arcs-0000.bin').write_bytes(b''.join(ARC.pack(a, b, way, 2*i, 2*i+1, 1, b'\0'*3, 125) for i, (a, b, way) in enumerate(self.arcs)))
        self.rules, self.decisions, self.entries = (self.root/n for n in ('rules.bin', 'decisions.bin', 'entries.bin'))
        self.rules.write_bytes(b''.join(struct.pack('<QQQQ', *r) for r in [(100, 10, 20, 30), (101, 10, 20, 40), (102, 50, 20, 30)]))
        self.decisions.write_bytes(b''.join(struct.pack('<QII', *r) for r in [(100, 0, 1), (101, 0, 1), (102, 0, 1)]))
        self.entries.write_bytes(b''.join(struct.pack('<II', *r) for r in [(0, 1), (5, 1)]))
        self.offsets, self.targets, self.permutation, self.supported, self.final = (self.root/n for n in ('offsets.u24', 'targets.u24', 'map.u32', 'supported.u24', 'final.u24'))
        self.output = self.root/'output'
        self.write_graph()

    def write_graph(self, closed=(), permutation=None):
        (self.source/'closures-0000.bin').write_bytes(b''.join(struct.pack('<Q', n) for n in closed))
        active = sorted((i for i, a in enumerate(self.arcs) if self.ids[a[2]] not in closed), key=lambda i: (self.arcs[i][0], i))
        native = {pre: index for index, pre in enumerate(active)}
        size = len(active)
        permutation = list(permutation) if permutation is not None else ([3, 5, 1, 4, 0, 2] if size == 6 else list(reversed(range(size))))
        self.offsets.write_bytes(u24(sum(self.arcs[i][0] < vertex for i in active) for vertex in range(8)))
        self.targets.write_bytes(u24(self.arcs[i][1] for i in active))
        self.permutation.write_bytes(u32(permutation))
        supported = [(native[1], native[2])] if 1 in native and 2 in native else []
        self.supported.write_bytes(u24(n for row in supported for n in row))
        source = {(permutation[a], permutation[b]) for a, b in supported}
        triggers = {(permutation[native[a]], permutation[native[b]]) for a, b in ((0, 1), (5, 1)) if a in native and b in native}
        self.final.write_bytes(u24(n for row in sorted(source | triggers) for n in row))
        self.dimensions = [5, 7, 6, size, 3]

    def produce(self):
        report, fields = build(self.source, self.rules, self.decisions, self.entries, self.offsets,
                               self.targets, self.permutation, self.supported, self.final, self.dimensions)
        self.output.mkdir(exist_ok=True)
        for name, raw in fields.items():
            path = self.output/name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(raw)
        return report, fields

    def verify(self):
        return audit(self.source, self.rules, self.decisions, self.entries, self.offsets,
                     self.permutation, self.supported, self.final, self.output, self.dimensions)

    def test_complete_bytes_native_state_exit_trigger_identity_and_union(self):
        report, fields = self.produce()
        self.assertEqual(list(unpack24(fields['context/state-arcs.u24'])), [1, 5, 1, 5])
        self.assertEqual(fields['context/state-offsets.u32'], u32([0, 2, 4]))
        self.assertEqual(list(unpack24(fields['context/exit-arcs.u24'])), [0, 4, 0])
        self.assertEqual(fields['context/exit-offsets.u32'], u32([0, 2, 3]))
        self.assertEqual(list(unpack24(fields['context/triggers.u24'])), [2, 5, 3, 3, 5, 1])
        self.assertEqual(fields['context/trigger-incoming.bit'], bytes([12]))
        self.assertEqual(fields['routing/forbidden-turns.u24'], u24([5, 1]))
        self.assertEqual(report['contextRuntimeBackingBytes'], 64)
        checked = self.verify()
        self.assertEqual(checked['allContextStatesSourceMapped'], 4)
        self.assertEqual(checked['allProhibitedExitArcRecordsChecked'], 3)
        self.assertEqual(checked['allActiveEntryTriggerPairsChecked'], 2)
        self.assertTrue(checked['oldFinalTurnUnionExact'])

    def test_auditor_rejects_forged_missing_and_cross_context_records(self):
        mutations = [
            {'context/state-arcs.u24': u24([3, 5, 1, 5])},
            {'context/state-offsets.u32': u32([0, 3, 4])},
            {'context/exit-arcs.u24': u24([0, 3, 0])},
            {'context/exit-arcs.u24': u24([0, 0]), 'context/exit-offsets.u32': u32([0, 1, 2])},
            {'context/triggers.u24': u24([2, 5, 1, 3, 5, 1])},
            {'context/triggers.u24': u24([3, 5, 1])},
            {'context/trigger-incoming.bit': bytes([0])},
            {'routing/forbidden-turns.u24': b''},
            {'prefix-counts.bin': b''},
        ]
        for changed in mutations:
            with self.subTest(fields=list(changed)):
                self.produce()
                for name, raw in changed.items():
                    (self.output/name).write_bytes(raw)
                with self.assertRaises(AssertionError):
                    self.verify()

    def test_nonidentity_and_identity_spatial_orders_both_source_reconcile(self):
        for permutation in (range(6), reversed(range(6))):
            self.write_graph(permutation=permutation)
            self.produce()
            self.assertEqual(self.verify()['allSupportedTurnPairsRetained'], 1)

    def test_other_closure_keeps_unreachable_prefix_states_without_permission_inference(self):
        self.write_graph(closed=[50])
        report, _ = self.produce()
        self.assertEqual(report['contextPrefixGroups'], 2)
        self.assertEqual(report['contextStates'], 4)
        self.assertEqual(report['activeTriggerPairs'], 1)
        self.assertEqual(self.verify()['allActiveEntryTriggerPairsChecked'], 1)

    def test_empty_context_groups_and_empty_turn_table_are_valid(self):
        self.write_graph(closed=[20])
        report, fields = self.produce()
        self.assertEqual(report['contextStates'], 0)
        self.assertEqual(fields['context/state-offsets.u32'], u32([0, 0, 0]))
        self.assertEqual(fields['context/triggers.u24'], b'')
        self.assertEqual(fields['routing/forbidden-turns.u24'], b'')
        self.assertEqual(self.verify()['allContextPrefixesChecked'], 2)

    def test_csr_source_target_and_permutation_corruption_stop_construction(self):
        self.targets.write_bytes(u24([6, 2, 3, 5, 4, 1]))
        with self.assertRaises(AssertionError):
            self.produce()
        self.write_graph()
        self.permutation.write_bytes(u32([0]*6))
        with self.assertRaises(AssertionError):
            self.produce()

    def test_source_only_turns_cannot_disappear_or_gain_an_unrecorded_exemption(self):
        self.final.write_bytes(u24([2, 5, 3, 5]))
        with self.assertRaises(AssertionError):
            self.produce()
        self.write_graph()
        self.supported.write_bytes(b'')
        with self.assertRaises(AssertionError):
            self.produce()

    def test_complete_dimension_drift_and_callback_cancellation_stop(self):
        self.dimensions[2] += 1
        with self.assertRaises(AssertionError):
            self.produce()
        self.write_graph()
        def cancel():
            raise ValueError('cancelled')
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            build(self.source, self.rules, self.decisions, self.entries, self.offsets, self.targets,
                  self.permutation, self.supported, self.final, self.dimensions, cancel)


if __name__ == '__main__':
    unittest.main()
