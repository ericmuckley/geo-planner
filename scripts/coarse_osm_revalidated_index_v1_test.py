"""Fresh source blocks revalidate a read-only input; never repair failed bytes."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from coarse_osm_country_screen_v1 import BoundedCodec,OwnedStorage
from coarse_osm_delta_v1 import ReferenceCodec,ROWS
from coarse_osm_projector_v1 import EncodedIndex,BLOCK_EVENT
from coarse_osm_revalidated_index_v1 import SourceIndex
from coarse_timing_input import PilotError

ARTIFACT=None
CODECS=[]


def configure_native(path,sha):
    global ARTIFACT
    ARTIFACT=path,sha


def event(rows):
    payload=ReferenceCodec().encode(rows)
    return BLOCK_EVENT.pack(len(rows),rows[0][0],rows[-1][0],len(payload))+payload


class NativeTests(unittest.TestCase):
    def setUp(self):
        if ARTIFACT is None:self.skipTest('Qualified native artifact required')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def fixture(self,count=4097):
        codec=BoundedCodec(*ARTIFACT,row_budget=2000000);CODECS.append(codec)
        index=EncodedIndex(self.root/'input',OwnedStorage(self.root),codec=codec,index_limit=4*1024**2)
        rows=[(2*i+1,i%100,0) for i in range(count)]
        for row in rows:index.add_xy(*row)
        index.finish();index.close();manifest=json.loads((index.root/'index.json').read_text())
        return index.root,codec,manifest,rows

    def feed(self,index,codec,rows):
        for start in range(0,len(rows),ROWS):index.append_encoded(event(rows[start:start+ROWS]),codec)

    def test_full_node_comparison_and_repeat_finish_verify_without_writes(self):
        root,codec,manifest,rows=self.fixture();before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
        index=SourceIndex(root,codec,manifest);self.addCleanup(index.close);self.feed(index,codec,rows);index.finish();index.finish()
        self.assertEqual(index.report()['nodeRowsCompared'],4097);self.assertEqual(index.report()['sourceBlocksCompared'],2)
        self.assertEqual(index.report()['sourceShardsCompared'],1);self.assertEqual(index.report()['wholeFileVerificationPasses'],1)
        self.assertEqual(index.payload_bytes_read,3*manifest['shards'][0]['bytes'])
        self.assertTrue(index.report()['wholeSourceEofStillRequiredFromCaller'])
        self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()})

    def test_mismatched_source_coordinate_is_rejected_without_repair(self):
        root,codec,manifest,rows=self.fixture(2);before=(root/'00000000.bin').read_bytes();index=SourceIndex(root,codec,manifest);self.addCleanup(index.close)
        changed=deepcopy(rows);changed[1]=(changed[1][0],42,43)
        with self.assertRaises(PilotError):index.append_encoded(event(changed),codec)
        self.assertEqual((root/'00000000.bin').read_bytes(),before);self.assertFalse(index.finished)

    def test_missing_duplicate_extra_and_out_of_order_blocks_fail(self):
        root,codec,manifest,rows=self.fixture();index=SourceIndex(root,codec,manifest);self.addCleanup(index.close)
        index.append_encoded(event(rows[:ROWS]),codec)
        with self.assertRaises(PilotError):index.finish()
        with self.assertRaises(PilotError):index.append_encoded(event(rows[:ROWS]),codec)
        index.append_encoded(event(rows[ROWS:]),codec);index.finish()
        with self.assertRaises(PilotError):index.append_encoded(event(rows[ROWS:]),codec)

    def test_same_mtime_payload_drift_after_snapshot_is_detected_before_finish(self):
        root,codec,manifest,rows=self.fixture();index=SourceIndex(root,codec,manifest);self.addCleanup(index.close)
        index.append_encoded(event(rows[:ROWS]),codec);path=root/'00000000.bin';before=path.stat();raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw);os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
        index.append_encoded(event(rows[ROWS:]),codec)
        with self.assertRaises(PilotError):index.finish()
        self.assertEqual(path.read_bytes(),raw)

    def test_source_census_and_sidecar_drift_are_not_admitted(self):
        root,codec,manifest,rows=self.fixture(2);changed=deepcopy(manifest);changed['rows']+=1
        with self.assertRaises(PilotError):SourceIndex(root,codec,changed)
        index=SourceIndex(root,codec,manifest);self.addCleanup(index.close);self.feed(index,codec,rows);index.finish()
        path=root/'index.json';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(PilotError):index.finish()

    def test_payload_io_limit_precedes_input_read(self):
        root,codec,manifest,rows=self.fixture(2);index=SourceIndex(root,codec,manifest,read_limit=1);self.addCleanup(index.close)
        with self.assertRaises(PilotError):index.append_encoded(event(rows),codec)
        self.assertEqual(index.payload_bytes_read,0)

    def test_independent_view_needs_completed_same_input_and_detects_late_drift(self):
        root,codec,manifest,rows=self.fixture(2);first=SourceIndex(root,codec,manifest);self.addCleanup(first.close)
        with self.assertRaises(PilotError):SourceIndex(root,codec,manifest,replacing=first)
        self.feed(first,codec,rows);first.finish();second=SourceIndex(root,codec,manifest,replacing=first);self.addCleanup(second.close)
        self.feed(second,codec,rows);second.finish();(root/'unexpected').write_bytes(b'foreign')
        with self.assertRaises(PilotError):second.finish()
