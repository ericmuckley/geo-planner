import hashlib
import math
from pathlib import Path
import random
import struct
import tempfile
import unittest

from native_support import NativeClient, compile_kernel, decode_labels, membership_bytes, pack_graph, verify_packed
from state_graph import bellman_ford, build_graph, partial_source


IDENTITY = "12" * 32


class NativePackingTests(unittest.TestCase):
    def test_layout_is_deterministic_little_endian_and_preserves_zero_cost(self):
        data = pack_graph([[(1, 0)], []], IDENTITY)
        self.assertEqual(len(data), 48 + 3 * 4 + 8)
        self.assertEqual(struct.unpack_from("<8sII32s", data), (b"GPCSR001", 2, 1, bytes.fromhex(IDENTITY)))
        self.assertEqual(struct.unpack_from("<3I", data, 48), (0, 1, 1))
        self.assertEqual(data, pack_graph([[(1, 0)], []], IDENTITY))

    def test_invalid_targets_costs_identity_and_empty_graph_are_rejected(self):
        for adjacency in ([], [[(1, 1)]], [[(-1, 1)]], [[(0, -1)]], [[(0, 1.5)]], [[(0, True)]], [[(0, 1 << 32)]]):
            with self.assertRaises(ValueError): pack_graph(adjacency, IDENTITY)
        with self.assertRaises(ValueError): pack_graph([[]], "bad")

    def test_checksum_guard_and_output_sizes_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "graph.csr"
            data = pack_graph([[]], IDENTITY)
            path.write_bytes(data)
            expected = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            verify_packed(path, expected)
            path.write_bytes(data[:-1] + b"x")
            with self.assertRaisesRegex(ValueError, "checksum"):
                verify_packed(path, expected)
        with self.assertRaises(ValueError): decode_labels(b"", 1)


class NativeKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temporary.name)
        cls.binary = cls.directory / "native_search"
        cls.compilation = compile_kernel(cls.binary)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def client(self, adjacency):
        path = self.directory / "graph.csr"
        path.write_bytes(pack_graph(adjacency, IDENTITY))
        return NativeClient(self.binary, path, IDENTITY)

    def test_full_and_bounded_costs_match_turn_aware_oracle(self):
        roads = [{"id": str(i), "way": str(i), "from": tail, "to": head, "costMs": cost}
                 for i, (tail, head, cost) in enumerate(((0, 1, 10), (1, 2, 10), (1, 3, 7), (3, 2, 9), (2, 0, 20), (4, 5, 0)))]
        graph = build_graph(roads, [{"id": "no", "fromWay": "0", "via": 1, "toWay": "1", "kind": "no_left_turn"}])
        client = self.client(graph.adjacency)
        try:
            for seeds in ([(0, 0)], partial_source(graph, 0, "1/3"), [(0, 7), (5, 0)]):
                exact = bellman_ford(graph.adjacency, seeds)
                for budget in (None, 0, 7, 16, 50, 43_200_000):
                    meta, payload, _ = client.request(seeds, budget)
                    expected = exact if budget is None else [cost if cost <= budget else math.inf for cost in exact]
                    self.assertEqual(decode_labels(payload, len(roads)), expected)
                    self.assertEqual(meta["complete"], budget is None)
        finally:
            client.close()

    def test_bitmaps_padding_and_persistent_request_framing(self):
        adjacency = [[(1, 2)], [(2, 3)], []]
        client = self.client(adjacency)
        try:
            for budget, expected in ((0, b"\x01"), (2, b"\x03"), (5, b"\x07"), (None, b"\x07")):
                metadata, payload, _ = client.request([(0, 0)], budget, "membership")
                self.assertEqual(payload, expected)
                self.assertEqual(metadata["requestId"], client.sequence)
                self.assertEqual(metadata["payloadBytes"], 1)
            self.assertEqual(client.hello["states"], 3)
        finally:
            client.close()

    def test_large_accumulated_costs_do_not_overflow_32_bits(self):
        adjacency = [[(1, 3_000_000_000)], [(2, 3_000_000_000)], []]
        client = self.client(adjacency)
        try:
            _, data, _ = client.request([(0, 0)], None)
            self.assertEqual(decode_labels(data, 3), [0, 3_000_000_000, 6_000_000_000])
            _, data, _ = client.request([(0, 0)], 4_000_000_000)
            self.assertEqual(decode_labels(data, 3), [0, 3_000_000_000, math.inf])
        finally:
            client.close()

    def test_seeded_random_directed_graphs_match_independent_oracle(self):
        rng = random.Random(20261016)
        for _ in range(8):
            adjacency = [[(target, rng.randrange(5)) for target in range(8) if rng.random() < .18] for _ in range(8)]
            client = self.client(adjacency)
            try:
                for seeds in ([(0, 0)], [(1, 5), (2, 1)], [(0, 7), (0, 2)]):
                    expected = bellman_ford(adjacency, seeds)
                    _, data, _ = client.request(seeds, None)
                    self.assertEqual(decode_labels(data, 8), expected)
                    _, mask, _ = client.request(seeds, 7, "membership")
                    self.assertEqual(mask, membership_bytes(expected, 7))
            finally:
                client.close()

    def test_malformed_binary_structures_and_graph_identity_are_rejected(self):
        good = pack_graph([[(1, 4)], []], IDENTITY)
        examples = [good[:20], b"badmagic" + good[8:], good + b"x"]
        bad_offsets = bytearray(good)
        struct.pack_into("<I", bad_offsets, 48, 1)
        examples.append(bad_offsets)
        bad_target = bytearray(good)
        struct.pack_into("<I", bad_target, 60, 99)
        examples.append(bad_target)
        for data in examples:
            path = self.directory / "invalid.csr"
            path.write_bytes(data)
            with self.assertRaises(RuntimeError): NativeClient(self.binary, path, IDENTITY)
        path.write_bytes(good)
        with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
            NativeClient(self.binary, path, "34" * 32)

    def test_invalid_queries_are_rejected_without_fallback(self):
        for seeds, budget, mode in (([], 0, "labels"), ([(99, 0)], 0, "labels"), ([(0, -1)], 0, "labels"),
                                    ([(0, 0)], -1, "labels"), ([(0, 0)], 1 << 64, "labels"),
                                    ([(0, 0)], 0, "unknown")):
            client = self.client([[], []])
            try:
                with self.assertRaises(RuntimeError): client.request(seeds, budget, mode)
            finally:
                client.close()


if __name__ == "__main__":
    unittest.main()
