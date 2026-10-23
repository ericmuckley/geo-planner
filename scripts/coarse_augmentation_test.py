"""Physical/topology fixtures for the offline augmentation, without source IO."""

import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import unittest

from coarse_census import part_key, shape_parts

spec = importlib.util.spec_from_file_location("augmentation", Path(__file__).with_name("build-coarse-augmentation.py"))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def rectangle(west, east, south=0, north=.2):
    return [[[west, south], [east, south], [east, north], [west, north], [west, south]]]


class AugmentationTests(unittest.TestCase):
    def test_both_transfers_pay_local_speed_and_road_bend_pays_class_speed(self):
        geography = builder.v3.Geography([rectangle(0, .4)], [], 0, .1, 2)
        a, b, pa, pb = [.02, .02], [.28, .02], [.02, .08], [.28, .08]
        bend = [.15, .15]
        road_km = sum(builder.v4.v2.distance_km(x, y) for x, y in [(pa, bend), (bend, pb)])
        cost, local_km = builder.charged_edge(a, b, pa, pb, road_km, 80, geography)
        self.assertEqual(cost, math.ceil((local_km / 25 + road_km / 80) * 36000))
        self.assertGreater(cost, math.ceil((local_km + road_km) / 80 * 36000))
        self.assertEqual((cost, local_km), builder.charged_edge(b, a, pb, pa, road_km, 80, geography))

    def test_land_transfer_cannot_cross_narrow_lake_or_separate_islands(self):
        a, b, pa, pb = [.02, .02], [.28, .02], [.02, .08], [.28, .08]
        lake = builder.v3.Geography([rectangle(0, .4)], [rectangle(0, .1, .0499, .0501)], 0, .1, 2)
        islands = builder.v3.Geography([rectangle(0, .1, 0, .04), rectangle(0, .1, .06, .2), rectangle(.2, .4)], [], 0, .1, 2)
        for geography in [lake, islands]:
            self.assertIsNone(builder.charged_edge(a, b, pa, pb, 30, 80, geography))

    def test_explicit_road_arc_can_cross_water_with_checked_land_transfers(self):
        geography = builder.v3.Geography([rectangle(0, .1), rectangle(.2, .4)], [], 0, .1, 2)
        a, b, pa, pb = [.02, .02], [.28, .02], [.02, .08], [.28, .08]
        road_km = builder.v4.v2.distance_km(pa, pb)
        self.assertIsNotNone(builder.charged_edge(a, b, pa, pb, road_km, 80, geography))

    def test_multipart_sections_never_invent_a_connecting_road(self):
        shape = SimpleNamespace(parts=[0, 2], points=[[.01, .01], [.09, .01], [.11, .01], [.19, .01]])
        parts = shape_parts(shape)
        self.assertEqual([len(part) for part in parts], [2, 2])
        visits = [builder.v4.v2.road_visits(part, [0, 0, .2, .1], .1, 2, lambda *_: None) for part in parts]
        self.assertEqual([[v[0] for v in group] for group in visits], [[0], [1]])

    def test_exact_partition_dedup_respects_class_and_bends(self):
        a = {"id": "one", "class": "S1100", "points": [[0, 0], [.1, .01], [.2, 0]]}
        b = {**a, "id": "different", "points": list(reversed(a["points"]))}
        self.assertEqual(part_key(a), part_key(b))
        self.assertNotEqual(part_key(a), part_key({**a, "class": "S1200"}))
        self.assertNotEqual(part_key(a), part_key({**a, "points": [[0, 0], [.2, 0]]}))

    def test_partition_seams_share_paid_canonical_cells(self):
        path = [[.025, .05], [.15, .05], [.275, .05]]
        raster = lambda p: builder.v4.v2.road_visits(p, [0, 0, .3, .1], .1, 3, lambda *_: None)
        full = {key for key, _, _ in builder.visit_edges(raster(path), 3)}
        split = [path[:2], path[1:]]
        edges = [edge for part in split for edge in builder.visit_edges(raster(part), 3)]
        self.assertEqual({key for key, _, _ in edges}, full)
        geography = builder.v3.Geography([rectangle(0, .3)], [], 0, .1, 1)
        for _, a, b in edges:
            anchor_a = [a[0] * .1 + .05, .05]
            anchor_b = [b[0] * .1 + .05, .05]
            road_km = (b[1] + b[2] - a[1] - a[2]) / 2
            result = builder.charged_edge(anchor_a, anchor_b, builder.v4.v2.visit_point(a),
                                          builder.v4.v2.visit_point(b), road_km, 80, geography)
            self.assertIsNotNone(result)
            self.assertGreater(result[0], 0)
            self.assertGreater(result[1], 0)  # A source partition never gets a free anchor transfer.

    def test_interpolated_midpoint_arc_has_a_physical_lower_bound(self):
        a = [0, 0, 0, [(0, [.01, .05])]]
        b = [1, 0, 0, [(0, [.19, .05])]]
        chord = builder.v4.v2.distance_km(a[3][0][1], b[3][0][1])
        b[1] = b[2] = chord - .00001
        self.assertEqual(builder.bounded_arc_km(a, b), chord)
        b[1] = b[2] = chord + 2
        self.assertEqual(builder.bounded_arc_km(a, b), chord + 2)


if __name__ == "__main__":
    unittest.main()
