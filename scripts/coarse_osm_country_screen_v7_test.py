"""Selected-ID ABI, full-field projections and unchanged source error guards."""
from copy import deepcopy
import unittest

from coarse_osm_country_screen_v7 import NativeScreen
from coarse_osm_country_wire_v4 import framed_records,reference_seal
from coarse_osm_native_smoke import fixture_records,STATE
from coarse_timing_input import PilotError

ARTIFACT=None
ENGINES=[]


def configure_native(path,sha):
    global ARTIFACT
    ARTIFACT=path,sha


def caps(nodes=2000000):
    return {'singleNormalizedElementBytes':4194304,'scanNodesPerPass':nodes,'scanWaysPerPass':1000,'scanRelationsPerPass':1000,
            'scanObjectVisitsTotal':2000000,'pbfHeaderBytesExclusiveMaximum':65536,'pbfUncompressedBlobBytesExclusiveMaximum':33554432}


class Tests(unittest.TestCase):
    def engine(self,**options):
        if ARTIFACT is None:self.skipTest('Compiled selected-ID V7target required')
        value=NativeScreen(*ARTIFACT,**options);ENGINES.append(value);return value

    def test_all_selected_node_fields_and_all_highway_batches_are_exact(self):
        engine=self.engine();rows=list(fixture_records());selected=[];ways=[]
        receipt=engine.validate_frames(framed_records(rows),STATE,caps(),selected=[1,2,3,4],on_record=selected.append,
            on_way_batch=lambda batch:ways.extend(batch),batch_scope='all')
        self.assertEqual([r for r in selected if r['type']=='node'],[r for r in rows if r['type']=='node'])
        self.assertEqual(ways,[r for r in rows if r['type']=='way' and r['tags'].get('highway')])
        self.assertEqual(receipt['semanticSha256'],reference_seal(rows));self.assertTrue(receipt['nativeEof'])
        self.assertEqual(receipt['selectedNodeProjections'],4);self.assertEqual(receipt['witnessRows'],4)

    def test_prior_native_abi_is_rejected(self):
        self.engine()
        with self.assertRaisesRegex(PilotError,'C ABI version'):
            NativeScreen('/legacy-v5/country-screen.so','9c81c86e3605738430b1c8f9f762bce71830740e5c46737485371ef8c0561166')

    def test_above_two_million_and_invalid_typed_selection_are_rejected(self):
        for selected in [range(1,2000002),[True],[0],[2,1],[1,1],[2**63]]:
            engine=self.engine()
            with self.assertRaises(PilotError):engine.validate_frames(framed_records(fixture_records()),STATE,caps(),selected=selected)

    def test_two_million_boundary_is_accepted_but_missing_source_nodes_fail(self):
        engine=self.engine()
        with self.assertRaisesRegex(PilotError,'missing_witness'):
            engine.validate_frames(framed_records(fixture_records()),STATE,caps(),selected=range(1,2000001))
        self.assertFalse(engine.last['nativeEof']);self.assertEqual(engine.last['nodes'],4)

    def test_metadata_rejection_still_counts_received_but_not_accepted(self):
        rows=list(fixture_records());rows[0]['version']=0;engine=self.engine()
        with self.assertRaises(PilotError):engine.validate_frames(framed_records(rows),STATE,caps())
        self.assertFalse(engine.last['nativeEof']);self.assertEqual(engine.last['nodes'],1);self.assertEqual(engine.last['acceptedNodes'],0)

    def test_callback_failure_is_not_a_complete_source_receipt(self):
        engine=self.engine()
        def reject(row):raise PilotError('selected sink refused')
        with self.assertRaisesRegex(PilotError,'selected sink refused'):
            engine.validate_frames(framed_records(fixture_records()),STATE,caps(),selected=[1],on_record=reject,on_way_batch=lambda rows:None,batch_scope='all')
        self.assertFalse(engine.last['nativeEof'])

    def test_missing_selected_reference_and_source_count_cap_fail(self):
        for selected,limits in [([5],caps()),([],caps(3))]:
            engine=self.engine()
            with self.assertRaises(PilotError):engine.validate_frames(framed_records(fixture_records()),STATE,limits,selected=selected)
            self.assertFalse(engine.last['nativeEof'])
