"""Small cost-policy fixtures, independent of source files or routing services."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("calibration", Path(__file__).with_name("build-coarse-calibration.py"))
calibration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calibration)


class CalibrationCosts(unittest.TestCase):
    def test_census_local_cost_does_not_change_with_road_class(self):
        self.assertEqual(calibration.price(0, 25 / 60, 95, False), 600)
        self.assertEqual(calibration.price(0, 25 / 60, 85, False), 600)

    def test_source_costs_keep_local_time(self):
        # One minute on the road plus one minute of fixed local transfer.
        self.assertEqual(calibration.price(95 / 60, 25 / 60, 95, False), 1200)
        self.assertEqual(calibration.price(85 / 60, 25 / 60, 85, False), 1200)

    def test_legacy_connectors_follow_road_class(self):
        self.assertEqual(calibration.price(95 / 60, 95 / 60, 95, True), 1200)
        self.assertGreater(calibration.price(1, 1, 95, False), calibration.price(1, 1, 95, True))

    def test_policy_preserves_class_order_and_ties(self):
        self.assertEqual([calibration.SPEED_MAPPING[x] for x in [55, 80, 90, 105]], [55, 85, 90, 95])

    def test_encoding_limit_is_not_silently_saturated(self):
        with self.assertRaises(AssertionError):
            calibration.price(95, 25, 95, False)


if __name__ == "__main__":
    unittest.main()
