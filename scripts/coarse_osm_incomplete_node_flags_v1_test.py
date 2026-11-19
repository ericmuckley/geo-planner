import copy
import unittest

from coarse_osm_incomplete_node_flags_v1 import audit, build, rules_from_metadata
from coarse_osm_incomplete_node_restrictions_v1_test import singleton
from coarse_timing_input import PilotError


def fixture():
    from dataclasses import asdict
    from coarse_osm_incomplete_node_restrictions_v1 import classify
    rule = classify(singleton(node=100))['rule']
    rules = rules_from_metadata([{'source': singleton(node=100), 'derived': asdict(rule)}])
    mapping = [{'vertex': 1, 'sourceAnchor': 0, 'sourceNodeId': '100', 'flags': 7},
               {'vertex': 0, 'sourceAnchor': 1, 'sourceNodeId': '200', 'flags': 5}]
    evidence = {'100': {'rawTags': {'highway': 'traffic_signals'}, 'restrictionContributorIds': [1]},
                '200': {'rawTags': {'barrier': 'cattle_grid'}, 'restrictionContributorIds': []}}
    return bytes([4, 7, 4]), mapping, evidence, [1, 0, 2], rules


class Tests(unittest.TestCase):
    def test_composed_opening_preserves_signal_reversal_and_previous_cattle_grid(self):
        flags, mapping, evidence, permutation, rules = fixture()
        proposed, changes = build(flags, mapping, evidence, permutation, rules)
        self.assertEqual(proposed, bytes([4, 6, 4]))
        self.assertEqual([r['vertex'] for r in changes], [1])
        proof = audit(flags, proposed, mapping, evidence, permutation, rules)
        self.assertEqual(list(proof['changedVertices']), [1])
        self.assertTrue(proof['everyOldOpenVertexExact'])
        self.assertTrue(proof['signalsAndReversalBitsExact'])

    def test_independent_contributor_or_direct_node_guard_stays_blocked(self):
        for change in ('other-relation', 'private', 'locked'):
            flags, mapping, evidence, permutation, rules = fixture()
            if change == 'other-relation':
                evidence['100']['restrictionContributorIds'] = [1, 2]
            else:
                evidence['100']['rawTags'] |= ({'access': 'private'} if change == 'private' else
                                              {'barrier': 'gate', 'access': 'yes', 'locked:conditional': 'yes'})
            proposed, changes = build(flags, mapping, evidence, permutation, rules)
            self.assertEqual(proposed, flags)
            self.assertEqual(changes, [])
            audit(flags, proposed, mapping, evidence, permutation, rules)

    def test_current_flag_source_identity_and_complete_permutation_drift_refuse(self):
        flags, mapping, evidence, permutation, rules = fixture()
        for bad in ([1, 1, 2], [1, 0], [1, 0, 3]):
            with self.assertRaises(PilotError):
                build(flags, mapping, evidence, bad, rules)
        altered = copy.deepcopy(mapping)
        altered[0]['sourceAnchor'] = 1
        with self.assertRaises(PilotError):
            build(flags, altered, evidence, permutation, rules)
        with self.assertRaises(PilotError):
            build(bytes([5, 7, 4]), mapping, evidence, permutation, rules)
        with self.assertRaises(PilotError):
            build(bytes([4, 7, 5]), mapping, evidence, permutation, rules)

    def test_independent_full_byte_audit_rejects_invented_opening_or_signal_change(self):
        flags, mapping, evidence, permutation, rules = fixture()
        proposed, _ = build(flags, mapping, evidence, permutation, rules)
        for invalid in (bytes([0, 6, 4]), bytes([4, 4, 4]), bytes([4, 6, 5]), flags):
            with self.assertRaises(PilotError):
                audit(flags, invalid, mapping, evidence, permutation, rules)

    def test_metadata_source_derived_identity_and_complete_order_are_bound(self):
        from dataclasses import asdict
        from coarse_osm_incomplete_node_restrictions_v1 import classify
        row = {'source': singleton(), 'derived': asdict(classify(singleton())['rule'])}
        for rows in ([row, row], [row | {'derived': row['derived'] | {'via_node': 200}}]):
            with self.assertRaises(PilotError):
                rules_from_metadata(rows)

    def test_a_different_native_node_cannot_lose_this_contribution(self):
        from dataclasses import replace
        flags, mapping, evidence, permutation, rules = fixture()
        wrong = {1: replace(rules[1], via_node=200)}
        with self.assertRaises(PilotError):
            build(flags, mapping, evidence, permutation, wrong)
        with self.assertRaises(PilotError):
            audit(flags, bytes([4, 6, 4]), mapping, evidence, permutation, wrong)


if __name__ == '__main__':
    unittest.main()
