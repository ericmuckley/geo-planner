from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from crossing_audit import barrier_examples, route_evidence, source_uncertainties, uncertainty_reason
from maneuver_graph import build_maneuver_graph, source_seeds
from maneuver_graph_test import road
from state_graph import build_graph, dijkstra
from regional_support import route_to_interior


class CrossingAuditTests(unittest.TestCase):
    def test_explicit_hint_requires_crossing_and_access_context(self):
        self.assertIsNotNone(uncertainty_reason({"fixme": "Unsure on BORDER CHECKPOINT barrier and ACCESS"}))
        for props in ({"fixme": "Missing name"}, {"hgv": "designated"}, {"access": "yes"}, {"fixme": "border name unknown"}):
            self.assertIsNone(uncertainty_reason(props))

    def test_source_excerpt_retains_original_way_tags_and_all_references(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / "source.osm", Path(temporary) / "excerpt.osm"
            source.write_text('''<osm><node id="1" lon="0" lat="0"/><node id="2" lon="1" lat="0"/>
            <way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="service"/>
            <tag k="fixme" v="border checkpoint access unknown"/></way>
            <way id="20"><nd ref="2"/><tag k="fixme" v="Missing name"/></way></osm>''')
            before = source.read_bytes()
            rows = source_uncertainties(source, output)
            self.assertEqual([row["id"] for row in rows], [10])
            root = ET.parse(output).getroot()
            self.assertEqual([node.get("id") for node in root.findall("node")], ["1", "2"])
            self.assertEqual(root.find("way").get("id"), "10")
            self.assertEqual(source.read_bytes(), before)

    def test_partial_route_cost_and_warning_do_not_change_legal_graph(self):
        base = build_graph([{**road("a", 1, 2, 10), "way": 10}, {**road("b", 2, 3, 20), "way": 20}])
        graph = build_maneuver_graph(base, [])
        starts = [(0, Fraction(1, 2))]
        seeds = source_seeds(graph, starts)
        labels = dijkstra(graph.adjacency, seeds).labels
        route = {**route_to_interior(graph, labels, seeds, starts, 1, Fraction(1, 2)), "targetRoadId": "b", "targetFraction": "1/2"}
        evidence = route_evidence(graph, {"seeds": seeds}, route, [{"id": 20}], {2})
        self.assertEqual(evidence["recomputedCostMs"], 15)
        self.assertEqual(evidence["sourceUncertaintyWayIds"], [20])
        self.assertEqual(evidence["qualifiedStaticBarrierNodesTraversed"], [2])
        self.assertFalse(evidence["carEligibilityVerified"])
        self.assertFalse(route_evidence(graph, {"seeds": seeds}, route, [], set())["carEligibilityVerified"])
        with self.assertRaises(ValueError): route_evidence(graph, {"seeds": seeds}, {**route, "costMs": 16}, [], set())
        with self.assertRaises(ValueError): route_evidence(graph, {"seeds": seeds}, {**route, "roadIds": ["a"]}, [], set())

    def test_closed_barrier_evidence_preserves_prohibited_through_direction(self):
        base = build_graph([road("a", 1, 2, 10), road("b", 2, 3, 10)], blocked_nodes={2})
        graph = build_maneuver_graph(base, [])
        audit = {"barrierPolicy": {"decisions": [{"id": 2, "blockedByModel": True}]}}
        rows = barrier_examples(graph, audit, {2})
        self.assertFalse(rows[0]["transitions"][0]["allowed"])
        self.assertFalse(rows[0]["transitions"][0]["uTurn"])


if __name__ == "__main__": unittest.main()
