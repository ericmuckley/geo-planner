import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest

from compact_storage import Roads
from input_import import resolve as frozen_resolve, road_lookup as frozen_lookup
from member_fixtures import qualify
from member_lookup import resolve, road_lookup


def base(rows):
    roads = Roads()
    for index, (way, tail, head) in enumerate(rows):
        roads.append({"id": f"{way}:{index}:f", "way": way, "from": tail, "to": head,
                      "costMs": 1, "fromPoint": [0, 0], "toPoint": [1, 1], "name": None})
    return SimpleNamespace(roads=roads, adjacency=[[(index + 1, 1)] for index in range(len(rows) - 1)] + [[]])


class MemberLookupTests(unittest.TestCase):
    def test_selected_keys_equal_frozen_lookup_with_last_write_semantics(self):
        graph = base([(10, 1, 2), (10, 2, 1), (10, 1, 2), (20, 2, 3), (30, 3, 4)])
        actual, duplicate, stats = road_lookup(graph, {10, 30, 999})
        self.assertEqual(actual, {key: value for key, value in frozen_lookup(graph).items() if key[0] in {10, 30, 999}})
        self.assertEqual(actual[(10, 1, 2)], 2)
        self.assertTrue(duplicate)
        self.assertEqual(stats["retainedKeys"], 3)
        self.assertEqual(stats["memberRoadsScanned"], 4)
        self.assertEqual(stats["duplicateRoads"], 1)
        self.assertEqual(stats["maxWayKeys"], 2)

    def test_duplicate_outside_members_is_still_global(self):
        graph = base([(10, 1, 2), (20, 2, 3), (50, 5, 6), (50, 5, 6), (50, 5, 6)])
        lookup, duplicate, stats = road_lookup(graph, {10, 20})
        self.assertEqual(len(lookup), 2)
        self.assertTrue(duplicate)
        self.assertEqual(stats["duplicateRoads"], len(graph.roads) - len(frozen_lookup(graph)))

    def test_reverse_geometry_and_equal_nodes_on_other_ways_are_distinct(self):
        graph = base([(10, 1, 2), (10, 2, 1), (20, 1, 2)])
        _, duplicate, stats = road_lookup(graph, {10})
        self.assertFalse(duplicate)
        self.assertEqual(stats["maxWayKeys"], 2)

    def test_lookup_uses_arrays_without_materializing_road_rows(self):
        class ArrayOnly(Roads):
            def __getitem__(self, index): raise AssertionError("Do not materialize a road row")
        graph = base([(10, 1, 2)])
        graph.roads.__class__ = ArrayOnly
        self.assertEqual(road_lookup(graph, {10})[0], {(10, 1, 2): 0})

    def test_empty_and_large_ids_remain_exact(self):
        self.assertEqual(road_lookup(base([]), set())[0:2], ({}, False))
        identifier = 9_007_199_254_740_993
        graph = base([(identifier, identifier + 1, identifier + 2)])
        self.assertEqual(road_lookup(graph, {identifier})[0], frozen_lookup(graph))
        self.assertEqual(road_lookup(graph, set())[0:2], ({}, False))

    def test_unsorted_way_groups_fail_before_using_a_local_duplicate_set(self):
        for rows in ([(20, 1, 2), (10, 1, 2)], [(10, 1, 2), (20, 2, 3), (10, 1, 2)]):
            with self.assertRaisesRegex(ValueError, "ascending way order"): road_lookup(base(rows), {10})

    def test_duplicate_guard_preserves_error_priority_and_valid_resolution(self):
        rule = {"id": 99, "ways": [10, 20, 30]}
        ways = {10: [1, 2], 20: [2, 3], 30: [3, 4]}
        rows = [(10, 1, 2), (20, 2, 3), (30, 3, 4)]
        for duplicate in (False, True):
            for condition in ("valid", "missing-member", "ambiguous", "not-endpoint", "identical-joins", "missing-segment", "blocked"):
                graph = base(rows + ([(50, 5, 6), (50, 5, 6)] if duplicate else []))
                members = copy.deepcopy(ways)
                if condition == "missing-member": del members[10]
                if condition == "ambiguous": members[10] = [1, 2, 3]
                if condition == "not-endpoint": members[10] = [1, 2, 8]
                if condition == "identical-joins": members[30] = [2, 4]
                if condition == "missing-segment": members[10] = [9, 2]
                if condition == "blocked": graph.adjacency[0] = []
                lookup, found, _ = road_lookup(graph, {10, 20, 30})
                with self.subTest(duplicate=duplicate, condition=condition):
                    try: expected = frozen_resolve(rule, members, graph, frozen_lookup(graph))
                    except ValueError as error:
                        with self.assertRaises(ValueError) as caught: resolve(rule, members, graph, lookup, found)
                        self.assertEqual(str(caught.exception), str(error))
                    else: self.assertEqual(resolve(rule, members, graph, lookup, found), expected)

    def test_resolver_body_changes_only_the_duplicate_guard(self):
        root = Path(__file__).parent
        def function(file):
            return next(node for node in ast.parse((root / file).read_text()).body if isinstance(node, ast.FunctionDef) and node.name == "resolve")
        old, new = function("input_import.py"), function("member_lookup.py")
        old.args = new.args
        guards = [node for node in ast.walk(old) if isinstance(node, ast.If) and any(isinstance(child, ast.Constant) and child.value == "Duplicate directed road geometry" for child in ast.walk(node))]
        self.assertEqual(len(guards), 1)
        guards[0].test = ast.Name(id="duplicate_geometry", ctx=ast.Load())
        self.assertEqual(ast.dump(old), ast.dump(new))

    def test_frozen_source_fixture_parity_oracles_and_conservative_fallbacks(self):
        report = qualify()
        self.assertEqual(report["caseCount"], 17)
        self.assertGreater(report["fullCostComparisons"], 0)
        self.assertEqual(report["boundedCostComparisons"], report["fullCostComparisons"] * 3)


if __name__ == "__main__": unittest.main()
