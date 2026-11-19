import unittest
from coarse_osm_native_flag_order_v1 import rebase_flags
from coarse_timing_input import PilotError


def fixture():
    return [bytes([5,6,7,4]), bytes([7,5,4,6]), bytes([6,4,4,6]), [2,0,3,1], [100,200,300,400,500], [0,2,3,4], [100,400]]


class Tests(unittest.TestCase):
    def test_nonidentity_complete_round_trip_and_original_unchanged(self):
        args = fixture()
        before = [v[:] for v in args]
        actual, proof = rebase_flags(*args)
        self.assertEqual(actual, bytes([4,6,6,4]))
        self.assertEqual(proof['spatialAndNativeRowsIndependentlyCompared'], 4)
        self.assertEqual(proof['sourceQualifiedOpenedNodeIdsPreserved'], 2)
        self.assertEqual(args, before)

    def test_identity_without_opening(self):
        flags, _ = rebase_flags(bytes([4,5]), bytes([4,5]), bytes([4,5]), [0,1], [10,20], [0,1], [])
        self.assertEqual(flags, bytes([4,5]))

    def test_duplicate_out_of_range_or_short_permutation_refuses(self):
        for permutation in [[2,0,2,1], [2,0,4,1], [2,0,3], [2,0,-1,1]]:
            args = fixture(); args[3] = permutation
            with self.assertRaises(PilotError): rebase_flags(*args)

    def test_mismatched_original_order_or_dimensions_refuse(self):
        for original in [bytes([5,7,4,6]), bytes([7,5,4]), bytes([7,5,4,8])]:
            args = fixture(); args[1] = original
            with self.assertRaises(PilotError): rebase_flags(*args)

    def test_signal_reversal_open_blocker_or_new_blocker_change_refuses(self):
        for final in [bytes([4,4,4,6]), bytes([6,4,6,6]), bytes([6,4,5,6])]:
            args = fixture(); args[2] = final
            with self.assertRaises(PilotError): rebase_flags(*args)

    def test_wrong_missing_duplicate_or_unbound_opened_source_identity_refuses(self):
        for identities in [[100], [100,300], [100,100], [400,100]]:
            args = fixture(); args[-1] = identities
            with self.assertRaises(PilotError): rebase_flags(*args)
        args = fixture(); args[5] = [9,2,3,4]
        with self.assertRaises(PilotError): rebase_flags(*args)


if __name__ == '__main__':
    unittest.main()
