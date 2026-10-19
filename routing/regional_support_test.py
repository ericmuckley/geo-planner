from fractions import Fraction
import math
from pathlib import Path
import shutil
import tempfile
import unittest

from anchors import file_hash, save_json
from import_maneuvers import import_maneuvers
from maneuver_graph_test import MODEL, network, osm
from regional_support import cached_extract, check_bounds, route_to_interior, snap_attachments, supported_xml
from state_graph import dijkstra


class RegionalSupportTests(unittest.TestCase):
    def test_bounds_cannot_exceed_downloaded_source(self):
        check_bounds([-2, -1, 2, 1], [-3, -2, 3, 2])
        for bounds in ([2, -1, -2, 1], [-4, -1, 2, 1], [-2, -1, 2, 3], [0, 1]):
            with self.assertRaises(ValueError): check_bounds(bounds, [-3, -2, 3, 2])

    def test_cache_requires_source_bounds_image_and_both_checksums(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            (cache / "roads.osm").write_bytes(b"xml")
            (cache / "region.osm.pbf").write_bytes(b"pbf")
            source, bounds = {"bytes": 4, "sha256": "source"}, [-2, -1, 2, 1]
            save_json(cache / "preparation.json", {"source": source, "bbox": bounds, "xmlBytes": 3, "xmlSha256": file_hash(cache / "roads.osm"),
                      "pbfBytes": 3, "pbfSha256": file_hash(cache / "region.osm.pbf")})
            save_json(cache / "extract.json", {"identity": {"source": source, "bbox": bounds, "imageId": "image",
                      "strategy": "smart; types=restriction,restriction:motorcar,restriction:motor_vehicle,restriction:vehicle"}})
            self.assertEqual(cached_extract(cache, source, bounds, "image")[0], cache / "roads.osm")
            with self.assertRaises(ValueError): cached_extract(cache, source, bounds, "other")
            (cache / "region.osm.pbf").write_bytes(b"bad")
            with self.assertRaisesRegex(ValueError, "checksum"): cached_extract(cache, source, bounds, "image")

    def test_tight_route_uses_legal_detour_for_interior_target(self):
        graph = network()
        starts, seeds = [(0, Fraction(1, 2))], [(graph.initial_states[0], 5)]
        labels = dijkstra(graph.adjacency, seeds).labels
        route = route_to_interior(graph, labels, seeds, starts, 2, Fraction(1, 2))
        self.assertEqual(route["costMs"], 46)
        self.assertEqual(route["roadIds"], ["a", "b", "exit", "return", "b", "c"])
        for left, right in zip(route["states"], route["states"][1:]):
            self.assertIn(right, [target for target, _ in graph.adjacency[left]])

    def test_unreachable_and_direct_same_road_routes(self):
        graph = network(detour=False)
        starts, seeds = [(0, Fraction(1, 3))], [(graph.initial_states[0], 7)]
        labels = dijkstra(graph.adjacency, seeds).labels
        self.assertIsNone(route_to_interior(graph, labels, seeds, starts, 2, Fraction(1, 2))["costMs"])
        route = route_to_interior(graph, labels, seeds, starts, 0, Fraction(2, 3))
        self.assertEqual(route["costMs"], 4)
        self.assertTrue(route["directSameRoad"])

    def test_source_projection_preserves_partial_costs_and_snap_cutoff(self):
        graph = network()
        for road in graph.base.roads:
            road.update({"fromPoint": [road["from"] / 10000, 0], "toPoint": [road["to"] / 10000, 0]})
        starts, seeds, snap = snap_attachments(graph, [.00005, 0], 100)
        self.assertEqual(starts, [(0, Fraction(1, 2))])
        self.assertEqual(seeds, [(graph.initial_states[0], 5)])
        self.assertEqual(snap["distanceMeters"], 0)
        with self.assertRaises(ValueError): snap_attachments(graph, [10, 10], 100)


@unittest.skipUnless(shutil.which("osmium"), "Osmium integration runs in the cached Docker tools image")
class RegionalFilterTests(unittest.TestCase):
    def test_filter_preserves_restriction_references_and_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            source = output / "input.osm"
            source.write_text(osm().replace('<osm>', '<osm version="0.6">'))
            before, _ = import_maneuvers(source, [-1, -1, 1, 1], MODEL)
            filtered = supported_xml(source, output, "test-image")
            after, _ = import_maneuvers(filtered, [-1, -1, 1, 1], MODEL)
            self.assertEqual(before.identity, after.identity)
            self.assertEqual(filtered, supported_xml(source, output, "test-image"))
            filtered.write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "checksum"): supported_xml(source, output, "test-image")

    def test_frozen_real_downtown_graph_survives_filter_unchanged(self):
        reference = Path("/reference/roads.osm")
        if not reference.exists(): self.skipTest("Frozen reference is mounted in Docker")
        with tempfile.TemporaryDirectory() as temporary:
            filtered = supported_xml(reference, Path(temporary), "test-image")
            graph, _ = import_maneuvers(filtered, [-117.18, 32.70, -117.13, 32.74], MODEL)
            self.assertEqual(graph.identity, "11f122d0a182984228629f64f97bd4cd2bca462fc9cb0af1d8c209ef0df854ef")


if __name__ == "__main__":
    unittest.main()
