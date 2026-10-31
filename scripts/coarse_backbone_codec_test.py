import random
import unittest

from coarse_backbone_codec import decode_signed32, encode_signed32


class BackboneCodecTests(unittest.TestCase):
    def test_signed_limits_zero_and_repetitions_round_trip(self):
        values = [-(1 << 31), -128, -64, -1, 0, 0, 1, 63, 64, 128, (1 << 31)-1]
        self.assertEqual(list(decode_signed32([encode_signed32(values)], len(values))), values)

    def test_one_byte_and_arbitrary_block_boundaries(self):
        values = [-10000000, 4000000, 3, -1, 0]
        encoded = encode_signed32(values)
        self.assertEqual(list(decode_signed32([bytes([b]) for b in encoded], len(values))), values)

    def test_seeded_signed32_values_round_trip(self):
        rng = random.Random(2358)
        values = [rng.randrange(-(1 << 31), 1 << 31) for _ in range(1000)]
        self.assertEqual(list(decode_signed32([encode_signed32(values)], len(values))), values)

    def test_encoder_rejects_out_of_range(self):
        for value in [-(1 << 31)-1, 1 << 31]:
            with self.assertRaises(ValueError):
                encode_signed32([value])

    def test_decoder_rejects_truncation_overflow_noncanonical_and_long_input(self):
        for raw in [b'\x80', b'\xff\xff\xff\xff\x10', b'\x80\x00', b'\x80'*6]:
            with self.assertRaises(ValueError):
                list(decode_signed32([raw], 100))

    def test_value_limit_is_enforced(self):
        with self.assertRaises(ValueError):
            list(decode_signed32([b'\x00\x00'], 1))


if __name__ == '__main__':
    unittest.main()
