"""Directional identity and frozen-path controls for the external default table."""
import unittest

from coarse_osm_default_timing_v1 import CURRENT_DEFAULTS, PUBLISHED_DEFAULTS, ROLES, continuous_path_ticks, estimated_way


class Controls(unittest.TestCase):
    def test_every_role_and_direction_uses_only_default_bits(self):
        for role_index, role in enumerate(ROLES):
            for flags in (3, 7, 11, 15):
                speeds = [CURRENT_DEFAULTS[role] if flags & (1 << (i + 2)) else 27.5 + i for i in range(2)]
                row = (10, *speeds, flags | (role_index << 4), 9)
                result = estimated_way(row)
                self.assertEqual(result[0], row[0]); self.assertEqual(result[3:], row[3:])
                for i in range(2):
                    self.assertEqual(result[i+1], PUBLISHED_DEFAULTS[role] if flags & (1 << (i+2)) else speeds[i])
                self.assertEqual(row[1:3], tuple(speeds))
    def test_forbidden_direction_stays_zero(self):
        self.assertEqual(estimated_way((1, 0., 55., (4 << 4) | 2 | 8, 5)), (1, 0., 65, (4 << 4) | 2 | 8, 5))
    def test_forged_defaults_and_unknown_role_rejected(self):
        for row in ((1, 51., 0., 5, 0), (1, 100., 0., 1 | (15 << 4), 0), (1, 0., 0., 1, 0), (1, float('nan'), 0., 1, 0)):
            with self.assertRaises(AssertionError): estimated_way(row)
    def test_nonroad_and_explicit_components_remain(self):
        parts = dict(roadTravelTicks=600, initialTicks=30, signalTicks=20, gridTravelTicks=50)
        groups = {'primary/default': dict(ticks=300, speedMinKph=55, speedMaxKph=55), 'motorway/tagged': dict(ticks=300, speedMinKph=93.5, speedMaxKph=93.5)}
        self.assertAlmostEqual(continuous_path_ticks(parts, groups), 100 + 300 + 300*55/65)
        self.assertEqual(parts['roadTravelTicks'], 600)
    def test_empty_road_local_path_is_unchanged(self):
        self.assertEqual(continuous_path_ticks(dict(roadTravelTicks=0, gridTravelTicks=72), {}), 72)
    def test_unknown_and_inconsistent_source_groups_stop(self):
        for group in ({'primary/default':dict(ticks=10,speedMinKph=50,speedMaxKph=55)}, {'road/tagged':dict(ticks=10,speedMinKph=30,speedMaxKph=30)}, {}):
            with self.assertRaises(AssertionError): continuous_path_ticks(dict(roadTravelTicks=10), group)


if __name__ == '__main__': unittest.main()
