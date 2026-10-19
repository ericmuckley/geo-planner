from array import array
from fractions import Fraction
import math
import unittest

from base_ids_test import compact, road
from compact_storage import build_graph, build_maneuver_graph
from experiment import intervals, reachable_geometry, road_prefixes, SnapIndex, validate_query
from maneuver_graph import destination_oracle, interior_destination, source_seeds
from native_support import UINT64_MAX
from regional_support import snap_attachments
from state_graph import dijkstra


class ExperimentTests(unittest.TestCase):
    def graph(self, rules=(), patterns=(), **kwargs):
        rows = [road("10:0:f", 1, 2, 1000), road("10:0:r", 2, 1, 1000), road("20:0:f", 2, 3, 2000), road("30:0:f", 3, 4, 1000)]
        points = {1: [0, 0], 2: [0.01, 0], 3: [0.02, 0], 4: [0.03, 0]}
        for row in rows:
            row["fromPoint"], row["toPoint"] = points[row["from"]], points[row["to"]]
        return build_maneuver_graph(build_graph(compact(rows), rules, **kwargs), patterns)

    def labels(self, graph, starts, budget):
        return array("Q", [UINT64_MAX if value == math.inf else value for value in dijkstra(graph.adjacency, source_seeds(graph, starts), budget).labels])

    def test_budget_partial_entry_before_head_and_direct_source_interval(self):
        graph = self.graph()
        starts = [(0, Fraction(1, 2))]
        labels = self.labels(graph, starts, 1000)
        self.assertEqual(labels[2], UINT64_MAX)
        entries = road_prefixes(graph, labels, 1000)
        self.assertEqual(entries[2], 500)
        self.assertEqual(intervals(2, 2000, entries[2], 1000, starts), [(0, 0.25)])
        self.assertEqual(intervals(0, 1000, UINT64_MAX, 100, starts), [(0.5, 0.6)])

    def test_legal_prefixes_match_independent_interior_checks_at_sample_fractions(self):
        for restrictions, patterns in (((), ()),
            ([{"id": 99, "kind": "no_right_turn", "fromWay": 10, "toWay": 20, "via": 2}], ()),
            ((), [{"id": 99, "roads": [0, 2, 3]}])):
            graph = self.graph(restrictions, patterns, node_delays={2: 250}, u_turn_ms=500)
            starts = [(0, Fraction(1, 2))]
            exact = dijkstra(graph.adjacency, source_seeds(graph, starts)).labels
            for budget in (100, 500, 1000, 2000, 5000):
                entries = road_prefixes(graph, self.labels(graph, starts, budget), budget)
                for index in range(len(graph.base.roads)):
                    spans = intervals(index, graph.base.roads.costs[index], entries[index], budget, starts)
                    for fraction in (Fraction(1, 10), Fraction(1, 2), Fraction(9, 10)):
                        expected = interior_destination(graph, exact, index, fraction, starts) <= budget
                        self.assertEqual(expected, destination_oracle(graph, source_seeds(graph, starts), index, fraction, starts) <= budget)
                        actual = any(start <= float(fraction) <= end for start, end in spans)
                        self.assertEqual(actual, expected, (budget, index, fraction))

    def test_blocked_node_prevents_outgoing_prefix(self):
        graph = self.graph(blocked_nodes={2})
        entries = road_prefixes(graph, self.labels(graph, [(0, 0)], 10000), 10000)
        self.assertEqual(entries[2], UINT64_MAX)

    def test_spatial_snap_matches_frozen_full_scan_and_both_directions(self):
        graph = self.graph()
        index = SnapIndex(graph.base.roads)
        for point in ([0.005, 0.0001], [0.01, 0], [0.015, 0.0002]):
            expected_starts, expected_seeds, expected = snap_attachments(graph, point, 100)
            starts, seeds, actual = index.snap(graph, point, 100)
            self.assertEqual(starts, expected_starts)
            self.assertEqual(seeds, expected_seeds)
            self.assertEqual(actual["snapped"], expected["snapped"])
        with self.assertRaises(ValueError): index.snap(graph, [1, 1], 100)

    def test_geometry_sampling_keeps_counts_and_limits_payload(self):
        graph = self.graph()
        starts = [(0, Fraction(1, 2))]
        labels = self.labels(graph, starts, 10000)
        full, counts = reachable_geometry(graph, labels, starts, 10000, 100)
        sample, smaller = reachable_geometry(graph, labels, starts, 10000, 3)
        self.assertLessEqual(len(sample), 3)
        self.assertEqual(counts["reachableDirectedRoads"], smaller["reachableDirectedRoads"])
        self.assertEqual(counts["reachableBounds"], smaller["reachableBounds"])
        self.assertGreaterEqual(len(full), len(sample))

    def test_query_boundary_rejects_extra_fields_bad_units_and_nonfinite_coordinates(self):
        for body in ({"origin": {"lat": 32, "lon": -117}, "budgetMinutes": 90, "provider": "hosted"},
                     {"origin": {"lat": True, "lon": -117}, "budgetMinutes": 90},
                     {"origin": {"lat": float("nan"), "lon": -117}, "budgetMinutes": 90},
                     {"origin": {"lat": 32, "lon": -117}, "budgetMinutes": True},
                     {"origin": {"lat": 32, "lon": -117}, "budgetMinutes": 721}):
            with self.assertRaises(ValueError): validate_query(body)
        self.assertEqual(validate_query({"origin": {"lat": 32, "lon": -117}, "budgetMinutes": 120}), ([-117, 32], 7200000))


if __name__ == "__main__": unittest.main()
