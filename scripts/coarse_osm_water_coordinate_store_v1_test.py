import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

from coarse_osm_water_coordinate_store_v1 import CoordinateStore


class Controls(unittest.TestCase):
    def test_exact_source_shadow_and_independent_stream_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            with CoordinateStore(directory,2,encoded_budget=1024,missing_budget=1024) as store:
                raw=struct.pack('<Qii',1,0,0);store.accept(30,b'WXY1\x01\x00\x00');store.accept(31,struct.pack('<Q',2));store.accept(32,raw)
                result=store.finish({'complete':1,'requested':2,'present':1,'missing':1,'encodedBytes':7,'missingBytes':8,'canonicalBytes':16})
                self.assertEqual(result['sourceShadow']['sha256'],hashlib.sha256(raw).hexdigest())
                self.assertTrue(result['coordinatesRetained']);self.assertFalse(result['ringsConstructed'])

    def test_empty_coordinate_stream_preserves_real_format_header(self):
        with tempfile.TemporaryDirectory() as directory:
            with CoordinateStore(directory,0,encoded_budget=1024,missing_budget=1024) as store:
                store.accept(30,b'WXY1')
                result=store.finish({'complete':1,'requested':0,'present':0,'missing':0,'encodedBytes':4,'missingBytes':0,'canonicalBytes':0})
                self.assertEqual(result['missing']['parts'],[])
                self.assertEqual(result['sourceShadow']['sha256'],hashlib.sha256(b'').hexdigest())

    def test_chunk_event_alignment_and_raw_bounds_are_required(self):
        for event,raw in ((29,b'X'),(31,b'X'),(32,b'X'),(30,b'X'*24),(31,b'X'*16),(32,b'X'*32)):
            with tempfile.TemporaryDirectory() as directory:
                with CoordinateStore(directory,1,encoded_budget=1024,missing_budget=1024) as store:
                    with self.assertRaises(Exception):store.accept(event,raw)

    def test_separate_compression_budgets_stop_before_accepted_finish(self):
        for event,raw in ((30,b'WXY1'),(31,struct.pack('<Q',1))):
            with tempfile.TemporaryDirectory() as directory:
                with CoordinateStore(directory,1,encoded_budget=1,missing_budget=1) as store:
                    with self.assertRaises(Exception):store.accept(event,raw)

    def test_incomplete_counts_and_closed_store_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            with CoordinateStore(directory,0,encoded_budget=1024,missing_budget=1024) as store:
                counts={'complete':1,'requested':0,'present':0,'missing':0,'encodedBytes':4,'missingBytes':0,'canonicalBytes':0}
                with self.assertRaises(Exception):store.finish(counts)
                store.accept(30,b'WXY1');store.finish(counts)
                with self.assertRaises(Exception):store.finish(counts)
                with self.assertRaises(Exception):store.accept(30,b'X')


if __name__=='__main__':unittest.main()
