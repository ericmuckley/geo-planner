"""Bounded native projector bridge and lossless field frames; no full-data launcher."""
from copy import deepcopy
import ctypes
import hashlib
import os
from pathlib import Path
import struct

from coarse_osm_bulk_pbf import framing
from coarse_osm_compact_v1 import coordinate
from coarse_osm_delta_v1 import BLOCK,ENTRY,SHARD,MAX_PAYLOAD,ROWS,NativeCodec
from coarse_osm_delta_v2 import Index as DeltaIndex
from coarse_osm_records import canonical
from coarse_timing_input import require

KINDS=('node','way','relation')
FRAME_HEAD=struct.Struct('<4sBBHqq')
BLOCK_EVENT=struct.Struct('<IqqI')
MAX_FRAME=2097152
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


class EncodedIndex(DeltaIndex):
    """Accept bounded source-validated native blocks without Python node objects."""
    def append_encoded(self,event,codec):
        require(not self.finished and not self.closed and not self.rows,'Encoded index state')
        require(BLOCK_EVENT.size+8<=len(event)<=BLOCK_EVENT.size+MAX_PAYLOAD,'Encoded block event bound')
        count,first,last,size=BLOCK_EVENT.unpack_from(event);payload=event[BLOCK_EVENT.size:]
        require(0<count<=ROWS and self.last<first<=last<2**63 and size==len(payload),'Encoded block identity/size')
        # Validate with the frozen C decoder into typed arrays, without Python per-row tuples.
        ids=(ctypes.c_int64*count)();xy=(ctypes.c_int32*(count*2))();source=(ctypes.c_uint8*size).from_buffer_copy(payload)
        require(codec.encoded_rows+codec.decoded_rows+count<=codec.row_budget,'Encoded block decode budget')
        codec.decoded_rows+=count;codec.calls+=1
        require(codec.dec(source,size,count,first,last,ids,xy,count)==0,'Encoded block native verification')
        raw=BLOCK.pack(b'GPDB',1,0,count,first,last,size,0,hashlib.sha256(payload).digest())+payload
        require(self.generated_bytes+len(self.shard_body)+len(raw)+len(self.table)+128+SHARD.size<=self.index_limit,'Encoded index cap')
        require(len(self.table)+ENTRY.size+128<=self.catalog_limit,'Encoded catalog cap')
        if not self.shard_blocks:self.shard_first=first
        self.table.extend(ENTRY.pack(last,SHARD.size+len(self.shard_body),len(raw),count,0,len(self.shards),0))
        self.shard_body.extend(raw);self.shard_rows+=count;self.shard_blocks+=1;self.blocks+=1
        self.last=last;self.count+=count
        if self.shard_blocks==self.block_limit:self.flush_shard()


class NativeProjector:
    def __init__(self,path,sha,*,aggregate_visits=2000000):
        self.codec=NativeCodec(path,sha);self.library=self.codec.library
        abi=self.library.gp_projector_abi;abi.argtypes=[];abi.restype=ctypes.c_uint32;require(abi()==0x10000,'Projector ABI')
        u64=ctypes.POINTER(ctypes.c_uint64);i64=ctypes.POINTER(ctypes.c_int64)
        common=[ctypes.c_char_p,ctypes.c_uint32,u64,ctypes.c_uint32,i64,ctypes.c_uint32,CALLBACK,ctypes.c_void_p,u64,ctypes.c_uint32,ctypes.c_char_p,ctypes.c_uint32]
        self.frames=self.library.gp_project_frames;self.frames.argtypes=[ctypes.c_void_p,ctypes.c_uint64,*common];self.frames.restype=ctypes.c_int
        self.pbf=self.library.gp_project_pbf;self.pbf.argtypes=[ctypes.c_char_p,*common];self.pbf.restype=ctypes.c_int
        require(type(aggregate_visits) is int and 0<aggregate_visits<=2000000,'Projector aggregate bound')
        self.aggregate_limit,self.visits=aggregate_visits,0;self.active=False;self.last=None

    def _run(self,function,args,snapshot,caps,*,proof=False,selected=(),on_record=None,on_block=None,check=lambda:None,fallback=True):
        require(not self.active,'Projector reentrant scan')
        require(isinstance(snapshot,str) and len(snapshot.encode('utf-8'))==20 and snapshot.isascii() and '\0' not in snapshot,'Projector snapshot boundary')
        limit=caps['singleNormalizedElementBytes'];require(type(limit) is int and 0<limit<=1048576,'Projector element cap')
        keys=('scanNodesPerPass','scanWaysPerPass','scanRelationsPerPass','scanObjectVisitsTotal')
        values=[caps[k] for k in keys];require(all(type(v) is int and 0<v<=2000000 for v in values),'Projector visit caps')
        values=[min(v,self.aggregate_limit-self.visits) for v in values];require(min(values)>0,'Projector aggregate exhausted')
        require(len(selected)<=250000 and all(type(v) is int and 0<v<2**63 and (k==0 or v>selected[k-1]) for k,v in enumerate(selected)),'Projector selected IDs')
        limits=(ctypes.c_uint64*4)(*values);ids=(ctypes.c_int64*len(selected))(*selected);receipt=(ctypes.c_uint64*10)();error=ctypes.create_string_buffer(512)
        hashed=hashlib.sha256(SEAL_PREFIX);failure=[];projected=0;blocks=0;fallbacks=0;events=[0]*5
        def callback(user,event,pointer,size):
            nonlocal projected,blocks,fallbacks
            try:
                require(size<=MAX_FRAME and event<5,'Projector callback byte/kind bound');events[event]+=1;check();body=ctypes.string_at(pointer,size) if size else b''
                if event==0:hashed.update(body)
                elif event==1:
                    fallbacks+=1;require(fallback,'Projector canonical fallback unavailable')
                    require(len(canonical(decode_frame(body)))<=limit,'Projector exact canonical byte cap')
                elif event==2:
                    projected+=1
                    if on_record is not None:on_record(decode_frame(body))
                elif event==3:
                    blocks+=1
                    if on_block is not None:on_block(body)
                else:require(event==4 and not body,'Projector callback kind')
                return 0
            except BaseException as exc:failure.append(exc);return -1
        handle=CALLBACK(callback);self.active=True;self._receipt=receipt;completed=False
        try:
            check()
            code=function(*args,snapshot.encode('utf-8'),limit,limits,int(proof),ids,len(selected),handle,None,receipt,10,error,512)
            check();completed=code==0
        finally:
            self.active=False;self.visits+=receipt[3]
            self.last={'counts':{k:int(receipt[i]) for i,k in enumerate(KINDS) if receipt[i]},'visits':int(receipt[3]),'nativeEof':bool(receipt[4]) and completed and not failure,
                'fallbacks':int(receipt[5]),'blocks':int(receipt[6]),'semanticBytes':int(receipt[7]),'projectedFrames':int(receipt[8]),'checkpoints':int(receipt[9]),
                'semanticSha256':hashed.hexdigest(),'semanticFormat':'geo-planner-projected-fields-v1','error':error.value.decode('ascii'),
                'callbackEvents':dict(zip(('semantic_batches','fallbacks','projected','blocks','checkpoints'),events)),
                'mode':'full-field-proof' if proof else 'fast-validated-blocks','pythonProjectionFrames':projected,'callbackFallbacks':fallbacks,'callbackBlocks':blocks}
        if failure:raise failure[0]
        require(code==0 and self.last['nativeEof'],'Native projector stopped: '+self.last['error'])
        if not (self.last['projectedFrames']==projected and self.last['blocks']==blocks and self.last['fallbacks']==fallbacks and self.last['checkpoints']==events[4]):
            self.last['nativeEof']=False
            require(False,'Projector callback/receipt accounting')
        return deepcopy(self.last)

    def progress(self):
        values=self._receipt if self.active else None
        return {'counts':{k:int(values[i]) for i,k in enumerate(KINDS) if values[i]},'visits':int(values[3])} if values is not None else {'counts':{},'visits':0}

    def validate_frames(self,raw,snapshot,caps,**options):
        if not self.active:self.last=None
        require(isinstance(raw,bytes) and len(raw)<=MAX_INPUT,'Projector frame input cap')
        data=ctypes.create_string_buffer(raw)
        return self._run(self.frames,[data,len(raw)],snapshot,caps,**options)

    def scan(self,path,snapshot,caps,**options):
        require(not self.active,'Projector reentrant scan')
        self.last=None
        path=Path(path)
        require(not path.is_symlink() and path.is_file() and path.stat().st_size<=MAX_INPUT,'Projector synthetic PBF type/size bound')
        identity=framing(path,caps,snapshot,options.get('check',lambda:None))
        try:
            result=self._run(self.pbf,[os.fsencode(path)],snapshot,caps,**options)
            require(hashlib.sha256(path.read_bytes()).hexdigest()==identity['sourceSha256'],'Projector source content changed')
            result['sourceIdentity']=identity;return result
        except BaseException:
            if self.last is not None:self.last['nativeEof']=False
            raise
