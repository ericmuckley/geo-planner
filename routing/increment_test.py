import unittest

from increment import check_counts


class IncrementAdmissionTests(unittest.TestCase):
    def test_built_counts_must_fit_measured_interval_and_history_ceiling(self):
        census = {"roadStatesLowerBound": 100, "roadStatesUpperBound": 120, "historyStatesUpperBound": 125}
        check_counts(100, 100, census)
        check_counts(120, 125, census)
        for roads, states in ((99, 105), (121, 121), (100, 99), (120, 126)):
            with self.subTest(roads=roads, states=states), self.assertRaises(ValueError):
                check_counts(roads, states, census)
