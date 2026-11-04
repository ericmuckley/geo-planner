from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coarse_osm_water_reference_store_v1 import Budget, Shards, Reader, ReferenceStore


class Controls(unittest.TestCase):
    def packed(self,root):
        raw=bytes(range(256))*3
        writer=Shards(root,'test',Budget())
        try:
            for cursor in range(0,len(raw),91):writer.write(raw[cursor:cursor+91])
            return raw,writer.finish()
        finally:writer.close()

    def test_bounded_reader_crosses_many_shards_exactly(self):
        with tempfile.TemporaryDirectory() as directory,patch('coarse_osm_water_reference_store_v1.PART_BYTES',64):
            raw,report=self.packed(Path(directory))
            with Reader(directory,report) as reader:
                chunks=[]
                while body:=reader.read(31):chunks.append(body)
                self.assertEqual(b''.join(chunks),raw);self.assertTrue(reader.finished)
            self.assertEqual(len(report['parts']),12)

    def test_corrupt_file_hash_and_missing_shard_stop(self):
        for remove in (False,True):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);_,report=self.packed(root);path=root/report['parts'][0]['name']
                if remove:path.unlink()
                else:path.write_bytes(path.read_bytes()+b'X')
                with self.assertRaises(Exception),Reader(root,report) as reader:reader.read(1000)

    def test_raw_part_seal_and_total_seal_are_required(self):
        for field in ('part','total'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);_,report=self.packed(root)
                if field=='part':report['parts'][0]['rawSha256']='0'*64
                else:report['rawSha256']='0'*64
                with self.assertRaises(Exception),Reader(root,report) as reader:reader.read(1000)

    def test_decompression_cannot_exceed_manifest_raw_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);_,report=self.packed(root);report['parts'][0]['rawBytes']=report['rawBytes']=1
            with self.assertRaises(Exception),Reader(root,report) as reader:reader.read(1000)

    def test_reference_store_exact_byte_states_and_empty_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            with ReferenceStore(directory,raw_way_bytes=0,reference_count=0) as store:
                store.prepare_nodes();report=store.finish(0)
                self.assertEqual(report['compressedBytes'],0)
                with self.assertRaises(Exception):store.finish(0)
                with self.assertRaises(Exception):store.way_chunk(b'X')
            with Reader(directory,report['ways']) as reader:self.assertEqual(reader.read(1),b'')

    def test_compressed_budget_and_incomplete_byte_count_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            with ReferenceStore(directory,raw_way_bytes=1,reference_count=0,budget=1) as store:
                with self.assertRaises(Exception):store.way_chunk(b'X')
        with tempfile.TemporaryDirectory() as directory:
            with ReferenceStore(directory,raw_way_bytes=2,reference_count=0) as store:
                store.way_chunk(b'X')
                with self.assertRaises(Exception):store.prepare_nodes()

    def test_path_traversal_and_symlinks_are_rejected(self):
        for mode in ('path','symlink'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);_,report=self.packed(root);part=report['parts'][0]
                if mode=='path':part['name']='../'+part['name']
                else:
                    path=root/part['name'];target=root/'target.gz';path.rename(target);path.symlink_to(target)
                with self.assertRaises(Exception),Reader(root,report) as reader:reader.read(1)

    def test_closed_writer_and_unbounded_reader_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);writer=Shards(root,'test',Budget());writer.finish()
            with self.assertRaises(Exception):writer.write(b'X')
            with self.assertRaises(Exception):writer.finish()
            _,report=self.packed(root)
            with Reader(root,report) as reader:
                for size in (0,-1,8388609):
                    with self.assertRaises(Exception):reader.read(size)


if __name__=='__main__':unittest.main()
