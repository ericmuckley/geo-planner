import copy
import unittest

from coarse_osm_entry_graph_v1 import plan_entries, QueryGraph
from evaluate_osm_entry_capture_v1 import SourceReplay


def relation(identity=1, kind='no_u_turn', a=10, b=20, c=30):
    return {'id': identity, 'tags': {'type': 'restriction', 'restriction': kind},
            'members': [{'type': 'way', 'role': role, 'ref': value} for role, value in [('from', a), ('via', b), ('to', c)]]}


def arc(tail, head, way=10, ms=1250, first=0, last=1, direction=1):
    return {'tail': tail, 'head': head, 'way': way, 'ms': ms, 'first': first, 'last': last, 'direction': direction}


class Controls(unittest.TestCase):
    def test_actual_resolution_preserves_other_arrivals(self):
        arcs = [arc(0, 1), arc(1, 2, 20), arc(2, 3, 30), arc(4, 1, 40)]
        p = plan_entries([relation()], arcs)
        self.assertEqual(p['oldClosed'], {10, 20, 30})
        self.assertEqual(p['closed'], set())
        self.assertEqual(p['pairs'], {(0, 1)})
        g = QueryGraph(arcs, [4]*5, p['pairs'])
        self.assertIsNone(g.query({'vertex': 0}, {'vertex': 3})['ticks'])
        self.assertEqual(g.query({'vertex': 4}, {'vertex': 3})['ticks'], 30)

    def test_overlapping_fallback_is_never_reopened(self):
        p = plan_entries([relation(), relation(2, 'only_straight_on', 20, 30, 40)],
                         [arc(0, 1), arc(1, 2, 20), arc(2, 3, 30), arc(3, 4, 40)])
        self.assertEqual(p['closed'], {20, 30, 40})
        self.assertEqual(p['fallback'], [2])
        self.assertEqual(len(p['converted']), 1)

    def test_unresolved_members_and_no_shared_junction_keep_closures(self):
        for arcs in ([arc(0, 1), arc(1, 2, 20)], [arc(0, 1), arc(2, 3, 20), arc(3, 4, 30)]):
            p = plan_entries([relation()], arcs)
            self.assertEqual(p['closed'], p['oldClosed'])
            self.assertEqual(p['converted'], [])

    def test_priced_partials_direct_competition_and_terminal_prefix(self):
        g = QueryGraph([arc(0, 1), arc(1, 2, 20)], [4, 6, 4], [])
        result = g.query({'partials': [{'arc': 0, 'ticks': 4}]}, {'partials': [{'arc': 1, 'ticks': 3}]})
        self.assertEqual(result['ticks'], 47)
        self.assertEqual([s['kind'] for s in result['steps']], ['suffix', 'prefix'])
        result = g.query({'partials': [{'arc': 0, 'ticks': 4}]}, {'vertex': 1}, 2)
        self.assertEqual(result['ticks'], 2)
        self.assertTrue(result['direct'])
        g.replay({'vertex': 0}, {'vertex': 0}, None, g.query({'vertex': 0}, {'vertex': 0}))

    def test_node_arrival_departure_reversal_and_signal_rules(self):
        g = QueryGraph([arc(0, 1), arc(1, 0, direction=-1), arc(0, 2, 20)], [7, 0, 4], [])
        self.assertEqual(g.query({'vertex': 1}, {'vertex': 0})['ticks'], 10)
        self.assertIsNone(g.query({'vertex': 1}, {'vertex': 2})['ticks'])
        self.assertEqual(g.query({'vertex': 0}, {'vertex': 2})['ticks'], 10)
        g = QueryGraph([arc(0, 1), arc(1, 0, direction=-1)], [4, 6], [])
        self.assertEqual(g.delay(0, 1), 200)
        g.flags[1] = 2
        self.assertIsNone(g.delay(0, 1))

    def test_replay_rejects_forged_prices_and_forbidden_turns(self):
        g = QueryGraph([arc(0, 1), arc(1, 2, 20)], [4]*3, [])
        q = g.query({'vertex': 0}, {'vertex': 2})
        bad = copy.deepcopy(q)
        bad['steps'][0]['ticks'] += 1
        bad['ticks'] += 1
        with self.assertRaises(AssertionError):
            g.replay({'vertex': 0}, {'vertex': 2}, None, bad)
        g.forbidden.add((0, 1))
        with self.assertRaises(AssertionError):
            g.replay({'vertex': 0}, {'vertex': 2}, None, q)

    def test_source_native_geometry_replay_checks_price_and_actual_endpoints(self):
        from import_roads import distance_m
        import math
        ms = math.ceil(distance_m([0, 0], [.001, 0])*3600/40)
        ways = [(10, 40, 40, 0, 2)]
        arcs = [(0, 1, 0, 0, 1, 1, ms)]
        replay = SourceReplay([100, 200], [0, 0, 10000, 0], [0, 1], [0, 1], ways, arcs, [], set(), [])
        result = {'ticks': (ms+124)//125, 'steps': [{'arc': 0, 'kind': 'full', 'ticks': (ms+124)//125}]}
        witness = replay.audit({'sourceNodeIds': [100, 200]}, result, [4, 4])
        self.assertEqual(witness['nativeNodeIds'], [100, 200])
        with self.assertRaises(AssertionError):
            replay.audit({'sourceNodeIds': [100, 999]}, result, [4, 4])

    def test_independent_source_audit_rejects_prohibited_sequence_without_entry_table(self):
        from import_roads import distance_m
        import math
        ids, xy, refs, ways, arcs = [100, 200, 300, 400], [], [], [], []
        for i in range(4):
            xy.extend([i*10000, 0])
        total = 0
        steps = []
        for i, way in enumerate((10, 20, 30)):
            refs.extend([i, i+1])
            ways.append((way, 40, 40, 0, len(refs)))
            ms = math.ceil(distance_m([i*.001, 0], [(i+1)*.001, 0])*3600/40)
            arcs.append((i, i+1, i, 0, 1, 1, ms))
            steps.append({'arc': i, 'kind': 'full', 'ticks': (ms+124)//125})
            total += (ms+124)//125
        e = relation()
        replay = SourceReplay(ids, xy, list(range(4)), refs, ways, arcs, [e], set(), [{'id': 1}])
        with self.assertRaisesRegex(AssertionError, 'via-way prohibited sequence'):
            replay.audit({'sourceNodeIds': [100, 400]}, {'ticks': total, 'steps': steps}, [4]*4)


if __name__ == '__main__':
    unittest.main()
