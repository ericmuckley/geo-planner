from pathlib import Path
import tempfile
import unittest

from coverage_census import census, directions
from coverage_preflight import assessment
from maneuver_graph_test import MODEL, osm
from stream_import import import_maneuvers


class CoverageCensusTests(unittest.TestCase):
    def test_way_directions_respect_access_speed_and_conservative_exclusions(self):
        self.assertEqual(directions({"highway": "motorway"}), 1)
        self.assertEqual(directions({"highway": "residential", "oneway": "-1"}), 1)
        self.assertEqual(directions({"highway": "residential", "motor_vehicle:backward": "no"}), 1)
        self.assertEqual(directions({"highway": "residential", "access": "no", "motorcar": "yes"}), 2)
        for extra in ({"maxspeed": "signals"}, {"maxspeed:backward": "0"}, {"service": "driveway"},
                      {"oneway": "alternating"}, {"access:conditional": "yes @ (Mo)"}, {"motor_vehicle:lanes": "yes|no"}):
            self.assertEqual(directions({"highway": "residential", **extra}), 0)

    def test_census_bounds_contain_frozen_model_with_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "roads.osm"
            source.write_text(osm())
            bounds = [-1, -1, 1, 1]
            graph, _ = import_maneuvers(source, bounds, MODEL)
            result = census(source, bounds, directory / "counts.sqlite")
            self.assertLessEqual(result["roadStatesLowerBound"], len(graph.base.roads))
            self.assertGreaterEqual(result["roadStatesUpperBound"], len(graph.base.roads))
            self.assertGreaterEqual(result["historyStatesUpperBound"], len(graph.states))
            self.assertGreater(result["candidateViaWayRules"], 0)
            with self.assertRaisesRegex(ValueError, "exists"):
                census(source, bounds, directory / "counts.sqlite")

    def test_only_complete_inside_segments_count_and_missing_references_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "roads.osm"
            source.write_text('<osm><node id="1" lon="0" lat="0"/><node id="2" lon="1" lat="0"/>'
                              '<node id="3" lon="2" lat="0"/><way id="5"><nd ref="1"/><nd ref="1"/>'
                              '<nd ref="2"/><nd ref="3"/><tag k="highway" v="residential"/></way></osm>')
            result = census(source, [0, -1, 1, 1], directory / "counts.sqlite")
            self.assertEqual(result["supportedPhysicalSegmentsInside"], 1)
            self.assertEqual(result["roadStatesUpperBound"], 2)
            self.assertEqual(result["supportedBoundarySegments"], 1)
            source.write_text(source.read_text().replace('<node id="3" lon="2" lat="0"/>', ''))
            with self.assertRaisesRegex(ValueError, "Missing node"):
                census(source, [0, -1, 1, 1], directory / "missing.sqlite")

    def test_capacity_gate_uses_larger_peak_and_measured_counts_with_headroom(self):
        calibration = {"sourceNodes": 10, "sourceWays": 5, "wayEligibleDirectedSegments": 20}
        candidate = {"sourceNodes": 20, "sourceWays": 5, "wayEligibleDirectedSegments": 30}
        def measured(peak):
            return {"resourceCheckpoints": {"complete": {"workerMaxRssKiB": 100, "memory.peak": str(peak)}}}
        result = assessment(candidate, calibration, measured(200), measured(300), {"admissionHeadroomFactor": 1.25, "memoryLimitBytes": 700})
        self.assertEqual(result["admissionEstimateBytes"], 750)
        self.assertEqual(result["decision"], "hold-for-compact-storage")
        self.assertEqual(result["scalingRatio"], 2)


if __name__ == "__main__":
    unittest.main()
