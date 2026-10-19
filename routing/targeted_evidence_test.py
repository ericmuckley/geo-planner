import ast
from collections import defaultdict
from pathlib import Path
import unittest

from compact_storage import Roads
from evidence_fixtures import qualify
from targeted_evidence import selected_incidence


def roads(rows):
    result = Roads()
    for index, (tail, head) in enumerate(rows):
        result.append({"id": f"1:{index}:f", "way": 1, "from": tail, "to": head, "costMs": 1,
                       "fromPoint": [0, 0], "toPoint": [1, 1], "name": None})
    return result


class TargetedEvidenceTests(unittest.TestCase):
    def test_selected_indexes_preserve_order_and_repeated_references(self):
        source = roads([(9, 2), (2, 9), (9, 2), (3, 4), (2, 2)])
        incoming, outgoing, stats = selected_incidence(source, {2, 99})
        old_in, old_out = defaultdict(list), defaultdict(list)
        for index, row in enumerate(source):
            old_in[row["to"]].append(index); old_out[row["from"]].append(index)
        self.assertEqual(dict(incoming), {2: old_in[2]})
        self.assertEqual(dict(outgoing), {2: old_out[2]})
        self.assertEqual(incoming[99], [])
        self.assertEqual(outgoing[99], [])
        self.assertEqual(stats["incomingReferences"], 3)
        self.assertEqual(stats["outgoingReferences"], 2)

    def test_numeric_arrays_do_not_materialize_road_rows(self):
        class ArrayOnly(Roads):
            def __getitem__(self, index): raise AssertionError("Unexpected road-row allocation")
        source = roads([(1, 2), (3, 4)])
        source.__class__ = ArrayOnly
        incoming, outgoing, _ = selected_incidence(source, {2})
        self.assertEqual(dict(incoming), {2: [0]})
        self.assertEqual(dict(outgoing), {})

    def test_empty_selection_empty_roads_and_large_node_ids(self):
        self.assertEqual(selected_incidence(roads([]), {1})[2]["scannedRoads"], 0)
        self.assertFalse(selected_incidence(roads([(1, 2)]), set())[0])
        node = 9_007_199_254_740_993
        incoming, outgoing, _ = selected_incidence(roads([(1, node), (node, 2)]), {node})
        self.assertEqual(incoming[node], [0]); self.assertEqual(outgoing[node], [1])

    def test_source_fixtures_preserve_excerpt_audit_returns_and_failures(self):
        result = qualify()
        self.assertEqual(result["caseCount"], 11)
        self.assertEqual(result["successes"], 5)
        self.assertEqual(result["failuresMatched"], 6)

    def test_source_function_changes_only_indexing_and_measurement_statements(self):
        root = Path(__file__).parent
        def function(file):
            return next(node for node in ast.parse((root / file).read_text()).body if isinstance(node, ast.FunctionDef) and node.name == "source_examples")
        original, current = function("barriers.py"), function("targeted_evidence.py")
        # Strip the explicit measurement statements and substitute the frozen scan.
        current.args = original.args
        scan = next(index for index, node in enumerate(current.body) if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "selected_incidence")
        current.body[1:scan + 2] = original.body[1:3]
        class RemoveMarks(ast.NodeTransformer):
            def visit_Expr(self, node):
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "mark": return None
                return node
        current = RemoveMarks().visit(current)
        self.assertEqual(ast.dump(original), ast.dump(current))


if __name__ == "__main__": unittest.main()
