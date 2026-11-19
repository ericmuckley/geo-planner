import copy
import unittest

from coarse_osm_car_passable_barriers_v1 import graph_node_decision
from coarse_osm_car_policy_v1 import TURN_KINDS
from coarse_osm_incomplete_node_restrictions_v1 import classify, remaining_contributors
from coarse_timing_input import PilotError


def singleton(identity=1, node=100, kind='no_u_turn'):
    return {'type': 'relation', 'id': identity, 'tags': {'type': 'restriction', 'restriction': kind},
            'members': [{'type': 'node', 'ref': node, 'role': 'via'}]}


class Tests(unittest.TestCase):
    def test_all_documented_static_kinds_identify_missing_both_roads_without_mutation(self):
        for kind in TURN_KINDS:
            element = singleton(kind=kind)
            before = copy.deepcopy(element)
            rule = classify(element)['rule']
            self.assertEqual((rule.identity, rule.via_node, rule.kind), (1, 100, kind))
            self.assertEqual(element, before)

    def test_complete_valid_and_way_containing_or_other_shapes_never_change(self):
        element = singleton()
        from_way = {'type': 'way', 'role': 'from', 'ref': 10}
        to_way = {'type': 'way', 'role': 'to', 'ref': 20}
        for members in (element['members'] + [from_way, to_way], element['members'] + [from_way],
                        element['members'] * 2, [], [{'type': 'relation', 'role': 'via', 'ref': 100}],
                        [{'type': 'node', 'role': 'from', 'ref': 100}]):
            self.assertIsNone(classify(element | {'members': members})['rule'])

    def test_unknown_mixed_and_every_conditional_keep_fallback(self):
        element = singleton()
        for changes in ({'restriction': 'no_movement'}, {'restriction:motorcar': 'only_left_turn'},
                        {'restriction:conditional': 'no_u_turn @ (Mo-Fr)'}, {'locked:conditional': 'yes'},
                        {'restriction:unknown': 'no_u_turn'}, {'except': 'motorcar'}, {'except': 'unknown'},
                        {'except': ''}, {'type': 'restriction:unknown'}):
            self.assertIsNone(classify(element | {'tags': element['tags'] | changes})['rule'])

    def test_exact_car_types_hierarchy_and_known_noncar_exceptions(self):
        element = singleton()
        for kind in ('restriction', 'restriction:motorcar', 'restriction:motor_vehicle', 'restriction:vehicle'):
            tags = {'type': kind, 'restriction:motorcar': 'no_u_turn', 'restriction:vehicle': 'no_u_turn', 'except': 'bus;bicycle'}
            self.assertIsNotNone(classify(element | {'tags': tags})['rule'])

    def test_independent_node_causes_remain_and_direct_barriers_still_block(self):
        rule = classify(singleton())['rule']
        remaining = remaining_contributors(100, [1, 2], {1: rule})
        self.assertEqual(remaining, [2])
        self.assertTrue(graph_node_decision({}, remaining)['blocked'])
        remaining = remaining_contributors(100, [1], {1: rule})
        self.assertEqual(remaining, [])
        self.assertFalse(graph_node_decision({}, remaining)['blocked'])
        for tags in ({'access': 'private'}, {'barrier': 'gate'}, {'barrier': 'gate', 'access': 'yes', 'locked:conditional': 'yes'}):
            self.assertTrue(graph_node_decision(tags, remaining)['blocked'])

    def test_malformed_native_identity_unknown_member_or_wrong_node_refuse(self):
        element = singleton()
        for changes in ({'id': True}, {'id': 0}, {'id': 2**63}, {'type': 'way'}, {'tags': None}):
            self.assertIsNone(classify(element | changes)['rule'])
        self.assertIsNone(classify(element | {'members': [{'type': 'node', 'role': 'via', 'ref': True}]})['rule'])
        rule = classify(element)['rule']
        with self.assertRaises(PilotError):
            remaining_contributors(200, [1], {1: rule})
        with self.assertRaises(PilotError):
            remaining_contributors(100, [1, 1], {1: rule})


if __name__ == '__main__':
    unittest.main()
