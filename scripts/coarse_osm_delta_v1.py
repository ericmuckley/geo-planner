"""Exact block/delta XY32 storage, bounded C ABI and independent Python codec."""
from array import array
from collections import OrderedDict
import ctypes
import hashlib
from pathlib import Path
import re
import struct
import stat

from coarse_osm_compact_v1 import coordinate, SCALE, Storage
from coarse_osm_records import canonical, strict_json
from coarse_timing_input import require

ROWS = 4096
SHARD_BLOCKS = 512
CACHE_BLOCKS = 64
MAX_ID = 2**63-1
MAX_PAYLOAD = ROWS*8+(ROWS-1)*9
BLOCK = struct.Struct('<4sBBHQQII32s')
ENTRY = struct.Struct('<QQIHHII')
SHARD = struct.Struct('<8sHHIIIQQQQ32s32sQ')
DIRECTORY = struct.Struct('<8sHHIQQQ32s32s24s')
FORMAT = 'block-id-delta-xy32-v1'
assert (BLOCK.size, ENTRY.size, SHARD.size, DIRECTORY.size) == (64, 32, 128, 128)


def valid_rows(rows):
    require(0 < len(rows) <= ROWS, 'Delta row count')
    previous = 0
    for identity, x, y in rows:
        require(all(type(v) is int for v in (identity,x,y)) and previous < identity <= MAX_ID, 'Delta identity/order/type')
        require(-1800000000 <= x <= 1800000000 and -900000000 <= y <= 900000000, 'Delta XY range')
        previous = identity


class ReferenceCodec:
    """Independent straightforward oracle; not the native fast implementation."""
    def encode(self, rows):
        valid_rows(rows); payload=bytearray();previous=rows[0][0]
        for k,(identity,x,y) in enumerate(rows):
            if k:
                delta=identity-previous
                while delta>127:payload.append((delta&127)|128);delta>>=7
                payload.append(delta);previous=identity
            payload.extend(struct.pack('<ii',x,y))
        return bytes(payload)

    def decode(self, payload, count, first, last):
        require(type(count) is int and 0<count<=ROWS and type(first) is int and type(last) is int and 0<first<=last<=MAX_ID, 'Delta decode header')
        require(8*count+count-1<=len(payload)<=8*count+9*(count-1), 'Delta payload size')
        position=0;identity=first;rows=[]
        for k in range(count):
            if k:
                delta=0
                for shift in range(0,63,7):
                    require(position<len(payload),'Delta truncated varint')
                    byte=payload[position];position+=1;delta|=(byte&127)<<shift
                    if not byte&128:
                        require(not shift or byte&127,'Delta noncanonical varint');break
                else:require(False,'Delta overlong varint')
                require(delta>0 and identity+delta<=MAX_ID,'Delta zero/overflow');identity+=delta
            require(position+8<=len(payload),'Delta truncated XY')
            x,y=struct.unpack_from('<ii',payload,position);position+=8;rows.append((identity,x,y))
        valid_rows(rows)
        require(position==len(payload) and identity==last,'Delta trailing bytes/last ID')
        return rows


class NativeCodec:
    def __init__(self, path, expected_sha, *, row_budget=2000000):
        path=Path(path)
        require(not path.is_symlink() and path.is_file() and path.stat().st_size<=33554432,'Delta native artifact type/size')
        require(hashlib.sha256(path.read_bytes()).hexdigest()==expected_sha,'Delta native artifact drift')
        require(type(row_budget) is int and row_budget>0,'Delta native row budget')
        self.row_budget=row_budget;self.encoded_rows=self.decoded_rows=self.calls=0
        self.library=ctypes.CDLL(str(path.resolve()))
        abi=self.library.gp_delta_abi;abi.argtypes=[];abi.restype=ctypes.c_uint32
        require(abi()==0x10000,'Delta C ABI version')
        i64=ctypes.POINTER(ctypes.c_int64);i32=ctypes.POINTER(ctypes.c_int32);u8=ctypes.POINTER(ctypes.c_uint8)
        self.enc=self.library.gp_delta_encode;self.enc.argtypes=[i64,i32,ctypes.c_uint32,u8,ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32)];self.enc.restype=ctypes.c_int
        self.dec=self.library.gp_delta_decode;self.dec.argtypes=[u8,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_int64,ctypes.c_int64,i64,i32,ctypes.c_uint32];self.dec.restype=ctypes.c_int

    def encode(self, rows):
        valid_rows(rows)
        ids=(ctypes.c_int64*len(rows))(*(r[0] for r in rows));xy=(ctypes.c_int32*(len(rows)*2))(*(v for r in rows for v in r[1:]))
        out=(ctypes.c_uint8*MAX_PAYLOAD)();written=ctypes.c_uint32()
        require(self.encoded_rows+self.decoded_rows+len(rows)<=self.row_budget,'Delta native aggregate row budget')
        self.encoded_rows+=len(rows);self.calls+=1
        code=self.enc(ids,xy,len(rows),out,MAX_PAYLOAD,ctypes.byref(written))
        require(code==0 and 0<written.value<=MAX_PAYLOAD,'Delta native encode refused')
        return bytes(out[:written.value])

    def decode(self, payload, count, first, last):
        require(type(count) is int and 0<count<=ROWS and type(first) is int and type(last) is int and 0<first<=last<=MAX_ID and len(payload)<=MAX_PAYLOAD,'Delta native decode bounds')
        ids=(ctypes.c_int64*count)();xy=(ctypes.c_int32*(count*2))();raw=(ctypes.c_uint8*len(payload)).from_buffer_copy(payload)
        require(self.encoded_rows+self.decoded_rows+count<=self.row_budget,'Delta native aggregate row budget')
        self.decoded_rows+=count;self.calls+=1
        code=self.dec(raw,len(payload),count,first,last,ids,xy,count)
        require(code==0,'Delta native decode refused')
        return [(ids[k],xy[2*k],xy[2*k+1]) for k in range(count)]


def encode_block(rows,codec):
    payload=codec.encode(rows)
    return BLOCK.pack(b'GPDB',1,0,len(rows),rows[0][0],rows[-1][0],len(payload),0,hashlib.sha256(payload).digest())+payload


def block_fields(raw):
    require(BLOCK.size+8<=len(raw)<=BLOCK.size+MAX_PAYLOAD,'Delta block length')
    magic,version,flags,count,first,last,size,reserved,digest=BLOCK.unpack_from(raw)
    require((magic,version,flags,reserved)==(b'GPDB',1,0,0) and size==len(raw)-BLOCK.size,'Delta block header')
    require(0<count<=ROWS and 0<first<=last<=MAX_ID and count*8+count-1<=size<=count*8+9*(count-1),'Delta block count/IDs')
    payload=raw[BLOCK.size:];require(hashlib.sha256(payload).digest()==digest,'Delta block checksum')
    return count,first,last,payload


def decode_block(raw,codec):
    count,first,last,payload=block_fields(raw)
    return codec.decode(payload,count,first,last)


def read_file(path, maximum):
    require(not path.is_symlink() and path.is_file() and path.stat().st_size<=maximum,'Delta file type/size')
    return path.read_bytes()


def file_stamp(path):
    value=path.lstat()
    require(stat.S_ISREG(value.st_mode),'Delta regular file required')
    return (value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,value.st_ctime_ns)


class Reader:
    def __init__(self, root, codec, *, index_limit=33554432, catalog_limit=16777216, cache_blocks=CACHE_BLOCKS):
        self.root,self.codec=Path(root),codec
        require(type(cache_blocks) is int and 0<=cache_blocks<=CACHE_BLOCKS,'Delta cache bound')
        self.index_limit,self.catalog_limit,self.cache_limit=index_limit,catalog_limit,cache_blocks
        self.cache=OrderedDict();self.closed=False;self.loaded_bytes=0;self.stamps={}
        raw=read_file(self.root/'index.json',catalog_limit);self.manifest_sha=hashlib.sha256(raw).hexdigest();m=strict_json(raw)
        require(isinstance(m,dict) and set(m)=={'format','rows','blocks','directory','shards'} and m['format']==FORMAT,'Delta manifest schema')
        require(all(type(m[k]) is int and m[k]>=0 for k in ('rows','blocks')) and isinstance(m['shards'],list) and len(m['shards'])<=catalog_limit//64,'Delta manifest counts')
        self.manifest=m
        require(set(m['directory'])=={'bytes','sha256'},'Delta directory descriptor')
        require(type(m['directory']['bytes']) is int and DIRECTORY.size<=m['directory']['bytes']<=catalog_limit and re.fullmatch('[0-9a-f]{64}',m['directory']['sha256']),'Delta directory descriptor values')
        directory=read_file(self.root/'directory.bin',catalog_limit)
        require(len(directory)==m['directory']['bytes'] and hashlib.sha256(directory).hexdigest()==m['directory']['sha256'],'Delta directory checksum/size')
        magic,version,flags,entry_size,blocks,rows,shards,body_sha,shards_sha,reserved=DIRECTORY.unpack_from(directory)
        require((magic,version,flags,entry_size,reserved)==(b'GPDIR1\0\0',1,0,ENTRY.size,b'\0'*24),'Delta directory header')
        require((blocks,rows,shards)==(m['blocks'],m['rows'],len(m['shards'])) and len(directory)==DIRECTORY.size+blocks*ENTRY.size,'Delta directory count/size')
        require(hashlib.sha256(directory[DIRECTORY.size:]).digest()==body_sha and hashlib.sha256(canonical(m['shards'])).digest()==shards_sha,'Delta directory body/shards seal')
        self.directory=directory
        total_rows=total_blocks=total_bytes=previous_last=0
        self.starts=[]
        for number,entry in enumerate(m['shards']):
            require(isinstance(entry,dict) and set(entry)=={'first','last','rows','blocks','bytes','sha256'},'Delta shard descriptor')
            require(all(type(entry[k]) is int for k in ('first','last','rows','blocks','bytes')) and 0<entry['blocks']<=SHARD_BLOCKS and 0<entry['rows']<=entry['blocks']*ROWS,'Delta shard counts')
            require(previous_last<entry['first']<=entry['last']<=MAX_ID and SHARD.size<entry['bytes']<=SHARD.size+SHARD_BLOCKS*(BLOCK.size+MAX_PAYLOAD) and re.fullmatch('[0-9a-f]{64}',entry['sha256']),'Delta shard descriptor bounds')
            self.starts.append(total_blocks);offset=SHARD.size;shard_rows=0
            for local in range(entry['blocks']):
                end,start,length,count,zero,shard,zero2=self.entry(total_blocks+local)
                require(shard==number and start==offset and zero==zero2==0 and 0<count<=ROWS and BLOCK.size+count*8+count-1<=length<=BLOCK.size+count*8+9*(count-1),'Delta directory entry')
                require(previous_last<end<=MAX_ID,'Delta directory ID order')
                previous_last=end;offset+=length;shard_rows+=count
            require(previous_last==entry['last'] and shard_rows==entry['rows'] and offset==entry['bytes'],'Delta directory shard totals')
            total_blocks+=entry['blocks'];total_rows+=entry['rows'];total_bytes+=entry['bytes']
        require((total_rows,total_blocks)==(m['rows'],m['blocks']) and total_bytes+len(raw)+len(directory)<=index_limit,'Delta index counts/byte cap')
        require(bool(m['rows'])==bool(m['blocks'])==bool(m['shards']),'Delta empty index closure')
        self.bytes=total_bytes+len(raw)+len(directory)

    def entry(self,number):
        require(type(number) is int and 0<=number<self.manifest['blocks'],'Delta directory position')
        return ENTRY.unpack_from(self.directory,DIRECTORY.size+number*ENTRY.size)

    def path(self,number):return self.root/f'{number:08d}.bin'

    def verify_catalogs(self):
        require(hashlib.sha256(read_file(self.root/'index.json',self.catalog_limit)).hexdigest()==self.manifest_sha,'Delta manifest changed')
        require(read_file(self.root/'directory.bin',self.catalog_limit)==self.directory,'Delta directory changed')

    def validate_shard(self,number,selected=None):
        require(not self.closed and type(number) is int and 0<=number<len(self.manifest['shards']),'Delta shard lookup state')
        entry=self.manifest['shards'][number];before=file_stamp(self.path(number));raw=read_file(self.path(number),self.index_limit)
        require(before==file_stamp(self.path(number)),'Delta shard changed during read')
        require(len(raw)==entry['bytes'] and hashlib.sha256(raw).hexdigest()==entry['sha256'],'Delta shard full checksum/size')
        magic,version,flags,shard,blocks,zero,rows,first,last,length,payload_sha,entries_sha,reserved=SHARD.unpack_from(raw)
        require((magic,version,flags,shard,zero,reserved)==(b'GPSHARD1',1,0,number,0,0),'Delta shard header')
        require((blocks,rows,first,last,length)==(entry['blocks'],entry['rows'],entry['first'],entry['last'],len(raw)-SHARD.size),'Delta shard header totals')
        begin=self.starts[number];table=self.directory[DIRECTORY.size+begin*ENTRY.size:DIRECTORY.size+(begin+blocks)*ENTRY.size]
        require(hashlib.sha256(raw[SHARD.size:]).digest()==payload_sha and hashlib.sha256(table).digest()==entries_sha,'Delta shard/table seal')
        previous=0;chosen=None
        for k in range(blocks):
            end,start,size,count,_,_,_=self.entry(begin+k)
            n,block_first,block_last,payload=block_fields(raw[start:start+size])
            require(n==count and block_last==end and previous<block_first,'Delta block/directory order')
            if k==0:require(block_first==first,'Delta shard first ID')
            previous=end
            if selected is None or begin+k==selected:
                values=self.codec.decode(payload,n,block_first,block_last)
                if begin+k==selected:
                    chosen=(array('q',(v[0] for v in values)),array('i',(c for v in values for c in v[1:])))
        require(before==file_stamp(self.path(number)),'Delta shard changed during validation')
        self.stamps[number]=before
        self.loaded_bytes+=len(raw)
        return chosen

    def block(self,number):
        require(not self.closed,'Delta reader closed')
        end,start,size,count,_,shard,_=self.entry(number)
        stamp=file_stamp(self.path(shard))
        if shard in self.stamps:
            require(stamp==self.stamps[shard],'Delta cached shard changed')
        if number in self.cache:
            self.cache.move_to_end(number);return self.cache[number]
        if shard not in self.stamps:
            # One full checksum/header scan before trusting exact block reads.
            chosen=self.validate_shard(shard,number)
        else:
            with self.path(shard).open('rb') as stream:
                stream.seek(start);raw=stream.read(size)
            require(stamp==file_stamp(self.path(shard)) and len(raw)==size,'Delta block read drift/size')
            values=decode_block(raw,self.codec)
            require(len(values)==count and values[-1][0]==end,'Delta queried block directory mismatch')
            chosen=(array('q',(v[0] for v in values)),array('i',(c for v in values for c in v[1:])))
            self.loaded_bytes+=len(raw)
        if self.cache_limit:
            self.cache[number]=chosen
            while len(self.cache)>self.cache_limit:self.cache.popitem(last=False)
        return chosen

    def points(self,ids):
        require(not self.closed and len(ids)<=65536,'Delta lookup batch/closed')
        self.verify_catalogs()
        grouped={};found={}
        for identity in ids:
            require(type(identity) is int and 0<identity<=MAX_ID,'Delta query identity')
            lo,hi=0,self.manifest['blocks']
            while lo<hi:
                middle=(lo+hi)//2
                if self.entry(middle)[0]<identity:lo=middle+1
                else:hi=middle
            require(lo<self.manifest['blocks'],'Delta missing node');grouped.setdefault(lo,[]).append(identity)
        for number,keys in grouped.items():
            values,xy=self.block(number)
            for identity in keys:
                lo,hi=0,len(values)
                while lo<hi:
                    middle=(lo+hi)//2
                    if values[middle]<identity:lo=middle+1
                    else:hi=middle
                require(lo<len(values) and values[lo]==identity,'Delta missing node')
                x,y=xy[2*lo:2*lo+2];found[identity]=[x/SCALE,y/SCALE]
        return [found[i] for i in ids]

    def close(self):self.cache.clear();self.closed=True


class Index:
    def __init__(self,root,storage,*,codec,rows_per_shard=None,index_limit=33554432,catalog_limit=16777216,replacing=None,blocks_per_shard=SHARD_BLOCKS):
        require(rows_per_shard in (None,65536),'Delta row-shard option unsupported; fixed4096-row blocks')
        require(type(blocks_per_shard) is int and 0<blocks_per_shard<=SHARD_BLOCKS,'Delta shard block bound')
        self.root=Path(root);self.root.mkdir();self.codec,self.storage=codec,storage
        self.index_limit,self.catalog_limit,self.replacing=index_limit,catalog_limit,replacing
        self.block_limit=blocks_per_shard
        self.rows=[];self.shard_body=bytearray();self.table=bytearray();self.shards=[]
        self.shard_first=self.shard_rows=self.shard_blocks=self.shard_table_start=0
        self.last=self.count=self.generated_bytes=self.blocks=0
        self.closed=self.finished=False;self.reader=None

    def path(self,number):return self.root/f'{number:08d}.bin'

    def add(self,raw):
        self.add_xy(raw['id'],coordinate(raw['lon'],180),coordinate(raw['lat'],90))

    def add_xy(self,identity,x,y):
        require(not self.closed and not self.finished,'Delta writer closed/finished')
        require(type(identity) is int and self.last<identity<=MAX_ID,'Delta writer identity/order')
        valid_rows([(identity,x,y)])
        self.rows.append((identity,x,y));self.last=identity;self.count+=1
        if len(self.rows)==ROWS:self.flush_block()

    def flush_block(self):
        if not self.rows:return
        raw=encode_block(self.rows,self.codec)
        require(self.generated_bytes+len(self.shard_body)+len(raw)+len(self.table)+DIRECTORY.size+SHARD.size<=self.index_limit,'Delta index write cap')
        require(len(self.table)+ENTRY.size+DIRECTORY.size<=self.catalog_limit,'Delta directory write cap')
        if not self.shard_blocks:self.shard_first=self.rows[0][0]
        self.table.extend(ENTRY.pack(self.rows[-1][0],SHARD.size+len(self.shard_body),len(raw),len(self.rows),0,len(self.shards),0))
        self.shard_body.extend(raw);self.shard_rows+=len(self.rows);self.shard_blocks+=1;self.blocks+=1;self.rows.clear()
        if self.shard_blocks==self.block_limit:self.flush_shard()

    def flush_shard(self):
        if not self.shard_blocks:return
        require(not self.rows,'Delta unflushed block at shard seal')
        table=bytes(self.table[self.shard_table_start:]);payload=bytes(self.shard_body)
        header=SHARD.pack(b'GPSHARD1',1,0,len(self.shards),self.shard_blocks,0,self.shard_rows,self.shard_first,self.last,len(payload),hashlib.sha256(payload).digest(),hashlib.sha256(table).digest(),0)
        raw=header+payload;entry={'first':self.shard_first,'last':self.last,'rows':self.shard_rows,'blocks':self.shard_blocks,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        require(self.generated_bytes+len(raw)+len(self.table)+DIRECTORY.size<=self.index_limit,'Delta shard/index cap')
        number=len(self.shards);self.storage.write(self.path(number),raw)
        self.shards.append(entry);self.generated_bytes+=len(raw)
        if self.replacing is not None:
            old=self.replacing
            require(old.finished and not old.closed and number<len(old.reader.manifest['shards']) and entry==old.reader.manifest['shards'][number],'Delta source/index replacement drift')
            old.reader.cache.clear();old.reader.validate_shard(number)
            path=old.path(number);before=file_stamp(path)
            require(hashlib.sha256(read_file(path,self.index_limit)).hexdigest()==entry['sha256'] and before==file_stamp(path),'Delta removal file drift')
            self.storage.remove(path,entry['bytes'])
        self.shard_body.clear();self.shard_table_start=len(self.table);self.shard_rows=self.shard_blocks=0

    def finish(self):
        require(not self.closed,'Delta index closed')
        if self.finished:return
        self.flush_block();self.flush_shard()
        require(len(canonical(self.shards))<=self.catalog_limit,'Delta shard catalog cap')
        directory=DIRECTORY.pack(b'GPDIR1\0\0',1,0,ENTRY.size,self.blocks,self.count,len(self.shards),hashlib.sha256(self.table).digest(),hashlib.sha256(canonical(self.shards)).digest(),b'\0'*24)+self.table
        manifest={'format':FORMAT,'rows':self.count,'blocks':self.blocks,'directory':{'bytes':len(directory),'sha256':hashlib.sha256(directory).hexdigest()},'shards':self.shards}
        raw=canonical(manifest)+b'\n'
        require(len(directory)<=self.catalog_limit and len(raw)<=self.catalog_limit and self.generated_bytes+len(directory)+len(raw)<=self.index_limit,'Delta final catalog/index cap')
        if self.replacing is not None:
            self.replacing.reader.verify_catalogs();require(manifest==self.replacing.reader.manifest,'Delta replacement closure mismatch')
        self.storage.write(self.root/'directory.bin',directory);self.storage.write(self.root/'index.json',raw)
        self.generated_bytes+=len(directory)+len(raw);self.finished=True
        self.reader=Reader(self.root,self.codec,index_limit=self.index_limit,catalog_limit=self.catalog_limit)
        self.table.clear()

    def points(self,ids):
        require(self.finished and not self.closed,'Delta unfinished lookup');return self.reader.points(ids)

    def close(self):
        if self.reader is not None:self.reader.close()
        self.rows.clear();self.table.clear();self.shard_body.clear();self.closed=True
