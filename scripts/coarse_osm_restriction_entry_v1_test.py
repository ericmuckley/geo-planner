import unittest

from coarse_osm_restriction_entry_v1 import entry_pairs, entry_restriction


def relation(kind='no_u_turn'):
    return {'id': 1, 'tags': {'type': 'restriction', 'restriction': kind},
            'members': [{'type': 'way', 'role': r, 'ref': v} for r, v in [('from', 10), ('via', 20), ('to', 30)]]}


def arc(i, a, b, way):
    return {'id': i, 'tail': a, 'head': b, 'way': way}


class Controls(unittest.TestCase):
    def test_narrow_static_car_scope(self):
        for kind in ('no_left_turn', 'no_right_turn', 'no_straight_on', 'no_u_turn'):
            self.assertEqual(entry_restriction(relation(kind)).via_way, 20)
        for kind in ('only_left_turn', 'only_straight_on', 'no_entry', 'no_exit', 'unknown'):
            self.assertIsNone(entry_restriction(relation(kind)))

    def test_calendar_modes_exemptions_and_other_shapes_keep_fallback(self):
        edits = [lambda e: e['tags'].update({'restriction:conditional': 'no_u_turn @ (Mo-Fr)'}),
                 lambda e: e['tags'].update({'except': 'bicycle;motorcar'}),
                 lambda e: e['tags'].update({'type': 'restriction:bicycle'}),
                 lambda e: e['members'].append({'type': 'way', 'role': 'via', 'ref': 40}),
                 lambda e: e['members'][1].update({'type': 'node'}),
                 lambda e: e['members'][1].update({'ref': 10})]
        for edit in edits:
            e = relation()
            edit(e)
            self.assertIsNone(entry_restriction(e))

    def test_car_mode_precedence_and_same_from_to(self):
        e = relation('only_straight_on')
        e['tags']['restriction:motorcar'] = 'no_u_turn'
        e['members'][2]['ref'] = 10
        self.assertEqual(entry_restriction(e).to_way, 10)

    def test_all_real_shared_junctions_and_parallel_arcs_are_forbidden(self):
        rule = entry_restriction(relation())
        incoming = [arc(0, 1, 2, 10), arc(1, 4, 3, 10), arc(2, 5, 2, 10)]
        outgoing = [arc(3, 2, 3, 20), arc(4, 3, 2, 20), arc(5, 2, 6, 20)]
        self.assertEqual(entry_pairs(rule, incoming, outgoing, {10, 20, 30}), [(0, 3), (0, 5), (1, 4), (2, 3), (2, 5)])

    def test_missing_groups_and_absent_junctions_keep_full_closure_fallback(self):
        rule = entry_restriction(relation())
        self.assertIsNone(entry_pairs(rule, [arc(0, 1, 2, 10)], [arc(1, 3, 4, 20)], {10, 20, 30}))
        self.assertIsNone(entry_pairs(rule, [arc(0, 1, 2, 10)], [arc(1, 2, 3, 20)], {10, 20}))
        with self.assertRaises(ValueError):
            entry_pairs(rule, [arc(0, 1, 2, 99)], [], {10, 20, 30})

    def test_generated_prohibited_paths_always_contain_an_entry_pair(self):
        # Multiple directions, intersections and via lengths require no history
        # state: every violating complete path necessarily uses this first pair.
        rule = entry_restriction(relation())
        checked = 0
        for length in range(1, 21):
            for junction in range(10):
                incoming = [arc(1, -1, junction, 10), arc(2, -2, junction, 10)]
                via = [arc(100+i, junction+i, junction+i+1, 20) for i in range(length)]
                pairs = set(entry_pairs(rule, incoming, via, {10, 20, 30}))
                for start in incoming:
                    path = [start, *via, arc(999, junction+length, 1000, 30)]
                    self.assertTrue(any((a['id'], b['id']) in pairs for a, b in zip(path, path[1:])))
                    checked += 1
                # Via/to remain usable for unrelated arrivals; this proposal
                # does not claim that every legal from->via exit is retained.
                self.assertNotIn((500, via[0]['id']), pairs)
        self.assertEqual(checked, 400)

    def test_large_arc_groups_fail_before_a_pair_expansion(self):
        rule = entry_restriction(relation())
        with self.assertRaisesRegex(ValueError, 'per-relation arc bound'):
            entry_pairs(rule, [arc(0, 1, 2, 10)]*200001, [], {10, 20, 30})


if __name__ == '__main__':
    unittest.main()
