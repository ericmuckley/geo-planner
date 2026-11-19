from pathlib import Path
import struct
import tempfile
import unittest

from coarse_osm_car_packed_audit_v1 import ARC
from coarse_osm_context_footprint_v1 import PREFIX_COUNT, inventory


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ids = [10, 20, 30, 40, 50]
        self.arcs = [(0, 1, 0), (1, 2, 1), (2, 3, 1), (3, 4, 2), (2, 5, 3), (6, 1, 4)]
        self.rules = [(100, 10, 20, 30), (101, 10, 20, 40), (102, 50, 20, 30)]
        self.decisions = [(100, 0, 1), (101, 0, 1), (102, 0, 1)]
        self.pairs = [(0, 1), (5, 1)]
        self.closed = []

    def run_inventory(self, dimensions=None, check=lambda: None):
        (self.root/'ways-0000.bin').write_bytes(b''.join(struct.pack('<QddII', n, 40, 40, 3, 0) for n in self.ids))
        (self.root/'arcs-0000.bin').write_bytes(b''.join(ARC.pack(tail, head, way, 2*i, 2*i+1, 1, b'\0'*3, 125) for i, (tail, head, way) in enumerate(self.arcs)))
        (self.root/'closures-0000.bin').write_bytes(b''.join(struct.pack('<Q', n) for n in self.closed))
        rules, decisions, pairs = (self.root/n for n in ('rules.bin', 'decisions.bin', 'pairs.bin'))
        rules.write_bytes(b''.join(struct.pack('<QQQQ', *r) for r in self.rules))
        decisions.write_bytes(b''.join(struct.pack('<QII', *r) for r in self.decisions))
        pairs.write_bytes(b''.join(struct.pack('<II', *r) for r in self.pairs))
        retained = sum(self.ids[way] not in self.closed for _, _, way in self.arcs)
        return inventory(self.root, rules, decisions, pairs,
                         dimensions or [len(self.ids), 7, len(self.arcs), retained, len(self.rules)], check)

    def test_complete_group_union_state_exit_label_and_byte_bounds(self):
        report, raw = self.run_inventory()
        self.assertEqual(report['completePreArcsChecked'], 6)
        self.assertEqual(report['resolvedRulesRetained'], 3)
        self.assertEqual(report['allResolvedPrefixGroups'], 2)
        self.assertEqual(report['additionalContextStateUpperBound'], 4)
        self.assertEqual(report['possibleExitArcRecordsUpperBound'], 3)
        self.assertEqual(report['activeEntryPairs'], 2)
        self.assertEqual(report['additionalQueryLabelBytes'], 16)
        self.assertEqual(report['rawContextRuntimeFieldsUpperBoundBytes'], 63)
        self.assertEqual(report['triggerIncomingBitsetBytes'], 1)
        self.assertEqual(list(PREFIX_COUNT.iter_unpack(raw)), [(10, 20, 2, 2, 2, 1), (50, 20, 2, 1, 1, 1)])
        self.assertFalse(report['runtimeArtifactBuilt'])
        self.assertFalse(report['sourceCostsOrFlagsOrClosureUnionChanged'])

    def test_other_closures_do_not_make_resolved_rules_missing(self):
        self.closed = [20]
        report, _ = self.run_inventory()
        self.assertEqual(report['resolvedRulesRetained'], 3)
        self.assertEqual(report['inactiveMissingMemberRulesRetained'], 0)
        self.assertEqual(report['additionalContextStateUpperBound'], 0)
        self.assertEqual(report['activeEntryPairs'], 0)
        self.assertEqual(report['entryPairsBlockedByOtherClosures'], 2)

    def test_blocked_entry_contexts_are_included_in_conservative_bound(self):
        self.closed = [50, 99]
        report, raw = self.run_inventory()
        self.assertEqual(report['closureIdsRetained'], 2)
        self.assertEqual(report['allResolvedPrefixGroups'], 2)
        self.assertEqual(report['activeEntryPrefixGroups'], 1)
        self.assertEqual(report['additionalContextStateUpperBound'], 4)
        self.assertEqual(report['activePrefixOnlyContextStates'], 2)
        self.assertEqual(list(PREFIX_COUNT.iter_unpack(raw))[1][-1], 0)

    def test_missing_selected_zero_arc_and_outside_ways_stay_explicit(self):
        self.ids.append(60)
        self.rules.extend([(103, 10, 20, 60), (104, 10, 20, 99)])
        self.decisions.extend([(103, 3, 0), (104, 3, 0)])
        report, _ = self.run_inventory()
        self.assertEqual(report['inactiveMissingMemberRulesRetained'], 2)
        self.assertEqual(report['allResolvedPrefixGroups'], 2)
        self.decisions[-1] = (104, 0, 1)
        with self.assertRaises(AssertionError):
            self.run_inventory()

    def test_no_join_fallback_requires_all_member_closures(self):
        self.rules.append((103, 30, 10, 50))
        self.decisions.append((103, 2, 0))
        with self.assertRaisesRegex(AssertionError, 'fallback closure lost'):
            self.run_inventory()
        self.closed = [10, 30, 50]
        report, _ = self.run_inventory()
        self.assertEqual(report['noJoinFallbackRulesRetained'], 1)
        self.assertEqual(report['resolvedRulesRetained'], 3)

    def test_entry_pair_order_identity_and_actual_junction_are_checked(self):
        self.pairs = [(0, 1), (0, 1)]
        with self.assertRaises(AssertionError):
            self.run_inventory()
        self.pairs = [(0, 2)]
        with self.assertRaises(AssertionError):
            self.run_inventory()
        self.pairs = [(0, 9)]
        with self.assertRaises(AssertionError):
            self.run_inventory()
        self.pairs = [(0, 1)]
        self.decisions[0] = (999, 0, 1)
        with self.assertRaises(AssertionError):
            self.run_inventory()

    def test_complete_counts_status_and_sorted_source_ids_cannot_drift(self):
        for dimensions in ([5, 7, 7, 6, 3], [5, 7, 6, 5, 3], [5, 7, 6, 6, 4]):
            with self.assertRaises(AssertionError):
                self.run_inventory(dimensions)
        self.decisions[0] = (100, 1, 0)
        with self.assertRaises(AssertionError):
            self.run_inventory()
        self.ids[1] = self.ids[0]
        with self.assertRaises(AssertionError):
            self.run_inventory()

    def test_streaming_callback_stops_a_large_synthetic_fact_pass(self):
        self.ids = [10]
        self.arcs = [(0, 1, 0)]*65536
        self.rules = self.decisions = self.pairs = []
        def cancel():
            raise ValueError('cancelled')
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            self.run_inventory(check=cancel)


if __name__ == '__main__':
    unittest.main()
