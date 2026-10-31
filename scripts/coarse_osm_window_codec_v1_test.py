"""Native compact blocks against an independent Python byte/geometry oracle."""
import ctypes
import hashlib
import random
import struct
import unittest

from coarse_osm_delta_v1 import ReferenceCodec
from coarse_osm_window_cells_v1 import Cells,SCALE
from coarse_osm_window_codec_v1 import Codec,ENVELOPE,BODY,body
from coarse_timing_input import PilotError

ARTIFACT=None
CODECS=[]


def configure_native(path,sha):
    global ARTIFACT
    ARTIFACT=path,sha


def envelope(payload):return ENVELOPE.pack(b'WC01',1,0,hashlib.sha256(payload).digest())+payload


def reference(rows,cells):
    ids=bytearray();codes=[cells.cell(x,y) for _,x,y in rows]
    for a,b in zip(rows,rows[1:]):
        delta=b[0]-a[0]
        while delta>=128:ids.append((delta&127)|128);delta>>=7
        ids.append(delta)
    runs=[]
    for cell in codes:
        if runs and runs[-1][0]==cell:runs[-1][1]+=1
        else:runs.append([cell,1])
    payload=BODY.pack(len(rows),rows[0][0],rows[-1][0],len(ids),len(runs))+ids+b''.join(struct.pack('<HH',*run) for run in runs)
    return envelope(payload)


class NativeTests(unittest.TestCase):
    def codec(self,windows=None,**caps):
        if ARTIFACT is None:self.skipTest('Compiled window-cell target required')
        grid=Cells(windows or [{'id':'q','bbox':[0,0,1,1]}]);codec=Codec(*ARTIFACT,grid,**caps);CODECS.append(codec);return codec

    def encode(self,codec,rows):
        return codec.encode(ReferenceCodec().encode(rows),len(rows),rows[0][0],rows[-1][0])

    def test_native_bytes_equal_independent_reference_for_arbitrary_cells_and_gaps(self):
        randomizer=random.Random(51479)
        windows=[{'id':str(i),'bbox':[-170+i*6,-80+i*3,-168+i*6,-79+i*3]} for i in range(21)]
        codec=self.codec(windows);identity=1;rows=[]
        for _ in range(4096):
            identity+=randomizer.choice([1,1,127,128,16384,2**35])
            rows.append((identity,randomizer.randint(-180*SCALE,180*SCALE),randomizer.randint(-90*SCALE,90*SCALE)))
        actual=self.encode(codec,rows);self.assertEqual(actual,reference(rows,codec.cells))
        queries=[rows[i][0] for i in [4095,0,172,172,3]]
        self.assertEqual(codec.lookup(actual,queries),[codec.cells.cell(*rows[i][1:]) for i in [4095,0,172,172,3]])

    def test_max_signed_ids_and_rle_repeated_coordinates(self):
        codec=self.codec();rows=[(1,-1,-1),(2**62+21,0,0),(2**63-1,SCALE,SCALE)]
        actual=self.encode(codec,rows);self.assertEqual(actual,reference(rows,codec.cells))
        self.assertEqual(codec.lookup(actual,[2**63-1,1,1]),[codec.cells.cell(SCALE,SCALE),codec.cells.cell(-1,-1),codec.cells.cell(-1,-1)])
        rows=[(i+1,0,0) for i in range(4096)];actual=self.encode(codec,rows)
        self.assertEqual(actual,reference(rows,codec.cells));self.assertEqual(len(actual),ENVELOPE.size+BODY.size+4095+4)

    def test_missing_typed_reference_never_becomes_an_outside_cell(self):
        codec=self.codec();raw=self.encode(codec,[(1,0,0),(3,SCALE,SCALE)])
        for queries in [[2],[0],[-1],[True],[2**63],[]]:
            with self.assertRaises(PilotError):codec.lookup(raw,queries)

    def test_envelope_and_resigned_semantic_corruption_are_rejected(self):
        codec=self.codec();raw=self.encode(codec,[(1,0,0),(3,SCALE,SCALE)])
        corrupt=bytearray(raw);corrupt[-1]^=1
        with self.assertRaises(PilotError):codec.lookup(bytes(corrupt),[1])
        original=body(raw)[0];changes=[]
        for offset,value,fmt in [(0,0,'<I'),(4,-1,'<q'),(12,1,'<q'),(24,0,'<I')]:
            damaged=bytearray(original);struct.pack_into(fmt,damaged,offset,value);changes.append(damaged)
        id_bytes=BODY.unpack_from(original)[3];start=BODY.size+id_bytes
        for offset,value in [(start,codec.cells.count),(start+2,0),(start+2,4096)]:
            damaged=bytearray(original);struct.pack_into('<H',damaged,offset,value);changes.append(damaged)
        damaged=bytearray(original);damaged[BODY.size]=0;changes.append(damaged)
        changes.extend([original[:-1],original+b'\0'])
        for damaged in changes:
            with self.assertRaises(PilotError):codec.lookup(envelope(damaged),[1])

    def test_noncanonical_duplicate_runs_and_overlong_id_varint_fail(self):
        codec=self.codec();raw=self.encode(codec,[(1,0,0),(3,0,0)])
        payload=body(raw)[0];n,first,last,ids,runs=BODY.unpack_from(payload)
        run=payload[BODY.size+ids:];cell=struct.unpack_from('<H',run)[0]
        duplicate=BODY.pack(n,first,last,ids,2)+payload[BODY.size:BODY.size+ids]+struct.pack('<HHHH',cell,1,cell,1)
        overlong=BODY.pack(n,first,last,2,runs)+b'\x82\x00'+run
        for damaged in [duplicate,overlong]:
            with self.assertRaises(PilotError):codec.lookup(envelope(damaged),[1])

    def test_fine_source_corruption_and_grid_bounds_are_rejected(self):
        codec=self.codec();payload=ReferenceCodec().encode([(1,0,0),(3,0,0)])
        for bad in [payload[:-1],payload+b'\0',struct.pack('<ii',180*SCALE+1,0)+payload[8:]]:
            with self.assertRaises(PilotError):codec.encode(bad,2,1,3)
        codec.x[0]=180*SCALE+1
        with self.assertRaises(PilotError):codec.encode(payload,2,1,3)

    def test_native_row_and_call_caps_include_roundtrip_and_failed_calls(self):
        codec=self.codec(row_budget=3);payload=ReferenceCodec().encode([(1,0,0),(3,0,0)])
        with self.assertRaises(PilotError):codec.encode(payload,2,1,3)
        self.assertEqual((codec.rows,codec.calls),(2,1))
        codec=self.codec(call_budget=1)
        with self.assertRaises(PilotError):codec.encode(payload,2,1,3)
        self.assertEqual(codec.calls,1)

    def test_native_small_output_buffers_leave_sentinels_untouched(self):
        codec=self.codec();raw=self.encode(codec,[(1,0,0),(3,0,0)]);payload=body(raw)[0]
        source=(ctypes.c_uint8*len(payload)).from_buffer_copy(payload);queries=(ctypes.c_int64*2)(1,3);out=(ctypes.c_uint16*2)(65535,65535)
        self.assertNotEqual(codec.query(source,len(payload),codec.cells.count,queries,2,out,1),0)
        self.assertEqual(list(out),[65535,65535])
        queries[1]=2
        self.assertNotEqual(codec.query(source,len(payload),codec.cells.count,queries,2,out,2),0)
        self.assertEqual(list(out),[65535,65535])
