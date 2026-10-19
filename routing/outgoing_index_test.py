import ast
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from base_ids_test import canonical, compact, road
from compact_storage import Roads, build_graph as frozen_build
from outgoing_fixtures import qualify
from outgoing_index import OutgoingIndex, build_graph


class OutgoingIndexTests(unittest.TestCase):
    def compare(self, source, **kwargs):
        measurements = {}
        try:
            expected = frozen_build(copy.deepcopy(source), **kwargs)
        except Exception as error:
            with self.assertRaises(type(error)) as caught:
                build_graph(copy.deepcopy(source), measurements=measurements, **kwargs)
            self.assertEqual(str(caught.exception), str(error))
        else:
            actual = build_graph(copy.deepcopy(source), measurements=measurements, **kwargs)
            self.assertEqual(canonical(actual), canonical(expected))
        return measurements

    def test_interleaved_nodes_keep_append_order_and_missing_default(self):
        tails = [9007199254740993, 0, 9007199254740993, 17, 0, 9007199254740993]
        index = OutgoingIndex()
        for node in tails: index.count(node)
        marks = []
        index.finish(tails, marks.append)
        self.assertEqual(list(index.get(tails[0])), [0, 2, 5])
        self.assertEqual(list(index.get(0)), [1, 4])
        self.assertEqual(list(index.get(17)), [3])
        missing = object()
        self.assertIs(index.get(9, missing), missing)
        self.assertEqual(marks, ["outgoingOffsetsReady", "outgoingBuffersReady", "outgoingFilled"])
        self.assertEqual(index.summary()["outgoingNodeMaps"], 1)
        self.assertEqual(index.offsets.itemsize, 4)
        self.assertEqual(index.references.itemsize, 4)

    def test_high_fanout_retains_order_with_flat_references(self):
        source = compact([road("1:0:f", 0, 1)] + [road(f"{i + 10}:0:f", 1, i + 2) for i in range(4096)])
        stages = []
        stats = self.compare(source)
        self.assertEqual(stats["outgoingReferences"], 4097)
        self.assertEqual(stats["outgoingNodes"], 2)
        self.assertEqual(stats["outgoingArrayPayloadBytes"], 4 * (4097 + 3))
        self.assertEqual(stats["outgoingMode"], "compact")
        build_graph(source, observe=stages.append)
        self.assertLess(stages.index("outgoingFilled"), stages.index("outgoingReady"))
        self.assertLess(stages.index("outgoingReady"), stages.index("arcsBuilt"))

    def test_empty_index_and_graph_match(self):
        stats = self.compare(Roads())
        self.assertEqual(stats["outgoingReferences"], 0)
        self.assertEqual(stats["outgoingArrayPayloadBytes"], 4)
        self.assertEqual(stats["idKeysRetained"], 0)

    def test_generic_unordered_and_subclass_fallbacks_remain(self):
        for source in ([road("10:0:f"), road("20:0:f", 2, 3)],
                       compact([road("20:0:f", 2, 3), road("10:0:f")])):
            stats = self.compare(source)
            self.assertEqual(stats["outgoingMode"], "lists")
            self.assertTrue(stats["fallbackToStrings"])
        class AlternateIds(Roads):
            def __getitem__(self, index):
                row = super().__getitem__(index)
                row["id"] = "same"
                return row
        source = compact([road("10:0:f"), road("20:0:f")])
        source.__class__ = AlternateIds
        self.compare(source)

    def test_capacity_fallback_preserves_validation_and_ordered_id_storage(self):
        source = compact([road("10:0:f"), road("20:0:f", 2, 3)])
        with patch("outgoing_index.MAX_REFERENCES", 1):
            stats = self.compare(source)
            self.assertEqual(stats["outgoingMode"], "lists")
            self.assertTrue(stats["orderedKeyFastPath"])
            self.assertFalse(stats["fallbackToStrings"])

    def test_duplicate_and_self_loop_priority_precedes_turn_validation(self):
        invalid = [{"id": 9, "kind": "bad", "fromWay": 10, "toWay": 20, "via": 2}]
        for rows in ([road("10:0:f"), road("10:0:f")], [road("10:0:f", 1, 1)],
                     [road("10:0:f"), road("20:0:f"), road("10:0:f")]):
            self.compare(compact(rows), restrictions=invalid)
        self.compare(compact([road("10:0:f", 1, 1)]), node_delays={1: -1})
        self.compare(compact([road("10:0:f", 1, 1)]), node_delays={1: -1}, u_turn_ms=-1)

    def test_cost_and_delay_error_types_messages_and_priority(self):
        invalid = [{"id": 9, "kind": "bad", "fromWay": 10, "toWay": 20, "via": 2}]
        for cost in (-1, True, 1.5, float("nan")):
            self.compare([road("10:0:f"), road("10:0:f", cost=cost)], restrictions=invalid)
        for delay in (-1, True, 1.5):
            self.compare(compact([road("10:0:f")]), node_delays={1: delay})

    def test_large_osm_ids_truth_value_directions_and_parallel_geometry(self):
        self.compare(compact([road("9007199254740993:4294967295:f", 9007199254740995, 18446744073709551615)]))
        source = compact([road("10:0:r"), road("10:0:r")])
        source.directions[0] = 2
        self.compare(source)
        self.compare(compact([road("10:0:f"), road("10:1:f"), road("20:0:f")]))

    def test_incomplete_arrays_preserve_failure_behavior(self):
        for field in ("segments", "directions", "tails", "heads", "costs", "names"):
            with self.subTest(field=field):
                source = compact([road("10:0:f"), road("20:0:f")])
                getattr(source, field).pop()
                self.compare(source)

    def test_turn_rules_delays_and_blocked_nodes_match_arc_and_audit_order(self):
        source = compact([road("10:0:f"), road("10:0:r", 2, 1), road("20:0:f", 2, 3), road("30:0:f", 2, 4)])
        for kind in ("no_left_turn", "only_right_turn", "no_u_turn", "only_u_turn", "no_straight_on", "only_straight_on", "bad"):
            self.compare(source, restrictions=[{"id": 99, "kind": kind, "fromWay": 10, "toWay": 10 if kind.endswith(("u_turn", "straight_on")) else 20, "via": 2}], node_delays={2: 5000}, u_turn_ms=20000)
        self.compare(source, blocked_nodes={2})

    def test_fresh_importer_oracle_fixtures_for_compact_and_string_fallback(self):
        for mode in ("ordered", "strings"):
            result = qualify(mode)
            self.assertEqual(result["caseCount"], 17)
            self.assertEqual(result["fullCostComparisons"], 296)
            self.assertEqual(result["boundedCostComparisons"], 888)

    def test_validation_routing_and_import_bodies_remain_frozen(self):
        root = Path(__file__).parent
        def function(file, name):
            return next(node for node in ast.parse((root / file).read_text()).body if isinstance(node, ast.FunctionDef) and node.name == name)
        old, new = function("base_ids.py", "ordered_build_graph"), function("outgoing_index.py", "ordered_build_graph")
        def road_loop(node):
            return next(item for item in node.body if isinstance(item, ast.For) and isinstance(item.target, ast.Tuple))
        old_loop, new_loop = road_loop(old), road_loop(new)
        new_loop.body[-1] = old_loop.body[-1]
        self.assertEqual(ast.dump(old_loop), ast.dump(new_loop))
        def routing_body(node):
            start = next(i for i, item in enumerate(node.body) if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "rules" for t in item.targets))
            end = next(i for i, item in enumerate(node.body) if isinstance(item, ast.Delete))
            return [ast.dump(item) for item in node.body[start:end]]
        self.assertEqual(routing_body(old), routing_body(new))
        self.assertEqual(ast.dump(function("base_id_input.py", "build_base")), ast.dump(function("outgoing_input.py", "build_base")))
        for name in ("import_barriers", "import_maneuvers"):
            self.assertEqual(ast.dump(function("base_id_import.py", name)), ast.dump(function("outgoing_import.py", name)))


if __name__ == "__main__": unittest.main()
