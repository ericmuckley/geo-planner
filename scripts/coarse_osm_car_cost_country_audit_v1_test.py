"""Independent world-audit regressions, synthetic typed records only."""
from array import array
from pathlib import Path
import tempfile
import unittest

from country_cost_audit_v1 import audit_identities, way_speeds, I, Q, REF


class IdentityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root = Path(temp.name)

    def check(self, tags, relations, anchors, change=lambda rows: rows, ids=(1, 2, 3, 4)):
        values = [(1, 1, 1, 1), (2, 1, 2, 0), (3, 1, 1, 1), (3, 2, 1, 1), (4, 2, 1, 1)]
        values = change(values);refs = []
        for part in range(2):
            path = self.root/f'refs-{part}';path.write_bytes(b''.join(REF.pack(*row) for row in values[part::2]));refs.append(path)
        path = self.root/'tags';path.write_bytes(b''.join(Q.pack(value) for value in tags))
        return audit_identities(refs,[path],array('Q',relations),iter((value,) for value in ids),
                                iter((value,) for value in anchors),(5,4,len(anchors),6,4,len(tags)))

    def test_endpoints_junctions_and_unprotected_interior(self):
        result = self.check([], [], [0, 2, 3]);self.assertEqual(result['selectedNativeIds'], 4)

    def test_tags_protect_interior_and_unselected_tags_are_still_counted(self):
        self.check([2, 99], [], [0, 1, 2, 3])

    def test_explicit_relation_nodes_protect_interior_with_duplicate_metadata(self):
        self.check([], [2, 2, 100], [0, 1, 2, 3])

    def test_missing_native_id_fails(self):
        with self.assertRaises((AssertionError, StopIteration)):
            self.check([], [], [0, 2, 3], ids=(1, 2, 4))

    def test_bad_reference_flag_and_unsorted_tags_fail(self):
        with self.assertRaises(AssertionError):
            self.check([], [], [0, 2, 3], change=lambda rows: [(1, 1, 2, 1)]+rows[1:])
        with self.assertRaises(AssertionError):self.check([3, 2], [], [0, 2, 3])


class SpeedTests(unittest.TestCase):
    def test_oneway_keeps_absent_backward_default_but_zero_unused_speed(self):
        self.assertEqual(way_speeds(1|4|8,100.,0.),(0,1))

    def test_two_way_defaults_and_explicit_speeds(self):
        self.assertEqual(way_speeds(3|4|8|(4<<4),55.,55.),(4,3))
        self.assertEqual(way_speeds(3|(4<<4),30.,45.),(4,3))

    def test_no_allowed_direction_has_zero_speeds_even_with_default_bits(self):
        self.assertEqual(way_speeds(4|8|(9<<8),0.,0.),(0,0))

    def test_bad_unused_speed_or_default_rejects(self):
        for mask,forward,backward in ((1|4|8,100.,100.),(1|4,99.,0.),(1,0.,0.)):
            with self.assertRaises(AssertionError):way_speeds(mask,forward,backward)

    def test_bad_role_nonfinite_and_out_of_range_speed_rejects(self):
        for mask,forward,backward in ((15<<4,0.,0.),(1,float('nan'),0.),(1,161.,0.),(1,float('inf'),0.)):
            with self.assertRaises(AssertionError):way_speeds(mask,forward,backward)
