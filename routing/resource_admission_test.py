import unittest

from resource_admission import evaluate


class ResourceAdmissionTests(unittest.TestCase):
    def test_preparation_and_scaled_complete_import_both_need_headroom(self):
        def measured(peak):
            return {"xmlByteIdentical": True, "identicalArtifactSha256": {"graph": "same"}, "roads": 100, "states": 100,
                    "resourceCheckpoints": {"complete": {"memory.max": str(4 * 1024 ** 3), "memory.swap.max": "0", "memory.swap.peak": "0",
                        "memory.peak": str(peak), "memory.events": {"oom": "0", "oom_kill": "0", "oom_group_kill": "0", "max": "0"}}}}
        counts = {key: 100 for key in ("sourceNodes", "sourceWays", "sourceRelations", "wayEligibleDirectedSegments", "historyPrefixCeiling", "candidateViaWayRules", "roadStatesUpperBound", "historyStatesUpperBound")}
        good = measured(2 * 1024 ** 3)
        self.assertTrue(evaluate(good, good, counts, counts)["cappedImportEligible"])
        large = measured(4 * 1024 ** 3)
        self.assertFalse(evaluate(large, good, counts, counts)["cappedImportEligible"])
        self.assertFalse(evaluate(good, good, counts, {**counts, "sourceNodes": 200})["cappedImportEligible"])
        pressured = measured(2 * 1024 ** 3)
        pressured["resourceCheckpoints"]["complete"]["memory.events"]["max"] = "1"
        self.assertFalse(evaluate(pressured, good, counts, counts)["cappedImportEligible"])
        missing = {**good, "xmlByteIdentical": False}
        self.assertFalse(evaluate(missing, good, counts, counts)["cappedImportEligible"])
        invalid = measured(2 * 1024 ** 3)
        invalid["resourceCheckpoints"]["complete"]["memory.swap.max"] = "1"
        with self.assertRaises(ValueError): evaluate(invalid, good, counts, counts)


if __name__ == "__main__": unittest.main()
