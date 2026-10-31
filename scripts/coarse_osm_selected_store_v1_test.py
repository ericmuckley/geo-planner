"""Selected-state identity, ordering, caps, transaction and independent raw-data checks."""
from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import unittest

from coarse_osm_selected_store_v1 import SelectedStore,CACHE_BYTES,MAX_PAGES
from coarse_osm_native_smoke import fixture_records,STATE
from coarse_timing_input import PilotError

WINDOWS=[{'id':'z-last-lexically','bbox':[0,0,1,1]},{'id':'a-first-lexically','bbox':[.25,.25,.75,.75]}]


class Run:
    def __init__(self,root,**caps):
        self.root=Path(root);self.state={'publisherStateUtc':STATE};self.memory=0
        self.caps={'selectedUniqueTypedElements':2000000,'selectedWindowElementOccurrences':4000000,
                   'retainedNativeObjectBytes':512*1024**2,'singleNormalizedElementBytes':8*1024**2,**caps}
    def charge(self,size):self.memory+=size


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def store(self,name='selected.sqlite',*,windows=WINDOWS,max_pages=MAX_PAGES,**caps):
        store=SelectedStore(self.root/name,windows,Run(self.root,**caps),max_pages=max_pages);self.addCleanup(store.close);return store

    def test_native_fields_ordered_duplicates_and_window_order_survive_streaming(self):
        store=self.store();rows=list(fixture_records());nodes=rows[:2];way=next(row for row in rows if row['type']=='way')
        for raw in [*nodes,way]:
            for window in WINDOWS:store.add(window['id'],(raw['type'],raw['id']))
            store.keep(raw)
        output=list(store.records());self.assertEqual([r['element'] for r in output],[*nodes,way])
        self.assertTrue(all(r['windowIds']==[w['id'] for w in WINDOWS] for r in output));self.assertIn('geometryDependencySha256',output[-1])
        self.assertEqual(store.node_ids(),[nodes[0]['id'],nodes[1]['id']]);self.assertEqual(store.seal()['unique'],3)

    def test_raw_snapshots_are_detached_and_replacement_is_explicit(self):
        store=self.store();raw=list(fixture_records())[0];key=raw['type'],raw['id'];store.add(WINDOWS[0]['id'],key);store.keep(raw)
        changed=store.raw(key);changed['tags']['extra']='changed';self.assertEqual(store.raw(key),raw)
        store.replace(key,changed);self.assertEqual(store.raw(key),changed);self.assertEqual(store.seal()['objects'],1)
        with self.assertRaises(PilotError):store.replace(key,raw)

    def test_primary_and_audit_database_values_remain_independent(self):
        left=self.store('primary.sqlite');right=self.store('audit.sqlite');raw=list(fixture_records())[0];key=raw['type'],raw['id']
        for store in [left,right]:store.add(WINDOWS[0]['id'],key);store.keep(raw)
        changed=deepcopy(raw);changed['tags']['barrier']='different';left.replace(key,changed)
        self.assertNotEqual(list(left.records()),list(right.records()));self.assertEqual(right.raw(key),raw)

    def test_missing_geometry_and_materialization_fail_closed(self):
        store=self.store();store.add(WINDOWS[0]['id'],('node',1))
        with self.assertRaises(PilotError):store.seal()
        self.assertTrue(store.failed)
        with self.assertRaises(PilotError):store.add(WINDOWS[0]['id'],('node',2))
        other=self.store('missing-node.sqlite');way=next(r for r in fixture_records() if r['type']=='way');other.add(WINDOWS[0]['id'],('way',way['id']));other.keep(way)
        with self.assertRaises(PilotError):list(other.records())

    def test_count_occurrence_raw_and_typed_id_caps_stop_before_admission(self):
        raw=list(fixture_records())[0]
        for name,caps,action in [
            ('unique',{'selectedUniqueTypedElements':1},lambda s:s.add(WINDOWS[0]['id'],('node',2))),
            ('occurrence',{'selectedWindowElementOccurrences':1},lambda s:s.add(WINDOWS[1]['id'],('node',1))),
            ('raw',{'retainedNativeObjectBytes':1},lambda s:s.keep(raw)),
            ('typed',{},lambda s:s.add(WINDOWS[0]['id'],('node',True))),
            ('width',{},lambda s:s.add(WINDOWS[0]['id'],('node',2**63)))]:
            store=self.store(name+'.sqlite',**caps);store.add(WINDOWS[0]['id'],('node',1))
            with self.assertRaises(PilotError):action(store)
            self.assertTrue(store.failed)

    def test_duplicate_membership_is_idempotent_but_duplicate_raw_objects_fail(self):
        store=self.store();raw=list(fixture_records())[0];key=raw['type'],raw['id']
        store.add(WINDOWS[0]['id'],key);store.add(WINDOWS[0]['id'],key);self.assertEqual(store.occurrences,1)
        store.keep(raw)
        with self.assertRaises(PilotError):store.keep(raw)

    def test_relation_links_preserve_external_members_without_recursive_resolution(self):
        store=self.store();store.add(WINDOWS[1]['id'],('node',2))
        members=[{'type':'way','ref':999,'role':'from'},{'type':'node','ref':2,'role':'via'},{'type':'relation','ref':2,'role':'to'}]
        self.assertEqual(store.linked_windows(members),[WINDOWS[1]['id']])

    def test_full_signed_id_width_and_unicode_metadata_are_lossless(self):
        store=self.store();raw=deepcopy(list(fixture_records())[0]);raw['id']=2**63-1;raw['tags']['note']='é 😀\nraw'
        store.add(WINDOWS[0]['id'],('node',raw['id']));store.keep(raw)
        self.assertEqual(store.node_ids(),[2**63-1]);self.assertEqual(store.raw(('node',2**63-1)),raw);store.seal()

    def test_owned_fresh_path_and_closed_state_are_mandatory(self):
        store=self.store()
        with self.assertRaises(PilotError):self.store()
        with self.assertRaises(PilotError):SelectedStore(self.root.parent/'outside.sqlite',WINDOWS,Run(self.root))
        store.close()
        with self.assertRaises(PilotError):store.contains(('node',1))

    def test_sqlite_page_cache_and_journal_guards_are_real(self):
        store=self.store(max_pages=8);raw=list(fixture_records())[0];raw['tags']['large']='x'*32768
        self.assertEqual(store.conn.execute('PRAGMA cache_size').fetchone()[0],-8192)
        self.assertEqual(store.conn.execute('PRAGMA journal_mode').fetchone()[0],'delete')
        with self.assertRaises(sqlite3.DatabaseError):store.keep(raw)
        self.assertTrue(store.failed);self.assertLessEqual(store.path.stat().st_size,8*4096)
        self.assertEqual(store.run.memory,CACHE_BYTES+65536)

    def test_configuration_and_membership_corruption_prevent_seal(self):
        for name,sql in [('config','PRAGMA cache_size=-4096'),('members','DELETE FROM memberships')]:
            store=self.store(name+'.sqlite');raw=list(fixture_records())[0];store.add(WINDOWS[0]['id'],('node',raw['id']));store.keep(raw);store.conn.execute(sql)
            with self.assertRaises(PilotError):store.seal()

    def test_more_than_old_unique_and_occurrence_limits_without_python_record_retention(self):
        store=self.store()
        for identity in range(1,250002):
            for window in WINDOWS:store.add(window['id'],('node',identity))
            store.keep({'type':'node','id':identity,'version':1,'timestamp':STATE,'visible':True,'tags':{},'lat':0.25,'lon':identity/10000000})
        self.assertEqual((store.unique,store.occurrences),(250001,500002));self.assertEqual(len(store.node_ids()),250001)
        self.assertEqual(store.run.memory,CACHE_BYTES+65536);self.assertGreater(store.commits,1)
        self.assertLess(store.path.stat().st_size,128*1024**2)
        self.assertEqual(store.seal()['objects'],250001)
