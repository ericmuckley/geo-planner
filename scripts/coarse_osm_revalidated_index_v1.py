"""Read-only source-block comparison; caller must still prove whole-source EOF."""
import ctypes
from copy import deepcopy
import hashlib
from pathlib import Path

from coarse_osm_delta_v1 import BLOCK,SHARD,DIRECTORY,ENTRY,ROWS,MAX_PAYLOAD,file_stamp
from coarse_osm_delta_v2 import Reader
from coarse_osm_projector_v1 import BLOCK_EVENT
from coarse_timing_input import require

READ_LIMIT=64*1024**3


class SourceIndex:
    def __init__(self,root,codec,expected,*,index_limit=24*1024**3,replacing=None,check=lambda:None,read_limit=READ_LIMIT):
        require(type(read_limit) is int and 0<read_limit<=READ_LIMIT,'Read-only fine IO bound')
        self.root=Path(root);require(self.root.is_dir() and not self.root.is_symlink(),'Read-only fine root kind')
        self.codec=codec;self.check=check;self.read_limit=read_limit;self.expected=deepcopy(expected)
        self.reader=Reader(self.root,codec,index_limit=index_limit,catalog_limit=16*1024**2)
        require(self.reader.manifest==expected,'Read-only fine source census binding')
        require({p.name for p in self.root.iterdir()}=={'index.json','directory.bin',*(f'{i:08d}.bin' for i in range(len(expected['shards'])))},'Read-only fine input roster')
        for name in ('index.json','directory.bin'):self.kind(self.root/name)
        if replacing is not None:
            require(isinstance(replacing,SourceIndex) and replacing.finished and not replacing.closed and replacing.root==self.root and replacing.expected==expected,'Read-only fine independent view binding')
        self.rows=self.blocks=self.last=self.payload_bytes_read=self.verification_passes=self.shards_compared=0
        self.active=None;self.snapshot=b'';self.active_rows=self.active_blocks=0
        self.finished=self.closed=False

    @staticmethod
    def kind(path):
        value=file_stamp(path);require(path.stat().st_nlink==1,'Read-only fine hardlink input');return value

    def charge(self,amount):
        require(self.payload_bytes_read+amount<=self.read_limit,'Read-only fine payload IO cap')
        self.payload_bytes_read+=amount

    def checksum(self,number):
        self.check();path=self.root/f'{number:08d}.bin';expected=self.expected['shards'][number];before=self.kind(path)
        require(before[2]==expected['bytes'],'Read-only fine closed size drift');self.charge(expected['bytes'])
        with path.open('rb') as stream:pin=hashlib.file_digest(stream,'sha256').hexdigest()
        require(pin==expected['sha256'] and self.kind(path)==before,'Read-only fine closed checksum drift')

    def finish_part(self):
        if self.active is None:return
        expected=self.expected['shards'][self.active]
        require(self.active_blocks==expected['blocks'] and self.active_rows==expected['rows'] and self.last==expected['last'],'Read-only fine source shard closure')
        self.checksum(self.active);self.shards_compared+=1;self.active=None;self.snapshot=b''

    def load(self,number):
        self.finish_part();self.check();expected=self.expected['shards'][number];path=self.root/f'{number:08d}.bin';before=self.kind(path)
        require(before[2]==expected['bytes']<=64*1024**2,'Read-only fine snapshot size');self.charge(expected['bytes'])
        raw=path.read_bytes();require(len(raw)==expected['bytes'] and hashlib.sha256(raw).hexdigest()==expected['sha256'] and self.kind(path)==before,'Read-only fine snapshot drift')
        magic,version,flags,shard,blocks,zero,rows,first,last,length,payload_sha,entries_sha,reserved=SHARD.unpack_from(raw)
        require((magic,version,flags,shard,zero,reserved)==(b'GPSHARD1',1,0,number,0,0),'Read-only fine shard header')
        require((blocks,rows,first,last,length)==(expected['blocks'],expected['rows'],expected['first'],expected['last'],len(raw)-SHARD.size),'Read-only fine shard totals')
        begin=self.reader.starts[number];table=self.reader.directory[DIRECTORY.size+begin*ENTRY.size:DIRECTORY.size+(begin+blocks)*ENTRY.size]
        require(hashlib.sha256(raw[SHARD.size:]).digest()==payload_sha and hashlib.sha256(table).digest()==entries_sha,'Read-only fine shard/table seals')
        self.active=number;self.snapshot=raw;self.active_rows=self.active_blocks=0

    def append_encoded(self,event,codec):
        require(not self.finished and not self.closed and codec is self.codec and self.blocks<self.expected['blocks'],'Read-only fine source state/extra block')
        require(BLOCK_EVENT.size+8<=len(event)<=BLOCK_EVENT.size+MAX_PAYLOAD,'Read-only fine source event bound')
        count,first,last,size=BLOCK_EVENT.unpack_from(event);payload=event[BLOCK_EVENT.size:]
        require(0<count<=ROWS and self.last<first<=last<2**63 and size==len(payload),'Read-only fine source event identity')
        codec.check_call();require(codec.encoded_rows+codec.decoded_rows+count<=codec.row_budget,'Read-only fine native row cap')
        codec.decoded_rows+=count;codec.calls+=1
        ids=(ctypes.c_int64*count)();xy=(ctypes.c_int32*(count*2))();source=(ctypes.c_uint8*size).from_buffer_copy(payload)
        require(codec.dec(source,size,count,first,last,ids,xy,count)==0,'Read-only fine native source decode')
        end,start,length,n,zero,owner,zero2=self.reader.entry(self.blocks)
        require(n==count and end==last and zero==zero2==0,'Read-only fine source directory identity')
        if owner!=self.active:self.load(owner)
        raw=BLOCK.pack(b'GPDB',1,0,count,first,last,size,0,hashlib.sha256(payload).digest())+payload
        require(len(raw)==length and self.snapshot[start:start+length]==raw,'Read-only fine source block differs')
        self.rows+=count;self.blocks+=1;self.last=last;self.active_rows+=count;self.active_blocks+=1

    def verify_files(self):
        require(not self.closed,'Read-only fine view closed')
        require({p.name for p in self.root.iterdir()}=={'index.json','directory.bin',*(f'{i:08d}.bin' for i in range(len(self.expected['shards'])))},'Read-only fine closed roster drift')
        for name in ('index.json','directory.bin'):self.kind(self.root/name)
        self.reader.verify_catalogs()
        for number in range(len(self.expected['shards'])):self.checksum(number)
        self.verification_passes+=1

    def finish(self):
        require(not self.closed,'Read-only fine finish after close')
        if self.finished:self.verify_files();return
        require(self.rows==self.expected['rows'] and self.blocks==self.expected['blocks'],'Read-only fine missing source blocks')
        self.finish_part();require(self.shards_compared==len(self.expected['shards']),'Read-only fine missing source shards')
        self.finished=True

    def report(self):
        return {'nodeRowsCompared':self.rows,'sourceBlocksCompared':self.blocks,'sourceShardsCompared':self.shards_compared,
                'wholeFileVerificationPasses':self.verification_passes,'payloadBytesRead':self.payload_bytes_read,
                'catalogBytesPerRead':len(self.reader.directory)+(self.root/'index.json').stat().st_size,
                'readOnly':True,'wholeSourceEofStillRequiredFromCaller':True}

    def close(self):self.reader.close();self.snapshot=b'';self.closed=True
