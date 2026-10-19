import unittest

from compact_storage import Roads
from road_keys import RoadKeys


def roads(keys):
    result = Roads()
    for way, segment, direction in keys:
        result.append({"id": f"{way}:{segment}:{direction}", "way": way, "from": 1, "to": 2,
                       "costMs": 5, "fromPoint": [0, 0], "toPoint": [1, 1], "name": None})
    return result


class RoadKeyTests(unittest.TestCase):
    def test_restorations_equal_string_membership_with_missing_and_added_keys(self):
        original = roads([(2, 0, "r"), (2, 10, "f"), (10, 1, "f"), (2**60, 9, "r")])
        final = roads([(1, 0, "f"), (2, 0, "f"), (2, 0, "r"), (2, 10, "r"), (10, 1, "f"), (2**60, 9, "r"), (2**60, 10, "f")])
        before = {road["id"] for road in original}
        keys = RoadKeys(original)
        self.assertEqual(keys.restored(final), [road for road in final if road["id"] not in before])
        self.assertIs(keys.ways, original.ways)
        self.assertEqual(keys.summary()["payloadBytes"], len(original) * 13)
        self.assertEqual(RoadKeys(roads([])).restored(final), list(final))
        self.assertEqual(keys.restored(roads([])), [])

    def test_rejects_unsorted_or_duplicate_keys_on_either_side(self):
        for invalid in ([(2, 0, "f"), (1, 0, "f")], [(2, 0, "r"), (2, 0, "f")], [(1, 0, "f"), (1, 0, "f")]):
            with self.assertRaises(ValueError): RoadKeys(roads(invalid))
            with self.assertRaises(ValueError): RoadKeys(roads([])).restored(roads(invalid))
