"""V2lossless ID-gap runs with canonical raw fallback; no source reader."""
import ctypes
import hashlib
import struct

from coarse_osm_delta_v1 import NativeCodec,ROWS,MAX_PAYLOAD
from coarse_timing_input import require

ENVELOPE=struct.Struct('<4sHH32s')
BODY=struct.Struct('<IqqIII')
MAX_BODY=65536


def body(raw):
    require(isinstance(raw,bytes) and ENVELOPE.size+BODY.size<=len(raw)<=ENVELOPE.size+MAX_BODY,'Cell block byte bound')
    magic,version,flags,pin=ENVELOPE.unpack_from(raw);payload=raw[ENVELOPE.size:]
    require((magic,version,flags)==(b'WC02',2,0) and hashlib.sha256(payload).digest()==pin,'Cell envelope/hash')
    rows,first,last,id_bytes,id_runs,runs=BODY.unpack_from(payload)
    require(0<rows<=ROWS and 0<first<=last<2**63 and 0<=id_runs<=rows-1 and (2*id_runs if id_runs else rows-1)<=id_bytes<=9*(rows-1) and 0<runs<=rows,'Cell block metadata')
    require(BODY.size+id_bytes+4*runs==len(payload),'Cell block payload length')
    return payload,rows,first,last


class Codec:
    def __init__(self,path,sha,cells,*,row_budget=2000000,call_budget=100000):
        require(type(row_budget) is int and 0<row_budget<=10**12 and type(call_budget) is int and 0<call_budget<=100000000,'Cell codec budget')
        self.native=NativeCodec(path,sha);self.library=self.native.library;self.cells=cells
        self.rows=self.calls=0;self.row_budget=row_budget;self.call_budget=call_budget
        self.x=(ctypes.c_int32*len(cells.x))(*cells.x);self.y=(ctypes.c_int32*len(cells.y))(*cells.y)
        abi=self.library.gp_window_cells_v2_abi;abi.argtypes=[];abi.restype=ctypes.c_uint32
        require(abi()==0x20000,'Cell C ABI')
        u8=ctypes.POINTER(ctypes.c_uint8);u32=ctypes.POINTER(ctypes.c_uint32)
        i32=ctypes.POINTER(ctypes.c_int32);i64=ctypes.POINTER(ctypes.c_int64);u16=ctypes.POINTER(ctypes.c_uint16)
        self.enc=self.library.gp_window_cells_v2_encode
        self.enc.argtypes=[u8,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_int64,ctypes.c_int64,i32,ctypes.c_uint32,i32,ctypes.c_uint32,u8,ctypes.c_uint32,u32]
        self.enc.restype=ctypes.c_int
        self.query=self.library.gp_window_cells_v2_lookup
        self.query.argtypes=[u8,ctypes.c_uint32,ctypes.c_uint32,i64,ctypes.c_uint32,u16,ctypes.c_uint32];self.query.restype=ctypes.c_int
        self.convert=self.library.gp_window_cells_v2_from_v1
        self.convert.argtypes=[u8,ctypes.c_uint32,ctypes.c_uint32,u8,ctypes.c_uint32,u32];self.convert.restype=ctypes.c_int

    def charge(self,rows):
        require(self.calls<self.call_budget and self.rows+rows<=self.row_budget,'Cell native rows/calls cap')
        self.calls+=1;self.rows+=rows

    def encode(self,payload,count,first,last):
        require(isinstance(payload,bytes) and 0<len(payload)<=MAX_PAYLOAD and type(count) is int and 0<count<=ROWS,'Cell source block bound')
        require(type(first) is int and type(last) is int and 0<first<=last<2**63,'Cell source ID width')
        source=(ctypes.c_uint8*len(payload)).from_buffer_copy(payload);out=(ctypes.c_uint8*MAX_BODY)();written=ctypes.c_uint32()
        self.charge(count)
        code=self.enc(source,len(payload),count,first,last,self.x,len(self.x),self.y,len(self.y),out,MAX_BODY,ctypes.byref(written))
        require(code==0 and BODY.size<=written.value<=MAX_BODY,'Cell native encode refused')
        encoded=bytes(out[:written.value]);result=ENVELOPE.pack(b'WC02',2,0,hashlib.sha256(encoded).digest())+encoded
        _,n,low,high=body(result);require((n,low,high)==(count,first,last),'Cell encoded metadata drift')
        # Re-decode the complete canonical ID/run block; no Python node rows.
        values=self.lookup(result,[first,last]);require(len(values)==2,'Cell roundtrip count')
        return result

    def lookup(self,raw,queries):
        payload,count,_,_=body(raw)
        require(0<len(queries)<=65536 and all(type(v) is int and 0<v<2**63 for v in queries),'Cell typed query IDs')
        source=(ctypes.c_uint8*len(payload)).from_buffer_copy(payload);ids=(ctypes.c_int64*len(queries))(*queries);out=(ctypes.c_uint16*len(queries))()
        self.charge(count)
        code=self.query(source,len(payload),self.cells.count,ids,len(queries),out,len(queries))
        require(code==0,'Cell native lookup refused or missing node')
        return list(out)

    def from_v1(self,raw):
        from coarse_osm_window_codec_v1 import body as legacy_body
        payload,count,first,last=legacy_body(raw)
        source=(ctypes.c_uint8*len(payload)).from_buffer_copy(payload);out=(ctypes.c_uint8*MAX_BODY)();written=ctypes.c_uint32()
        self.charge(count)
        code=self.convert(source,len(payload),self.cells.count,out,MAX_BODY,ctypes.byref(written))
        require(code==0 and BODY.size<=written.value<=MAX_BODY,'Cell V2native conversion refused')
        encoded=bytes(out[:written.value]);result=ENVELOPE.pack(b'WC02',2,0,hashlib.sha256(encoded).digest())+encoded
        _,n,low,high=body(result);require((n,low,high)==(count,first,last),'Cell V2conversion metadata drift')
        self.lookup(result,[first,last])
        return result
