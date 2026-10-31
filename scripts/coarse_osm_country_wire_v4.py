"""GPF1 field-wire oracle with the V4 screen's explicit 8 MiB frame bound.

The wire encoding/semantic seal is unchanged. The frozen V1 oracle's 2 MiB
policy remains intact; this version permits 4 MiB validated source objects.
"""
import ctypes
import hashlib
import struct
from coarse_osm_compact_v1 import coordinate
from coarse_osm_records import canonical
from coarse_timing_input import require

KINDS=('node','way','relation')
FRAME_HEAD=struct.Struct('<4sBBHqq')
BLOCK_EVENT=struct.Struct('<IqqI')
MAX_FRAME=8388608
MAX_INPUT=16777216
SEAL_PREFIX=b'geo-planner-projected-fields-v1\0'
CALLBACK=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32)


def field_frame(raw,*,tag_pairs=None):
    """Independent wire oracle for a projected native object, not a PBF decoder."""
    def string(value):
        body=value.encode('utf-8');return struct.pack('<I',len(body))+body
    kind=KINDS.index(raw['type']);identity=raw['id'];version=raw['version']
    require(type(identity) is int and type(version) is int and -(2**63)<=identity<2**63 and -(2**63)<=version<2**63,'Projected scalar widths')
    out=bytearray(FRAME_HEAD.pack(b'GPF1',kind,1 if raw.get('visible',True) else 0,0,identity,version));out.extend(string(raw['timestamp']))
    pairs=tag_pairs if tag_pairs is not None else sorted(raw.get('tags',{}).items())
    out.extend(struct.pack('<I',len(pairs)))
    for key,value in pairs:out.extend(string(key));out.extend(string(value))
    if kind==0:
        out.extend(struct.pack('<ii',coordinate(raw['lon'],180),coordinate(raw['lat'],90)))
    elif kind==1:
        out.extend(struct.pack('<I',len(raw['nodes'])))
        for identity in raw['nodes']:out.extend(struct.pack('<q',identity))
    else:
        out.extend(struct.pack('<I',len(raw['members'])))
        for member in raw['members']:
            out.extend(struct.pack('<Bq',KINDS.index(member['type']),member['ref']));out.extend(string(member['role']))
    require(len(out)<=MAX_FRAME,'Projected frame bound')
    return bytes(out)


def framed_records(rows):
    output=bytearray()
    for row in rows:
        body=field_frame(row);output.extend(struct.pack('<I',len(body)));output.extend(body)
    require(len(output)<=MAX_INPUT,'Projected input cap');return bytes(output)


def decode_frame(body):
    require(isinstance(body,bytes) and FRAME_HEAD.size<=len(body)<=MAX_FRAME,'Projected frame size/type')
    magic,kind,visible,reserved,identity,version=FRAME_HEAD.unpack_from(body)
    require(magic==b'GPF1' and kind<3 and visible==1 and reserved==0 and identity>0 and version>0,'Projected frame header')
    p=FRAME_HEAD.size
    def number(fmt):
        nonlocal p
        size=struct.calcsize(fmt);require(p+size<=len(body),'Projected truncated integer');value=struct.unpack_from(fmt,body,p);p+=size;return value[0] if len(value)==1 else value
    def string():
        nonlocal p
        size=number('<I');require(size<=len(body)-p,'Projected truncated string');text=body[p:p+size].decode('utf-8');p+=size;return text
    raw={'type':KINDS[kind],'id':identity,'version':version,'timestamp':string(),'visible':True,'tags':{}}
    count=number('<I');require(count<=(len(body)-p)//8,'Projected tag count')
    for _ in range(count):
        key,value=string(),string();require(key not in raw['tags'],'Projected duplicate tag');raw['tags'][key]=value
    if kind==0:
        x,y=number('<ii');require(-1800000000<=x<=1800000000 and -900000000<=y<=900000000,'Projected XY range');raw.update(lon=x/10000000,lat=y/10000000)
    elif kind==1:
        count=number('<I');require(2<=count<=(len(body)-p)//8,'Projected reference count');raw['nodes']=[number('<q') for _ in range(count)]
        require(all(v>0 for v in raw['nodes']),'Projected reference identity')
    else:
        count=number('<I');require(count<=(len(body)-p)//13,'Projected member count');members=[]
        for _ in range(count):
            member_kind,ref=number('<Bq');require(member_kind<3 and ref>0,'Projected member identity');members.append({'type':KINDS[member_kind],'ref':ref,'role':string()})
        raw['members']=members
    require(p==len(body),'Projected trailing bytes');return raw


def reference_seal(rows):
    hashed=hashlib.sha256(SEAL_PREFIX)
    for raw in rows:
        body=field_frame(raw);hashed.update(struct.pack('<I',len(body)));hashed.update(body)
    return hashed.hexdigest()
