import unittest

from two_hour_region_prepare_v2 import scaling
from two_hour_release import two_hour_check


class TwoHourRegionTests(unittest.TestCase):
    def test_restriction_growth_can_dominate_road_only_resource_scaling(self):
        keys = ("sourceNodes", "sourceWays", "sourceRelations", "wayEligibleDirectedSegments", "historyPrefixCeiling", "candidateViaWayRules")
        reference = dict.fromkeys(keys, 10)
        candidate = dict.fromkeys(keys, 15)
        candidate.update(sourceRelations=25, roadStatesUpperBound=140, historyStatesUpperBound=150)
        ratios, scale = scaling(candidate, reference, {"roads": 100, "states": 110})
        self.assertEqual(scale, 2.5)
        self.assertEqual(ratios["roadCeiling"], 1.4)

    def test_boundary_acceptance_requires_every_origin_and_the_exact_budget(self):
        origins = [{"origin": str(i), "firstCutExitMs": 8000000,
                    "budgets": [{"budgetMs": 7200000, "reachableCutNodes": 0}]} for i in range(5)]
        self.assertEqual(len(two_hour_check(origins)), 5)
        with self.assertRaises(ValueError): two_hour_check(origins[:4])
        origins[-1]["firstCutExitMs"] = 7200000
        with self.assertRaises(ValueError): two_hour_check(origins)
        origins[-1]["firstCutExitMs"] = 8000000
        origins[-1]["budgets"][0]["reachableCutNodes"] = 1
        with self.assertRaises(ValueError): two_hour_check(origins)
        origins[-1]["budgets"][0] = {"budgetMs": 3600000, "reachableCutNodes": 0}
        with self.assertRaises(ValueError): two_hour_check(origins)


if __name__ == "__main__": unittest.main()
