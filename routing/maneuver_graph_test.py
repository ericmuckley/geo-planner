from fractions import Fraction
import math
from pathlib import Path
import tempfile
import unittest

from import_maneuvers import import_maneuvers
from maneuver_graph import build_maneuver_graph, destination_oracle, interior_destination, replay, source_seeds
from state_graph import bellman_ford, build_graph, dijkstra


MODEL = {"signalDelayMs": 5000, "uTurnDelayMs": 20000}


def road(name, tail, head, cost):
    return {"id": name, "way": name, "from": tail, "to": head, "costMs": cost}


def network(detour=True, delays=None):
    roads = [road("a", 0, 1, 10), road("b", 1, 2, 10), road("c", 2, 3, 10), road("other", 4, 1, 4)]
    if detour:
        roads += [road("exit", 2, 5, 7), road("return", 5, 1, 9)]
    return build_maneuver_graph(build_graph(roads, node_delays=delays), [{"id": 99, "roads": [0, 1, 2]}])


class ManeuverTests(unittest.TestCase):
    def test_forbidden_sequence_is_blocked_while_other_arrival_is_allowed(self):
        graph = network()
        blocked = replay(graph, [0, 1, 2], Fraction(1, 3))
        allowed = replay(graph, [3, 1, 2])
        self.assertFalse(blocked["allowed"])
        self.assertEqual(blocked["blockedStep"], 2)
        self.assertTrue(allowed["allowed"])
        self.assertNotEqual(blocked["states"][-1], allowed["states"][-2])
        self.assertEqual(graph.states[blocked["states"][-1]]["road"], graph.states[allowed["states"][-2]]["road"])

    def test_detour_can_clear_history_but_a_junction_does_not_reset_it(self):
        graph = network()
        self.assertFalse(replay(graph, [0, 1, 2])["allowed"])
        self.assertTrue(replay(graph, [0, 1, 4, 5, 1, 2])["allowed"])
        self.assertTrue(replay(graph, [1, 2], Fraction(1, 2))["allowed"])

    def test_overlapping_prefixes_and_multiple_segment_history(self):
        base = build_graph([road(str(i), i, i + 1, 2) for i in range(5)])
        graph = build_maneuver_graph(base, [{"id": 1, "roads": [0, 1, 2, 3, 4]}, {"id": 2, "roads": [1, 2, 3]}])
        result = replay(graph, [0, 1, 2, 3])
        self.assertFalse(result["allowed"])
        self.assertEqual(result["blockedStep"], 3)
        self.assertTrue(replay(graph, [2, 3, 4])["allowed"])

    def test_interior_destination_preserves_turn_history_and_allows_detour(self):
        graph = network()
        starts = [(0, Fraction(1, 2))]
        seeds = source_seeds(graph, starts)
        labels = dijkstra(graph.adjacency, seeds).labels
        self.assertEqual(labels, bellman_ford(graph.adjacency, seeds))
        self.assertEqual(interior_destination(graph, labels, 2, Fraction(1, 2), starts), 46)
        self.assertEqual(destination_oracle(graph, seeds, 2, Fraction(1, 2), starts), 46)

    def test_forbidden_entry_cannot_reach_an_interior_destination(self):
        graph = network(detour=False)
        starts = [(0, Fraction(0))]
        labels = dijkstra(graph.adjacency, source_seeds(graph, starts)).labels
        self.assertEqual(interior_destination(graph, labels, 2, Fraction(1, 2), starts), math.inf)

    def test_partial_destination_charges_entry_delay_not_full_road(self):
        graph = network(delays={2: 6})
        starts = [(3, Fraction(0))]
        labels = dijkstra(graph.adjacency, source_seeds(graph, starts)).labels
        self.assertEqual(interior_destination(graph, labels, 2, Fraction(1, 2), starts), 25)
        self.assertEqual(destination_oracle(graph, source_seeds(graph, starts), 2, Fraction(1, 2), starts), 25)

    def test_direct_same_road_source_and_multi_start_union(self):
        graph = network(detour=False)
        starts = [(0, Fraction(1, 3))]
        labels = dijkstra(graph.adjacency, source_seeds(graph, starts), 5).labels
        self.assertTrue(all(value == math.inf for value in labels))
        self.assertEqual(interior_destination(graph, labels, 0, Fraction(2, 3), starts), 4)
        self.assertEqual(interior_destination(graph, labels, 0, Fraction(1, 4), starts), math.inf)
        starts += [(3, Fraction(0))]
        labels = dijkstra(graph.adjacency, source_seeds(graph, starts)).labels
        self.assertEqual(interior_destination(graph, labels, 2, Fraction(1, 2), starts), 19)

    def test_full_history_walk_enumeration_agrees_with_product_search(self):
        graph = network()
        budget = 60
        expected = [math.inf] * len(graph.base.roads)

        def visit(path, cost):
            expected[path[-1]] = min(expected[path[-1]], cost)
            for following, weight in graph.base.adjacency[path[-1]]:
                extended = path + [following]
                if any(extended[-len(rule["roads"]):] == rule["roads"] for rule in graph.patterns):
                    continue
                if cost + weight <= budget:
                    visit(extended, cost + weight)

        visit([0], 0)
        labels = dijkstra(graph.adjacency, [(graph.initial_states[0], 0)], budget).labels
        actual = [min((labels[i] for i, state in enumerate(graph.states) if state["road"] == road), default=math.inf)
                  for road in range(len(graph.base.roads))]
        self.assertEqual(actual, expected)

    def test_invalid_attachments_destinations_and_patterns_are_rejected(self):
        graph = network()
        for starts in ([], [(99, 0)], [(True, 0)], [(0, -1)], [(0, 2)]):
            with self.assertRaises(ValueError): source_seeds(graph, starts)
        for fraction in (-1, 0, 1, 2):
            with self.assertRaises(ValueError): interior_destination(graph, [0] * len(graph.states), 0, fraction)
        for sequence in ([0, 1], [0, 1, 99], [0, 1, True]):
            with self.assertRaises(ValueError): build_maneuver_graph(graph.base, [{"id": 1, "roads": sequence}])


def osm(restriction="no_left_turn", extra="", from_nodes=(1, 2)):
    nodes = ''.join(f'<node id="{node}" lon="{node / 1000}" lat="0"/>' for node in range(1, 7))
    ways = ''.join(f'<way id="{way}">'+''.join(f'<nd ref="{node}"/>' for node in points)+
                   '<tag k="highway" v="residential"/><tag k="oneway" v="yes"/></way>'
                   for way, points in ((10, from_nodes), (20, (2, 3, 4)), (30, (4, 5)), (40, (6, 2))))
    relation = f'''<relation id="99"><member type="way" role="from" ref="10"/>
      <member type="way" role="via" ref="20"/><member type="way" role="to" ref="30"/>
      <tag k="type" v="restriction"/><tag k="restriction" v="{restriction}"/>{extra}</relation>'''
    return f'<osm>{nodes}{ways}{relation}</osm>'


class ManeuverImportTests(unittest.TestCase):
    def import_xml(self, xml):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roads.osm"
            path.write_text(xml)
            return import_maneuvers(path, [-1, -1, 1, 1], MODEL)

    def test_multi_segment_via_way_restores_roads_and_retains_source_ids(self):
        graph, audit = self.import_xml(osm())
        self.assertEqual(audit["restoredWayIds"], [10, 20, 30])
        self.assertEqual(audit["viaWayRestrictions"][0]["roadIds"], ["10:0:f", "20:0:f", "20:1:f", "30:0:f"])
        pattern = graph.patterns[0]["roads"]
        self.assertFalse(replay(graph, pattern)["allowed"])
        other = next(i for i, road in enumerate(graph.base.roads) if road["way"] == 40)
        self.assertTrue(replay(graph, [other] + pattern[1:])["allowed"])

    def test_conditional_and_only_way_restrictions_keep_conservative_closures(self):
        for xml in (osm(extra='<tag k="restriction:conditional" v="no_left_turn @ (Mo-Fr)"/>'), osm("only_straight_on")):
            graph, audit = self.import_xml(xml)
            self.assertEqual([road["way"] for road in graph.base.roads], [40])
            self.assertFalse(audit["viaWayRestrictions"])
            self.assertFalse(audit["restoredWayIds"])
            self.assertEqual(audit["unsupportedRestrictions"][0]["id"], 99)
            self.assertTrue(audit["viaWayFallbackReasons"])

    def test_ambiguous_topology_restores_the_original_closure(self):
        graph, audit = self.import_xml(osm(from_nodes=(1, 2, 3)))
        self.assertEqual([road["way"] for road in graph.base.roads], [40])
        self.assertIn("ambiguous", audit["viaWayFallbackReasons"][0]["reason"])
        self.assertEqual(audit["fallbackIterations"], 2)

    def test_another_unsupported_relation_prevents_partial_restoration(self):
        xml = osm().replace('</osm>', '''<relation id="100"><member type="way" role="from" ref="20"/>
          <member type="node" role="via" ref="4"/><member type="way" role="to" ref="30"/>
          <tag k="type" v="restriction"/><tag k="restriction:conditional" v="no_left_turn @ (Mo-Fr)"/></relation></osm>''')
        graph, audit = self.import_xml(xml)
        self.assertEqual([road["way"] for road in graph.base.roads], [40])
        self.assertEqual({rule["id"] for rule in audit["unsupportedRestrictions"]}, {99, 100})


if __name__ == "__main__":
    unittest.main()
