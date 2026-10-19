import random
import unittest

from queue_oracle import bellman_ford
from state_graph import bellman_ford as flat_bellman_ford, dijkstra


class QueueOracleTests(unittest.TestCase):
    def test_matches_independent_flat_relaxation_and_heap_on_directed_graphs(self):
        rng = random.Random(714)
        for size in range(1, 41):
            for _ in range(5):
                rows = [[(target, rng.randrange(30)) for target in range(size) if rng.random() < 0.12] for _ in range(size)]
                seeds = [(rng.randrange(size), rng.randrange(20)) for _ in range(3)]
                with self.subTest(size=size, seeds=seeds):
                    expected = flat_bellman_ford(rows, seeds)
                    self.assertEqual(bellman_ford(rows, seeds), expected)
                    self.assertEqual(dijkstra(rows, seeds).labels, expected)

    def test_rejects_reachable_negative_edges_and_invalid_seeds(self):
        with self.assertRaises(ValueError): bellman_ford([[(0, -1)]], [(0, 0)])
        with self.assertRaises(ValueError): bellman_ford([[]], [(1, 0)])
