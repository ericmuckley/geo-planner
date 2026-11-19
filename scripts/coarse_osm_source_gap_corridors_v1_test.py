import unittest

from coarse_backbone_paths import MultiCorridorIndex
from coarse_osm_source_gap_corridors_v1 import exposure


class SourceGapCorridorTests(unittest.TestCase):
    def test_only_the_uncovered_reference_weight_enters_the_gap_counter(self):
        result = exposure([([0., 0.], 2.), ([.1, 0.], 3.)],
                          MultiCorridorIndex([[[-.01, 0.], [.01, 0.]]]),
                          {'base': MultiCorridorIndex([[[.09, 0.], [.11, 0.]]]), 'closed': MultiCorridorIndex([])})
        self.assertEqual(result['referenceSampleKm'], 5.)
        self.assertEqual(result['referenceOutsideWinner1Km'], 3.)
        self.assertEqual(result['outsideWinner1KmNearExcludedKm']['base']['0.1'], 3.)
        self.assertEqual(result['outsideWinner1KmNearExcludedKm']['closed']['1'], 0.)

    def test_parallel_or_overlapping_exclusions_do_not_double_count_or_assign_identity(self):
        line = [[-.01, 0.], [.11, 0.]]
        result = exposure([([0., 0.], 2.), ([.1, 0.], 3.)], MultiCorridorIndex([]),
                          {'base': MultiCorridorIndex([line]), 'closed': MultiCorridorIndex([line])})
        self.assertEqual(result['outsideWinner1KmNearAnyExcludedKm']['0.1'], 5.)
        self.assertEqual(result['outsideWinner1KmNearBothExcludedClassesKm']['0.1'], 5.)
        self.assertEqual(result['referenceNearExcludedKm']['base']['1'], 5.)

    def test_known_winner_corridors_and_empty_reference_do_not_invent_coverage_gaps(self):
        line = [[-.01, 0.], [.11, 0.]]
        indexes = {'base': MultiCorridorIndex([line]), 'closed': MultiCorridorIndex([])}
        result = exposure([([0., 0.], 2.)], MultiCorridorIndex([line]), indexes)
        self.assertEqual(result['referenceOutsideWinner1Km'], 0.)
        self.assertEqual(result['outsideWinner1KmNearAnyExcludedKm']['1'], 0.)
        self.assertEqual(exposure([], MultiCorridorIndex([]), indexes)['referenceSampleKm'], 0.)


if __name__ == '__main__':
    unittest.main()
