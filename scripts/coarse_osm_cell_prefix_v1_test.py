"""Prefix framing, authentic input closure, strict order and conversion guards."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from coarse_osm_window_cells_v1 import Cells
from coarse_osm_window_codec_v1_test import reference as legacy
from coarse_osm_window_codec_v2_test import reference
from coarse_timing_input import PilotError
import run_osm_cell_prefix_v1 as prefix

WINDOWS=[{'id':'a','bbox':[0,0,1,1]}]
ROWS=[(1,0,0),(2,0,0),(3,0,0),(4,0,0)]


class Tests(unittest.TestCase):
    def setUp(self):
        self.grid=Cells(WINDOWS);self.old=legacy(ROWS,self.grid);self.new=reference(ROWS,self.grid)

    def measure(self,raw=None,**kwargs):
        raw=self.old if raw is None else raw
        class Codec:
            def from_v1(inner,block):
                self.assertEqual(block,self.old)
                return self.new
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'part';path.write_bytes(raw)
            expected={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
            expected.update(kwargs.pop('expected',{}))
            return prefix.measure(path,expected,Codec(),prefix.CAPS,**kwargs)

    def test_exact_block_sizes_and_canonical_conversion_totals(self):
        result=self.measure()
        self.assertEqual((result['rows'],result['blocks'],result['oldBytes'],result['newBytes']),(4,1,len(self.old),len(self.new)))
        self.assertTrue(result['everyIdAndCellNativeRoundtrip']);self.assertEqual(result['convertedSha256'],hashlib.sha256(self.new).hexdigest())

    def test_truncated_header_and_declared_body_fail(self):
        for raw in [self.old[:1],self.old[:67],self.old[:-1]]:
            with self.assertRaises(PilotError):self.measure(raw)

    def test_block_envelope_corruption_fails_before_conversion(self):
        damaged=bytearray(self.old);damaged[-1]^=1
        with self.assertRaises(PilotError):self.measure(bytes(damaged))

    def test_authentic_whole_part_hash_is_mandatory(self):
        with self.assertRaises(PilotError):self.measure(expected={'sha256':'0'*64})

    def test_global_id_order_cannot_repeat_at_part_boundary(self):
        with self.assertRaises(PilotError):self.measure(previous=1)

    def test_count_caps_are_checked_before_conversion(self):
        old=prefix.CAPS
        try:
            prefix.CAPS=old|{'rows':3}
            with self.assertRaises(PilotError):self.measure()
        finally:prefix.CAPS=old

    def test_cell_stream_drift_is_rejected(self):
        self.new=reference([(i,20000000,20000000) for i,_,_ in ROWS],self.grid)
        with self.assertRaises(PilotError):self.measure()

    def test_retained_prefix_accounting_and_limits_are_unchanged(self):
        self.assertEqual(prefix.RETAINED,55406628967)
        self.assertLess(prefix.RETAINED+prefix.OWNED+256*1024**2,64*1024**3)
        self.assertEqual(prefix.CAPS['inputBytes'],2080277463)
        self.assertEqual(prefix.CAPS['parts'],31)
        self.assertEqual(prefix.CAPS['rows'],1606229364)
