"""Small independent expectations for captured-only format/fixture preparation."""
import unittest

from coarse_osm_packed_capture_v1 import encode, pack24


class PackedCaptureTests(unittest.TestCase):
    def test_packed_boundaries(self):
        self.assertEqual(pack24([0, 65535, 65536, 0xffffff]), b'\0\0\0\xff\xff\0\0\0\1\xff\xff\xff')
        for bad in (-1, 1.5, 0x1000000):
            with self.assertRaises(ValueError):pack24([bad])

    def test_paid_internal_geometry_and_reverse_identity(self):
        cases = [{'windowId': 'fixture', 'sourceNodeIds': [12, 13], 'binaryQuantizedMs': 125},
                 {'windowId': 'same', 'sourceNodeIds': [12, 12], 'binaryQuantizedMs': 0}]
        fields, fixtures, counts = encode([11, 12, 13], [0]*6, [0, 2], b'\4\4', [0, 1, 2],
                                          [(10, 100., 100., 3, 3)],
                                          [(0, 1, 0, 0, 2, 1, 2), (1, 0, 0, 0, 2, -1, 2)], set(), [], cases)
        self.assertEqual(fields['reverse.u8'], b'\0\0')
        self.assertEqual(fields['offsets.u24'], pack24([0, 1, 2]))
        self.assertEqual(counts['paidInternalAliases'], 1)
        self.assertEqual(fixtures[0]['source'], {'partials': [{'arc': 0, 'ticks': 1}, {'arc': 1, 'ticks': 1}]})
        self.assertEqual(fixtures[0]['target'], {'vertex': 1})
        self.assertEqual(fixtures[1]['directTicks'], 0)

    def test_only_turn_to_outside_profile_blocks_retained_departure(self):
        fields, _, counts = encode([11, 12, 13], [0]*6, [0, 1, 2], b'\4'*3, [0, 1, 1, 2],
                                   [(10, 100., 0., 1, 2), (20, 100., 0., 1, 4)],
                                   [(0, 1, 0, 0, 1, 1, 1), (1, 2, 1, 0, 1, 1, 1)],
                                   set(), [(100, 10, 12, 999, 6)], [])
        self.assertEqual(fields['forbidden-turns.u24'], pack24([0, 1]))
        self.assertEqual(counts['forbiddenTurnPairs'], 1)

    def test_closures_remove_both_directions_without_free_aliases(self):
        fields, fixtures, counts = encode([11, 12, 13], [0]*6, [0, 2], b'\4\4', [0, 1, 2],
                                          [(10, 100., 100., 3, 3)],
                                          [(0, 1, 0, 0, 2, 1, 2), (1, 0, 0, 0, 2, -1, 2)], {10}, [],
                                          [{'windowId': 'closed', 'sourceNodeIds': [12, 13], 'binaryQuantizedMs': None}])
        self.assertEqual(counts['arcs'], 0)
        self.assertEqual(fields['targets.u24'], b'')
        self.assertEqual(fixtures[0]['source'], {'partials': []})

    def test_refuses_country_sized_input_before_object_expansion(self):
        with self.assertRaises(AssertionError):encode(range(200001), [], [], [], [], [], [], set(), [], [])


if __name__ == '__main__':unittest.main()
