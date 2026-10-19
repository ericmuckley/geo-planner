from fractions import Fraction
import math
import unittest

from maneuver_graph import destination_oracle as flat_oracle, interior_destination, source_seeds
from maneuver_graph_test import network
from state_graph import dijkstra
from virtual_sink import destination_oracle


class VirtualSinkTests(unittest.TestCase):
    def test_exact_partial_costs_for_history_detours_delays_and_multiple_starts(self):
        for detour in (False, True):
            for delays in (None, {2: 6}):
                graph = network(detour=detour, delays=delays)
                for starts in ([(0, Fraction(1, 3))], [(3, Fraction(0))], [(0, Fraction(1, 2)), (3, Fraction(1, 4))]):
                    seeds = source_seeds(graph, starts)
                    labels = dijkstra(graph.adjacency, seeds).labels
                    for road in range(len(graph.base.roads)):
                        for fraction in (Fraction(1, 4), Fraction(1, 2), Fraction(2, 3)):
                            with self.subTest(detour=detour, delays=delays, starts=starts, road=road, fraction=fraction):
                                expected = flat_oracle(graph, seeds, road, fraction, starts)
                                self.assertEqual(destination_oracle(graph, seeds, road, fraction, starts), expected)
                                self.assertEqual(interior_destination(graph, labels, road, fraction, starts), expected)

    def test_unreachable_history_and_direct_source_before_and_after_destination(self):
        graph = network(detour=False)
        starts = [(0, Fraction(1, 3))]
        seeds = source_seeds(graph, starts)
        self.assertEqual(destination_oracle(graph, seeds, 2, Fraction(1, 2), starts), math.inf)
        self.assertEqual(destination_oracle(graph, seeds, 0, Fraction(2, 3), starts), 4)
        self.assertEqual(destination_oracle(graph, seeds, 0, Fraction(1, 4), starts), math.inf)
        self.assertEqual(destination_oracle(graph, seeds, 0, Fraction(1, 3), starts), 0)

    def test_invalid_attachments_and_destinations_are_rejected(self):
        graph = network()
        for road, fraction, seeds, starts in ((True, Fraction(1, 2), [(0, 0)], []),
                (99, Fraction(1, 2), [(0, 0)], []), (0, 0, [(0, 0)], []), (0, 1, [(0, 0)], []),
                (0, Fraction(1, 2), [(len(graph.states), 0)], []), (0, Fraction(1, 2), [(0, 0)], [(0, 2)])):
            with self.subTest(road=road, fraction=fraction, seeds=seeds, starts=starts), self.assertRaises(ValueError):
                destination_oracle(graph, seeds, road, fraction, starts)
