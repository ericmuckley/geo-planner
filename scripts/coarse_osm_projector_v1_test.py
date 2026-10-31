"""Native metadata/projection controls, synthetic frames/PBF only."""
from copy import deepcopy
import ctypes
import datetime
import gc
import hashlib
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from coarse_osm_projector_v1 import (NativeProjector,EncodedIndex,field_frame,framed_records,decode_frame,reference_seal,SEAL_PREFIX,CALLBACK)
from coarse_osm_projector_extract_v1 import extract
from coarse_osm_native_smoke import fixture_records,write_xml,STATE,negative_fixtures
from coarse_osm_stream_v1 import NativeValidator
from coarse_osm_delta_v2 import Storage,Reader
from coarse_osm_bulk import Run,extract as reference_extract,records as reference_records
from coarse_osm_validation_v4 import checked_records
from coarse_osm_bulk_pbf import native_records
from coarse_osm_records import canonical
from coarse_timing_input import PilotError

ARTIFACT=None
ENGINES=[]


def configure_native(path,sha):
    global ARTIFACT
    ARTIFACT=(path,sha)


class NativeView:
    def __init__(self,raw,pairs=None):self.raw=raw;self.pairs=pairs if pairs is not None else list(raw.get('tags',{}).items())
    def type_str(self):return {'node':'n','way':'w','relation':'r'}[self.raw['type']]
    @property
    def id(self):return self.raw['id']
    @property
    def version(self):return self.raw['version']
    @property
    def timestamp(self):return datetime.datetime.strptime(self.raw['timestamp'],'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
    @property
    def visible(self):return self.raw.get('visible',True)
    @property
    def tags(self):
        return [SimpleNamespace(k=k.decode('utf-8') if isinstance(k,bytes) else k,v=v.decode('utf-8') if isinstance(v,bytes) else v) for k,v in self.pairs]
    @property
    def location(self):
        x=round(self.raw['lon']*10000000);y=round(self.raw['lat']*10000000)
        return SimpleNamespace(x=x,y=y,lon=self.raw['lon'],lat=self.raw['lat'])
    @property
    def nodes(self):return [SimpleNamespace(ref=i) for i in self.raw['nodes']]
    @property
    def members(self):return [SimpleNamespace(type={'node':'n','way':'w','relation':'r'}[m['type']],ref=m['ref'],role=m['role']) for m in self.raw['members']]


class Tests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.number=0
        repo=Path(__file__).resolve().parents[1]
        self.config=json.loads((repo/'docs/evidence/coarse-osm-offline-plan-2026-10-26/proposal.json').read_text())
        self.config['source']['proposedPublisherReplicationStateUtc']=STATE;self.config['windows']=[{'id':'a','bbox':[0,0,1,1]},{'id':'b','bbox':[.25,.25,.75,.75]}]
        self.config['proposedCaps'].update(sqliteIndexBytesEach=1048576,sqliteMaxPagesEach=256,sqliteCacheBytesEach=8192,
            workingBytesIncludingTmp=33554432,tmpBytes=65536,pythonSelectionStateBytes=4194304,retainedNativeObjectBytes=1048576,normalizedExtractBytes=1048576,
            scanNodesPerPass=10000,scanWaysPerPass=10000,scanRelationsPerPass=10000,scanObjectVisitsTotal=100000,wallSeconds=30)
        self.caps=self.config['proposedCaps']
    def directory(self):
        self.number+=1;p=self.root/str(self.number);p.mkdir();return p
    def engine(self,**kwargs):
        if ARTIFACT is None:self.skipTest('Compiled target projector required')
        engine=NativeProjector(*ARTIFACT,**kwargs);ENGINES.append(engine);return engine
    def pbf(self,rows=None):
        import osmium
        root=self.directory();xml=root/'fixture.osm';path=root/'fixture.pbf';write_xml(xml,fixture_records() if rows is None else rows)
        header=osmium.io.Header();header.set('osmosis_replication_timestamp',STATE)
        with osmium.SimpleWriter(str(path),header=header,bufsz=65536) as writer:
            for obj in osmium.FileProcessor(str(xml)):writer.add(obj)
        return path
    def run_extract(self,**kwargs):
        engine=self.engine();root=self.directory();result=extract(self.pbf(),self.config,root,engine=engine,**kwargs)
        return result,root

    def test_python_field_frame_exact_roundtrip_and_tag_semantic_order(self):
        rows=fixture_records();rows[0]['tags']={'é':'a"\\\n\x7f 😀','x':'\x00\t'}
        for row in rows:self.assertEqual(decode_frame(field_frame(row)),row)
        copy=deepcopy(rows);copy[0]['tags']=dict(reversed(list(rows[0]['tags'].items())))
        self.assertEqual(reference_seal(rows),reference_seal(copy))
        self.assertNotEqual(reference_seal(rows),hashlib.sha256(b''.join(canonical(r)+b'\n' for r in rows)).hexdigest())

    def test_python_frame_parser_rejects_corruption_and_bounds(self):
        body=field_frame(fixture_records()[0])
        for value in (body[:-1],body+b'x',b'',b'X'+body[1:]):
            with self.assertRaises(PilotError):decode_frame(value)
        for offset in (4,5,6):
            value=bytearray(body);value[offset]=9
            with self.assertRaises(PilotError):decode_frame(bytes(value))
        with self.assertRaises(PilotError):framed_records([dict(fixture_records()[0],id=True)])

    def test_native_full_field_proof_and_fast_selection_are_identical(self):
        engine=self.engine();rows=fixture_records();rows[0]['tags']={'é':'😀\x7f"\\','x':'\u2028'}
        for proof,selected,expected in [(True,(),rows),(False,(),rows[4:]),(False,(1,2),rows[:2]+rows[4:])]:
            output=[];blocks=[];result=engine.validate_frames(framed_records(rows),STATE,self.caps,proof=proof,selected=selected,on_record=output.append,on_block=blocks.append)
            self.assertEqual(output,expected);self.assertEqual(result['semanticSha256'],reference_seal(rows))
            self.assertEqual(result['counts'],{'node':4,'way':3,'relation':2});self.assertEqual(result['visits'],9)
            self.assertEqual(len(blocks),1);self.assertTrue(result['nativeEof']);self.assertEqual(result['projectedFrames'],len(expected))
        empty=engine.validate_frames(b'',STATE,self.caps);self.assertEqual(empty['counts'],{});self.assertEqual(empty['semanticSha256'],hashlib.sha256(SEAL_PREFIX).hexdigest())

    def test_native_scalar_calendar_order_state_outcomes_match_frozen_validator(self):
        base=fixture_records()[0];cases=[base]
        for changes in ({'id':0},{'id':-1},{'version':0},{'version':-1},{'visible':False},
            {'timestamp':'2026-02-30T00:00:00Z'},{'timestamp':'2026-02-29T00:00:00Z'},
            {'timestamp':'2026-01-01T24:00:00Z'},{'timestamp':'2026-01-01T00:60:00Z'},
            {'timestamp':'2026-01-01T00:00:60Z'},{'timestamp':'2026-10-26T00:00:00Z'},
            {'timestamp':'1970-01-01T00:00:00Z'},{'timestamp':'2000-02-29T23:59:59Z'},
            {'timestamp':'2026-1-01T00:00:00Z'},{'timestamp':'2026-01-01T00:00:00.0Z'},
            {'timestamp':'2026-01-01T00:00:00+00:00'}):cases.append(dict(base,**changes))
        for row in cases:
            reference=NativeValidator(STATE,1048576,self.caps,lambda raw,line:None)
            projected_run=Run(self.directory(),self.config)
            try:
                list(checked_records(lambda:iter([row]),projected_run,STATE,'projected-reference'))
                reference.see(NativeView(row));accepted=True
            except Exception:accepted=False
            engine=self.engine()
            try:engine.validate_frames(framed_records([row]),STATE,self.caps);actual=True
            except Exception:actual=False
            self.assertEqual(actual,accepted,row)
            self.assertEqual(engine.last['counts'],projected_run.state['passes'][0]['counts'])
            if not actual:self.assertFalse(engine.last['nativeEof'])
        for rows in ([base,base],[dict(base,id=2),base],[fixture_records()[4],base]):
            engine=self.engine()
            with self.assertRaises(PilotError):engine.validate_frames(framed_records(rows),STATE,self.caps)
            self.assertFalse(engine.last['nativeEof'])

    def test_native_utf8_duplicates_and_incremental_copy_limits(self):
        engine=self.engine();base=fixture_records()[0]
        for text in ('\x00\b\t\n\f\r\x1f\x7f','éø😀𐀀\u2028','a"\\b'):
            row=dict(base,tags={'text':text});output=[]
            engine.validate_frames(framed_records([row]),STATE,self.caps,proof=True,on_record=output.append);self.assertEqual(output,[row])
        pairs=[('duplicate','a'),('duplicate','b')];body=field_frame(base,tag_pairs=pairs)
        with self.assertRaises(PilotError):engine.validate_frames(struct.pack('<I',len(body))+body,STATE,self.caps)
        self.assertEqual(engine.last['error'],'duplicate_tag_key')
        original=field_frame(dict(base,tags={'key':'MARK'}))
        for invalid in (b'\xff\xff\xff\xff',b'\xc0\x80xx',b'\xed\xa0\x80x',b'\xf4\x90\x80\x80',b'\xf0\x80\x80\x80'):
            body=original.replace(b'MARK',invalid)
            with self.assertRaises(PilotError):engine.validate_frames(struct.pack('<I',len(body))+body,STATE,self.caps)
            self.assertIn('utf8',engine.last['error'])
        row=dict(base,tags={'x':'a'*1000});caps=dict(self.caps,singleNormalizedElementBytes=500)
        with self.assertRaises(PilotError):engine.validate_frames(framed_records([row]),STATE,caps)
        self.assertEqual(engine.last['error'],'tag_copy_limit');self.assertEqual(engine.last['counts'],{'node':1})

    def test_native_exact_canonical_caps_and_node_fallback_match_reference(self):
        node=dict(fixture_records()[0],lon=0.,lat=0.,tags={})
        unicode_node=dict(node,tags={'x':'😀'*70})
        way=dict(fixture_records()[4],tags={'highway':'primary','x':'\x7f'*100})
        relation=dict(fixture_records()[7],tags={'type':'restriction'},members=[{'type':'way','ref':1,'role':'😀'*80}])
        for row in (node,unicode_node,way,relation):
            size=len(canonical(row))
            for limit in (size-1,size,size+1):
                caps=dict(self.caps,singleNormalizedElementBytes=limit)
                reference=NativeValidator(STATE,limit,caps,lambda raw,line:None)
                try:reference.see(NativeView(row));accepted=True
                except Exception:accepted=False
                engine=self.engine()
                try:result=engine.validate_frames(framed_records([row]),STATE,caps);actual=True
                except Exception:actual=False
                self.assertEqual(actual,accepted,(row['type'],limit,size,engine.last))
                if actual and row['type']=='node':self.assertGreater(result['fallbacks'],0)
        engine=self.engine();limit=len(canonical(node))
        with self.assertRaises(PilotError):engine.validate_frames(framed_records([node]),STATE,dict(self.caps,singleNormalizedElementBytes=limit),fallback=False)
        self.assertFalse(engine.last['nativeEof']);self.assertEqual(engine.last['fallbacks'],1)

    def test_native_refs_members_xy_and_visit_quotas_reject_before_filtering(self):
        rows=fixture_records();variants=[]
        for refs in ([1],[1,0],[1,-1]):variants.append(dict(rows[4],nodes=refs))
        variants.append(dict(rows[7],members=[{'type':'way','ref':-1,'role':'from'}]))
        engine=self.engine()
        for row in variants:
            with self.assertRaises(PilotError):engine.validate_frames(framed_records([row]),STATE,self.caps)
            self.assertFalse(engine.last['nativeEof'])
        body=bytearray(field_frame(dict(rows[0],tags={})));body[-8:]=struct.pack('<ii',1800000001,0)
        with self.assertRaises(PilotError):engine.validate_frames(struct.pack('<I',len(body))+body,STATE,self.caps)
        for field in ('scanNodesPerPass','scanObjectVisitsTotal'):
            caps=dict(self.caps,**{field:1})
            with self.assertRaises(PilotError):engine.validate_frames(framed_records(rows[:2]),STATE,caps)
            self.assertEqual(engine.last['counts'],{'node':2});self.assertEqual(engine.last['visits'],2)

    def test_native_callback_lifetimes_failure_reentrancy_and_truncated_wire(self):
        engine=self.engine();rows=fixture_records()
        def failed(raw):raise RuntimeError('controlled consumer failure')
        with self.assertRaisesRegex(RuntimeError,'controlled consumer failure'):engine.validate_frames(framed_records(rows),STATE,self.caps,proof=True,on_record=failed)
        self.assertFalse(engine.last['nativeEof'])
        def recurse(raw):engine.validate_frames(b'',STATE,self.caps)
        with self.assertRaisesRegex(PilotError,'reentrant'):engine.validate_frames(framed_records(rows),STATE,self.caps,proof=True,on_record=recurse)
        self.assertFalse(engine.last['nativeEof'])
        output=[]
        def collect(raw):gc.collect();output.append(raw)
        engine.validate_frames(framed_records(rows),STATE,self.caps,proof=True,on_record=collect);self.assertEqual(output,rows)
        for raw in (b'\x01',framed_records(rows)[:-1],struct.pack('<I',2097153)):
            with self.assertRaises(PilotError):engine.validate_frames(raw,STATE,self.caps)
            self.assertFalse(engine.last['nativeEof'])

    def test_native_fast_nodes_handoff_has_no_python_node_projection(self):
        engine=self.engine();rows=[dict(fixture_records()[0],id=i+1,lon=(i%100)/10000000,lat=0.,tags={}) for i in range(9000)]
        index=EncodedIndex(self.directory()/'index',Storage(33554432,67108864),codec=engine.codec)
        projected=[];result=engine.validate_frames(framed_records(rows),STATE,self.caps,on_record=projected.append,on_block=lambda event:index.append_encoded(event,engine.codec))
        index.finish();self.assertEqual(projected,[]);self.assertEqual(result['blocks'],3);self.assertEqual(result['visits'],9000)
        self.assertEqual(result['semanticSha256'],reference_seal(rows));self.assertEqual(index.points([1,9000,1]),[[0.,0.],[.0000099,0.],[0.,0.]])
        oracle=Reader(index.root,engine.codec);self.assertEqual(oracle.manifest['rows'],9000)

    def test_actual_synthetic_pbf_fields_epoch_and_framing_match_frozen_projector(self):
        engine=self.engine();rows=fixture_records();rows[0]['timestamp']='1970-01-01T00:00:00Z';rows[0]['tags']={'unicode':'é😀','quote':'a"\\b'}
        path=self.pbf(rows);expected=list(native_records(path,1048576));actual=[]
        receipt=engine.scan(path,STATE,self.caps,proof=True,on_record=actual.append)
        self.assertEqual(actual,expected);self.assertEqual(receipt['semanticSha256'],reference_seal(expected));self.assertEqual(actual[0]['timestamp'],'1970-01-01T00:00:00Z')
        for name,(body,reason) in negative_fixtures(path.read_bytes()).items():
            bad=self.directory()/(name+'.pbf');bad.write_bytes(body)
            with self.assertRaises(Exception):engine.scan(bad,STATE,self.caps)
            self.assertTrue(engine.last is None or not engine.last['nativeEof'])

    def test_native_pbf_post_scan_content_hash_refuses_same_metadata_overwrite(self):
        engine=self.engine();path=self.pbf();modified=False
        def change(raw):
            nonlocal modified
            if not modified:
                body=path.read_bytes();path.write_bytes(body[:-1]+bytes([body[-1]^1]));modified=True
        with self.assertRaises(Exception):engine.scan(path,STATE,self.caps,proof=True,on_record=change)
        self.assertFalse(engine.last['nativeEof'])

    def test_native_two_pass_independent_output_matches_reference(self):
        engine=self.engine();path=self.pbf();root=self.directory();result=extract(path,self.config,root,engine=engine)
        self.assertEqual(result['status'],'passed_native_projector_synthetic',result);self.assertTrue(result['independentAuditComplete'])
        prior=self.directory();reference=reference_extract(lambda:iter(native_records(path,1048576)),self.config,prior,source_identity={'publisherStateUtc':STATE})
        self.assertTrue(reference['independentAuditComplete']);self.assertEqual((root/'elements.jsonl').read_bytes(),(prior/'elements.jsonl').read_bytes())
        self.assertEqual(result['scanObjectVisits'],18);self.assertEqual(result['nativeReceipts'][0]['projectedFrames'],5);self.assertEqual(result['nativeReceipts'][1]['projectedFrames'],7)

    def test_native_independent_audit_rejects_omitted_extra_membership_and_output(self):
        def clear(s):
            s.keys.clear()
            for value in s.members.values():value.clear()
        def omit_node(s):
            s.keys.remove(('node',2))
            for value in s.members.values():value.discard(('node',2))
        def extra(s):s.add('a',('node',3))
        def wrong_window(s):s.members['b'].clear()
        for hook in (clear,omit_node,extra,wrong_window):
            result,_=self.run_extract(primary_hook=hook);self.assertEqual(result['status'],'stopped');self.assertFalse(result['independentAuditComplete'])
        def omit(selection,snapshot):yield from (r for r in reference_records(selection,snapshot) if r['element']['type']!='relation')
        with patch('coarse_osm_projector_extract_v1.records',omit):
            result,_=self.run_extract();self.assertEqual(result['status'],'stopped');self.assertIn('Independent',result['error'])

    def test_unselected_metadata_is_validated_and_bound_by_semantic_seal(self):
        engine=self.engine();base=dict(fixture_records()[0],tags={});changed=dict(base,tags={'discarded':'changed'})
        a=engine.validate_frames(framed_records([base]),STATE,self.caps)
        b=engine.validate_frames(framed_records([changed]),STATE,self.caps)
        self.assertEqual(a['projectedFrames'],0);self.assertEqual(b['projectedFrames'],0)
        self.assertNotEqual(a['semanticSha256'],b['semanticSha256'])
        self.assertEqual(a['semanticSha256'],reference_seal([base]));self.assertEqual(b['semanticSha256'],reference_seal([changed]))
        with self.assertRaises(PilotError):engine.validate_frames(framed_records([dict(base,visible=False)]),STATE,self.caps)
        self.assertFalse(engine.last['nativeEof'])

    def test_native_pbf_source_change_between_passes_preserves_stop(self):
        engine=self.engine();path=self.pbf();rows=fixture_records();rows[3]['tags']['unselected']='changed';other=self.pbf(rows)
        result=extract(path,self.config,self.directory(),engine=engine,before_second=lambda:path.write_bytes(other.read_bytes()))
        self.assertEqual(result['status'],'stopped');self.assertFalse(result['independentAuditComplete'])
        self.assertTrue('drift' in result['error'].lower())

    def test_raw_abi_null_options_and_aggregate_limits_fail_closed(self):
        engine=self.engine();raw=ctypes.create_string_buffer(b'');receipt=(ctypes.c_uint64*10)();error=ctypes.create_string_buffer(512);limits=(ctypes.c_uint64*4)(100,100,100,100)
        code=engine.frames(raw,0,STATE.encode(),1048576,limits,0,None,0,CALLBACK(),None,receipt,10,error,512)
        self.assertNotEqual(code,0);self.assertFalse(receipt[4])
        small=self.engine(aggregate_visits=1);small.validate_frames(framed_records([fixture_records()[0]]),STATE,self.caps)
        with self.assertRaises(PilotError):small.validate_frames(framed_records([fixture_records()[0]]),STATE,self.caps)
        for selected in ((1,1),(2,1),(0,)):
            with self.assertRaises(PilotError):engine.validate_frames(b'',STATE,self.caps,selected=selected)


if __name__=='__main__':unittest.main()
