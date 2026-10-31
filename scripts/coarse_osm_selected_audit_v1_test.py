"""Disk audit recreates raw output independently, including dependencies and scopes."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from coarse_osm_native_smoke import fixture_records,STATE
from coarse_osm_records import canonical,intersects
from coarse_osm_selected_store_v1 import SelectedStore
from coarse_osm_selected_audit_v1 import SelectedAudit
from coarse_osm_selected_store_v1_test import Run,WINDOWS
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.proposal={'windows':WINDOWS,'source':{'proposedPublisherReplicationStateUtc':STATE}}
        self.run=Run(self.root);self.primary=SelectedStore(self.root/'primary.sqlite',WINDOWS,self.run)
        self.audit=SelectedAudit(self.root/'audit.sqlite',self.proposal,self.run)
        self.addCleanup(self.primary.close);self.addCleanup(self.audit.close)

    def materialize(self):
        rows=list(fixture_records());nodes={r['id']:r for r in rows if r['type']=='node'}
        for raw in rows:
            if raw['type']!='way' or 'highway' not in raw['tags']:continue
            points=[[nodes[i]['lon'],nodes[i]['lat']] for i in raw['nodes']]
            for window in WINDOWS:
                if intersects(points,window['bbox']):
                    self.primary.add(window['id'],('way',raw['id']))
                    for identity in raw['nodes']:self.primary.add(window['id'],('node',identity))
            if self.primary.contains(('way',raw['id'])):self.primary.keep(raw)
            self.audit.way_with_points(raw,points)
        for raw in rows:
            key=raw['type'],raw['id']
            if raw['type']=='node' and self.primary.contains(key):self.primary.keep(raw);self.audit.keep(raw)
            if raw['type']=='relation' and raw['tags'].get('type')=='restriction':
                self.audit.relation(raw)
                for window in self.primary.linked_windows(raw['members']):self.primary.add(window,key)
                if self.primary.contains(key):self.primary.keep(raw)
        return rows

    def write(self):
        rows=list(self.primary.records());raw=b''.join(canonical(r)+b'\n' for r in rows);path=self.root/'output.jsonl';path.write_bytes(raw)
        self.run.state.update(retainedElements=len(rows),extractBytes=len(raw),windowOccurrences=self.primary.occurrences)
        return path

    def test_full_raw_metadata_scopes_crossings_and_external_members_are_preserved(self):
        self.materialize();path=self.write();self.audit.compare(path)
        rows=list(self.primary.records());self.assertEqual([r['element']['type'] for r in rows],['node','node','relation','way'])
        way=rows[-1]['element'];self.assertEqual(way['tags']['access'],'private');self.assertEqual(way['tags']['maxspeed:conditional'],'35 @ wet')
        self.assertEqual(rows[2]['element']['members'][-1]['ref'],999)
        self.assertEqual(self.primary.seal()['rawBytes'],self.audit.seal()['rawBytes'])

    def test_raw_field_or_window_tampering_is_detected(self):
        self.materialize();raw=self.primary.raw(('way',1));raw['tags']['maxspeed']='99 mph';self.primary.replace(('way',1),raw)
        with self.assertRaises(PilotError):self.audit.compare(self.write())

    def test_hint_only_node_without_independent_membership_fails(self):
        rows=self.materialize();extra=next(r for r in rows if r['type']=='node' and r['id']==3);self.audit.keep(extra)
        with self.assertRaises(PilotError):self.audit.compare(self.write())

    def test_extra_output_bytes_are_rejected(self):
        self.materialize();path=self.write();path.write_bytes(path.read_bytes()+b'{}\n')
        with self.assertRaises(PilotError):self.audit.compare(path)
