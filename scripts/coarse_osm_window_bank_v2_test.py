"""Compact snapshot/ownership/closure/drift and geometry controls, tiny data only."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest

from coarse_osm_country_screen_v1 import OwnedStorage
from coarse_osm_delta_v1 import ReferenceCodec,ROWS
from coarse_osm_records import canonical
from coarse_osm_window_cells_v1 import Cells,SCALE
from coarse_osm_window_codec_v2 import Codec,ENVELOPE,BODY,body
from coarse_osm_window_bank_v2 import Writer,Bank,ENTRY
from coarse_timing_input import PilotError

ARTIFACT=None
CODECS=[]


def configure_native(path,sha):
    global ARTIFACT
    ARTIFACT=path,sha


class NativeTests(unittest.TestCase):
    def setUp(self):
        if ARTIFACT is None:self.skipTest('Qualified window-cell native artifact required')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.windows=[{'id':'a','bbox':[0,0,1,1]},{'id':'b','bbox':[.25,.25,.75,.75]}]

    def codec(self,windows=None):
        codec=Codec(*ARTIFACT,Cells(windows or self.windows));CODECS.append(codec);return codec

    def make(self,count=5000,**caps):
        codec=self.codec();root=self.root/'bank';storage=OwnedStorage(self.root,limit=16*1024**2)
        writer=Writer(root,storage,self.windows,count,**caps)
        rows=[(2*i+1,0,0) for i in range(count)]
        for start in range(0,count,ROWS):
            block=rows[start:start+ROWS];encoded=codec.encode(ReferenceCodec().encode(block),len(block),block[0][0],block[-1][0]);writer.append(encoded,codec)
        writer.finish();return root,codec,writer

    def test_multiple_parts_and_partial_last_block_preserve_order_duplicates_and_gaps(self):
        root,codec,writer=self.make(part_limit=100);bank=Bank(root,codec,self.windows,expected_rows=5000)
        self.addCleanup(bank.close);self.assertEqual(len(bank.parts),2);self.assertEqual(bank.manifest['blocks'],2)
        expected=codec.cells.cell(0,0);self.assertEqual(bank.lookup([9999,1,8193,1]),[expected]*4)
        for ids in [[2],[10001],[0],[True]]:
            with self.assertRaises(PilotError):bank.lookup(ids)
        bank.verify_files();self.assertEqual(writer.stored_bytes,sum(p.stat().st_size for p in root.iterdir()))

    def test_live_disk_drift_cannot_change_immutable_answers_and_close_rejects_it(self):
        root,codec,_=self.make(3);bank=Bank(root,codec,self.windows);self.addCleanup(bank.close)
        expected=bank.lookup([1,3,5]);path=root/'0000.bin';before=path.stat();raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw);os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
        self.assertEqual(bank.lookup([1,3,5]),expected)
        with self.assertRaises(PilotError):bank.verify_files()

    def test_original_query_and_expected_source_count_are_bound(self):
        root,codec,_=self.make(3);changed=deepcopy(self.windows);changed[0]['bbox'][0]=1e-9
        with self.assertRaises(PilotError):Bank(root,codec,changed)
        with self.assertRaises(PilotError):Bank(root,codec,self.windows,expected_rows=4)
        with self.assertRaises(PilotError):Bank(root,self.codec([{'id':'other','bbox':[0,0,1,1]}]),self.windows)

    def test_part_and_directory_corruption_before_snapshot_fail(self):
        root,codec,_=self.make(3)
        for name in ['0000.bin','directory.bin']:
            path=root/name;original=path.read_bytes();damaged=bytearray(original);damaged[-1]^=1;path.write_bytes(damaged)
            with self.assertRaises(PilotError):Bank(root,codec,self.windows)
            path.write_bytes(original)

    def test_resigned_bad_directory_offsets_are_rejected(self):
        root,codec,_=self.make(3);directory=bytearray((root/'directory.bin').read_bytes());struct.pack_into('<Q',directory,8,1)
        (root/'directory.bin').write_bytes(directory);manifest=json.loads((root/'index.json').read_text());manifest['directory']['sha256']=hashlib.sha256(directory).hexdigest();(root/'index.json').write_bytes(canonical(manifest)+b'\n')
        with self.assertRaises(PilotError):Bank(root,codec,self.windows)

    def test_native_canonical_validation_precedes_bank_append(self):
        codec=self.codec();writer=Writer(self.root/'bank',OwnedStorage(self.root),self.windows,1)
        raw=codec.encode(ReferenceCodec().encode([(1,0,0)]),1,1,1);payload=bytearray(body(raw)[0]);struct.pack_into('<H',payload,BODY.size,codec.cells.count)
        damaged=ENVELOPE.pack(b'WC02',2,0,hashlib.sha256(payload).digest())+payload
        with self.assertRaises(PilotError):writer.append(bytes(damaged),codec)
        self.assertEqual(writer.rows,0);self.assertFalse(list(writer.root.iterdir()))

    def test_storage_caps_and_incomplete_source_never_create_finished_catalog(self):
        codec=self.codec();writer=Writer(self.root/'short',OwnedStorage(self.root),self.windows,2)
        with self.assertRaises(PilotError):writer.finish()
        self.assertFalse((writer.root/'index.json').exists())
        tiny=Writer(self.root/'tiny',OwnedStorage(self.root),self.windows,1,limit=1048576)
        raw=codec.encode(ReferenceCodec().encode([(1,0,0)]),1,1,1)
        with self.assertRaises(PilotError):tiny.append(raw,codec)
        root,codec,_=self.make(3)
        with self.assertRaises(PilotError):Bank(root,codec,self.windows,limit=128)

    def test_unexpected_symlink_and_hardlink_outputs_are_rejected(self):
        root,codec,_=self.make(3);extra=root/'extra';extra.write_bytes(b'unexpected')
        with self.assertRaises(PilotError):Bank(root,codec,self.windows)
        extra.unlink();path=root/'0000.bin';raw=path.read_bytes();path.unlink();outside=self.root/'raw';outside.write_bytes(raw);path.symlink_to(outside)
        with self.assertRaises(PilotError):Bank(root,codec,self.windows)
        path.unlink();os.link(outside,path)
        with self.assertRaises(PilotError):Bank(root,codec,self.windows)

    def test_bank_keeps_crossings_and_rejects_only_certified_outside_segments(self):
        codec=self.codec();rows=[(1,-SCALE,SCALE//2),(2,2*SCALE,SCALE//2),(3,-2*SCALE,2*SCALE),(4,-SCALE,2*SCALE)]
        writer=Writer(self.root/'bank',OwnedStorage(self.root),self.windows,4)
        writer.append(codec.encode(ReferenceCodec().encode(rows),4,1,4),codec);writer.finish()
        bank=Bank(writer.root,codec,self.windows);self.addCleanup(bank.close)
        self.assertEqual(bank.grid.candidates(bank.lookup([1,2])),['a','b'])
        self.assertEqual(bank.grid.candidates(bank.lookup([3,4])),[])
        with self.assertRaises(PilotError):bank.lookup([3,999])

    def test_close_releases_snapshots_and_refuses_later_queries(self):
        root,codec,_=self.make(3);bank=Bank(root,codec,self.windows);bank.close()
        self.assertEqual(bank.parts,());self.assertEqual(bank.directory,b'')
        with self.assertRaises(PilotError):bank.lookup([1])
