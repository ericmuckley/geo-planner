"""Check storage-only qualification changes against the frozen representations."""

import math
import struct
import unittest

from native_support import UINT64_MAX
from regional_checks import bounded_equal, label_blocks
from region_admission import admission
from barrier_policy import barrier_decision
from region_release import check_resources, compare_barriers


class RegionalQualificationTests(unittest.TestCase):
    def test_streamed_fields_preserve_little_endian_bytes_at_chunk_boundaries(self):
        values = [0, 1, math.inf, 2**40, 17] * 1700
        expected = struct.pack(f"<{len(values)}Q", *(UINT64_MAX if value == math.inf else value for value in values))
        self.assertEqual(b"".join(label_blocks(values)), expected)
        self.assertEqual(b"".join(label_blocks([])), b"")

    def test_bounded_comparison_preserves_threshold_and_disconnection(self):
        exact = [0, 9, 10, 11, math.inf]
        self.assertTrue(bounded_equal([0, 9, 10, math.inf, math.inf], exact, 10))
        self.assertFalse(bounded_equal([0, 9, math.inf, math.inf, math.inf], exact, 10))
        self.assertFalse(bounded_equal([0], exact, 10))

    def test_phase_admission_retains_margin_and_pressure_gate(self):
        self.assertTrue(admission("test", 1024**3, 2, False)["eligible"])
        self.assertFalse(admission("test", 1024**3, 4, False)["eligible"])
        self.assertFalse(admission("test", 1024**3, 1, True)["eligible"])

    def test_release_rejects_pressure_even_without_an_oom(self):
        memory = {"memory.peak": str(1024**3), "memory.max": str(4 * 1024**3),
                  "memory.swap.max": "0", "memory.swap.current": "0", "memory.swap.peak": "0",
                  "memory.events": {"max": 0, "oom": 0, "oom_kill": 0, "oom_group_kill": 0}}
        report = {"resourceCheckpoints": {"end": memory}}
        self.assertEqual(check_resources(report)["pressureEvents"], 0)
        memory["memory.events"]["max"] = 1
        with self.assertRaises(ValueError): check_resources(report)
        memory["memory.events"]["max"] = 0
        memory["memory.peak"] = str(33 * 1024**3 // 10)
        with self.assertRaises(ValueError): check_resources(report)

    def test_newly_included_explicit_gate_keeps_the_same_policy(self):
        tags = {"barrier": "gate", "access": "yes"}
        old = {"id": 1, "point": [0.5, 1.1], "tags": tags, "open": False, "blockedByModel": True, "reason": "outside-bounds"}
        new = {**old, **barrier_decision(tags), "blockedByModel": False}
        self.assertEqual(len(compare_barriers([old], [new], [0, 0, 1, 1], [0, 0, 2, 2])), 1)
        with self.assertRaises(ValueError): compare_barriers([old], [new], [0, 0, 2, 2], [0, 0, 3, 3])

    def test_boundary_expansion_cannot_open_a_private_gate(self):
        tags = {"barrier": "gate", "access": "private"}
        old = {"id": 1, "point": [0.5, 1.1], "tags": tags, "open": False, "blockedByModel": True, "reason": "outside-bounds"}
        new = {**old, "open": True, "blockedByModel": False, "reason": "explicit-car-permission"}
        with self.assertRaises(ValueError): compare_barriers([old], [new], [0, 0, 1, 1], [0, 0, 2, 2])


if __name__ == "__main__": unittest.main()
