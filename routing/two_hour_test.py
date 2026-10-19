import copy
from importlib.util import find_spec
from pathlib import Path
import random
import tempfile
import unittest

from import_roads import DEFAULT_SPEEDS, distance_m, speed_kph
from paged_ids import PagedIdSet
from paged_select import select_ids
from sparse_select import select_ids as previous_select
from two_hour_admission import evaluate
from two_hour_frontier import plan


class PagedIdsTests(unittest.TestCase):
    def test_membership_matches_set_for_clustered_and_far_apart_original_ids(self):
        rng = random.Random(214)
        values = [1, 4095, 4096, 4097, 14284658989, 2 ** 60] + [rng.randrange(1, 100000) for _ in range(1000)]
        actual = PagedIdSet()
        for value in values + values: actual.add(value)
        self.assertEqual(len(actual), len(set(values)))
        for value in values + [0, -1, 2 ** 60 + 1, 2 ** 61]: self.assertEqual(value in actual, value in set(values))
        far = PagedIdSet();far.add(1);far.add(2 ** 60)
        self.assertEqual(far.storage_summary()["bitmapBytes"], 1024)
        for value in (0, -1, True, 1.5):
            with self.assertRaises(ValueError): actual.add(value)

    @unittest.skipUnless(find_spec("osmium"), "Pinned reader runs inside the sparse tools image")
    def test_paged_selection_matches_original_ids_parent_closure_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.osm"
            source.write_text('<osm version="0.6"><node id="1" lon="-2" lat="0"/><node id="14284658989" lon="0" lat="0"/>'
                '<way id="10"><nd ref="1"/><nd ref="14284658989"/><tag k="highway" v="residential"/></way>'
                '<relation id="99"><member type="relation" ref="100" role="via"/><tag k="type" v="restriction:motorcar"/></relation>'
                '<relation id="100"><member type="way" ref="10" role="from"/><tag k="type" v="restriction"/></relation></osm>')
            old, new = Path(tmp) / "old.txt", Path(tmp) / "new.txt"
            a, b = previous_select(source, [-1, -1, 1, 1], old), select_ids(source, [-1, -1, 1, 1], new)
            self.assertEqual(old.read_bytes(), new.read_bytes())
            self.assertEqual({k:v for k,v in a.items() if k not in {"wallMs", "scope"}}, {k:v for k,v in b.items() if k not in {"wallMs", "scope", "nodeStorage"}})


class FrontierTests(unittest.TestCase):
    def test_remaining_time_envelopes_include_every_origin_and_flag_parent_clipping(self):
        rows = [{"node": 1, "point": [0,0], "origins": {"a": {"costMs": 3600000}, "b": {"costMs": 8000000}}},
                {"node": 2, "point": [2,0], "origins": {"a": {"costMs": 7200000}, "b": {"costMs": None}}}]
        result = plan(rows, [-.1,-.1,2.1,.1], [-1,-1,3,1])
        self.assertEqual(result["originCutPairs"], 2)
        self.assertEqual(result["reachedCutNodes"], 2)
        self.assertEqual(result["candidateBounds"], [-1,-1,2.1,1])
        self.assertFalse(result["envelopeContainedInParent"])
        self.assertAlmostEqual(distance_m([0,0],[0,result["envelopeBounds"][3]]),160000,places=5)
        self.assertLessEqual(max(DEFAULT_SPEEDS.values()), result["maxSpeedKph"])
        with self.assertRaises(ValueError): speed_kph("161", 100)
        polar = plan([{**rows[0], "point": [0,89.9]}], [-1,89,1,89.9], [-180,-90,180,90])
        self.assertEqual(polar["envelopeBounds"][::2], [-180,180])
        with self.assertRaises(ValueError): plan(rows, [-1,-1,1,1], [-2,-2,2,2], 0)


class TwoHourAdmissionTests(unittest.TestCase):
    def test_resource_gate_uses_worst_phase_and_keeps_source_clipping_separate(self):
        def measured(value):
            return {"resourceCheckpoints": {"verified": {"memory.max": str(4 * 1024 ** 3), "memory.peak": str(value),
                "memory.swap.max": "0", "memory.swap.current": "0", "memory.swap.peak": "0",
                "memory.events": {key: "0" for key in ("max", "oom", "oom_kill", "oom_group_kill")}}}}
        counts={key:100 for key in ("sourceNodes","sourceWays","sourceRelations","wayEligibleDirectedSegments","historyPrefixCeiling","candidateViaWayRules","roadStatesUpperBound","historyStatesUpperBound")}
        calibration={**measured(1000000000),"candidate":counts,"xmlByteIdentical":True,"fixtures":[{"graphAndAuditIdentical":True}]*6}
        built={**measured(2000000000),"roads":100,"states":100,"graphIdentity":"graph"}
        qualified={**measured(1000000000),"costComparisons":500,"boundedCostComparisons":4000,"interiorDestinationComparisons":2,"graphIdentity":"graph"}
        native={"costComparisons":4500,"membershipComparisons":4000,"interiorDestinationComparisons":2,"graphIdentity":"graph"}
        cuts={**measured(1000000000),"graphIdentity":"graph"}
        frontier={"envelopeContainedInParent":False,"clippedSides":["east"]}
        def run(c=counts, q=qualified, rebuild=measured(2500000000), p=measured(1000000000)):
            return evaluate(calibration,p,c,built,rebuild,q,native,cuts,frontier)
        result=run();self.assertTrue(result["cappedExperimentEligible"])
        self.assertEqual(result["wholeWorkloadEstimateWithHeadroomBytes"],3125000000)
        self.assertFalse(result["sourceEnvelopeContained"]);self.assertFalse(result["coverageVerified"])
        self.assertFalse(run(c={k:v*2 for k,v in counts.items()})["cappedExperimentEligible"])
        self.assertFalse(run(rebuild=measured(3800000000))["cappedExperimentEligible"])
        self.assertFalse(run(p=measured(3800000000))["cappedExperimentEligible"])
        self.assertFalse(run(q={**qualified,"costComparisons":0})["sourceAndOracleParity"])
        pressure=measured(1000000000);pressure["resourceCheckpoints"]["verified"]["memory.events"]["max"]="1"
        self.assertFalse(run(p=pressure)["cappedExperimentEligible"])
        swap=copy.deepcopy(pressure);swap["resourceCheckpoints"]["verified"]["memory.swap.max"]="1"
        with self.assertRaises(ValueError):run(p=swap)
