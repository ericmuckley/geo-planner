import ast
import copy
from pathlib import Path
import unittest

from base_ids import build_graph, ordered_road_ids
from base_id_fixtures import qualify
from compact_storage import Roads, build_graph as frozen_build, encoded_blocks


def road(identifier, tail=1, head=2, cost=10):
    way = int(identifier.split(":")[0])
    return {"id": identifier, "way": way, "from": tail, "to": head, "costMs": cost,
            "fromPoint": [0, 0], "toPoint": [1, 1], "name": None}


def compact(rows):
    result = Roads()
    for row in rows: result.append(row)
    return result


def canonical(graph):
    return b"".join(encoded_blocks({"identity": graph.identity, "roads": graph.roads,
                                   "adjacency": graph.adjacency, "blocked": graph.blocked_turns}))


class BaseIdTests(unittest.TestCase):
    def compare(self, source, **kwargs):
        for mode in ("strings", "ordered"):
            with self.subTest(mode=mode):
                measurements = {}
                try: expected = frozen_build(copy.deepcopy(source), **kwargs)
                except Exception as error:
                    with self.assertRaises(type(error)) as caught: build_graph(copy.deepcopy(source), id_mode=mode, measurements=measurements, **kwargs)
                    self.assertEqual(str(caught.exception), str(error))
                else:
                    actual = build_graph(copy.deepcopy(source), id_mode=mode, measurements=measurements, **kwargs)
                    self.assertEqual(canonical(actual), canonical(expected))
                return_measurement = measurements
        return return_measurement

    def test_ordered_ids_keep_one_key_with_exact_graph_and_container_measurements(self):
        source = compact([road("10:0:f"), road("10:0:r", 2, 1), road("10:1:f", 2, 3), road("20:0:f", 3, 4)])
        result = self.compare(source, node_delays={2: 5000}, u_turn_ms=20000)
        self.assertTrue(result["orderedKeyFastPath"])
        self.assertEqual(result["idKeysRetained"], 1)
        self.assertEqual(result["idSetShallowBytes"], 0)
        self.assertEqual(result["idStringShallowBytes"], 0)
        self.assertEqual(result["outgoingReferences"], len(source))
        self.assertGreater(result["outgoingContainerBytes"], 0)

    def test_adjacent_duplicates_and_self_loops_preserve_validation_message(self):
        for rows in ([road("10:0:f"), road("10:0:f")], [road("10:0:f", 2, 2)],
                     [road("10:0:f"), road("10:0:f", 2, 2)]): self.compare(compact(rows))

    def test_unordered_unique_and_nonadjacent_duplicate_inputs_use_original_behavior(self):
        result = self.compare(compact([road("20:0:f", 2, 3), road("10:0:f")]))
        self.assertTrue(result["fallbackToStrings"])
        self.assertEqual(result["mode"], "strings")
        self.compare(compact([road("10:0:f"), road("20:0:f"), road("10:0:f")]))

    def test_duplicate_geometry_with_distinct_ids_is_not_duplicate_id(self):
        result = self.compare(compact([road("10:0:f"), road("10:1:f"), road("20:0:f")]))
        self.assertEqual(result["idKeysRetained"], 1)

    def test_generic_input_and_subclasses_use_frozen_string_ids(self):
        result = self.compare([road("10:0:f"), road("20:0:f", 2, 3)])
        self.assertTrue(result["fallbackToStrings"])
        class AlternateIds(Roads):
            def __getitem__(self, index):
                row = super().__getitem__(index)
                row["id"] = "same"
                return row
        source = compact([road("10:0:f"), road("20:0:f")]); source.__class__ = AlternateIds
        self.assertFalse(ordered_road_ids(source))
        self.compare(source)

    def test_cost_delay_duplicate_and_restriction_error_priority_is_preserved(self):
        invalid_rule = [{"id": 9, "kind": "bad", "fromWay": 10, "toWay": 20, "via": 2}]
        for cost in (-1, True, 1.5, float("nan")):
            self.compare([road("10:0:f"), road("10:0:f", cost=cost)], restrictions=invalid_rule)
        self.compare(compact([road("10:0:f"), road("10:0:f")]), restrictions=invalid_rule)
        self.compare(compact([road("10:0:f", 1, 1)]), node_delays={1: -1}, u_turn_ms=0)
        self.compare(compact([road("10:0:f", 1, 1)]), node_delays={1: -1}, u_turn_ms=-1)
        self.compare(compact([road("10:0:f")]), restrictions=invalid_rule)

    def test_direction_truth_values_match_canonical_ids_and_large_ids_remain_exact(self):
        source = compact([road("10:0:r"), road("10:0:r")])
        source.directions[0] = 2
        self.assertTrue(ordered_road_ids(source))
        self.compare(source)
        source = compact([road("9007199254740993:4294967295:f", 9007199254740995, 9007199254740997)])
        self.compare(source)

    def test_empty_and_incomplete_compact_key_arrays_preserve_frozen_behavior(self):
        self.assertEqual(self.compare(Roads())["idKeysRetained"], 0)
        source = compact([road("10:0:f"), road("20:0:f")]); source.segments.pop()
        self.assertFalse(ordered_road_ids(source))
        self.compare(source)

    def test_turn_rules_and_blocked_nodes_produce_identical_arcs_and_audits(self):
        source = compact([road("10:0:f"), road("20:0:f", 2, 3), road("30:0:f", 2, 4)])
        for kind in ("no_left_turn", "only_right_turn"):
            self.compare(source, restrictions=[{"id": 99, "kind": kind, "fromWay": 10, "toWay": 20, "via": 2}])
        self.compare(source, blocked_nodes={2})

    def test_fresh_importer_fixture_parity_for_both_id_modes(self):
        for mode in ("strings", "ordered"):
            result = qualify(mode)
            self.assertEqual(result["caseCount"], 17)
            self.assertEqual(result["fullCostComparisons"], 296)
            self.assertEqual(result["boundedCostComparisons"], 888)

    def test_routing_body_and_source_import_body_remain_frozen(self):
        root = Path(__file__).parent
        def function(file, name):
            return next(node for node in ast.parse((root / file).read_text()).body if isinstance(node, ast.FunctionDef) and node.name == name)
        original = function("compact_storage.py", "build_graph")
        for name in ("string_build_graph", "ordered_build_graph"):
            current = function("base_ids.py", name)
            # The adjacency and restriction body stays verbatim in both versions.
            def routing_body(node):
                start = next(index for index, item in enumerate(node.body) if isinstance(item, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "rules" for target in item.targets))
                end = next(index for index, item in enumerate(node.body) if isinstance(item, ast.Delete))
                return [item for item in node.body[start:end] if not (isinstance(item, ast.Expr) and isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Name) and item.value.func.id == "mark")]
            self.assertEqual([ast.dump(node) for node in routing_body(original)], [ast.dump(node) for node in routing_body(current)])
        original = function("input_import.py", "build_base")
        current = function("base_id_input.py", "build_base")
        current.args = original.args
        call = next(node for node in ast.walk(current) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "build_graph")
        call.args = call.args[:5]
        self.assertEqual(ast.dump(original), ast.dump(current))


if __name__ == "__main__": unittest.main()
