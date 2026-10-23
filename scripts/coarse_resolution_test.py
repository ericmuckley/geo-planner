"""Resolution changes rebuild geometry; no source IO or producer runs."""

from array import array
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("resolution", Path(__file__).with_name("build-coarse-resolution.py"))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def rectangle(west, south, east, north):
    return [[west, south], [east, south], [east, north], [west, north], [west, south]]


class ResolutionTests(unittest.TestCase):
    def test_masks_recompute_centers_and_holes_at_each_resolution(self):
        polygon = [rectangle(0, 0, .2, .2), rectangle(.05, .05, .15, .15)]
        coarse = list(builder.rasterize(polygon, [0, 0, .2, .2], .1, 2, 2))
        fine = list(builder.rasterize(polygon, [0, 0, .2, .2], .05, 4, 4))
        self.assertEqual(coarse, [1, 2, 3])
        self.assertEqual(fine, [0, 1, 2, 3, 4, 7, 8, 11, 12, 13, 14, 15])
        finer = list(builder.rasterize(polygon, [0, 0, .2, .2], .025, 8, 8))
        self.assertEqual(len(finer), 48)

    def test_road_visits_rebuild_from_source_rather_than_upsample_labels(self):
        path = [[.001, .025], [.199, .025]]
        coarse = builder.v2.road_visits(path, [0, 0, .2, .1], .1, 2, lambda *_: None)
        fine = builder.v2.road_visits(path, [0, 0, .2, .1], .05, 4, lambda *_: None)
        self.assertEqual([v[0] for v in coarse], [0, 1])
        self.assertEqual([v[0] for v in fine], [0, 1, 2, 3])
        self.assertEqual(len(list(builder.augmentation.visit_edges(fine, 4))), 3)

    def test_fine_visit_packing_keeps_bends_and_actual_cell_offsets(self):
        path = [[.001, .01], [.025, .04], [.049, .01]]
        visit, = builder.v2.road_visits(path, [0, 0, .05, .05], .05, 1, lambda *_: None)
        p = builder.v2.visit_point(visit)
        delta = [round((v - .025) * 100000) for v in p]
        row = builder.visit_row(visit, 80, [.025, .025], delta, .05)
        self.assertIn([0, 1500], row["offsets"])
        self.assertEqual(row["offsets"][row["anchorIndex"]], delta)
        self.assertTrue(all(abs(v) <= 2501 for p in row["offsets"] for v in p))

    def test_fine_shore_connections_never_join_islands_across_a_channel(self):
        boundary = [[rectangle(.001, .001, .039, .049)], [rectangle(.061, .001, .099, .049)]]
        data = {"bounds": [0, 0, .1, .05], "step": .05, "width": 2, "height": 1,
                "boundary": boundary, "lakes": []}
        geography = builder.v3.Geography(boundary, [], 0, .05, 1)
        land, traversable, display, offsets = bytearray([0, 1]), bytearray([0, 1]), bytearray([0, 1]), array("h", [0] * 4)
        shores, added = builder.add_shores(data, land, traversable, display, offsets, geography)
        self.assertEqual(added, 1)
        self.assertEqual(list(shores), [0, 0])
        self.assertEqual(list(traversable), [1, 1])


if __name__ == "__main__":
    unittest.main()
