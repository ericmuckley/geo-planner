"""Exact gap-run bytes, canonical raw fallback and lossless legacy conversion."""
import ctypes
import hashlib
import random
import struct
import unittest

from coarse_osm_delta_v1 import ReferenceCodec
from coarse_osm_window_cells_v1 import Cells,SCALE
from coarse_osm_window_codec_v2 import Codec,ENVELOPE,BODY,body
from coarse_osm_window_codec_v1_test import reference as legacy_reference
from coarse_timing_input import PilotError

ARTIFACT=None
CODECS=[]


def configure_native(path,sha):
    global ARTIFACT
    ARTIFACT=path,sha


def variable(value):
    result=bytearray()
    while value>=128:result.append((value&127)|128);value>>=7
    result.append(value);return bytes(result)


def envelope(payload):return ENVELOPE.pack(b'WC02',2,0,hashlib.sha256(payload).digest())+payload


def reference(rows,cells):
    gaps=[b[0]-a[0] for a,b in zip(rows,rows[1:])];raw=b''.join(variable(gap) for gap in gaps);runs=[]
    for gap in gaps:
        if runs and runs[-1][0]==gap:runs[-1][1]+=1
        else:runs.append([gap,1])
    compact=b''.join(variable(gap)+variable(count) for gap,count in runs)
    use_runs=len(compact)<len(raw);ids=compact if use_runs else raw
    codes=[]
    for _,x,y in rows:
        cell=cells.cell(x,y)
        if codes and codes[-1][0]==cell:codes[-1][1]+=1
        else:codes.append([cell,1])
    payload=BODY.pack(len(rows),rows[0][0],rows[-1][0],len(ids),len(runs) if use_runs else 0,len(codes))+ids+b''.join(struct.pack('<HH',*run) for run in codes)
    return envelope(payload)


class NativeTests(unittest.TestCase):
    def codec(self,windows=None,**caps):
        if ARTIFACT is None:self.skipTest('Compiled V2window-cell artifact required')
        grid=Cells(windows or [{'id':'q','bbox':[0,0,1,1]}]);codec=Codec(*ARTIFACT,grid,**caps);CODECS.append(codec);return codec

    def encode(self,codec,rows):return codec.encode(ReferenceCodec().encode(rows),len(rows),rows[0][0],rows[-1][0])

    def test_native_bytes_equal_independent_reference_for_arbitrary_cells_and_gaps(self):
        windows=[{'id':str(i),'bbox':[-170+i*6,-80+i*3,-168+i*6,-79+i*3]} for i in range(21)]
        codec=self.codec(windows);rng=random.Random(61437);identity=1;rows=[]
        for _ in range(4096):
            identity+=rng.choice([1,1,1,127,128,16384,2**35])
            rows.append((identity,rng.randint(-180*SCALE,180*SCALE),rng.randint(-90*SCALE,90*SCALE)))
        actual=self.encode(codec,rows);self.assertEqual(actual,reference(rows,codec.cells))
        positions=[4095,0,174,174,3]
        self.assertEqual(codec.lookup(actual,[rows[i][0] for i in positions]),[codec.cells.cell(*rows[i][1:]) for i in positions])

    def test_dense_runs_shrink_and_raw_wins_ties(self):
        codec=self.codec();rows=[(i+1,0,0) for i in range(4096)];raw=self.encode(codec,rows)
        self.assertEqual(raw,reference(rows,codec.cells));self.assertEqual(len(raw),79)
        self.assertEqual(BODY.unpack_from(body(raw)[0])[3:5],(3,1))
        tie=self.encode(codec,rows[:3]);self.assertEqual(BODY.unpack_from(body(tie)[0])[3:5],(2,0))
        single=self.encode(codec,rows[:1]);self.assertEqual(BODY.unpack_from(body(single)[0])[3:5],(0,0))

    def test_sparse_mixed_gaps_keep_raw_fallback_and_full_signed_ids(self):
        codec=self.codec();rows=[(1,0,0),(129,0,0),(130,0,0),(2**35,0,0),(2**63-1,0,0)]
        raw=self.encode(codec,rows);self.assertEqual(raw,reference(rows,codec.cells));self.assertEqual(BODY.unpack_from(body(raw)[0])[4],0)
        self.assertEqual(codec.lookup(raw,[2**63-1,1,1]),[codec.cells.cell(0,0)]*3)
        rows=[(1,0,0),(1+2**61,0,0),(1+2**62,0,0)];raw=self.encode(codec,rows)
        self.assertEqual(raw,reference(rows,codec.cells));self.assertEqual(BODY.unpack_from(body(raw)[0])[4],1)

    def test_missing_or_invalid_typed_references_fail(self):
        codec=self.codec();raw=self.encode(codec,[(1,0,0),(3,0,0)])
        for queries in [[2],[0],[-1],[True],[2**63],[]]:
            with self.assertRaises(PilotError):codec.lookup(raw,queries)

    def test_invalid_gap_run_counts_overflow_and_noncanonical_modes_fail(self):
        codec=self.codec();cell=codec.cells.cell(0,0)
        def block(n,first,last,ids,runs):return envelope(BODY.pack(n,first,last,len(ids),runs,1)+ids+struct.pack('<HH',cell,n))
        cases=[block(4,1,4,b'\x01\x01\x01',0),block(4,1,4,b'\x00\x03',1),block(4,1,4,b'\x01\x00',1),
               block(4,1,4,b'\x01\x04',1),block(4,1,4,b'\x01\x02',1),block(4,1,4,b'\x81\x00\x03',1),
               block(4,1,4,b'\x01\x83\x00',1),block(4,1,4,b'\x01\x01\x01\x02',2),
               block(3,1,3,b'\x01\x02',1),block(4,2**63-3,2**63-1,b'\x01\x03',1),
               block(4,1,4,b'\x80'*27,0)]
        for raw in cases:
            with self.assertRaises(PilotError):codec.lookup(raw,[BODY.unpack_from(body(raw)[0])[1]])

    def test_cell_run_and_envelope_corruption_are_rejected(self):
        codec=self.codec();raw=self.encode(codec,[(1,0,0),(3,0,0)]);corrupt=bytearray(raw);corrupt[-1]^=1
        with self.assertRaises(PilotError):codec.lookup(bytes(corrupt),[1])
        payload=body(raw)[0];n,first,last,id_bytes,id_runs,cell_runs=BODY.unpack_from(payload);start=BODY.size+id_bytes
        for offset,value,fmt in [(0,0,'<I'),(28,0,'<I'),(start,codec.cells.count,'<H'),(start+2,0,'<H'),(start+2,4096,'<H')]:
            damaged=bytearray(payload);struct.pack_into(fmt,damaged,offset,value)
            with self.assertRaises(PilotError):codec.lookup(envelope(damaged),[1])
        cell=codec.cells.cell(0,0);duplicate=BODY.pack(n,first,last,id_bytes,id_runs,2)+payload[BODY.size:start]+struct.pack('<HHHH',cell,1,cell,1)
        with self.assertRaises(PilotError):codec.lookup(envelope(duplicate),[1])

    def test_fine_source_and_axis_corruption_are_rejected(self):
        codec=self.codec();payload=ReferenceCodec().encode([(1,0,0),(3,0,0)])
        for bad in [payload[:-1],payload+b'\0',struct.pack('<ii',180*SCALE+1,0)+payload[8:]]:
            with self.assertRaises(PilotError):codec.encode(bad,2,1,3)
        codec.x[0]=180*SCALE+1
        with self.assertRaises(PilotError):codec.encode(payload,2,1,3)

    def test_legacy_conversion_preserves_every_cell_and_exact_reference_bytes(self):
        codec=self.codec();positions=[(-1,-1),(0,0),(2*SCALE,SCALE//2),(0,0)]
        rows=[(i+1,*positions[i%4]) for i in range(4096)];legacy=legacy_reference(rows,codec.cells)
        converted=codec.from_v1(legacy);self.assertEqual(converted,reference(rows,codec.cells));self.assertLess(len(converted),len(legacy))
        ids=[row[0] for row in reversed(rows)]+[1,1]
        expected={identity:codec.cells.cell(x,y) for identity,x,y in rows}
        self.assertEqual(codec.lookup(converted,ids),[expected[identity] for identity in ids])

    def test_legacy_conversion_rejects_resigned_bad_cell_streams(self):
        codec=self.codec();legacy=legacy_reference([(1,0,0),(3,0,0)],codec.cells)
        from coarse_osm_window_codec_v1 import body as legacy_body
        payload=bytearray(legacy_body(legacy)[0]);id_bytes=struct.unpack_from('<I',payload,20)[0]
        struct.pack_into('<H',payload,28+id_bytes,codec.cells.count)
        damaged=ENVELOPE.pack(b'WC01',1,0,hashlib.sha256(payload).digest())+payload
        with self.assertRaises(PilotError):codec.from_v1(bytes(damaged))

    def test_row_and_call_caps_include_roundtrip_and_legacy_conversion(self):
        codec=self.codec(row_budget=3);payload=ReferenceCodec().encode([(1,0,0),(3,0,0)])
        with self.assertRaises(PilotError):codec.encode(payload,2,1,3)
        self.assertEqual((codec.rows,codec.calls),(2,1))
        codec=self.codec(call_budget=1)
        with self.assertRaises(PilotError):codec.from_v1(legacy_reference([(1,0,0),(3,0,0)],codec.cells))
        self.assertEqual(codec.calls,1)

    def test_native_output_capacity_and_late_missing_id_preserve_sentinels(self):
        codec=self.codec();rows=[(1,0,0),(3,0,0)];raw=self.encode(codec,rows);payload=body(raw)[0]
        source=(ctypes.c_uint8*len(payload)).from_buffer_copy(payload);queries=(ctypes.c_int64*2)(1,2);out=(ctypes.c_uint16*2)(65535,65535)
        self.assertNotEqual(codec.query(source,len(payload),codec.cells.count,queries,2,out,2),0);self.assertEqual(list(out),[65535,65535])
        legacy=legacy_reference(rows,codec.cells)[ENVELOPE.size:];source=(ctypes.c_uint8*len(legacy)).from_buffer_copy(legacy)
        output=(ctypes.c_uint8*8)(*[170]*8);written=ctypes.c_uint32(99)
        self.assertNotEqual(codec.convert(source,len(legacy),codec.cells.count,output,8,ctypes.byref(written)),0)
        self.assertEqual(written.value,0);self.assertEqual(list(output),[170]*8)
