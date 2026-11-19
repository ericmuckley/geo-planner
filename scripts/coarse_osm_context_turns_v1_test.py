import copy
import random
from types import SimpleNamespace
import unittest

from coarse_osm_context_turns_v1 import ContextQueryGraph, plan_contexts
from coarse_osm_entry_graph_v1 import QueryGraph
from coarse_osm_entry_graph_v1_test import arc, relation
from coarse_osm_restriction_entry_v1 import EntryRestriction


def rule(a=10, b=20, c=30, identity=1):
    return EntryRestriction(identity, a, b, c)


class Controls(unittest.TestCase):
    def test_prohibited_completion_other_exit_and_unrelated_arrival(self):
        arcs = [arc(0, 1), arc(1, 2, 20), arc(2, 3, 20, first=1, last=2),
                arc(3, 4, 30), arc(2, 5, 40), arc(6, 1, 50)]
        base = QueryGraph(arcs, [4]*7, [])
        graph = ContextQueryGraph(base, [rule()])
        self.assertIsNone(graph.query({'vertex': 0}, {'vertex': 4})['ticks'])
        self.assertEqual(graph.query({'vertex': 0}, {'vertex': 5})['ticks'], 30)
        self.assertEqual(graph.query({'vertex': 0}, {'vertex': 3})['ticks'], 30)
        self.assertEqual(graph.query({'vertex': 6}, {'vertex': 4})['ticks'], 40)
        old = QueryGraph(arcs, [4]*7, [(0, 1)])
        self.assertIsNone(old.query({'vertex': 0}, {'vertex': 5})['ticks'])

    def test_distinct_contexts_cannot_merge_at_the_cheapest_physical_arc(self):
        arcs = [arc(0, 1, 10, ms=125), arc(0, 1, 40, ms=1250),
                arc(1, 2, 20, ms=125), arc(2, 3, 30, ms=125)]
        graph = ContextQueryGraph(QueryGraph(arcs, [4]*4, []), [rule()])
        result = graph.query({'vertex': 0}, {'vertex': 3})
        self.assertEqual(result['ticks'], 12)
        self.assertEqual([s['arc'] for s in result['steps']], [1, 2, 3])
        self.assertEqual(graph.source.query({'vertex': 0}, {'vertex': 3})['ticks'], 3)

    def test_start_inside_via_has_no_invented_prior_from_way(self):
        base = QueryGraph([arc(0, 1), arc(1, 2, 20), arc(2, 3, 30)], [4]*4, [])
        graph = ContextQueryGraph(base, [rule()])
        self.assertEqual(graph.query({'vertex': 1}, {'vertex': 3})['ticks'], 20)
        self.assertEqual(graph.query({'partials': [{'arc': 1, 'ticks': 4}]}, {'vertex': 3})['ticks'], 14)
        self.assertIsNone(graph.query({'partials': [{'arc': 0, 'ticks': 4}]}, {'vertex': 3})['ticks'])
        self.assertEqual(graph.query({'vertex': 0}, {'partials': [{'arc': 1, 'ticks': 3}]})['ticks'], 13)
        self.assertIsNone(graph.query({'vertex': 0}, {'partials': [{'arc': 2, 'ticks': 3}]})['ticks'])

    def test_context_switches_on_way_exit_and_shared_prefixes_union(self):
        base = QueryGraph([arc(0, 1), arc(1, 2, 20), arc(2, 3, 30), arc(3, 4, 40), arc(3, 5, 50)], [4]*6, [])
        graph = ContextQueryGraph(base, [rule(c=90), rule(20, 30, 40, 2)])
        self.assertIsNone(graph.query({'vertex': 0}, {'vertex': 4})['ticks'])
        self.assertEqual(graph.query({'vertex': 0}, {'vertex': 5})['ticks'], 40)
        base = QueryGraph([arc(0, 1), arc(1, 2, 20), arc(2, 3, 30), arc(2, 4, 40)], [4]*5, [])
        graph = ContextQueryGraph(base, [rule(), rule(c=40, identity=2)])
        for target in (3, 4):
            self.assertIsNone(graph.query({'vertex': 0}, {'vertex': target})['ticks'])
            self.assertEqual(graph.query({'vertex': 1}, {'vertex': target})['ticks'], 20)

    def test_unchanged_supported_turn_barrier_signal_reversal_and_partials(self):
        arcs = [arc(0, 1), arc(1, 2, 20), arc(2, 3, 40)]
        graph = ContextQueryGraph(QueryGraph(arcs, [4, 6, 4, 4], []), [rule()])
        result = graph.query({'partials': [{'arc': 0, 'ticks': 4}]}, {'partials': [{'arc': 1, 'ticks': 3}]})
        self.assertEqual(result['ticks'], 47)
        self.assertEqual([s['kind'] for s in result['steps']], ['suffix', 'prefix'])
        graph.source.forbidden.add((1, 2))
        self.assertIsNone(graph.query({'vertex': 0}, {'vertex': 3})['ticks'])
        graph.source.flags[1] = 1
        self.assertIsNone(graph.query({'vertex': 0}, {'vertex': 2})['ticks'])
        reverse = QueryGraph([arc(0, 1), arc(1, 0, direction=-1)], [4, 6], [])
        graph = ContextQueryGraph(reverse, [rule()])
        self.assertEqual(graph.source.delay(0, 1), 200)
        result = graph.query({'partials': [{'arc': 0, 'ticks': 4}]}, {'vertex': 0})
        self.assertEqual(result['ticks'], 214)

    def test_direct_competition_and_identical_endpoints_retain_sealed_semantics(self):
        graph = ContextQueryGraph(QueryGraph([arc(0, 1)], [4, 4], []), [])
        result = graph.query({'partials': [{'arc': 0, 'ticks': 4}]}, {'vertex': 1}, 2)
        self.assertEqual(result['ticks'], 2)
        self.assertTrue(result['direct'])
        self.assertEqual(graph.query({'vertex': 0}, {'vertex': 0})['ticks'], 0)

    def test_same_way_cycle_does_not_erase_from_context(self):
        arcs = [arc(0, 1), arc(1, 2, 20), arc(2, 3, 20, first=1, last=2),
                arc(3, 1, 20, first=2, last=3), arc(3, 4, 10, first=1, last=2)]
        graph = ContextQueryGraph(QueryGraph(arcs, [4]*5, []), [rule(c=10)])
        self.assertIsNone(graph.query({'vertex': 0}, {'vertex': 4})['ticks'])
        self.assertEqual(graph.query({'vertex': 1}, {'vertex': 4})['ticks'], 30)

    def test_replay_rejects_illegal_sequence_and_forged_prices(self):
        graph = ContextQueryGraph(QueryGraph([arc(0, 1), arc(1, 2, 20), arc(2, 3, 30)], [4]*4, []), [rule()])
        illegal = graph.source.query({'vertex': 0}, {'vertex': 3})
        with self.assertRaisesRegex(AssertionError, 'Prohibited via-way completion'):
            graph.replay({'vertex': 0}, {'vertex': 3}, None, illegal)
        legal = graph.query({'vertex': 0}, {'vertex': 2})
        bad = copy.deepcopy(legal)
        bad['ticks'] += 1
        with self.assertRaises(AssertionError):
            graph.replay({'vertex': 0}, {'vertex': 2}, None, bad)

    def test_fallback_contributors_and_inactive_relations_do_not_change(self):
        elements = [relation(), relation(2, 'only_straight_on', 20, 40, 60), relation(3, a=70, b=80, c=90)]
        arcs = [arc(0, 1), arc(1, 2, 20), arc(2, 3, 30), arc(2, 4, 40), arc(4, 5, 60), arc(6, 7, 70), arc(7, 8, 80)]
        proposal = plan_contexts(elements, arcs, len(arcs))
        self.assertEqual(proposal['closed'], {20, 40, 60})
        self.assertEqual(proposal['contextRules'], [rule()])
        self.assertEqual(proposal['fallback'], [2])
        self.assertEqual(proposal['inactive'], [{'id': 3, 'absentEssentialWays': [90]}])
        conditional = relation()
        conditional['tags']['restriction:conditional'] = 'no_left_turn @ (Mo-Fr)'
        self.assertEqual(plan_contexts([conditional], arcs, len(arcs))['contextRules'], [])
        with self.assertRaises(ValueError):
            plan_contexts(elements, arcs, len(arcs)-1)

    def test_explicit_capture_relation_and_context_state_caps(self):
        with self.assertRaises(ValueError):
            ContextQueryGraph(SimpleNamespace(arcs=[], flags=range(200001)), [])
        base = QueryGraph([arc(0, 1)], [4, 4], [])
        with self.assertRaises(ValueError):
            ContextQueryGraph(base, [rule()]*10001)
        with self.assertRaises(ValueError):
            ContextQueryGraph(base, [rule(a=True)])
        base = QueryGraph([arc(i, i+1, 20, first=i, last=i+1) for i in range(400)], [4]*401, [])
        with self.assertRaisesRegex(ValueError, 'state bound'):
            ContextQueryGraph(base, [rule(a=1000+i, c=99999, identity=i) for i in range(1001)])

    def test_deadline_callback_and_twelve_hour_limit(self):
        base = QueryGraph([arc(i, i+1, 20, ms=125, first=i, last=i+1) for i in range(1100)], [4]*1101, [])
        graph = ContextQueryGraph(base, [])
        def cancel():
            raise ValueError('cancelled')
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            graph.query({'vertex': 0}, {'vertex': 1100}, check=cancel)
        base = QueryGraph([arc(0, 1, ms=345599*125), arc(1, 2, 20, ms=125), arc(2, 3, 30, ms=125)], [4]*4, [])
        graph = ContextQueryGraph(base, [])
        self.assertEqual(graph.query({'vertex': 0}, {'vertex': 2})['ticks'], 345600)
        self.assertIsNone(graph.query({'vertex': 0}, {'vertex': 3})['ticks'])

    def test_5000_queries_match_independent_complete_dag_walk_enumeration(self):
        rng = random.Random(20261105)
        compared = 0
        for _ in range(200):
            arcs = []
            for tail in range(5):
                for head in range(tail+1, 5):
                    if rng.random() < .65:
                        index = len(arcs)
                        arcs.append(arc(tail, head, rng.randrange(1, 4), ms=125*rng.randrange(1, 10), first=2*index, last=2*index+1))
            forbidden = {(i, j) for i, a in enumerate(arcs) for j, b in enumerate(arcs) if a['head'] == b['tail'] and rng.random() < .15}
            rules = []
            for i in range(rng.randrange(5)):
                a, b, c = (rng.randrange(1, 4) for _ in range(3))
                if b not in (a, c):
                    rules.append(rule(a, b, c, i))
            triples = {(r.from_way, r.via_way, r.to_way) for r in rules}
            graph = ContextQueryGraph(QueryGraph(arcs, [0]*5, forbidden), rules)
            for source in range(5):
                for target in range(5):
                    costs = []
                    def walk(vertex, steps, ways, cost):
                        if vertex == target:
                            costs.append(cost)
                            return
                        for index, a in enumerate(arcs):
                            if a['tail'] != vertex or steps and (steps[-1], index) in forbidden:
                                continue
                            sequence = ways if ways and ways[-1] == a['way'] else [*ways, a['way']]
                            if len(sequence) >= 3 and tuple(sequence[-3:]) in triples:
                                continue
                            walk(a['head'], [*steps, index], sequence, cost+a['ms']//125)
                    walk(source, [], [], 0)
                    expected = min(costs) if costs else None
                    self.assertEqual(graph.query({'vertex': source}, {'vertex': target})['ticks'], expected)
                    compared += 1
        self.assertEqual(compared, 5000)


if __name__ == '__main__':
    unittest.main()
