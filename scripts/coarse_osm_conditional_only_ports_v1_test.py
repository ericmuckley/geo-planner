import copy
import unittest

from coarse_osm_conditional_node_ports_v1_test import fixture, rule
from coarse_osm_conditional_only_ports_v1 import audit, qualify
from coarse_timing_input import PilotError


def mandatory(**kw):
    return rule(kind='only_right_turn', **kw)


class Tests(unittest.TestCase):
    def checked(self, fields, rules):
        before = copy.deepcopy(fields)
        result = qualify(fields, rules)
        proof = audit(fields, rules, result)
        self.assertEqual(before, fields)
        self.assertEqual(proof['allCandidateSourceDescriptorsIndependentlyReplayed'], len(rules))
        return result, proof

    def test_complete_ports_and_approaches_with_uint64_source_identity(self):
        fields = fixture()
        offset = 2**53 + 1
        fields['ids'] = [v + offset for v in fields['ids']]
        fields['ways'] = [(v[0] + offset, *v[1:]) for v in fields['ways']]
        result, proof = self.checked(fields, [mandatory(from_way=10 + offset, via_node=200 + offset, to_way=20 + offset)])
        row = result['rows'][0]
        self.assertEqual(row['viaNodeId'], str(200 + offset))
        self.assertEqual(row['incomingPreArcIds'], [0])
        self.assertEqual(row['allOutgoingPreArcIds'], [1, 2])
        self.assertEqual(row['toOutgoingPreArcIds'], [2])
        self.assertEqual(row['forbiddenPreArcPairs'], [[0, 1]])
        self.assertEqual(proof['supportedRules'], 1)

    def test_unrelated_outgoing_way_is_included_and_wrong_approach_unaffected(self):
        fields = fixture()
        fields['ways'][2] = (30, 50., 50., 3, 6)
        fields['arcs'] += [(1, 2, 2, 0, 1, 1, bytes(3), 1000), (2, 1, 2, 0, 1, -1, bytes(3), 1000)]
        result, _ = self.checked(fields, [mandatory()])
        row = result['rows'][0]
        self.assertEqual(row['allOutgoingPreArcIds'], [1, 2, 4])
        self.assertEqual(row['forbiddenPreArcPairs'], [[0, 1], [0, 4]])
        self.assertTrue(all(pair[0] == 0 for pair in row['forbiddenPreArcPairs']))

    def test_missing_ineligible_or_disconnected_to_port_forbids_all_other_exits(self):
        for target in [30, 999]:
            result, proof = self.checked(fixture(), [mandatory(to_way=target)])
            row = result['rows'][0]
            self.assertEqual(row['status'], 'source-ports-supported')
            self.assertEqual(row['toOutgoingPreArcIds'], [])
            self.assertEqual(row['forbiddenPreArcPairs'], [[0, 1], [0, 2]])
            self.assertEqual(proof['supportedRulesWithoutToPorts'], 1)
        result, _ = self.checked(fixture(), [mandatory(via_node=100)])
        self.assertEqual(result['rows'][0]['toWayStatus'], 'to-way-base-eligible')
        self.assertEqual(result['rows'][0]['toOutgoingPreArcIds'], [])
        self.assertEqual(result['rows'][0]['forbiddenPreArcPairs'], [[1, 0]])

    def test_source_from_missing_ineligible_missing_via_nonanchor_and_no_incoming_keep_fallback(self):
        for candidate, reason in [(mandatory(from_way=999), 'from-way-outside-major-facts'),
                                  (mandatory(from_way=30), 'from-way-base-ineligible'),
                                  (mandatory(via_node=999), 'via-node-not-in-selected-source'),
                                  (mandatory(via_node=400), 'via-node-not-an-anchor'),
                                  (mandatory(from_way=20, via_node=100, to_way=10), 'no-directed-incoming-source-port')]:
            result, _ = self.checked(fixture(), [candidate])
            self.assertEqual(result['rows'][0]['status'], reason)
            self.assertEqual(result['rows'][0]['forbiddenPreArcPairs'], [])

    def test_multiplicity_keeps_every_directed_native_port(self):
        fields = fixture()
        fields['ways'] = [(10, 50., 50., 3, 5), (20, 50., 50., 3, 7), (30, 0., 0., 3 << 8, 9)]
        fields['arcs'] = [(0, 1, 0, 0, 1, 1, bytes(3), 1000), (1, 0, 0, 0, 1, -1, bytes(3), 1000),
                          (1, 1, 0, 1, 4, 1, bytes(3), 3000), (1, 1, 0, 1, 4, -1, bytes(3), 3000),
                          (1, 2, 1, 0, 1, 1, bytes(3), 1000), (2, 1, 1, 0, 1, -1, bytes(3), 1000)]
        result, _ = self.checked(fields, [mandatory()])
        row = result['rows'][0]
        self.assertEqual(row['incomingPreArcIds'], [0, 2, 3])
        self.assertEqual(row['allOutgoingPreArcIds'], [1, 2, 3, 4])
        self.assertEqual(row['toOutgoingPreArcIds'], [4])
        self.assertEqual(len(row['forbiddenPreArcPairs']), 9)

    def test_more_than_64_ports_preserves_complete_fallback_without_truncation(self):
        fields = fixture()
        fields['ways'][0] = (10, 50., 50., 3, 132)
        fields['ways'][1] = (20, 50., 50., 3, 134)
        fields['ways'][2] = (30, 0., 0., 3 << 8, 136)
        fields['arcs'] = [(1, 1, 0, n, n + 1, 1, bytes(3), 1000) for n in range(65)]
        result, _ = self.checked(fields, [mandatory()])
        row = result['rows'][0]
        self.assertEqual(row['status'], 'source-port-complexity-fallback')
        self.assertEqual(len(row['allOutgoingPreArcIds']), 65)
        self.assertEqual(row['forbiddenPreArcPairs'], [])

    def test_all_source_order_direction_price_padding_and_dimension_guards(self):
        for key, value in [('ids', [200, 100, 300, 400]), ('anchors', [0, 1, 1]),
                           ('ways', list(reversed(fixture()['ways']))), ('arcs', list(reversed(fixture()['arcs'])))]:
            fields = fixture()
            fields[key] = value
            with self.assertRaises(PilotError):
                qualify(fields, [mandatory()])
        for slot, value in [(0, 3), (2, 3), (4, 2), (5, 0), (6, b'bad'), (7, 0)]:
            fields = fixture()
            arc = list(fields['arcs'][0])
            arc[slot] = value
            fields['arcs'][0] = tuple(arc)
            with self.assertRaises(PilotError):
                qualify(fields, [mandatory()])

    def test_independent_join_refuses_omitted_unrelated_exit_wrong_to_ban_or_status(self):
        fields = fixture()
        result = qualify(fields, [mandatory()])
        for key, value in [('allOutgoingPreArcIds', [2]), ('incomingPreArcIds', [1]),
                           ('toOutgoingPreArcIds', [1]), ('forbiddenPreArcPairs', [[0, 2]]),
                           ('viaAnchor', 0), ('status', 'no-directed-incoming-source-port')]:
            changed = copy.deepcopy(result)
            changed['rows'][0][key] = value
            with self.assertRaises(PilotError):
                audit(fields, [mandatory()], changed)
        result['selectedSourcePortRows'] += 1
        with self.assertRaises(PilotError):
            audit(fields, [mandatory()], result)

    def test_duplicate_invalid_or_prohibitory_rules_refuse_and_empty_selection_is_complete(self):
        for rules in [[mandatory(), mandatory()], [mandatory(to_way=10)], [rule()], [mandatory(identity=True)]]:
            with self.assertRaises(PilotError):
                qualify(fixture(), rules)
        result, proof = self.checked(fixture(), [])
        self.assertEqual(result['rows'], [])
        self.assertEqual(proof['secondSourcePreArcsChecked'], 4)


if __name__ == '__main__':
    unittest.main()
