from array import array
import ast
import copy
from pathlib import Path
import unittest

from base_ids_test import canonical, compact, road
from compact_storage import Roads
from outgoing_index import build_graph as frozen_build
from source_outgoing import SourceOutgoingIndex, build_graph
from source_outgoing_fixtures import qualify


class SourceOutgoingTests(unittest.TestCase):
    def compare(self, source, node_ids=None, **options):
        if node_ids is None:
            node_ids = array("Q", sorted({node for row in source for node in (row["from"], row["to"])}))
        try:
            expected = frozen_build(copy.deepcopy(source), **options)
        except Exception as error:
            with self.assertRaises(type(error)) as caught:
                build_graph(copy.deepcopy(source), node_ids=node_ids, **options)
            self.assertEqual(str(caught.exception), str(error))
            return {}
        measurements = {}
        actual = build_graph(copy.deepcopy(source), node_ids=node_ids, measurements=measurements, **options)
        self.assertEqual(canonical(actual), canonical(expected))
        self.assertEqual(actual.blocked_turns, expected.blocked_turns)
        return measurements

    def test_reference_order_inactive_ids_and_missing_default(self):
        ids = array("Q", [0, 9, 17, 9007199254740993, 18446744073709551615])
        tails = [ids[3], 0, ids[3], 17, 0, ids[3]]
        index = SourceOutgoingIndex(ids)
        for tail in tails: index.count(tail)
        index.finish(tails, lambda stage: None)
        self.assertIs(index.node_ids, ids)
        self.assertEqual(list(index.get(ids[3])), [0, 2, 5])
        self.assertEqual(list(index.get(0)), [1, 4])
        missing = object()
        self.assertIs(index.get(9, missing), missing)
        self.assertIs(index.get(99, missing), missing)
        self.assertEqual(index.summary()["outgoingNodeMaps"], 0)
        with self.assertRaisesRegex(ValueError, "missing from source IDs"): index.count(99)

    def test_high_fanout_parallel_roads_and_unused_source_nodes(self):
        source = compact([road("1:0:f", 0, 1)] + [road(f"{i+10}:0:f", 1, i+2) for i in range(1024)])
        stats = self.compare(source, node_ids=array("Q", range(2048)))
        self.assertEqual(stats["outgoingMode"], "source-sorted")
        self.assertEqual(stats["outgoingNodes"], 2)
        self.assertEqual(stats["outgoingReferences"], 1025)
        self.compare(compact([road("10:0:f"), road("10:1:f"), road("20:0:f")]))

    def test_generic_unordered_strings_and_invalid_source_id_fallbacks(self):
        source = compact([road("10:0:f"), road("20:0:f", 2, 3)])
        for ids in ([], array("q", [3, 2, 1]), array("q", [1, 2, 2, 3])):
            self.assertEqual(self.compare(source, ids)["outgoingMode"], "compact")
        self.assertEqual(self.compare(source, id_mode="strings")["outgoingMode"], "lists")
        self.compare([road("20:0:f"), road("10:0:f")])
        self.compare(compact([road("20:0:f"), road("10:0:f")]))
        self.compare(source, id_mode="invalid")

    def test_empty_and_validation_error_priority(self):
        self.compare(Roads())
        invalid = [{"id": 9, "kind": "bad", "fromWay": 10, "toWay": 20, "via": 2}]
        for rows in ([road("10:0:f"), road("10:0:f")], [road("10:0:f", 1, 1)]):
            self.compare(compact(rows), restrictions=invalid)
            self.compare(compact(rows), node_delays={1: -1})
        for field in ("segments", "directions", "tails", "heads", "costs", "names"):
            source = compact([road("10:0:f"), road("20:0:f")])
            getattr(source, field).pop()
            self.compare(source, node_ids=array("Q", [1, 2]))

    def test_turn_costs_restrictions_and_blocked_nodes(self):
        source = compact([road("10:0:f"), road("10:0:r", 2, 1), road("20:0:f", 2, 3), road("30:0:f", 2, 4)])
        for kind in ("no_left_turn", "only_right_turn", "no_u_turn", "only_u_turn", "no_straight_on", "only_straight_on", "bad"):
            self.compare(source, restrictions=[{"id": 99, "kind": kind, "fromWay": 10,
                         "toWay": 10 if kind.endswith(("u_turn", "straight_on")) else 20, "via": 2}],
                         node_delays={2: 5000}, u_turn_ms=20000)
        self.compare(source, blocked_nodes={2})

    def test_scoped_barriers_and_partial_road_oracles(self):
        result = qualify()
        self.assertEqual(result["caseCount"], 17)
        self.assertGreater(result["partialComparisons"], 0)
        self.assertTrue(all(row["sourceSortedBuilds"] > 0 for row in result["cases"]))

    def test_routing_and_import_bodies_stay_frozen(self):
        root = Path(__file__).parent
        def function(file, name):
            return next(node for node in ast.parse((root/file).read_text()).body if isinstance(node, ast.FunctionDef) and node.name == name)
        old, new = function("outgoing_index.py", "ordered_build_graph"), function("source_outgoing.py", "ordered_build_graph")
        new.args = old.args
        for left, right in zip(old.body, new.body):
            if isinstance(left, ast.Assign) and isinstance(left.value, ast.Call) and isinstance(left.value.func, ast.Name) and left.value.func.id == "OutgoingIndex":
                right.value = left.value
        self.assertEqual(ast.dump(old), ast.dump(new))
        old_input, new_input = function("outgoing_input.py", "build_base"), function("source_outgoing_input.py", "build_base")
        for node in ast.walk(new_input):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "build_graph":
                node.keywords = [keyword for keyword in node.keywords if keyword.arg != "node_ids"]
        self.assertEqual(ast.dump(old_input), ast.dump(new_input))
        for name in ("import_maneuvers", "import_barriers"):
            self.assertEqual(ast.dump(function("scoped_import.py", name)), ast.dump(function("source_outgoing_import.py", name)))


if __name__ == "__main__": unittest.main()
