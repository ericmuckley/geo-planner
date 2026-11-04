"""Every-byte native spatial permutation checks against a separate small oracle."""
from pathlib import Path
import random
import struct
import tempfile
import unittest

from coarse_osm_car_spatial_native_v1 import NativeSpatial
from coarse_osm_car_spatial_reference_v1 import fixture,morton,permute
from coarse_osm_packed_capture_v1 import pack24

ARTIFACT=None


class SpatialTests(unittest.TestCase):
    def setUp(self):
        if ARTIFACT is None:self.skipTest('Explicit native spatial artifact required')
        self.native=NativeSpatial(*ARTIFACT);self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def compare(self,fields,name='test'):
        source=self.root/(name+'-in');source.mkdir();output=self.root/(name+'-out');output.mkdir()
        for key,raw in fields.items():(source/key).write_bytes(raw)
        result=self.native.encode(source,output);expected=permute(fields)
        self.assertEqual(set(expected),{path.name for path in output.iterdir()})
        for key,raw in expected.items():self.assertEqual((output/key).read_bytes(),raw,key)
        self.assertEqual(result['totalBytesIncludingOfflinePermutations'],sum(map(len,expected.values())))
        return result,expected

    def test_full_fields_parallel_coordinates_and_paid_costs(self):self.compare(fixture())

    def test_one_hundred_seeded_coordinate_orders_match_every_byte(self):
        randomizer=random.Random(20261102)
        for case in range(100):
            fields=fixture();xy=[value for _ in range(4) for value in (randomizer.randrange(-1800000000,1800000001),randomizer.randrange(-900000000,900000001))]
            fields['xy.i32']=struct.pack('<8i',*xy);self.compare(fields,str(case))

    def test_global_extremes_and_duplicate_coordinates_remain_distinct(self):
        fields=fixture();fields['xy.i32']=struct.pack('<8i',-1800000000,-900000000,1800000000,900000000,0,0,0,0)
        _,expected=self.compare(fields)
        order=struct.unpack('<4I',expected['new-vertex-to-old.u32']);self.assertEqual(len(set(order)),4)
        self.assertLess(order.index(2),order.index(3));self.assertEqual(morton(-1800000000,-900000000),0)

    def test_cost_and_reverse_overflows_survive_permutation(self):
        fields={'xy.i32':struct.pack('<2i',0,0),'offsets.u24':pack24([0,256]),'targets.u24':pack24([0]*256),
                'costs.u16':struct.pack('<256H',*([65535]+[1]*255)),'cost-overflow-arcs.u24':pack24([0]),'cost-overflow-ticks.u32':struct.pack('<I',0xffffffff),
                'reverse.u8':bytes([254]+[255]*254+[0]),'reverse-overflow-arcs.u24':pack24([0]),'reverse-overflow-targets.u24':pack24([255]),
                'node-flags.u8':b'\4','forbidden-turns.u24':b''}
        self.compare(fields)

    def test_empty_arc_rows_are_preserved(self):
        fields=fixture();fields['offsets.u24']=pack24([0,0,3,3,6]);fields['reverse.u8']=bytes([255]*6);fields['forbidden-turns.u24']=b''
        self.compare(fields)

    def test_corrupt_dimensions_overflow_or_coordinate_refused(self):
        for index,(key,raw) in enumerate([('xy.i32',b'x'),('targets.u24',pack24([4]*6)),('cost-overflow-arcs.u24',b''),('xy.i32',struct.pack('<8i',1800000001,0,0,0,0,0,0,0))]):
            source=self.root/f'in-{index}';source.mkdir();output=self.root/f'out-{index}';output.mkdir();fields=fixture();fields[key]=raw
            for name,value in fields.items():(source/name).write_bytes(value)
            with self.assertRaises(ValueError):self.native.encode(source,output)

    def test_source_symlink_and_existing_output_refused(self):
        source=self.root/'in';source.mkdir();output=self.root/'out';output.mkdir()
        for key,raw in fixture().items():(source/key).write_bytes(raw)
        path=source/'xy.i32';path.rename(self.root/'xy');path.symlink_to(self.root/'xy')
        with self.assertRaises(ValueError):self.native.encode(source,output)
        path.unlink();path.write_bytes((self.root/'xy').read_bytes());(output/'preserve').write_bytes(b'keep')
        with self.assertRaises(ValueError):self.native.encode(source,output)


if __name__=='__main__':unittest.main()
