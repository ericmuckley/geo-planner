"""Metadata and exhaustive projected-state controls, never national source permission."""
import copy
import itertools
import unittest

from coarse_osm_conditional_node_turns_v2 import classify as previous
from coarse_osm_conditional_only_node_v1 import KINDS, _project_syntax, classify, forbidden_exits
from coarse_timing_input import PilotError


def relation(kind='only_right_turn', condition='(Mo-Fr 07:00-09:00)'):
    return {'id': 2**53 + 7, 'tags': {'type': 'restriction', 'restriction:conditional': kind + ' @ ' + condition},
            'members': [{'type': 'way', 'role': 'from', 'ref': 2**53 + 9},
                        {'type': 'node', 'role': 'via', 'ref': 2**53 + 11},
                        {'type': 'way', 'role': 'to', 'ref': 2**53 + 13}]}


class Tests(unittest.TestCase):
    def test_three_kinds_exact_uint64_identities_and_source_preserved(self):
        for kind in KINDS:
            source = relation(kind)
            before = copy.deepcopy(source)
            rule = classify(source)['rule']
            self.assertEqual((rule.identity, rule.from_way, rule.via_node, rule.to_way, rule.kind),
                             (2**53 + 7, 2**53 + 9, 2**53 + 11, 2**53 + 13, kind))
            self.assertEqual(source, before)
            self.assertIsNone(previous(source)['rule'])

    def test_all_known_mode_keys_and_same_kind_base_values(self):
        for key in ['restriction', 'restriction:motorcar', 'restriction:motor_vehicle', 'restriction:vehicle']:
            item = relation()
            item['tags'] = {'type': 'restriction', key: 'only_right_turn', key + ':conditional': 'only_right_turn @ wet'}
            self.assertEqual(classify(item)['rule'].kind, 'only_right_turn')

    def test_guard_types_members_exemptions_and_unknown_keys(self):
        mutations = [lambda x: x['tags'].update(type='restriction:unknown'),
                     lambda x: x['tags'].update({'except': 'motorcar'}),
                     lambda x: x['tags'].update({'except': 'unknown'}),
                     lambda x: x['tags'].update({'restriction:bus:conditional': 'only_right_turn @ wet'}),
                     lambda x: x['tags'].update({'access:conditional': 'yes @ wet'}),
                     lambda x: x['members'][1].update(type='way'),
                     lambda x: x['members'][2].update(ref=x['members'][0]['ref']),
                     lambda x: x['members'].append({'type': 'node', 'role': 'via', 'ref': 99}),
                     lambda x: x.update(id=True)]
        for mutate in mutations:
            item = relation()
            mutate(item)
            self.assertIsNone(classify(item)['rule'])
        item = relation()
        item['tags']['except'] = 'bicycle;bus'
        self.assertIsNotNone(classify(item)['rule'])

    def test_mixed_no_turns_unknown_only_uturn_and_unconditional_keep_fallback(self):
        for value in ['only_u_turn', 'only_unknown', 'no_right_turn']:
            self.assertIsNone(classify(relation(value))['rule'])
        for base in ['no_right_turn', 'only_left_turn', 'none']:
            item = relation()
            item['tags']['restriction'] = base
            self.assertIsNone(classify(item)['rule'])
        item = relation()
        item['tags'] = {'type': 'restriction', 'restriction': 'only_right_turn'}
        self.assertIsNone(classify(item)['rule'])

    def test_opaque_conditions_preserved_and_original_bounds_applied_before_translation(self):
        text = ' only_right_turn @ (Mo;Tu); only_right_turn @ (wet AND only_right_turn)'
        values, projected = _project_syntax(text)
        self.assertEqual(values, ['only_right_turn', 'only_right_turn'])
        self.assertEqual(projected, ' no_right_turn @ (Mo;Tu); no_right_turn @ (wet AND only_right_turn)')
        prefix = 'only_right_turn @ '
        self.assertIsNotNone(_project_syntax(prefix + 'x' * (65536 - len(prefix))))
        self.assertIsNone(_project_syntax(prefix + 'x' * (65537 - len(prefix))))
        self.assertIsNotNone(_project_syntax(';'.join(['only_right_turn @ wet'] * 64)))
        self.assertIsNone(_project_syntax(';'.join(['only_right_turn @ wet'] * 65)))

    def test_malformed_syntax_and_mixed_clauses_refuse(self):
        for value in ['only_right_turn @ ()', 'only_right_turn @', 'only_right_turn @ (wet',
                      'only_right_turn @ wet)', 'only_right_turn @ wet @ snow',
                      'only_right_turn @ "event"', 'only_right_turn @ (((((((((wet)))))))))',
                      'only_right_turn @ wet;', 'only_right_turn @ wet; no_right_turn @ snow']:
            self.assertIsNone(_project_syntax(value))
        item = relation()
        item['tags']['restriction:conditional'] = 'only_right_turn @ wet; only_left_turn @ snow'
        self.assertIsNone(classify(item)['rule'])

    def test_exhaustive_allowed_exit_sets_are_conservative_in_every_active_state(self):
        outgoing = [10, 20, 30, 40]
        for size in range(5):
            for selected in itertools.combinations(outgoing, size):
                pairs = set(forbidden_exits([1, 2], outgoing, list(selected)))
                for active in [False, True]:
                    for old_bans in [set(), {(1, 20)}, {(2, 30), (3, 40)}]:
                        combined = pairs | old_bans
                        self.assertTrue(old_bans <= combined)
                        for incoming, target in itertools.product([1, 2, 3], outgoing):
                            if (incoming, target) in combined:
                                continue
                            self.assertTrue(incoming == 3 or not active or target in selected)
                            if incoming == 3:
                                self.assertEqual((incoming, target) in combined, (incoming, target) in old_bans)

    def test_missing_to_ports_forbid_all_exits_and_no_incoming_has_no_effect(self):
        self.assertEqual(forbidden_exits([1], [10, 20], []), [(1, 10), (1, 20)])
        self.assertEqual(forbidden_exits([], [10, 20], [20]), [])

    def test_multiple_mandatory_envelopes_intersect_without_opening_prior_bans(self):
        outgoing = [10, 20, 30]
        for a in [[], [10], [10, 20]]:
            for b in [[], [20], [10, 20]]:
                bans = set(forbidden_exits([1], outgoing, a)) | set(forbidden_exits([1], outgoing, b))
                self.assertEqual({o for o in outgoing if (1, o) not in bans}, set(a) & set(b))

    def test_forged_unsorted_duplicate_bool_overflow_and_capacity_ports_refuse(self):
        for ports in [[2, 1], [1, 1], [True], [-1], [0xffffff], list(range(65))]:
            with self.assertRaises(PilotError):
                forbidden_exits(ports, [10], [10])
        with self.assertRaises(PilotError):
            forbidden_exits([1], [10], [20])


if __name__ == '__main__':
    unittest.main()
