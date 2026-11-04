"""Rank values checked against sorted Python lists and an independent cut oracle."""
from array import array
from bisect import bisect_left
from pathlib import Path
import random
import struct
import tempfile
import unittest

from coarse_osm_car_node_index_v1 import NativeIndex
from coarse_osm_car_partition_v1_test import splits
from coarse_timing_input import PilotError

ARTIFACT = None
ABSENT = 0xffffffff


class Tests(unittest.TestCase):
    def setUp(self):
        if ARTIFACT is None:
            self.skipTest('Protected compiled index artifact required')
        self.native = NativeIndex(*ARTIFACT)

    def check_ids(self, ids, anchors, queries, maximum):
        def ordinal(values, value):
            at = bisect_left(values, value)
            return at if at < len(values) and values[at] == value else ABSENT
        anchor_ids = [n for n, flag in zip(ids, anchors) if flag]
        self.assertEqual(self.native.queries(ids, anchors, queries, maximum),
                         [(ordinal(ids, q), ordinal(anchor_ids, q)) for q in queries])

    def test_word_block_zero_and_maximum_boundaries(self):
        ids = [1, 63, 64, 65, 511, 512, 513, 1023, 1024, 1025]
        self.check_ids(ids, [i%2 for i in range(len(ids))], list(range(1100))+[2**64-1], 1025)

    def test_empty_and_all_or_no_anchors(self):
        self.check_ids([], [], [0, 1, 2, 2**64-1], 1)
        for flags in ([0]*100, [1]*100):
            self.check_ids(list(range(1, 101)), flags, list(range(102)), 100)

    def test_seeded_sparse_membership_and_rank(self):
        rng = random.Random(20261101)
        for _ in range(100):
            ids = sorted(rng.sample(range(1, 20001), rng.randrange(1, 500)))
            flags = [rng.randrange(2) for _ in ids]
            self.check_ids(ids, flags, ids+[rng.randrange(22000) for _ in range(100)], 20000)

    def test_bad_ids_order_duplicates_and_maximum_reject(self):
        for ids in ([0], [2, 1], [1, 1], [11]):
            with self.assertRaises(PilotError):
                self.native.queries(ids, [0]*len(ids), [1], 10)
        for maximum in (0, -1, 2**34, True):
            with self.assertRaises(PilotError):
                self.native.queries([], [], [], maximum)

    def test_bad_flags_lengths_and_unsigned_inputs_reject(self):
        for ids, flags, queries in (([1], [], []), ([1], [2], []), ([True], [0], []),
                                    ([1], [0], [-1]), ([1], [0], [2**64])):
            with self.assertRaises(PilotError):
                self.native.queries(ids, flags, queries, 10)

    def fixture(self, ways, tagged=(), relations=(), mutate=lambda rows: rows):
        rows = [(node, way, 1 if i in (0, len(refs)-1) else 2, int(i in (0, len(refs)-1)))
                for way, refs in ways.items() for i, node in enumerate(refs)]
        rows.sort(key=lambda r: (r[0], r[1], r[3], r[2]))
        expected = rows
        rows = mutate(rows)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            parts = []
            for i in range(0, len(rows), 3):
                path = root/str(i);path.write_bytes(b''.join(struct.pack('<QQII', *r) for r in rows[i:i+3]));parts.append(path)
            tags = root/'tags';tags.write_bytes(b''.join(struct.pack('<Q', n) for n in sorted(tagged)))
            anchors = splits(ways, tagged, relations)[1]
            result = self.native.run(parts, [tags], array('Q', sorted(relations)), reference_count=len(expected),
                                     way_count=len(ways), tag_count=len(tagged), maximum=max(r[0] for r in expected),
                                     selected=len({r[0] for r in expected}), anchors=len(anchors))
        self.assertEqual(result['referenceLookups'], len(expected))
        self.assertEqual(result['typedSourceMergePasses'], 2)
        self.assertEqual(result['complete'], 1)

    def test_incidence_merge_shared_nodes_loops_repeats_and_metadata(self):
        self.fixture({1: [1, 2, 3, 4], 2: [3, 5], 3: [6, 7, 6], 4: [8, 8, 9]}, tagged=(2, 10), relations=(7, 11))

    def test_seeded_graphs_match_independent_anchor_selection(self):
        rng = random.Random(20261102)
        for _ in range(30):
            ways = {w: [rng.randrange(1, 50) for _ in range(rng.randrange(2, 12))] for w in range(1, 12)}
            self.fixture(ways, tagged=rng.sample(range(1, 60), 5), relations=rng.sample(range(1, 60), 5))

    def test_bad_incidence_fields_and_missing_rows_fail(self):
        for mutate in (lambda rows: rows[:-1], lambda rows: [rows[0][:2]+(2, 1)]+rows[1:]):
            with self.assertRaises(PilotError):
                self.fixture({1: [1, 2, 3]}, mutate=mutate)

    def test_duplicate_tags_fail(self):
        with self.assertRaises(PilotError):
            self.fixture({1: [1, 2, 3]}, tagged=(2, 2))
