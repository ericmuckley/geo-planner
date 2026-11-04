from pathlib import Path
import tempfile
import unittest

from coarse_osm_car_spatial_audit_v1 import audit
from coarse_osm_car_spatial_reference_v1 import fixture,permute


class SpatialAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.source=self.root/'in';self.source.mkdir();self.output=self.root/'out';self.output.mkdir()
        self.fields=fixture();self.expected=permute(self.fields)
        for key,value in self.fields.items():(self.source/key).write_bytes(value)
        for key,value in self.expected.items():(self.output/key).write_bytes(value)

    def test_every_field_and_duplicate_source_point_preserved(self):
        result=audit(self.source,self.output);self.assertEqual(result['verticesChecked'],4);self.assertEqual(result['directedArcsCostsPhysicalReversesChecked'],6)

    def test_corrupt_cost_reverse_coordinate_or_permutation_refused(self):
        for key in ['costs.u16','reverse.u8','xy.i32','new-vertex-to-old.u32','old-arc-to-new.u32']:
            path=self.output/key;original=path.read_bytes();value=bytearray(original);value[0]^=1;path.write_bytes(value)
            with self.assertRaises((AssertionError,IndexError)):audit(self.source,self.output)
            path.write_bytes(original)

    def test_corrupt_forbidden_pair_or_spatial_cell_refused(self):
        for key in ['forbidden-turns.u24','cell-keys.u24','cell-offsets.u24']:
            path=self.output/key;original=path.read_bytes();value=bytearray(original);value[0]^=1;path.write_bytes(value)
            with self.assertRaises((AssertionError,IndexError)):audit(self.source,self.output)
            path.write_bytes(original)

    def test_missing_or_extra_output_refused(self):
        path=self.output/'extra';path.write_bytes(b'');
        with self.assertRaises(AssertionError):audit(self.source,self.output)
        path.unlink();(self.output/'cell-keys.u24').unlink()
        with self.assertRaises(AssertionError):audit(self.source,self.output)


if __name__=='__main__':unittest.main()
