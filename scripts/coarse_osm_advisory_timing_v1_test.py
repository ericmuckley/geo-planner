"""Unit/scope boundaries for an estimated advisory cap, separate from legal speeds."""
from copy import deepcopy
import unittest

from coarse_osm_advisory_timing_v1 import estimated_speed


class Tests(unittest.TestCase):
    def test_units_match_existing_source_parser(self):
        self.assertEqual(estimated_speed({'maxspeed:advisory': '30'}, 90), (30, 'capped'))
        self.assertEqual(estimated_speed({'maxspeed:advisory': '30 km/h'}, 90), (30, 'capped'))
        self.assertAlmostEqual(estimated_speed({'maxspeed:advisory': '30 mph'}, 90)[0], 48.28032)

    def test_already_slower_estimate_never_increases(self):
        self.assertEqual(estimated_speed({'maxspeed:advisory': '55 mph'}, 40), (40, 'already-slower'))

    def test_unknown_or_invalid_values_leave_current_price(self):
        for value in ('', 'signals', 'none', '30;40', '0', '-1', '161', 'infinity', 'nan', 30):
            self.assertEqual(estimated_speed({'maxspeed:advisory': value}, 70), (70, 'invalid-unchanged'))
        self.assertEqual(estimated_speed({}, 70), (70, 'missing-unchanged'))

    def test_directional_conditional_and_other_scope_remain_unchanged(self):
        for key in ('forward', 'backward', 'conditional', 'hgv', 'lanes', 'unknown'):
            self.assertEqual(estimated_speed({'maxspeed:advisory': '20', 'maxspeed:advisory:'+key: '10'}, 70), (70, 'scoped-unchanged'))

    def test_original_legal_and_access_tags_are_read_only(self):
        tags = {'maxspeed': '55 mph', 'maxspeed:advisory': '30 mph', 'access': 'yes', 'surface': 'asphalt'}
        before = deepcopy(tags)
        estimated_speed(tags, 79.665984)
        self.assertEqual(tags, before)

    def test_current_directional_estimates_and_existing_ninety_percent_are_retained(self):
        tags = {'maxspeed:advisory': '30 mph'}
        self.assertAlmostEqual(estimated_speed(tags, 79.665984)[0], 48.28032)
        self.assertEqual(estimated_speed(tags, 40)[0], 40)
        self.assertEqual(estimated_speed({'maxspeed:advisory': '55 mph'}, 79.665984)[0], 79.665984)


if __name__ == '__main__':
    unittest.main()
