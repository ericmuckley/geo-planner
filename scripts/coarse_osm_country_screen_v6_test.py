"""Execution closure controls, with all V1 native guards inherited unchanged."""
from copy import deepcopy
import hashlib
import os
import sys
import subprocess
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import coarse_osm_country_screen_v1_test as prior
from coarse_osm_country_screen_v6 import NativeScreen, Resources, run_pair, storage_decision, META, decode_way_batch
from coarse_osm_country_wire_v4 import framed_records
from coarse_osm_native_smoke import fixture_records, STATE
from coarse_timing_input import PilotError

ARTIFACT = None
ENGINES = []


class BatchHostTests(unittest.TestCase):
    def test_batch_decoder_rejects_inconsistent_headers_and_truncation(self):
        import struct
        from coarse_osm_country_wire_v4 import field_frame
        row=fixture_records()[4];frame=field_frame(row)
        body=struct.pack('<4sIII',b'GWB1',1,len(row['nodes']),len(frame)+4)+struct.pack('<I',len(frame))+frame
        self.assertEqual(decode_way_batch(body),[row])
        for broken in [body[:-1],body+b'x',b'BAD!'+body[4:],body[:4]+struct.pack('<I',2)+body[8:],body[:8]+struct.pack('<I',65537)+body[12:]]:
            with self.assertRaises(PilotError):decode_way_batch(broken)


def configure_native(path, sha):
    global ARTIFACT
    ARTIFACT = (path, sha)


class NativeTests(prior.NativeTests):
    def engine(self, **kwargs):
        if ARTIFACT is None:
            self.skipTest('Compiled V2 target required')
        engine = NativeScreen(*ARTIFACT, **kwargs)
        ENGINES.append(engine)
        return engine

    def test_all_scope_delivers_long_outside_probe_ways_and_selected_fields_before_restrictions(self):
        from coarse_osm_country_wire_v4 import reference_seal
        rows=fixture_records()[:4]
        way=dict(fixture_records()[4],nodes=[1]*2000)
        relation=dict(fixture_records()[-1],id=1,members=[{'type':'way','ref':1,'role':'from'}])
        rows=rows+[way,relation];events=[];engine=self.engine()
        receipt=engine.validate_frames(framed_records(rows),STATE,self.caps,selected=[2],batch_scope='all',
                                      on_way_batch=lambda batch:events.append(('ways',batch)),on_record=lambda row:events.append(('record',row)))
        self.assertEqual(events,[('record',rows[1]),('ways',[way]),('record',relation)])
        self.assertEqual(receipt['selectedNodeProjections'],1)
        self.assertEqual(receipt['restrictionProjections'],1)
        self.assertEqual(receipt['batchWays'],1)
        self.assertEqual(receipt['semanticSha256'],reference_seal(rows))
        outside=dict(way,nodes=[1,999]);rows=rows[:4]+[outside]
        old=[];engine.validate_frames(framed_records(rows),STATE,self.caps,on_way_batch=old.extend)
        self.assertEqual(old,[])
        actual=[];engine.validate_frames(framed_records(rows),STATE,self.caps,batch_scope='all',on_way_batch=actual.extend)
        self.assertEqual(actual,[outside])

    def test_way_count_ceiling_follows_two_references_per_way(self):
        base=fixture_records()[4];nodes=fixture_records()[:4]
        ways=[dict(base,id=index+1,nodes=[1,2]) for index in range(32769)]
        batches=[];receipt=self.engine().validate_frames(framed_records(nodes+ways),STATE,dict(self.caps,scanWaysPerPass=40000),
                                                       batch_scope='all',on_way_batch=lambda batch:batches.append(len(batch)))
        self.assertEqual(batches,[32768,1]);self.assertEqual(receipt['batchReferences'],65538)

    def test_v5_consumer_refuses_extended_abi(self):
        from coarse_osm_country_screen_v5 import NativeScreen as V5
        self.engine()
        with self.assertRaises(PilotError):V5(*ARTIFACT)

    def test_way_batches_are_complete_ordered_and_preserve_full_semantic_seal(self):
        from coarse_osm_country_wire_v4 import reference_seal
        nodes=fixture_records()[:4];base=fixture_records()[4]
        ways=[dict(base,id=i+1,nodes=[1,4]) for i in range(6000)]
        rows=nodes+ways;actual=[];engine=self.engine()
        result=engine.validate_frames(framed_records(rows),STATE,self.caps,on_way_batch=lambda batch:actual.append(batch),
                                      batch_caps={'ways':6000,'references':12000,'batches':3})
        self.assertEqual([len(batch) for batch in actual],[6000])
        self.assertEqual([row for batch in actual for row in batch],ways)
        self.assertEqual(result['semanticSha256'],reference_seal(rows))
        self.assertEqual((result['batchWays'],result['batchReferences'],result['wayBatches']),(6000,12000,1))
        self.assertEqual(result['pythonProjectionFrames'],0)
        actual=[];path=self.pbf(rows)
        result=self.engine().scan(path,STATE,self.caps,on_way_batch=lambda batch:actual.extend(batch))
        self.assertEqual(actual,ways);self.assertTrue(result['nativeEof'])

    def test_reference_and_byte_batch_limits_flush_before_exceeding_bounds(self):
        nodes=fixture_records()[:4];base=fixture_records()[4]
        ways=[dict(base,id=i+1,nodes=[1]*1024) for i in range(150)]
        actual=[];engine=self.engine()
        engine.validate_frames(framed_records(nodes+ways),STATE,self.caps,on_way_batch=lambda batch:actual.append(batch))
        self.assertEqual([sum(len(row['nodes']) for row in batch) for batch in actual],[65536,65536,22528])
        ways=[dict(base,id=i+1,nodes=[1,4],tags={'highway':'primary','x':'a'*2500000}) for i in range(6)]
        actual=[]
        engine.validate_frames(framed_records(nodes+ways),STATE,dict(self.caps,singleNormalizedElementBytes=4194304),on_way_batch=lambda batch:actual.append(batch))
        self.assertEqual([len(batch) for batch in actual],[3,3])

    def test_batch_budget_callback_and_unselected_errors_never_qualify_eof(self):
        rows=fixture_records();engine=self.engine();calls=[]
        with self.assertRaisesRegex(PilotError,'Way batch aggregate cap'):
            engine.validate_frames(framed_records(rows),STATE,self.caps,on_way_batch=calls.append,
                                   batch_caps={'ways':1,'references':2,'batches':1})
        self.assertFalse(engine.last['nativeEof']);self.assertEqual(calls,[])
        broken=rows+[dict(rows[-1],id=rows[-1]['id']+1,visible=False)]
        with self.assertRaises(PilotError):engine.validate_frames(framed_records(broken),STATE,self.caps,on_way_batch=calls.append)
        self.assertFalse(engine.last['nativeEof'])
        def fail(batch):raise PilotError('intentional batch consumer stop')
        with self.assertRaisesRegex(PilotError,'intentional batch consumer stop'):
            engine.validate_frames(framed_records(rows),STATE,self.caps,on_way_batch=fail)
        self.assertFalse(engine.last['nativeEof'])

    def test_v4_consumer_refuses_batch_abi(self):
        from coarse_osm_country_screen_v4 import NativeScreen as V4
        self.engine()
        with self.assertRaises(PilotError):V4(*ARTIFACT)

    def test_captured_valid_large_relations_pass_without_id_exceptions(self):
        from coarse_osm_country_wire_v4 import reference_seal
        path=Path('/inputs/member-regression.json')
        if not path.exists():path=Path(__file__).resolve().parents[1]/'docs/evidence/coarse-osm-country-exec-2026-10-30/member-diagnostic-regression.json'
        rows=json.loads(path.read_text())['objects']
        caps=dict(self.caps,singleNormalizedElementBytes=4194304)
        for index,row in enumerate(rows):
            # Change the IDs as well: the allowance depends only on object size.
            row=dict(row,id=index+1)
            engine=self.engine();actual=[]
            result=engine.validate_frames(framed_records([row]),STATE,caps,proof=True,on_record=actual.append)
            self.assertEqual(actual,[row])
            self.assertEqual(result['semanticSha256'],reference_seal([row]))
            self.assertEqual(result['maxCanonicalUpperBytes'],len(prior.canonical(row)))
            self.assertGreater(result['maxCopyBytes'],1048576)
            with self.assertRaises(PilotError):engine.validate_frames(framed_records([row]),STATE,self.caps)
            broken=dict(row,members=row['members'][:-1]+[dict(row['members'][-1],ref=0)])
            with self.assertRaises(PilotError):engine.validate_frames(framed_records([broken]),STATE,caps)
            self.assertFalse(engine.last['nativeEof'])
            # Exercise libosmium, not only the independent field-wire entry point.
            actual=[];source=self.pbf([row])
            result=engine.scan(source,STATE,caps,proof=True,on_record=actual.append)
            self.assertEqual(actual,[row])
            self.assertTrue(result['nativeEof'])

    def test_larger_source_policy_still_enforces_copy_and_exact_canonical_caps(self):
        row=dict(fixture_records()[-1],members=[{'type':'way','ref':1,'role':''}]*32768)
        caps=dict(self.caps,singleNormalizedElementBytes=4194304)
        engine=self.engine()
        with self.assertRaisesRegex(PilotError,'member_copy_identity'):
            engine.validate_frames(framed_records([row]),STATE,caps)
        row=dict(fixture_records()[0],tags={'x':'é'*(4194304//6)})
        with self.assertRaisesRegex(PilotError,'canonical_byte_limit'):
            engine.validate_frames(framed_records([row]),STATE,caps)
        self.assertFalse(engine.last['nativeEof'])

    def test_extended_wire_roundtrip_and_old_consumers_refuse_new_abi(self):
        from coarse_osm_country_screen_v2 import NativeScreen as V2
        row=dict(fixture_records()[0],tags={'x':'a'*(2097152+32)})
        caps=dict(self.caps,singleNormalizedElementBytes=4194304)
        actual=[];engine=self.engine()
        engine.validate_frames(framed_records([row]),STATE,caps,proof=True,on_record=actual.append)
        self.assertEqual(actual,[row])
        with self.assertRaises(PilotError):V2(*ARTIFACT)

    def test_type_summaries_are_exact_and_mode_independent(self):
        rows = fixture_records()
        rows[0] = dict(rows[0], timestamp='1970-01-01T00:00:00Z', tags={'é':'😀'}, version=3)
        rows[3] = dict(rows[3], timestamp=STATE, tags={'x':'a'*100})
        engine = self.engine()
        summary = engine.validate_frames(framed_records(rows), STATE, self.caps)
        proof = engine.validate_frames(framed_records(rows), STATE, self.caps, proof=True)
        self.assertEqual(summary['metadata'], proof['metadata'])
        nodes = summary['metadata']['node']
        self.assertEqual(nodes['minTimestamp'], '1970-01-01T00:00:00Z')
        self.assertEqual(nodes['maxTimestamp'], STATE)
        self.assertEqual(nodes['maxTagUtf8Bytes'], 101)
        self.assertEqual(nodes['maxVersion'], 3)
        self.assertEqual(nodes['count'], 4)
        self.assertEqual(summary['metadata']['way']['count'], 3)
        self.assertEqual(summary['metadata']['relation']['maxMembers'], 3)

    def test_aggregate_codec_and_reference_caps_refuse_before_next_call(self):
        engine = self.engine(aggregate_caps={'sourceCodecCalls':2})
        node = framed_records(fixture_records()[:1])
        engine.validate_frames(node, STATE, self.caps)
        with patch.object(engine, 'frames', side_effect=AssertionError('must not call')) as call:
            with self.assertRaisesRegex(PilotError, 'before native call'):
                engine.validate_frames(node, STATE, self.caps)
            call.assert_not_called()
        engine = self.engine(aggregate_caps={'references':2})
        engine.validate_frames(framed_records(fixture_records()[4:5]), STATE, self.caps)
        with self.assertRaisesRegex(PilotError, 'before native call'):
            engine.validate_frames(node, STATE, self.caps)
        self.assertEqual(engine.totals['references'], 2)

    def test_v2_complete_pair_closes_data_and_records(self):
        engine = self.engine()
        rows = fixture_records()
        path = self.pbf(rows)
        root = self.directory()/'pair'
        result = run_pair(path, {'node':4,'way':3,'relation':2}, self.caps, STATE, root, engine, prior.binding(path), minimum_ways=0)
        self.assertEqual(result['objectReceipts'], 18)
        self.assertTrue(result['storageDecision']['passed'])
        closed = json.loads((root/'close-receipt.json').read_text())
        self.assertGreater(closed['secondsThroughResultClose'], result['secondsBeforeResultClose'])
        for stage in result['passes']:
            self.assertGreater(stage['protectedSecondsIncludingReceiptClose'], 0)
        self.assertTrue((root/'pass-a/phase-receipt.json').exists())
        self.assertTrue((root/'pass-b/phase-receipt.json').exists())

    def test_incompatible_v1_consumer_cannot_accept_v2(self):
        from coarse_osm_country_screen_v1 import NativeScreen as Old
        self.engine()
        with self.assertRaises(PilotError):
            Old(*ARTIFACT)

    def test_hard_watchdog_kills_native_framing_and_posthash_stalls(self):
        self.engine()
        path = self.pbf()
        program = """import ctypes,sys,time
import coarse_osm_country_screen_v6 as module
from coarse_osm_country_screen_v6 import NativeScreen
from coarse_osm_native_smoke import STATE
from coarse_timing_input import start_watchdog
engine=NativeScreen(sys.argv[1],sys.argv[2])
phase=sys.argv[4]
caps={'singleNormalizedElementBytes':4194304,'scanNodesPerPass':100,'scanWaysPerPass':100,'scanRelationsPerPass':100,'scanObjectVisitsTotal':100,'pbfHeaderBytesExclusiveMaximum':65536,'pbfUncompressedBlobBytesExclusiveMaximum':33554432}
if phase=='framing':module.framing=lambda *a,**k:time.sleep(10)
def check():
 if phase=='posthash' and not engine.active and engine.last is not None:time.sleep(10)
start_watchdog(.2)
if phase=='no-callback':ctypes.CDLL(None).pause()
else:engine.scan(sys.argv[3],STATE,caps,proof=True,on_record=lambda row:time.sleep(10) if phase=='native-callback' else None,check=check)
"""
        for phase in ('native-callback', 'no-callback', 'framing', 'posthash'):
            result = subprocess.run([sys.executable, '-B', '-c', program, *ARTIFACT, str(path), phase],
                                    capture_output=True, timeout=5, env=os.environ | {'PYTHONPATH': os.pathsep.join(sys.path)})
            self.assertEqual(result.returncode, -9, (phase, result.stderr))


if __name__ == '__main__':
    unittest.main()
