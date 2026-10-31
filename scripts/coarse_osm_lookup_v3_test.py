"""Search-width, ordered-coordinate, cache and unchanged integrity controls."""
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest

from coarse_osm_country_screen_v1 import ProbeReader
from coarse_osm_delta_v2 import Index,ReferenceCodec,Storage,MAX_ID
from coarse_osm_lookup_v3 import Reader
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def index(self,rows):
        index=Index(self.root/'index',Storage(64*1024**2,64*1024**2),codec=ReferenceCodec())
        for row in rows:index.add_xy(*row)
        index.finish();return index

    def test_signed63_gaps_duplicates_and_exact_coordinate_bits(self):
        rows=[(1,-1800000000,-900000000),(2**31,1,-1),(2**40,0,0),(MAX_ID,1800000000,900000000)]
        index=self.index(rows);reader=Reader(index.root,ReferenceCodec());self.addCleanup(reader.close)
        keys=[MAX_ID,1,2**40,2**31,MAX_ID]
        coords={identity:(x/10000000,y/10000000) for identity,x,y in rows}
        self.assertEqual(b''.join(struct.pack('<dd',*point) for point in reader.points(keys)),b''.join(struct.pack('<dd',*coords[key]) for key in keys))
        for key in [0,True,2,MAX_ID+1]:
            with self.assertRaises(PilotError):reader.points([key])
        with self.assertRaises(PilotError):reader.points([1]*65537)
        reader.close()
        with self.assertRaises(PilotError):reader.points([1])

    def test_baseline_and_candidate_authenticate_identical_bytes_and_cache_sequence(self):
        index=Index(self.root/'index',Storage(64*1024**2,64*1024**2),codec=ReferenceCodec())
        for identity in range(1,71):index.add_xy(identity,identity,-identity);index.flush_block()
        index.finish();old=ProbeReader(index.root,ReferenceCodec());new=Reader(index.root,ReferenceCodec())
        self.addCleanup(old.close);self.addCleanup(new.close)
        for keys in [list(range(70,0,-1))+[1,1],list(range(1,71)),[70,1,70]]:
            self.assertEqual(old.points(keys),new.points(keys))
            for name in ['loaded_bytes','hits','misses','evictions','catalog_bytes']:
                self.assertEqual(getattr(old,name),getattr(new,name))
        self.assertEqual(len(new.cache),64)

    def test_same_metadata_shard_drift_is_rejected_after_warm_cache(self):
        index=self.index([(1,0,0),(2,1,1)]);reader=Reader(index.root,ReferenceCodec());self.addCleanup(reader.close)
        reader.points([1]);path=index.path(0);before=path.stat();raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)
        os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
        with self.assertRaises(PilotError):reader.points([1])

    def test_cached_search_keys_never_bypass_catalog_drift(self):
        index=self.index([(1,0,0),(2,1,1)]);reader=Reader(index.root,ReferenceCodec());self.addCleanup(reader.close)
        reader.points([1]);path=index.root/'directory.bin';raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)
        with self.assertRaises(PilotError):reader.points([1])

    def test_full_national_directory_search_keys_without_payload_allocation(self):
        folder=Path('/inputs/global')
        if not folder.exists():folder=Path(__file__).resolve().parents[1]/'docs/evidence/coarse-osm-country-exec-2026-10-30/screen-raw-v4/screen/pass-b'
        root=self.root/'catalog';root.mkdir()
        shutil.copyfile(folder/'global-catalog.json',root/'index.json');shutil.copyfile(folder/'global-directory.bin',root/'directory.bin')
        reader=Reader(root,ReferenceCodec(),index_limit=24*1024**3,catalog_limit=16*1024**2);self.addCleanup(reader.close)
        self.assertEqual(len(reader.block_ends),392146);self.assertEqual(len(reader.block_ends)*8,3137168)
        self.assertTrue(all(value==reader.entry(i)[0] for i,value in enumerate(reader.block_ends)))
        self.assertGreater(reader.block_ends[-1],2**32)
        self.assertEqual(list(root.glob('[0-9]*.bin')),[])

    def test_io_guard_still_refuses_before_an_extra_authenticated_read(self):
        index=self.index([(1,0,0),(2,1,1)]);size=index.reader.manifest['shards'][0]['bytes']
        reader=Reader(index.root,ReferenceCodec(),read_limit=2*size);self.addCleanup(reader.close)
        reader.points([1])
        with self.assertRaises(PilotError):reader.points([1])
