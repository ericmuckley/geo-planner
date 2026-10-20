import unittest

from six_hour_preflight import BUDGET_MS, CAP, COUNT_KEYS, ORIGINS, admission, frontier
from six_hour_sources import Listing, polygons, within


class SixHourPreflightTests(unittest.TestCase):
    def test_official_metadata_parser_and_footprint_holes(self):
        listing = Listing("test-261014.osm.pbf")
        listing.feed('<table><tr><td><a href="test-latest.osm.pbf">latest</a></td><td>99</td></tr>'
                     '<tr><td><a href="test-261014.osm.pbf">snapshot</a></td><td>2026-10-15 02:43</td><td>1234</td></tr></table>')
        self.assertEqual(listing.result, {"listingBytes": 1234, "listingModified": "2026-10-15 02:43"})
        rings = polygons('test\n1\n0 0\n4 0\n4 4\n0 4\nEND\n!1\n1 1\n3 1\n3 3\n1 3\nEND\nEND\n')
        self.assertTrue(within([0.5, 0.5], rings))
        self.assertFalse(within([2, 2], rings))
        self.assertFalse(within([5, 5], rings))

    def test_expansion_is_six_hours_and_never_clipped_to_cached_parent(self):
        row = {"node": 1, "point": [-118, 34], "stateCount": 3,
               "origins": {origin: {"costMs": 7200001} for origin in ORIGINS}}
        result = frontier([row], [-118.2, 31.5, -114.6, 34.7])
        self.assertEqual(result["budgetMs"], BUDGET_MS)
        self.assertEqual(result["originCutPairs"], 5)
        self.assertEqual(result["cutHistoryStatesAccounted"], 3)
        self.assertEqual(result["candidateBounds"], result["roundedBounds"])
        self.assertLess(result["candidateBounds"][0], -119.8)
        self.assertGreater(result["candidateBounds"][3], 35.5)
        self.assertEqual(result["clippedSides"], [])

    def test_require_all_sources_and_account_for_unreachable_cuts(self):
        row = {"node": 1, "point": [-118, 34], "stateCount": 2,
               "origins": {origin: {"costMs": None} for origin in ORIGINS}}
        result = frontier([row], [-118.2, 31.5, -114.6, 34.7])
        self.assertEqual(result["cutNodesAccounted"], 1)
        self.assertEqual(result["cutHistoryStatesAccounted"], 2)
        self.assertEqual(result["originCutPairs"], 0)
        row["origins"].pop("port-incoming")
        with self.assertRaises(ValueError): frontier([row], [-118.2, 31.5, -114.6, 34.7])

    def test_partial_sources_cannot_be_admitted_even_when_resources_fit(self):
        reference = dict.fromkeys(COUNT_KEYS, 10)
        candidate = reference | {"roadStatesUpperBound": 10, "historyStatesUpperBound": 10}
        measured = {name: (1000, False) for name in ("build", "rebuild", "qualification", "cuts", "preparation")}
        result = admission(candidate, reference, {"roads": 10, "states": 10}, measured, False)
        self.assertTrue(result["resourceScreenPasses"])
        self.assertFalse(result["eligibleForSeparateBuild"])
        self.assertEqual(result["decision"], "hold")

    def test_restrictions_margin_and_pressure_each_affect_gate(self):
        reference = dict.fromkeys(COUNT_KEYS, 10)
        candidate = reference | {"historyPrefixCeiling": 20, "roadStatesUpperBound": 10, "historyStatesUpperBound": 10}
        measured = {name: (CAP // 2, False) for name in ("build", "rebuild", "qualification", "cuts", "preparation")}
        result = admission(candidate, reference, {"roads": 10, "states": 10}, measured, True)
        self.assertEqual(result["scalingRatio"], 2)
        self.assertGreater(result["wholeWorkflowWith25PercentMarginBytes"], CAP)
        self.assertFalse(result["eligibleForSeparateBuild"])
        candidate["historyPrefixCeiling"] = 10
        measured = {name: (1000, name == "cuts") for name in measured}
        self.assertFalse(admission(candidate, reference, {"roads": 10, "states": 10}, measured, True)["eligibleForSeparateBuild"])


if __name__ == "__main__": unittest.main()
