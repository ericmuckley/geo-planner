from pathlib import Path
import tempfile
import unittest

import coarse_osm_water_relations_v1_test as previous
from coarse_osm_relation_tail_v1_test import source, STATE
from coarse_osm_selected_relations_v2 import selected_relation_rows
from coarse_osm_water_closure_v1 import resolve, audit_saved, save_way_ids
from coarse_osm_water_relation_store_v1 import RelationStore


class ReaderControls(previous.Controls):
    def scan(self, raw, count, **caps):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.pbf';path.write_bytes(raw);rows=[]
            stats=selected_relation_rows(path,source_bytes=len(raw),state=STATE,expected_relations=count,consume=rows.append,
                select=lambda _,tags:tags.get('natural')=='water' or tags.get('waterway')=='riverbank' or tags.get('landuse')=='reservoir',**caps)
            stats['waterRecordsSelected']=stats.pop('recordsSelected')
            return rows,stats


def relation(identity, children=(), ways=()):
    return {'type':'relation','id':identity,'version':1,'timestamp':STATE,'visible':True,'tags':{'type':'multipolygon'},
            'members':[{'type':'relation','ref':i,'role':'outer'} for i in children]+
                      [{'type':'way','ref':i,'role':'inner'} for i in ways]}


class ClosureControls(unittest.TestCase):
    def test_transitive_untagged_descendants_and_complete_union(self):
        roots={1:relation(1,[100],[11])};source_rows={100:relation(100,[90],[22]),90:relation(90,[],[33])}
        children,ways,report=resolve(roots,lambda ids:[source_rows[i] for i in ids if i in source_rows])
        self.assertEqual(set(children),{90,100});self.assertEqual(ways,[11,22,33])
        self.assertTrue(report['referenceClosureComplete'] and report['acyclic'])
        self.assertEqual(len(report['rounds']),2)

    def test_source_absent_ids_preserved_without_retry(self):
        calls=[]
        def fetch(ids):calls.append(ids);return []
        _,_,report=resolve({1:relation(1,[9])},fetch)
        self.assertEqual(calls,[{9}]);self.assertEqual(report['sourceAbsentRelationIds'],[9])
        self.assertFalse(report['referenceClosureComplete'])

    def test_cycles_are_explicit_and_do_not_loop(self):
        _,_,report=resolve({1:relation(1,[2])},lambda ids:[relation(2,[1])])
        self.assertTrue(report['referenceClosureComplete']);self.assertFalse(report['acyclic'])
        self.assertEqual(report['cycleBackEdges'],[[2,1]])

    def test_depth_cap_preserves_remaining_ids(self):
        _,_,report=resolve({1:relation(1,[2])},lambda ids:[relation(i,[i+1]) for i in ids],max_rounds=2)
        self.assertEqual(report['depthLimitedRelationIds'],[4]);self.assertEqual(report['sourceAbsentRelationIds'],[])
        self.assertFalse(report['referenceClosureComplete'])

    def test_nonrequested_duplicate_and_member_caps_stop(self):
        for fetch,limits in [(lambda ids:[relation(8)],{}),(lambda ids:[relation(2),relation(2)],{}),
                             (lambda ids:[relation(2)],{'max_new':0}),(lambda ids:[relation(2,ways=[9,10])],{'max_members':1})]:
            with self.assertRaises(Exception):resolve({1:relation(1,[2])},fetch,**limits)

    def test_selected_by_id_projects_untagged_members_without_rewriting(self):
        raw=source([previous.row(1),previous.row(2,tags={'type':'multipolygon'}),previous.row(3,tags={'type':'route'})])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'tiny.pbf';path.write_bytes(raw);rows=[]
            scan=selected_relation_rows(path,source_bytes=len(raw),state=STATE,expected_relations=3,consume=rows.append,select=lambda i,_:i==2)
            self.assertEqual([r['id'] for r in rows],[2]);self.assertEqual(rows[0]['tags'],{'type':'multipolygon'})
            self.assertEqual(scan['relations'],3);self.assertEqual(scan['recordsSelected'],1)

    def saved(self, root):
        roots={1:relation(1,[2],[11])}
        children,ways,report=resolve(roots,lambda ids:[relation(2,ways=[22])])
        with RelationStore(root) as store:
            for i in sorted(children):store.consume(children[i])
            stored=store.finish()
        save_way_ids(root/'closure-member-way-ids.u64',ways)
        return roots,stored,report

    def test_saved_closure_independent_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);roots,stored,report=self.saved(root)
            proof=audit_saved(root,roots,stored,report)
            self.assertEqual(proof['allDescendantsChecked'],1);self.assertEqual(proof['allUniqueWayIdsChecked'],2)

    def test_saved_closure_corruption_and_missing_ledger_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);roots,stored,report=self.saved(root)
            with self.assertRaises(Exception):audit_saved(root,roots,stored,report|{'sourceAbsentRelationIds':[99]})
            path=root/'closure-member-way-ids.u64';path.write_bytes(b'X'+path.read_bytes()[1:])
            with self.assertRaises(Exception):audit_saved(root,roots,stored,report)


if __name__=='__main__':unittest.main()
