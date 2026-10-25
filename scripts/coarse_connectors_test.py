"""Connector/source prices are separate and independent of fixture locations."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("connectors", Path(__file__).with_name("build-coarse-connectors.py"))
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


class ConnectorPrices(unittest.TestCase):
    def test_road_and_ne_connection_each_charge_one_minute(self):
        self.assertEqual(model.price(105/60, 55/60, 105, True), 1200)
        self.assertEqual(model.price(85/60, 55/60, 85, True), 1200)

    def test_ne_connection_price_does_not_follow_road_class(self):
        self.assertEqual(model.price(0, 55/60, 105, True), 600)
        self.assertEqual(model.price(0, 55/60, 85, True), 600)

    def test_census_connections_remain_local25(self):
        self.assertEqual(model.price(105/60, 25/60, 105, False), 1200)
        self.assertEqual(model.price(85/60, 25/60, 85, False), 1200)

    def test_minor55_ne_cost_has_no_special_change(self):
        self.assertEqual(model.price(55/60, 55/60, 55, True), 1200)

    def test_road_classes_keep_order_and_major_speed(self):
        self.assertEqual([model.SPEED_MAPPING[s] for s in [55,80,90,105]], [55,85,90,105])

    def test_positive_encoding_and_no_silent_saturation(self):
        self.assertEqual(model.price(0,0,105,True), 1)
        with self.assertRaises(AssertionError):
            model.price(105,105,105,True)


if __name__ == "__main__":
    unittest.main()
