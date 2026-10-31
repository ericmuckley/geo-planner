import unittest

from coarse_backbone import Components, VertexProbes, component_summary, quantized_deltas, sections
from coarse_path_features import distance_km


class BackboneTests(unittest.TestCase):
    def test_endpoint_occurring_at_interior_splits_and_conserves_length(self):
        points = [[-100, 40], [-99.99, 40.01], [-99.98, 40]]
        nodes = {tuple(p): i for i, p in enumerate(points)}
        split = list(sections(points, nodes))
        self.assertEqual(split, [(0, 1, 0, 1), (1, 2, 1, 2)])
        self.assertAlmostEqual(sum(distance_km(points[a], points[b]) for a, b, _, _ in split),
                               distance_km(points[0], points[1]) + distance_km(points[1], points[2]))

    def test_near_coordinates_never_merge(self):
        points = [[-100, 40], [-99.99, 40], [-99.98, 40]]
        nodes = {tuple(points[0]): 0, (-99.99, 40.00000001): 1, tuple(points[-1]): 2}
        self.assertEqual(list(sections(points, nodes)), [(0, 2, 0, 2)])

    def test_geometric_crossing_without_shared_endpoint_does_not_join(self):
        a = [[-100, 40], [-99.98, 40.02]]
        b = [[-100, 40.02], [-99.98, 40]]
        nodes = {tuple(p): i for i, p in enumerate(a + b)}
        uf = Components(4)
        for points in [a, b]:
            for _, _, x, y in sections(points, nodes):
                uf.join(x, y)
        self.assertNotEqual(uf.find(0), uf.find(2))

    def test_closed_geometry_and_repeated_vertex_remain_separate_sections(self):
        points = [[0, 0], [1, 0], [1, 0], [0, 0]]
        self.assertEqual(list(sections(points, {(0, 0): 0, (1, 0): 1})),
                         [(0, 1, 0, 1), (1, 2, 1, 1), (2, 3, 1, 0)])

    def test_component_length_share_retains_small_components(self):
        uf = Components(4)
        uf.join(0, 1)
        uf.join(1, 2)
        uf.join(3, 3)
        result = component_summary(uf, [0, 1, 3], [1, 2, 3], [3., 6., 1.])
        self.assertEqual(result["components"], 2)
        self.assertEqual(result["largestRoadLengthFraction"], .9)
        self.assertEqual(result["roadKm"], 10)

    def test_storage_rounding_does_not_change_node_identity(self):
        points = [[-100., 40.], [-99.99999999, 40.]]
        self.assertEqual(len({tuple(p) for p in points}), 2)
        self.assertEqual(list(quantized_deltas(points)), [(-10000000, 4000000), (0, 0)])

    def test_vertex_radius_and_missing_denominators(self):
        probe = VertexProbes([[-100, 40], [-90, 40]])
        probe.consider([-100.001, 40], 7)
        self.assertEqual(probe.best[0]["node"], 7)
        self.assertIsNone(probe.best[1])
        probe.consider([-100, 40], 8)
        self.assertEqual(probe.best[0]["distanceKm"], 0)

    def test_probe_index_handles_bin_boundaries_and_high_latitudes(self):
        probe = VertexProbes([[-100.001, 49.99]])
        probe.consider([-99.95, 49.99], 3)
        self.assertIsNotNone(probe.best[0])


if __name__ == "__main__":
    unittest.main()
