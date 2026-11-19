import copy
import unittest

from coarse_osm_restriction_shapes_v1 import classify


def relation(kind='only_right_turn'):
    return {'id': 1, 'tags': {'type': 'restriction', 'restriction': kind},
            'members': [{'type': 'way', 'role': role, 'ref': ref}
                        for role, ref in zip(('from', 'via', 'to'), (1, 2, 3))]}


class Shapes(unittest.TestCase):
    def test_only_is_metadata_not_permission(self):
        for kind in ('only_right_turn', 'only_left_turn', 'only_straight_on', 'only_u_turn'):
            self.assertEqual(classify(relation(kind)), ('static-single-via-way-only', (1, 2, 3)))
        self.assertEqual(classify(relation('no_left_turn')), ('static-single-via-way-no', (1, 2, 3)))

    def test_car_scope_and_precedence(self):
        raw = relation(); raw['tags']['except'] = 'motorcar'
        self.assertEqual(classify(raw)[0], 'non-car')
        raw = relation(); raw['tags']['restriction:motorcar'] = 'no_right_turn'
        self.assertEqual(classify(raw)[0], 'static-single-via-way-no')
        raw['tags']['type'] = 'restriction:bicycle'
        self.assertEqual(classify(raw)[0], 'non-car')

    def test_conditional_unknown_and_arity_stay_fallback(self):
        raw = relation(); raw['tags']['restriction:conditional'] = 'only_right_turn @ (Mo-Fr)'
        self.assertEqual(classify(raw), ('conditional-fallback', None))
        self.assertEqual(classify(relation('unknown')), ('other-static-fallback', None))
        for mutation in ('duplicate', 'multi', 'node', 'same', 'invalid'):
            raw = relation()
            if mutation == 'duplicate': raw['members'][2]['role'] = 'from'
            elif mutation == 'multi': raw['members'].append({'type': 'way', 'role': 'via', 'ref': 4})
            elif mutation == 'node': raw['members'][1]['type'] = 'node'
            elif mutation == 'same': raw['members'][1]['ref'] = 1
            else: raw['members'][1]['ref'] = True
            self.assertNotEqual(classify(raw)[0], 'static-single-via-way-only')

    def test_input_is_unchanged(self):
        raw = relation(); before = copy.deepcopy(raw)
        classify(raw)
        self.assertEqual(raw, before)


if __name__ == '__main__':
    unittest.main()
