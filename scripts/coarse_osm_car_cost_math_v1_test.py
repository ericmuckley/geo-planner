"""Exact integer-ms comparisons with the frozen Python distance/cost convention."""
from array import array
import math
import random
import unittest

from import_roads import distance_m
from coarse_osm_car_codec_v1 import ticks
from coarse_osm_car_cost_math_v1 import NativeCosts
from coarse_timing_input import PilotError

ARTIFACT = None
MAXIMUM = (2**32-1)*125


def reference(xy, speed, same=False):
    return 0 if same else max(1, math.ceil(distance_m([xy[0]/1e7, xy[1]/1e7], [xy[2]/1e7, xy[3]/1e7])*3600/speed))


class Tests(unittest.TestCase):
    def setUp(self):
        if ARTIFACT is None:
            self.skipTest('Protected compiled native cost artifact required')
        self.native = NativeCosts(*ARTIFACT)

    def batch(self, records):
        xy = array('i');speeds = array('d');same = bytearray()
        for points, speed, equal in records:
            xy.extend(points);speeds.append(speed);same.append(equal)
        return list(self.native.costs(xy, speeds, same))

    def test_repeat_identity_and_distinct_coincident_nodes(self):
        self.assertEqual(self.batch([([0, 0, 0, 0], 50, 1), ([0, 0, 0, 0], 50, 0)]), [0, 1])

    def test_seeded_global_and_short_coordinate_pairs(self):
        rng = random.Random(20261101);records = []
        for _ in range(10000):
            x, y = rng.randrange(-1800000000, 1800000001), rng.randrange(-900000000, 900000001)
            a, b = (rng.randrange(-1800000000, 1800000001), rng.randrange(-900000000, 900000001)) if rng.randrange(2) else (max(-1800000000, min(1800000000, x+rng.randrange(-10000, 10001))), max(-900000000, min(900000000, y+rng.randrange(-10000, 10001))))
            records.append(([x, y, a, b], rng.choice([30., 40., 55., 85., 100., 160., 55*1.609344]), 0))
        self.assertEqual(self.batch(records), [reference(*row) for row in records])

    def test_poles_antipodes_dateline_and_coordinate_extremes(self):
        pairs = ([0, 0, 1800000000, 0], [-1800000000, 0, 1800000000, 0],
                 [0, -900000000, 0, 900000000], [-1800000000, 900000000, 1800000000, 900000000], [1, 1, 2, 2])
        rows = [(p, 50., 0) for p in pairs]
        self.assertEqual(self.batch(rows), [reference(*row) for row in rows])

    def test_same_native_id_with_conflicting_coordinates_rejects(self):
        with self.assertRaises(PilotError):
            self.batch([([0, 0, 1, 0], 50., 1)])

    def test_coordinate_and_flag_ranges_reject(self):
        for xy in ([1800000001, 0, 0, 0], [0, 900000001, 0, 0], [0, 0, -1800000001, 0], [0, 0, 0, -900000001]):
            with self.assertRaises(PilotError):
                self.batch([(xy, 50., 0)])
        with self.assertRaises(PilotError):
            self.batch([([0, 0, 0, 0], 50., 2)])

    def test_invalid_speed_and_cost_overflow_reject(self):
        for speed in (0., -1., 160.1, math.inf, math.nan, 5e-324):
            with self.assertRaises(PilotError):
                self.batch([([0, 0, 10000000, 0], speed, 0)])

    def test_full_geometry_sum_preserves_hairpin_cost(self):
        rows = [([0, 0, 10000000, 10000000], 50., 0), ([10000000, 10000000, 0, 1], 50., 0)]
        costs = self.batch(rows);total = sum(reference(*row) for row in rows)
        self.assertEqual(self.native.sum(costs), (total, ticks(total)))
        self.assertGreater(total, 1000*reference([0, 0, 0, 1], 50.))

    def test_upward_ticks_sentinel_and_unsigned32_boundary(self):
        for value in (0, 1, 124, 125, 126, 65534*125, 65535*125, 65535*125+1, MAXIMUM-1, MAXIMUM):
            self.assertEqual(self.native.sum([value]), (value, ticks(value)))
        self.assertEqual(self.native.sum([]), (0, 0))

    def test_checked_sums_reject_overflow_and_invalid_values(self):
        for values in ([MAXIMUM, 1], [MAXIMUM+1], [-1], [True], [2**64]):
            with self.assertRaises(PilotError):
                self.native.sum(values)

    def test_typed_batch_shape_and_empty_input(self):
        self.assertEqual(self.batch([]), [])
        for xy, speed, same in ((array('i', [0]), array('d'), bytearray()),
                                (array('i'), array('f'), bytearray()), (array('i', [0]*4), array('d', [50.]), bytearray())):
            with self.assertRaises(PilotError):
                self.native.costs(xy, speed, same)
