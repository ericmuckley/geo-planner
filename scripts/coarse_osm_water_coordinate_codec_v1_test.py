import random
import struct
import unittest

from coarse_osm_water_coordinate_codec_v1 import MAGIC,uint,encode_rows,decode_rows,typed_rows,verify_partition


class Controls(unittest.TestCase):
    def test_independent_known_wire_and_typed_integer_bytes(self):
        rows=[(1,0,0),(2,-1,1)]
        raw=b'WXY1\x01\x00\x00\x01\x01\x02'
        self.assertEqual(b''.join(encode_rows(rows)),raw)
        self.assertEqual(list(decode_rows([raw])),rows)
        self.assertEqual(b''.join(typed_rows(rows)),struct.pack('<QiiQii',1,0,0,2,-1,1))

    def test_extreme_native_ids_and_e7_coordinates_roundtrip(self):
        rows=[(1,-1800000000,-900000000),(2,1800000000,900000000),(2**63-1,0,0)]
        self.assertEqual(list(decode_rows(encode_rows(rows))),rows)

    def test_hundred_generated_streams_and_every_chunk_boundary(self):
        rng=random.Random(20261106)
        for _ in range(100):
            identity=0;rows=[]
            for _ in range(30):
                identity+=rng.randrange(1,1000000)
                rows.append((identity,rng.randrange(-1800000000,1800000001),rng.randrange(-900000000,900000001)))
            raw=b''.join(encode_rows(rows))
            for size in (1,2,3,7,17,31):
                self.assertEqual(list(decode_rows(raw[i:i+size] for i in range(0,len(raw),size))),rows)

    def test_truncation_wrong_header_overlong_overflow_and_zero_delta_fail(self):
        raw=b''.join(encode_rows([(10,20,-30)]))
        for bad in (raw[:2],raw[:-1],b'WXY2',MAGIC+b'\x81\x00\x00\x00',MAGIC+b'\xff'*10+b'\x00',MAGIC+b'\x00\x00\x00'):
            with self.subTest(raw=bad),self.assertRaises(Exception):list(decode_rows([bad]))

    def test_encoder_bad_order_coordinate_range_and_types_fail(self):
        for rows in ([(0,0,0)],[(1,0,0),(1,1,1)],[(1,1800000001,0)],[(1,0,-900000001)],[(True,0,0)],[(1,0.,0)]):
            with self.subTest(rows=rows),self.assertRaises(Exception):list(encode_rows(rows))
        for value in (-1,2**64,True):
            with self.assertRaises(Exception):uint(value)

    def test_present_missing_partition_keeps_real_zero_coordinate(self):
        self.assertEqual(verify_partition([1,2,3,4],[(1,0,0),(4,-1,1)],[2,3]),{'requested':4,'present':2,'missing':2})
        self.assertEqual(verify_partition([],[],[]),{'requested':0,'present':0,'missing':0})

    def test_partition_duplicate_omitted_extra_and_unsorted_ids_fail(self):
        for requested,present,missing in [([1,2],[(1,0,0)],[1,2]),([1,2],[(1,0,0)],[]),([1],[(1,0,0),(2,0,0)],[]),
                                           ([2,1],[(1,0,0),(2,0,0)],[]),([1,1],[(1,0,0)],[]),([1],[],[1,2])]:
            with self.assertRaises(Exception):verify_partition(requested,present,missing)


if __name__=='__main__':unittest.main()
