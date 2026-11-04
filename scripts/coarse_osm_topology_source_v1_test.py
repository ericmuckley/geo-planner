"""Inherit frozen validators and independently qualify new typed source emission."""
import struct
import unittest

import coarse_osm_footprint_v1_test as prior
from coarse_osm_topology_source_v1 import NativeScreen
from coarse_osm_country_wire_v4 import framed_records
from coarse_osm_native_smoke import STATE,fixture_records
from coarse_osm_footprint_summary_v1 import MAJOR
from coarse_timing_input import PilotError

ARTIFACT=None


class Tests(prior.Tests):
    def engine(self,**kwargs):
        if ARTIFACT is None:self.skipTest('Compiled target topology source required')
        return NativeScreen(*ARTIFACT,**kwargs)
    def test_exact_typed_streams_include_all_tags_relations_and_long_way_refs(self):
        rows=prior.fixture();raw={k:bytearray() for k in (10,11,12,13)}
        receipt=self.engine().validate_frames(framed_records(rows),STATE,self.caps,on_topology=lambda k,b:raw[k].extend(b),presence_max_node_id=4)
        ways=[r for r in rows if r['type']=='way' and r['tags'].get('highway') in MAJOR]
        expected=[(node,r['id'],1 if k in (0,len(r['nodes'])-1) else 2,int(k in (0,len(r['nodes'])-1))) for r in ways for k,node in enumerate(r['nodes'])]
        self.assertEqual(list(struct.iter_unpack('<QQII',raw[11])),expected)
        self.assertEqual([n[0] for n in struct.iter_unpack('<Q',raw[10])],[r['id'] for r in rows if r['type']=='node' and r['tags']])
        for event,kind in ((12,'node'),(13,'way')):
            self.assertEqual([n[0] for n in struct.iter_unpack('<Q',raw[event])],[m['ref'] for r in rows if r['type']=='relation' for m in r['members'] if m['type']==kind])
        self.assertEqual(receipt['pythonProjectionFrames'],0);self.assertEqual(receipt['topologyWays'],len(ways))
    def test_missing_selected_source_node_and_presence_cap_stop(self):
        rows=fixture_records();rows[4]=dict(rows[4],nodes=[1,5])
        for sample,maximum in ((rows,5),(fixture_records(),3)):
            engine=self.engine()
            with self.assertRaisesRegex(PilotError,'topology_'):engine.validate_frames(framed_records(sample),STATE,self.caps,on_topology=lambda k,b:None,presence_max_node_id=maximum)
            self.assertFalse(engine.last['nativeEof'])
    def test_typed_sink_failure_is_not_source_eof(self):
        engine=self.engine()
        def fail(k,b):raise PilotError('topology sink refused')
        with self.assertRaisesRegex(PilotError,'topology sink refused'):engine.validate_frames(framed_records(fixture_records()),STATE,self.caps,on_topology=fail,presence_max_node_id=4)
        self.assertFalse(engine.last['nativeEof'])
    def test_presence_resource_bounds_and_prior_abi_are_rejected(self):
        for maximum in (0,True,14319708501):
            with self.assertRaises(PilotError):self.engine().validate_frames(b'',STATE,self.caps,on_topology=lambda k,b:None,presence_max_node_id=maximum)
