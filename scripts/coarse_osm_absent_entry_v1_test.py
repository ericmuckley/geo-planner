import unittest

from coarse_osm_absent_entry_v1 import plan_entries
from coarse_osm_entry_graph_v1 import plan_entries as previous_plan


def relation(identity=10, tags=None, members=None):
    return {'type': 'relation', 'id': identity,
            'tags': {'type': 'restriction', 'restriction': 'no_left_turn'} | (tags or {}),
            'members': members or [{'type': 'way', 'ref': i, 'role': role} for i, role in [(1, 'from'), (2, 'via'), (3, 'to')]]}


ARCS = [{'way': i, 'tail': i-1, 'head': i} for i in (1, 2, 3)]


class AbsentEntryTests(unittest.TestCase):
    def test_present_sequence_keeps_exact_existing_entry_ban(self):
        old = previous_plan([relation()], ARCS)
        new = plan_entries([relation()], ARCS, 3)
        self.assertEqual(new['pairs'], {(0, 1)})
        for key in old:
            self.assertEqual(new[key], old[key])
        self.assertEqual(new['inactive'], [])

    def test_each_absent_essential_leg_makes_this_narrow_sequence_impossible(self):
        for missing in (1, 2, 3):
            with self.subTest(missing=missing):
                arcs = [a for a in ARCS if a['way'] != missing]
                new = plan_entries([relation()], arcs, 2)
                self.assertEqual(new['closed'], set())
                self.assertEqual(new['pairs'], set())
                self.assertEqual(new['inactive'], [{'id': 10, 'absentEssentialWays': [missing]}])
                self.assertFalse(any([a['way'], b['way'], c['way']] == [1, 2, 3]
                                     for a in arcs for b in arcs for c in arcs))

    def test_other_closure_contributors_are_never_subtracted(self):
        other = relation(11, {'restriction': 'only_straight_on'})
        new = plan_entries([relation(), other], ARCS[1:], 2)
        self.assertEqual(new['closed'], {1, 2, 3})
        self.assertEqual(new['fallback'], [11])
        self.assertEqual(len(new['inactive']), 1)

    def test_conditional_only_unknown_and_non_narrow_shapes_keep_fallback(self):
        cases = [relation(tags={'restriction:conditional': 'no_left_turn @ (Mo-Fr)'}),
                 relation(tags={'restriction': 'only_right_turn'}),
                 relation(tags={'restriction': 'unknown'}),
                 relation(members=[{'type': 'way', 'ref': 1, 'role': 'from'},
                                   {'type': 'node', 'ref': 2, 'role': 'via'},
                                   {'type': 'way', 'ref': 3, 'role': 'to'},
                                   {'type': 'way', 'ref': 4, 'role': 'via'}])]
        for element in cases:
            with self.subTest(element=element):
                new = plan_entries([element], ARCS[1:], 2)
                self.assertEqual(new['closed'], previous_plan([element], ARCS[1:])['closed'])
                self.assertEqual(new['inactive'], [])

    def test_post_closure_subset_cannot_replace_bound_preclosure_input(self):
        with self.assertRaisesRegex(ValueError, 'Complete pre-relation'):
            plan_entries([relation()], [], 3)
        with self.assertRaisesRegex(ValueError, 'bound'):
            plan_entries([relation()]*10001, ARCS, 3)


if __name__ == '__main__':
    unittest.main()
