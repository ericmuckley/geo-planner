import copy
import unittest

from hour_admission import evaluate


class HourAdmissionTests(unittest.TestCase):
    def test_worst_build_and_qualification_are_included_with_preparation_and_margin(self):
        def measured(value):
            return {"resourceCheckpoints": {"verified": {"memory.max": str(4 * 1024 ** 3), "memory.peak": str(value),
                "memory.swap.max": "0", "memory.swap.current": "0", "memory.swap.peak": "0",
                "memory.events": {key: "0" for key in ("max", "oom", "oom_kill", "oom_group_kill")}}}}
        counts = {key: 100 for key in ("sourceNodes", "sourceWays", "sourceRelations", "wayEligibleDirectedSegments", "historyPrefixCeiling", "candidateViaWayRules")}
        counts.update({"roadStatesUpperBound": 100, "historyStatesUpperBound": 100})
        calibration = {**measured(2_000_000_000), "candidate": counts, "xmlByteIdentical": True,
                       "fixtures": [{"graphAndAuditIdentical": True}] * 6}
        built = {**measured(2_000_000_000), "roads": 100, "states": 100}
        rebuilt = measured(2_500_000_000)
        qualified = {**measured(2_700_000_000), "functionalSummaryIdentical": True}
        candidate = measured(2_000_000_000)
        result = evaluate(calibration, candidate, counts, built, rebuilt, qualified)
        self.assertTrue(result["cappedExperimentEligible"])
        self.assertEqual(result["wholeWorkloadEstimateWithHeadroomBytes"], 3_375_000_000)
        large = {**qualified, **measured(3_800_000_000)}
        self.assertFalse(evaluate(calibration, candidate, counts, built, rebuilt, large)["cappedExperimentEligible"])
        self.assertFalse(evaluate(calibration, measured(3_800_000_000), counts, built, rebuilt, qualified)["cappedExperimentEligible"])
        self.assertFalse(evaluate(calibration, candidate, counts, built, measured(3_800_000_000), qualified)["cappedExperimentEligible"])
        self.assertFalse(evaluate(calibration, candidate, counts, built, rebuilt, {**qualified, "functionalSummaryIdentical": False})["cappedExperimentEligible"])
        pressure = copy.deepcopy(candidate);pressure["resourceCheckpoints"]["verified"]["memory.events"]["max"] = "1"
        self.assertFalse(evaluate(calibration, pressure, counts, built, rebuilt, qualified)["cappedExperimentEligible"])
        bad = copy.deepcopy(candidate);bad["resourceCheckpoints"]["verified"]["memory.swap.peak"] = "1"
        with self.assertRaises(ValueError): evaluate(calibration, bad, counts, built, rebuilt, qualified)
