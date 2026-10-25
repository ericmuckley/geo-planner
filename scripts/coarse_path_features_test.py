"""Geometry/proximity invariants without graph, reference or service inputs."""
import unittest
from coarse_path_features import CorridorIndex, corridor_fraction, distance_km, polyline_samples, segment_distance_km


class PathFeatures(unittest.TestCase):
    def test_distance_is_symmetric_and_known_scale(self):
        self.assertAlmostEqual(distance_km([0, 0], [1, 0]), 111.19492664455873)
        self.assertEqual(distance_km([-117, 33], [-117, 33]), 0)
        self.assertEqual(distance_km([-117, 33], [-118, 34]), distance_km([-118, 34], [-117, 33]))

    def test_sampling_weights_preserve_length_and_reject_zero_step(self):
        points = [[-117, 33], [-117, 33], [-116.9, 33], [-116.9, 33.1]]
        samples = list(polyline_samples(points))
        self.assertAlmostEqual(sum(w for _, w in samples), sum(distance_km(a, b) for a, b in zip(points, points[1:])))
        self.assertTrue(all(0 < w <= 1 for _, w in samples))
        with self.assertRaises(AssertionError):
            list(polyline_samples(points, 0))

    def test_nearest_segment_checks_interior_not_just_vertices(self):
        a, b, p = [-117, 33], [-116, 33], [-116.5, 33]
        self.assertEqual(segment_distance_km(p, a, b), 0)
        self.assertTrue(CorridorIndex([a, b]).within(p, .01))

    def test_degenerate_segment_and_clamped_endpoint(self):
        a, b = [-117, 33], [-116.9, 33]
        self.assertEqual(segment_distance_km(a, a, a), 0)
        self.assertAlmostEqual(segment_distance_km([-117.1, 33], a, b), distance_km([-117.1, 33], a))

    def test_index_agrees_with_brute_force_at_bins_and_high_latitude(self):
        points = [[-117.15, 49], [-117.05, 49.05], [-116.95, 48.95]]
        index = CorridorIndex(points)
        for x in range(-8, 9):
            for y in range(-5, 6):
                p = [-117.05+x*.0125, 49+y*.0125]
                brute = any(segment_distance_km(p, a, b) <= 3 for a, b in zip(points, points[1:]))
                self.assertEqual(index.within(p, 3), brute)

    def test_unmatched_parallel_and_length_weighted_sensitivity(self):
        index = CorridorIndex([[-117, 33], [-116.9, 33]])
        samples = [([-116.95, 33], 1), ([-116.95, 33.1], 3)]
        self.assertEqual(corridor_fraction(samples, index, 1), .25)
        self.assertIsNone(corridor_fraction([], index, 1))
        self.assertFalse(index.within([-115, 33], 3))

    def test_sampling_a_coincident_polyline_has_full_membership(self):
        points = [[-117, 33], [-116.95, 33.03], [-116.9, 33.05]]
        self.assertEqual(corridor_fraction(list(polyline_samples(points)), CorridorIndex(points), .001), 1)


if __name__ == "__main__":
    unittest.main()
