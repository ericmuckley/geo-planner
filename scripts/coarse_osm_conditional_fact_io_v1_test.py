"""Exact unchanged-byte streaming and insertion boundaries for typed overlays."""
from array import array
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from coarse_osm_conditional_fact_io_v1 import CHUNK,Rows,Writer,replace_rows,insert_arcs


def source(root,prefix,raw):
    (root/'cost-facts').mkdir(exist_ok=True);roster={}
    for part,at in enumerate(range(0,len(raw),CHUNK)):
        name=f'cost-facts/{prefix}-{part:04d}.bin';chunk=raw[at:at+CHUNK];(root/name).write_bytes(chunk)
        roster[name]={'bytes':len(chunk),'sha256':hashlib.sha256(chunk).hexdigest()}
    return roster


class Tests(unittest.TestCase):
    def test_real_sixteen_mib_boundary_indexing_and_streamed_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=array('I',range(CHUNK//4+2)).tobytes();roster=source(root,'anchors',raw);rows=Rows(root,roster,'anchors','<I')
            try:
                self.assertEqual(rows[CHUNK//4-1],CHUNK//4-1);self.assertEqual(rows[CHUNK//4],CHUNK//4)
                self.assertEqual(b''.join(rows.bytes(CHUNK//4-1,CHUNK//4+2)),raw[-12:]);rows.verify_unchanged()
            finally:rows.close()

    def test_selected_row_replacement_preserves_every_other_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);roster=source(root,'flags',b'\x04\x05\x06\x07');rows=Rows(root,roster,'flags','<B')
            out=root/'out';(out/'cost-facts').mkdir(parents=True);writer=Writer(out,1000)
            try:
                writer.start('flags');replace_rows(rows,{1:4,3:6},writer);writer.finish()
                self.assertEqual((out/'cost-facts/flags-0000.bin').read_bytes(),b'\x04\x04\x06\x06');self.assertEqual(writer.bytes,4)
            finally:writer.finish();rows.close()

    def test_arcs_insert_before_between_and_after_old_groups_without_old_cost_changes(self):
        arc=struct.Struct('<IIIIIb3xQ')
        old=[(0,1,2,0,1,1,1000),(1,2,4,0,1,1,2000)];added=[(0,1,1,0,1,1,3000),(1,0,3,0,1,-1,4000),(0,2,5,0,1,1,5000)]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=b''.join(arc.pack(*r) for r in old);roster=source(root,'arcs',raw);rows=Rows(root,roster,'arcs',arc.format)
            out=root/'out';(out/'cost-facts').mkdir(parents=True);writer=Writer(out,1000)
            try:
                writer.start('arcs');insertions=insert_arcs(rows,added,writer);writer.finish()
                actual=list(arc.iter_unpack((out/'cost-facts/arcs-0000.bin').read_bytes()))
                self.assertEqual(actual,[added[0],old[0],added[1],old[1],added[2]])
                self.assertEqual([r['oldArcInsertion'] for r in insertions],[0,1,2]);self.assertEqual([r['newArcFirst'] for r in insertions],[0,2,4])
            finally:writer.finish();rows.close()

    def test_wrong_hash_unaligned_or_symlink_input_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);roster=source(root,'ways',b'1234');name=next(iter(roster))
            with self.assertRaises(AssertionError):Rows(root,{name:roster[name]|{'sha256':'0'*64}},'ways','<I')
            with self.assertRaises(AssertionError):Rows(root,roster,'ways','<Q')
            (root/name).unlink();(root/'target').write_bytes(b'1234');(root/name).symlink_to(root/'target')
            with self.assertRaises(AssertionError):Rows(root,roster,'ways','<I')

    def test_output_cap_and_existing_path_preserve_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'cost-facts').mkdir();writer=Writer(root,3);writer.start('flags')
            try:
                with self.assertRaises(AssertionError):writer.append(b'1234')
                self.assertEqual(writer.bytes,0)
                (root/'cost-facts/flags-0000.bin').write_bytes(b'original')
                with self.assertRaises(FileExistsError):writer.append(b'x')
                self.assertEqual((root/'cost-facts/flags-0000.bin').read_bytes(),b'original')
            finally:writer.finish()

    def test_source_drift_and_inserting_into_existing_way_group_rejected(self):
        arc=struct.Struct('<IIIIIb3xQ');row=(0,1,2,0,1,1,1000)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);roster=source(root,'arcs',arc.pack(*row));rows=Rows(root,roster,'arcs',arc.format)
            out=root/'out';(out/'cost-facts').mkdir(parents=True);writer=Writer(out,1000)
            try:
                writer.start('arcs')
                with self.assertRaises(AssertionError):insert_arcs(rows,[row],writer)
                (root/next(iter(roster))).write_bytes(arc.pack(*row[:-1],999))
                with self.assertRaises(AssertionError):rows.verify_unchanged()
            finally:writer.finish();rows.close()
