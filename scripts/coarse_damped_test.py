"""Small cost-policy fixtures, independent of source files or routing services."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("damped", Path(__file__).with_name("build-coarse-damped.py"))
calibration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calibration)


class DampedCosts(unittest.TestCase):
    def test_changes_are_smaller_in_both_directions(self):
        self.assertLess(calibration.price(100, 0, 100, True), calibration.price(100, 0, 95, True))
        self.assertGreater(calibration.price(100, 0, 82, True), calibration.price(100, 0, 85, True))

    def test_census_local_cost_does_not_change_with_road_class(self):
        self.assertEqual(calibration.price(0, 25 / 60, 100, False), 600)
        self.assertEqual(calibration.price(0, 25 / 60, 82, False), 600)

    def test_source_costs_keep_local_time(self):
        # One minute on the road plus one minute of fixed local transfer.
        self.assertEqual(calibration.price(100 / 60, 25 / 60, 100, False), 1200)
        self.assertEqual(calibration.price(82 / 60, 25 / 60, 82, False), 1200)

    def test_legacy_connectors_follow_road_class(self):
        self.assertEqual(calibration.price(100 / 60, 100 / 60, 100, True), 1200)
        self.assertGreater(calibration.price(1, 1, 100, False), calibration.price(1, 1, 100, True))

    def test_policy_preserves_class_order_and_ties(self):
        self.assertEqual([calibration.SPEED_MAPPING[x] for x in [55, 80, 90, 105]], [55, 82, 90, 100])

    def test_encoding_limit_is_not_silently_saturated(self):
        with self.assertRaises(AssertionError):
            calibration.price(100, 25, 100, False)


if __name__ == "__main__":
    unittest.main()
