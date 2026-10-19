from fractions import Fraction
import math
from pathlib import Path
import struct
import tempfile
import unittest

from anchors import save_json
from cell_index import CellReader, build_cells, classify_cells, materialize, refine_targets, summary_bounds, verify_cells
from state_graph import bellman_ford, build_graph, landmark_index, partial_source, state_bounds


def example():
    edges = [("a", "b", 10), ("b", "c", 10), ("b", "d", 7), ("d", "c", 9),
             ("c", "a", 20), ("x", "y", 0), ("y", "x", 0)]
    points = {"a": [0, 0], "b": [1, 0], "c": [2, 0], "d": [1, 1], "x": [10, 0], "y": [11, 0]}
    roads = [{"id": str(i), "way": str(i), "from": a, "to": b, "costMs": cost, "toPoint": points[b]}
             for i, (a, b, cost) in enumerate(edges)]
    return build_graph(roads, [{"id": "turn", "fromWay": "0", "via": "b", "toWay": "1", "kind": "no_left_turn"}])


class CellIndexTests(unittest.TestCase):
    def test_grouped_and_refined_membership_matches_independent_oracle(self):
        graph = example()
        index = landmark_index(graph, [0, 3, 5])
        with tempfile.TemporaryDirectory() as temporary:
            for leaf in (1, 2, 8):
                directory = Path(temporary) / str(leaf)
                metadata, order = build_cells(graph, index, leaf, directory)
                verify_cells(directory, graph.identity)
                seeds_cases = [[(s, 0)] for s in range(len(graph.roads))]
                seeds_cases.append(partial_source(graph, 0, Fraction(1, 3)) + [(5, 2)])
                for seeds in seeds_cases:
                    exact = bellman_ford(graph.adjacency, seeds)
                    for budget in (0, 7, 16, 30, 100):
                        reader = CellReader(directory, metadata)
                        try:
                            result = classify_cells(reader, seeds, budget)
                        finally:
                            reader.close()
                        reached, _ = refine_targets(graph.adjacency, seeds, budget, result["unresolved"])
                        self.assertEqual(materialize(result, order, reached), [v <= budget for v in exact])
                        for start, end, _, low, high in result["groups"]:
                            for position in range(start, end):
                                self.assertLessEqual(low, exact[order[position]])
                                self.assertLessEqual(exact[order[position]], high)

    def test_singleton_summary_equals_directed_landmark_bounds(self):
        graph = example()
        index = landmark_index(graph, [0, 3, 5])
        for source in range(len(graph.roads)):
            values = tuple(f.labels[source] for f in index.forward + index.backward)
            for target in range(len(graph.roads)):
                summary = tuple(value for forward, reverse in zip(index.forward, index.backward)
                                for value in (forward.labels[target], forward.labels[target], reverse.labels[target], reverse.labels[target]))
                self.assertEqual(summary_bounds([(0, values)], summary), state_bounds(source, target, index))

    def test_mixed_infinity_cells_remain_conservative(self):
        lower, upper = summary_bounds([(0, (0, 0))], (0, math.inf, 0, math.inf))
        self.assertEqual((lower, upper), (0, math.inf))
        self.assertEqual(summary_bounds([(0, (0, math.inf))], (math.inf, math.inf, 0, 10)), (math.inf, math.inf))

    def test_root_certificate_skips_all_detail_ranges(self):
        graph = example()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            metadata, order = build_cells(graph, landmark_index(graph, [0, 3, 5]), 1, directory)
            reader = CellReader(directory, metadata)
            try:
                result = classify_cells(reader, [(0, 1)], 0)
                self.assertEqual(reader.nodes_read, 1)
                self.assertEqual(reader.detail_states, 0)
                self.assertLess(reader.bytes, sum(a["bytes"] for a in metadata["artifacts"].values()))
            finally:
                reader.close()
            self.assertEqual(materialize(result, order, set()), [False] * len(order))

    def test_refinement_preserves_transit_paths_and_can_stop_after_targets_settle(self):
        adjacency = [[(1, 2)], [(2, 3)], []]
        reached, metrics = refine_targets(adjacency, [(0, 0)], 5, {2})
        self.assertEqual(reached, {2})
        self.assertEqual(metrics["settledStates"], 3)
        reached, metrics = refine_targets(adjacency, [(0, 0)], 5, {0})
        self.assertEqual(reached, {0})
        self.assertEqual(metrics["settledStates"], 1)
        self.assertEqual(metrics["scannedArcs"], 0)
        self.assertEqual(refine_targets(adjacency, [(0, 0)], 1, {2})[0], set())

    def test_wrong_graph_truncated_metadata_and_corrupt_bytes_fail_preflight(self):
        graph = example()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            metadata, _ = build_cells(graph, landmark_index(graph, [0]), 2, directory)
            with self.assertRaisesRegex(ValueError, "matching graph"):
                verify_cells(directory, "different")
            changed = {**metadata, "completeFields": False}
            save_json(directory / "manifest.json", changed)
            with self.assertRaisesRegex(ValueError, "complete fields"):
                verify_cells(directory, graph.identity)
            save_json(directory / "manifest.json", metadata)
            (directory / "details.bin").write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "checksum"):
                verify_cells(directory, graph.identity)

    def test_short_range_read_fails_instead_of_returning_missing_roads(self):
        graph = example()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            metadata, _ = build_cells(graph, landmark_index(graph, [0]), 2, directory)
            (directory / "details.bin").write_bytes(b"")
            reader = CellReader(directory, metadata)
            try:
                with self.assertRaisesRegex(ValueError, "Incomplete range"):
                    reader.source(0)
            finally:
                reader.close()

    def test_partition_is_deterministic_and_exactly_covers_states(self):
        graph = example()
        index = landmark_index(graph, [0, 3, 5])
        with tempfile.TemporaryDirectory() as temporary:
            a, order = build_cells(graph, index, 2, Path(temporary) / "a")
            b, other = build_cells(graph, index, 2, Path(temporary) / "b")
            self.assertEqual(sorted(order), list(range(len(graph.roads))))
            self.assertEqual(order, other)
            self.assertEqual(a, b)

    def test_cycle_is_rejected_and_invalid_query_inputs_fail(self):
        graph = example()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            metadata, _ = build_cells(graph, landmark_index(graph, [0]), 2, directory)
            path = directory / "cells.bin"
            data = bytearray(path.read_bytes())
            struct.pack_into("<ii", data, 0, 0, 0)
            path.write_bytes(data)
            reader = CellReader(directory, metadata)
            try:
                with self.assertRaises(ValueError):
                    classify_cells(reader, [(0, 0)], 1)
                with self.assertRaises(ValueError):
                    classify_cells(reader, [], 1)
            finally:
                reader.close()
        with self.assertRaises(ValueError):
            refine_targets(graph.adjacency, [(0, 0)], 1, {-1})


if __name__ == "__main__":
    unittest.main()
