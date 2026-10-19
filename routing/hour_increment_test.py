import unittest

from hour_increment import candidate_profile


class HourProfileTests(unittest.TestCase):
    def test_extension_preserves_costs_origins_budgets_and_old_profile(self):
        old = {"id": "old", "bbox": [-2, -2, 2, 2], "model": {"id": "v3", "signalPenaltyMs": 5000},
               "origins": [{"id": "source"}], "budgetsMs": [3600000, 43200000]}
        prepared = {"profile": {"bbox": [-2, -3, 3, 2], "model": "v3"}}
        actual = candidate_profile(old, prepared)
        self.assertEqual(actual, {**old, "id": "san-diego-baja-hour-v3", "bbox": [-2, -3, 3, 2]})
        self.assertEqual(old["bbox"], [-2, -2, 2, 2])
        with self.assertRaises(ValueError):
            candidate_profile(old, {"profile": {"bbox": [-2, -3, 3, 2], "model": "different"}})
        with self.assertRaises(ValueError):
            candidate_profile(old, {"profile": {"bbox": [-1, -3, 3, 2], "model": "v3"}})
