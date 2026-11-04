"""Independent source-way cut oracle for the native partition derivation."""
from array import array
from collections import Counter
from pathlib import Path
import random
import struct
import tempfile
import unittest

from coarse_osm_car_partition_v1 import Partitions
from coarse_osm_topology_kernel_v1 import REF
from coarse_timing_input import PilotError

ARTIFACT = None


def splits(ways, tags=(), relation_nodes=()):
    degree = Counter()
    ends = set()
    for refs in ways.values():
        ends.update((refs[0], refs[-1]))
        for a, b in zip(refs, refs[1:]):
            degree[a] += 1
            degree[b] += 1
    protected = ends | set(tags) | set(relation_nodes)
    anchors = {node for node, d in degree.items() if d != 2 or node in protected}
    return sorted(way for way, refs in ways.items() for node in refs[1:-1] if node in anchors), anchors


class Tests(unittest.TestCase):
    def setUp(self):
        if ARTIFACT is None:
            self.skipTest('Protected native partition artifact required')
        self.kernel = Partitions(*ARTIFACT)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.counter = 0

    def file(self, raw):
        self.counter += 1
        path = self.root / str(self.counter)
        path.write_bytes(raw)
        return path

    def derive(self, ways, tags=(), relations=(), cap=8000000):
        rows = [(node, way, 1 if i in (0, len(refs)-1) else 2, int(i in (0, len(refs)-1)))
                for way, refs in ways.items() for i, node in enumerate(refs)]
        rows.sort(key=lambda r: (r[0], r[1], r[3], r[2]))
        files = [self.file(b''.join(REF.pack(*r) for r in rows[i:i+7])) for i in range(0, len(rows), 7)]
        tag_files = [self.file(array('Q', sorted(tags)).tobytes())] if tags else []
        self.counter += 1
        out = self.root / ('splits-' + str(self.counter))
        result = self.kernel.derive(files, tag_files, array('Q', sorted(relations)), out,
                                    reference_count=len(rows), way_count=len(ways), tag_count=len(tags), maximum_splits=cap)
        expected, anchors = splits(ways, tags, relations)
        actual = array('Q')
        actual.frombytes(out.read_bytes())
        self.assertEqual(list(actual), expected)
        self.assertEqual(result['anchors'], len(anchors))
        self.assertEqual(result['contractedEdges'], sum(sum(node in anchors for node in refs)-1 for refs in ways.values()))
        self.assertEqual(result['outputBytes'], 8*len(expected))
        degrees = Counter(node for refs in ways.values() for pair in zip(refs, refs[1:]) for node in pair)
        minimum = {node for node, degree in degrees.items() if degree != 2 or node in set(tags) | set(relations)}
        self.assertEqual(result['anchorsWithoutWayEndsBeforeCycleAndCarRules'], len(minimum))
        return out, result

    def test_simple_shape_junction_tag_and_relation_node(self):
        ways = {1: [1, 2, 3, 4, 5], 2: [3, 6]}
        self.derive(ways, tags=[2, 999], relations=[4, 444])

    def test_loops_parallel_repeated_zero_and_large_native_ids(self):
        self.derive({1: [1, 2, 3, 1], 2: [1, 2, 3, 1], 3: [4, 4, 4], 4: [2**63-1, 42]})

    def test_seeded_graphs_and_duplicate_relation_metadata(self):
        rng = random.Random(20261104)
        for _ in range(100):
            ways = {i+1: [rng.randrange(1, 20) for _ in range(rng.randrange(2, 15))] for i in range(rng.randrange(1, 10))}
            self.derive(ways, tags=[2, 99], relations=[3, 3, 999])

    def test_empty_graph_and_unselected_tags(self):
        self.derive({}, tags=[1, 2, 3])

    def test_split_cap_and_existing_output_preserve_prior_bytes(self):
        with self.assertRaises(PilotError):
            self.derive({1: [1, 2, 3]}, tags=[2], cap=0)
        out, _ = self.derive({1: [1, 2]})
        before = out.read_bytes()
        with self.assertRaises(PilotError):
            self.kernel.derive([], [], array('Q'), out, reference_count=0, way_count=0, tag_count=0, maximum_splits=0)
        self.assertEqual(out.read_bytes(), before)

    def test_truncation_unsorted_and_invalid_typed_rows_fail(self):
        for raw in (b'x', REF.pack(2, 1, 1, 1) + REF.pack(1, 1, 1, 1), REF.pack(0, 1, 1, 1)):
            with self.assertRaises(PilotError):
                self.kernel.derive([self.file(raw)], [], array('Q'), self.root/'bad', reference_count=2, way_count=1, tag_count=0, maximum_splits=10)

    def test_metadata_order_and_tag_total_fail(self):
        path = self.file(REF.pack(1, 1, 1, 1) + REF.pack(2, 1, 1, 1))
        for relations in (array('Q', [2, 1]), array('Q', [0])):
            with self.assertRaises(PilotError):
                self.kernel.derive([path], [], relations, self.root/'bad', reference_count=2, way_count=1, tag_count=0, maximum_splits=10)
        with self.assertRaises(PilotError):
            self.kernel.derive([path], [], array('Q'), self.root/'bad', reference_count=2, way_count=1, tag_count=1, maximum_splits=10)

    def test_source_input_symlink_and_occurrence_mismatch_fail(self):
        path = self.file(REF.pack(1, 1, 1, 1) + REF.pack(2, 1, 1, 1))
        link = self.root/'link'
        link.symlink_to(path)
        for files, count in (([link], 2), ([path], 3)):
            with self.assertRaises(PilotError):
                self.kernel.derive(files, [], array('Q'), self.root/'bad', reference_count=count, way_count=1, tag_count=0, maximum_splits=10)
