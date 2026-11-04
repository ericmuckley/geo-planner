from pathlib import Path
import hashlib
import tempfile
import unittest
from unittest.mock import patch

from coarse_osm_relation_tail_v1_test import source, STATE
from coarse_osm_water_relations_v1 import water_relations, source_guard
from coarse_osm_water_relation_store_v1 import RelationStore, audit


def row(identity=1, **edits):
    return {'id':identity,'tags':{'type':'multipolygon','natural':'water'},
            'members':[('way',99,'outer'),('way',22,'inner'),('way',99,'outer'),
                       ('relation',88,'inner'),('node',7,'label'),('way',11,'')],**edits}


class Controls(unittest.TestCase):
    def guarded_source(self, edit=None, callback=lambda: None, link=False):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.pbf';raw=source([row()]);path.write_bytes(raw)
            expected={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'md5':hashlib.md5(raw).hexdigest()}
            if edit:expected.update(edit)
            if link:
                other=Path(directory)/'link.pbf';other.symlink_to(path);path=other
            return source_guard(path,expected,callback)

    def test_source_guard_hashes_complete_tiny_pbf(self):
        self.assertEqual(self.guarded_source()['bytes'],len(source([row()])))

    def test_source_guard_wrong_hash_md5_and_size_stop(self):
        for edit in ({'sha256':'0'*64},{'md5':'0'*32},{'bytes':1},{'bytes':100000}):
            with self.subTest(edit=edit),self.assertRaises(Exception):self.guarded_source(edit)

    def test_source_guard_rejects_symlink(self):
        with self.assertRaises(Exception):self.guarded_source(link=True)

    def test_source_guard_cancellation_propagates(self):
        def stop():raise TimeoutError('cancel')
        with self.assertRaises(TimeoutError):self.guarded_source(callback=stop)

    def scan(self, raw, count, **caps):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'source.pbf'
            path.write_bytes(raw)
            rows = []
            stats = water_relations(path,source_bytes=len(raw),state=STATE,expected_relations=count,consume=rows.append,**caps)
            return rows,stats

    def test_all_selector_arms_and_unrelated_records(self):
        rows,stats = self.scan(source([row(1),row(2,tags={'waterway':'riverbank'}),row(3,tags={'landuse':'reservoir'}),
                                             row(4,tags={'type':'route'}),row(5,tags={'natural':'Water'})]),5)
        self.assertEqual([r['id'] for r in rows],[1,2,3])
        self.assertEqual(stats['waterRecordsSelected'],3)
        self.assertEqual(stats['relations'],5)
        self.assertEqual(stats['nodeWayObjectsProjected'],0)

    def test_exact_roles_order_duplicates_nested_metadata_and_unicode(self):
        value = row(tags={'type':'multipolygon','natural':'water','name':'café 雪'})
        rows,_ = self.scan(source([value]),1)
        self.assertEqual(rows,[{'type':'relation','id':1,'version':3,'timestamp':STATE,'visible':True,
                               'tags':value['tags'],'members':[{'type':k,'ref':i,'role':r} for k,i,r in value['members']]}])

    def test_invalid_selected_metadata_and_member_types_stop(self):
        for edit in ({'version':0},{'visible':0},{'members':[('invalid',1,'outer')]},{'members':[('way',0,'outer')]}):
            with self.subTest(edit=edit),self.assertRaises(Exception):
                self.scan(source([row(**edit)]),1)

    def test_complete_count_order_and_tail_are_required(self):
        for raw,count,caps in [(source([row(1),row(1)]),2,{}),(source([row()]),2,{}),
                               (source([row(1),row(2)],separate=True),2,{'tail_bytes':1})]:
            with self.assertRaises(Exception): self.scan(raw,count,**caps)

    def test_corruption_and_decoded_byte_cap_stop(self):
        raw = source([row()])
        for value,caps in [(raw[:-1],{}),(raw,{'decoded_cap':1}),(raw,{'frame_cap':1})]:
            with self.assertRaises(Exception): self.scan(value,1,**caps)

    def test_generated_selection_and_members_independently_exact(self):
        inputs = [row(i,tags={'natural':'water'} if i%3 else {'water':'lake'}) for i in range(1,101)]
        rows,stats = self.scan(source(inputs,separate=True),100)
        self.assertEqual([r['id'] for r in rows],[i for i in range(1,101) if i%3])
        self.assertEqual(sum(len(r['members']) for r in rows),67*6)
        self.assertEqual(stats['waterRecordsSelected'],67)

    def store(self, root):
        elements,_ = self.scan(source([row(1),row(2,tags={'landuse':'reservoir'})]),2)
        with RelationStore(root) as store:
            for element in elements: store.consume(element)
            return store.finish()

    def test_store_preserves_every_member_and_audits_unique_way_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.store(root)
            self.assertEqual(report['uniqueMemberWays'],3)
            self.assertEqual(report['counts'],{'relations':2,'wayMembers':8,'nodeMembers':2,'relationMembers':2,
                                               'outerWayMembers':4,'innerWayMembers':2,'otherRoleWayMembers':2,
                                               'multipolygons':1,'otherTypes':1,'maxMembers':6})
            self.assertEqual(audit(root,report)['allMemberOccurrencesChecked'],12)

    def test_independent_audit_rejects_member_index_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); report = self.store(root)
            path = root/'member-way-ids.u64'; path.write_bytes(b'X'+path.read_bytes()[1:])
            with self.assertRaises(Exception): audit(root,report)

    def test_independent_audit_rejects_trailing_index_and_gzip_corruption(self):
        for filename in ('member-way-ids.u64','water-relations.jsonl.gz'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory); report=self.store(root);path=root/filename
                path.write_bytes(path.read_bytes()+b'X')
                with self.assertRaises(Exception):audit(root,report)

    def test_output_raw_cap_stops_before_complete_receipt(self):
        with tempfile.TemporaryDirectory() as directory,patch('coarse_osm_water_relation_store_v1.MAX_RAW',1):
            with self.assertRaises(Exception):self.store(Path(directory))

    def test_output_member_cap_stops_without_silent_drop(self):
        with tempfile.TemporaryDirectory() as directory,patch('coarse_osm_water_relation_store_v1.MAX_MEMBERS',1):
            with self.assertRaises(Exception):self.store(Path(directory))

    def test_audit_cancel_propagates(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);report=self.store(root)
            def stop():raise TimeoutError('cancel')
            with self.assertRaises(TimeoutError):audit(root,report,stop)


if __name__ == '__main__':unittest.main()
