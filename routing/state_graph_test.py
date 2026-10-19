from fractions import Fraction
import math
from pathlib import Path
import random
import tempfile
import unittest

from import_roads import access_allowed, import_roads, speed_kph
from state_graph import (bellman_ford, build_graph, classify, dijkstra, landmark_index,
                         pack_index, partial_source, state_bounds, unpack_index, validate_index)


def road(name, tail, head, cost, way=None):
    return {"id": name, "from": tail, "to": head, "costMs": cost, "way": way or name}


def network():
    return build_graph([
        road("ab", "a", "b", 10), road("bc", "b", "c", 10),
        road("bd", "b", "d", 7), road("dc", "d", "c", 9),
        road("ca", "c", "a", 20), road("xy", "x", "y", 1),
    ], [{"id": "turn", "fromWay": "ab", "via": "b", "toWay": "bc", "kind": "no_left_turn"}])


class StateGraphTests(unittest.TestCase):
    def test_prohibited_turn_requires_detour_and_preserves_arrival_direction(self):
        graph = network()
        self.assertNotIn(1, [state for state, _ in graph.adjacency[0]])
        labels = dijkstra(graph.adjacency, [(0, 0)]).labels
        self.assertEqual(labels[3], 16)
        self.assertEqual(labels[1], math.inf)  # Re-entering the same incoming road cannot reset the restriction.
        self.assertEqual(labels, bellman_ford(graph.adjacency, [(0, 0)]))
        self.assertEqual(labels[5], math.inf)

    def test_only_turn_excludes_other_departures(self):
        graph = build_graph(network().roads, [{"id": "only", "fromWay": "ab", "via": "b", "toWay": "bd", "kind": "only_right_turn"}])
        self.assertEqual(graph.adjacency[0], [(2, 7)])

    def test_several_only_turn_alternatives_are_a_union(self):
        graph = build_graph(network().roads, [
            {"id": 1, "fromWay": "ab", "via": "b", "toWay": "bd", "kind": "only_right_turn"},
            {"id": 2, "fromWay": "ab", "via": "b", "toWay": "bc", "kind": "only_straight_on"},
        ])
        self.assertEqual(graph.adjacency[0], [(1, 10), (2, 7)])

    def test_same_way_no_u_turn_keeps_continuation(self):
        graph = build_graph([road("ab", "a", "b", 10, "w"), road("ba", "b", "a", 10, "w"), road("bc", "b", "c", 11, "w")],
                            [{"id": 1, "fromWay": "w", "via": "b", "toWay": "w", "kind": "no_u_turn"}])
        self.assertEqual(graph.adjacency[0], [(2, 11)])

    def test_transition_delays_are_in_the_optimized_time_metric(self):
        graph = build_graph([road("ab", "a", "b", 10), road("ba", "b", "a", 10)], node_delays={"b": 5}, u_turn_ms=20)
        self.assertEqual(dijkstra(graph.adjacency, [(0, 0)]).labels[1], 35)

    def test_partial_source_keeps_restriction_history_and_rounds_up(self):
        graph = network()
        seeds = partial_source(graph, 0, Fraction(1, 3))
        self.assertEqual(seeds, [(0, 7)])
        self.assertEqual(dijkstra(graph.adjacency, seeds).labels[3], 23)
        with self.assertRaises(ValueError):
            partial_source(graph, 0, Fraction(4, 3))

    def test_bounded_search_distinguishes_horizon_from_complete_field(self):
        graph = network()
        short = dijkstra(graph.adjacency, [(0, 0)], 15)
        self.assertEqual(short.labels[2], 7)
        self.assertEqual(short.labels[3], math.inf)
        self.assertFalse(short.complete)
        self.assertEqual(short.horizon_ms, 15)
        self.assertEqual(dijkstra(graph.adjacency, [(0, 0)]).labels[3], 16)

    def test_landmark_fields_cannot_be_mixed_or_truncated(self):
        graph = network()
        index = landmark_index(graph, [0, 3])
        index.forward[0] = dijkstra(graph.adjacency, [(0, 0)], 30)
        with self.assertRaisesRegex(ValueError, "untruncated"):
            validate_index(graph, index)
        index = landmark_index(graph, [0])
        changed = build_graph([road("different", "z", "y", 1)])
        with self.assertRaisesRegex(ValueError, "different graph"):
            validate_index(changed, index)

    def test_nonnegative_costs_and_known_seeds_are_required(self):
        for value in (-1, True, 1.5, math.inf):
            with self.assertRaises(ValueError):
                build_graph([road("bad", "a", "b", value)])
        graph = network()
        for seeds in ([], [(100, 0)], [(0, -1)]):
            with self.assertRaises(ValueError):
                dijkstra(graph.adjacency, seeds)

    def test_packed_fields_preserve_direction_infinity_and_graph_identity(self):
        graph = network()
        index = landmark_index(graph, [0, 3, 5])
        packed = pack_index(graph, index)
        loaded = unpack_index(graph, index.states, packed, graph.identity, True)
        self.assertEqual([f.labels for f in index.forward + index.backward],
                         [f.labels for f in loaded.forward + loaded.backward])
        for data, identity, complete in ((packed[:-4], graph.identity, True),
                                         (packed, "different", True), (packed, graph.identity, False)):
            with self.assertRaises(ValueError):
                unpack_index(graph, index.states, data, identity, complete)

    def test_directed_bounds_and_multi_start_union_match_independent_oracle(self):
        graph = network()
        index = landmark_index(graph, [0, 3, 5])
        for seeds in ([(0, 0)], [(2, 3)], [(0, 7), (5, 0)]):
            exact = bellman_ford(graph.adjacency, seeds)
            for budget in (0, 7, 16, 20, 50):
                for target, (decision, low, high) in enumerate(classify(graph, index, seeds, budget)):
                    self.assertLessEqual(low, exact[target])
                    self.assertLessEqual(exact[target], high)
                    if decision == "reachable": self.assertLessEqual(exact[target], budget)
                    if decision == "unreachable": self.assertGreater(exact[target], budget)

    def test_random_directed_zero_cost_and_disconnected_graphs(self):
        rng = random.Random(20261016)
        for _ in range(12):
            roads = [road(f"r{i}", rng.randrange(5), rng.randrange(5), rng.randrange(8)) for i in range(18)]
            roads = [r for r in roads if r["from"] != r["to"]]
            graph = build_graph(roads)
            index = landmark_index(graph, list(range(min(3, len(roads)))))
            for source in range(len(roads)):
                exact = bellman_ford(graph.adjacency, [(source, 0)])
                self.assertEqual(dijkstra(graph.adjacency, [(source, 0)]).labels, exact)
                for target in range(len(roads)):
                    low, high = state_bounds(source, target, index)
                    self.assertLessEqual(low, exact[target])
                    self.assertLessEqual(exact[target], high)


class ImportModelTests(unittest.TestCase):
    def test_malformed_node_only_restriction_closes_node_and_is_audited(self):
        xml = '''<osm><node id="1" lon="0" lat="0"/><node id="2" lon="0.001" lat="0"/>
        <way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="residential"/></way>
        <relation id="99"><member type="node" role="via" ref="2"/><tag k="type" v="restriction"/><tag k="restriction" v="no_u_turn"/></relation></osm>'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roads.osm"
            path.write_text(xml)
            graph, audit = import_roads(path, [-1, -1, 1, 1], {"signalDelayMs": 0, "uTurnDelayMs": 0})
        self.assertEqual(graph.adjacency[0], [])
        self.assertEqual(audit["unsupportedRestrictions"][0]["blockedMemberNodes"], [2])

    def test_speeds_and_access_precedence(self):
        self.assertAlmostEqual(speed_kph("25 mph", 30), 40.2336)
        self.assertEqual(speed_kph(None, 30), 30)
        for value in ("signals", "30;50", "0", "200"):
            with self.assertRaises(ValueError): speed_kph(value, 30)
        self.assertTrue(access_allowed({"access": "private", "motorcar": "yes"}))
        self.assertFalse(access_allowed({"motor_vehicle": "yes", "motorcar": "no"}))
        self.assertFalse(access_allowed({"motorcar:backward": "no"}, "backward"))

    def test_osm_import_enforces_oneway_and_excludes_unsupported_restriction_members(self):
        xml = '''<osm>
        <node id="1" lon="0" lat="0"/><node id="2" lon="0.001" lat="0"/>
        <node id="3" lon="0.002" lat="0"/><node id="4" lon="0.001" lat="0.001"/>
        <way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="residential"/><tag k="oneway" v="yes"/></way>
        <way id="20"><nd ref="2"/><nd ref="3"/><tag k="highway" v="residential"/></way>
        <way id="30"><nd ref="2"/><nd ref="4"/><tag k="highway" v="residential"/></way>
        <relation id="99"><member type="way" role="from" ref="20"/><member type="way" role="via" ref="30"/><member type="way" role="to" ref="30"/><tag k="type" v="restriction"/><tag k="restriction" v="no_left_turn"/></relation>
        </osm>'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roads.osm"
            path.write_text(xml)
            graph, audit = import_roads(path, [-1, -1, 1, 1], {"signalDelayMs": 0, "uTurnDelayMs": 0})
        self.assertEqual([r["id"] for r in graph.roads], ["10:0:f"])
        self.assertEqual(audit["unsupportedRestrictions"][0]["id"], 99)
        self.assertEqual(audit["excludedWayCounts"]["unsupported-restriction-member"], 2)


if __name__ == "__main__":
    unittest.main()
