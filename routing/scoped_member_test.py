from types import SimpleNamespace
import unittest

from member_lookup_test import base
from scoped_fixtures import qualify
from scoped_member_lookup import resolve, road_lookup


class ScopedMemberTests(unittest.TestCase):
    def test_unrelated_duplicates_cannot_disable_a_valid_restriction(self):
        graph = base([(10, 1, 2), (20, 2, 3), (30, 3, 4), (50, 5, 6), (50, 5, 6)])
        lookup, ambiguous, stats = road_lookup(graph, {10, 20, 30})
        rule = resolve({"id": 99, "ways": [10, 20, 30]}, {10: [1, 2], 20: [2, 3], 30: [3, 4]}, graph, lookup, ambiguous)
        self.assertEqual(rule["roads"], [0, 1, 2])
        self.assertEqual(ambiguous, {50})
        self.assertEqual(stats["duplicateExamples"][0]["way"], 50)

    def test_ambiguous_member_geometry_is_rejected_even_with_distinct_road_ids(self):
        graph = base([(10, 1, 2), (10, 1, 2), (20, 2, 3), (30, 3, 4)])
        lookup, ambiguous, _ = road_lookup(graph, {10, 20, 30})
        with self.assertRaisesRegex(ValueError, "Duplicate directed"):
            resolve({"id": 99, "ways": [10, 20, 30]}, {10: [1, 2], 20: [2, 3], 30: [3, 4]}, graph, lookup, ambiguous)

    def test_all_source_fixtures_and_fresh_independent_costs(self):
        proof = qualify()
        self.assertEqual(proof["caseCount"], 17)
        self.assertEqual(sum(row["unchangedAfterIdentityNormalization"] for row in proof["cases"]), 16)
        self.assertEqual(proof["boundedCostComparisons"], proof["fullCostComparisons"] * 3)


if __name__ == "__main__": unittest.main()
