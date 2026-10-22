"""Small geometry fixtures; no source download or routing service required."""

import importlib.util
import math
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("builder", Path(__file__).with_name("build-coarse-grid-v2.py"))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
shore_spec = importlib.util.spec_from_file_location("shore_builder", Path(__file__).with_name("build-coarse-grid-v3.py"))
shore_builder = importlib.util.module_from_spec(shore_spec)
shore_spec.loader.exec_module(shore_builder)


class RoadGeometryTests(unittest.TestCase):
    def test_bend_uses_road_distance_instead_of_endpoint_chord(self):
        path = [[0.025, 0.025], [0.025, 0.075], [0.175, 0.075]]
        visits = builder.road_visits(path, [0, 0, 0.2, 0.1], 0.1, 2, lambda *_: None)
        measured = visits[-1][2]
        expected = sum(builder.distance_km(a, b) for a, b in zip(path, path[1:]))
        self.assertAlmostEqual(measured, expected, places=5)
        self.assertGreater(measured, builder.distance_km(path[0], path[-1]))
        reverse = builder.road_visits(list(reversed(path)), [0, 0, 0.2, 0.1], 0.1, 2, lambda *_: None)
        self.assertAlmostEqual(reverse[-1][2], measured, places=5)

    def test_cell_transfer_pays_for_both_connectors(self):
        a, b = [0.02, 0.02], [0.18, 0.02]
        pa, pb = [0.02, 0.08], [0.18, 0.08]
        road_km = builder.distance_km(pa, pb)
        expected_km = builder.distance_km(a, pa) + road_km + builder.distance_km(pb, b)
        time = builder.road_time(a, b, pa, pb, road_km, 105)
        self.assertEqual(time, math.ceil(expected_km / 105 * 36000))
        self.assertGreater(time, math.ceil(road_km / 105 * 36000))
        self.assertEqual(time, builder.road_time(b, a, pb, pa, road_km, 105))

    def test_boundary_holes_are_not_land(self):
        outer = [[0, 0], [0.3, 0], [0.3, 0.3], [0, 0.3], [0, 0]]
        hole = [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2], [0.1, 0.1]]
        edges = builder.edge_rows([[outer, hole]], 0, 0.1, 3)
        self.assertTrue(builder.contains([0.05, 0.15], edges[1]))
        self.assertFalse(builder.contains([0.15, 0.15], edges[1]))
        self.assertFalse(builder.contains([0.35, 0.15], edges[1]))


class ShoreGeometryTests(unittest.TestCase):
    @staticmethod
    def rectangle(west, east, south=0, north=.1):
        return [[[west, south], [east, south], [east, north], [west, north], [west, south]]]

    def test_narrow_water_channel_cannot_hide_between_samples(self):
        geometry = shore_builder.Geography([self.rectangle(0, .3)], [self.rectangle(.1499, .1501)], 0, .1, 1)
        self.assertFalse(geometry.land_segment([.05, .05], [.25, .05]))
        self.assertTrue(geometry.land_segment([.05, .05], [.14, .05]))

    def test_mixed_shore_connection_is_symmetric(self):
        geometry = shore_builder.Geography([self.rectangle(0, .3)], [self.rectangle(.1, .2, 0, .08)], 0, .1, 1)
        a, b = [.05, .09], [.15, .09]
        self.assertTrue(geometry.land_segment(a, b))
        self.assertTrue(geometry.land_segment(b, a))
        self.assertFalse(geometry.land_segment([.05, .05], [.15, .05]))

    def test_diagonal_corner_contact_does_not_connect_separate_islands(self):
        geometry = shore_builder.Geography([self.rectangle(0, .1), self.rectangle(.1, .2, .1, .2)], [], 0, .1, 2)
        self.assertFalse(geometry.land_segment([.05, .05], [.15, .15]))


if __name__ == "__main__":
    unittest.main()
