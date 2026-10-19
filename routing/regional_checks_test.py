"""Check storage-only qualification changes against the frozen representations."""

import math
import struct
import unittest

from native_support import UINT64_MAX
from regional_checks import bounded_equal, label_blocks
from region_admission import admission


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


if __name__ == "__main__": unittest.main()
