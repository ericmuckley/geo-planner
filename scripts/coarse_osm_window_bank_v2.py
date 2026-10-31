"""Immutable compact cell-bank snapshots; fine-coordinate authentication is separate."""
from array import array
from bisect import bisect_left
from copy import deepcopy
import hashlib
from pathlib import Path
import struct

from coarse_osm_delta_v1 import file_stamp,ROWS
from coarse_osm_records import canonical,strict_json
from coarse_osm_window_cells_v1 import Cells
from coarse_osm_window_codec_v2 import body
from coarse_timing_input import require

ENTRY=struct.Struct('<qQIIII')
LIMIT=2*1024**3
DIRECTORY_LIMIT=16*1024**2
PART_LIMIT=64*1024**2
FORMAT='immutable-window-cell-bank-v2'


def matching(grid,codec):
    require(grid.ids==codec.cells.ids and grid.boxes==codec.cells.boxes and grid.codes==codec.cells.codes,'Cell bank codec/query binding')


class Writer:
    def __init__(self,root,storage,windows,expected_rows,*,limit=LIMIT,part_limit=PART_LIMIT):
        require(type(expected_rows) is int and 0<expected_rows<=ROWS*(DIRECTORY_LIMIT//ENTRY.size),'Cell bank row bound')
        require(type(limit) is int and 0<limit<=LIMIT and type(part_limit) is int and 0<part_limit<=PART_LIMIT,'Cell bank byte bounds')
        self.root=Path(root);self.root.mkdir();self.storage=storage;self.windows=deepcopy(windows);self.grid=Cells(windows)
        self.expected_rows=expected_rows;self.limit=limit;self.part_limit=part_limit
        self.pending=bytearray();self.directory=bytearray();self.parts=[]
        self.rows=self.blocks=self.last=self.part_rows=self.part_blocks=self.part_first=self.stored_bytes=0
        self.finished=False

    def append(self,raw,codec):
        require(not self.finished,'Cell bank writer finished');matching(self.grid,codec)
        _,count,first,last=body(raw)
        require(count==min(ROWS,self.expected_rows-self.rows) and self.last<first,'Cell bank block count/order')
        require(len(raw)<=self.part_limit and len(self.directory)+ENTRY.size<=DIRECTORY_LIMIT,'Cell bank block/directory cap')
        codec.lookup(raw,[first,last])
        if self.pending and len(self.pending)+len(raw)>self.part_limit:self.flush()
        require(self.stored_bytes+len(self.pending)+len(raw)+len(self.directory)+ENTRY.size+1048576<=self.limit,'Cell bank projected logical cap')
        if not self.part_blocks:self.part_first=first
        self.directory.extend(ENTRY.pack(last,len(self.pending),len(raw),count,len(self.parts),0))
        self.pending.extend(raw);self.rows+=count;self.blocks+=1;self.last=last;self.part_rows+=count;self.part_blocks+=1

    def flush(self):
        if not self.pending:return
        require(len(self.parts)<128,'Cell bank part namespace cap')
        raw=bytes(self.pending);self.storage.write(self.root/f'{len(self.parts):04d}.bin',raw)
        self.parts.append({'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'rows':self.part_rows,'blocks':self.part_blocks,'first':self.part_first,'last':self.last})
        self.stored_bytes+=len(raw);self.pending.clear();self.part_rows=self.part_blocks=0

    def finish(self):
        if self.finished:return
        require(self.rows==self.expected_rows and self.blocks==(self.rows+ROWS-1)//ROWS,'Cell bank source closure')
        self.flush();directory=bytes(self.directory)
        manifest={'format':FORMAT,'windows':self.windows,'rows':self.rows,'blocks':self.blocks,'parts':self.parts,
                  'directory':{'bytes':len(directory),'sha256':hashlib.sha256(directory).hexdigest()},
                  'tableSha256':hashlib.sha256(self.grid.codes).hexdigest()}
        raw=canonical(manifest)+b'\n'
        require(len(raw)<=1048576 and self.stored_bytes+len(directory)+len(raw)<=self.limit,'Cell bank final logical cap')
        self.storage.write(self.root/'directory.bin',directory);self.storage.write(self.root/'index.json',raw)
        self.stored_bytes+=len(directory)+len(raw);self.finished=True


class Bank:
    def __init__(self,root,codec,windows,*,expected_rows=None,limit=LIMIT):
        require(type(limit) is int and 0<limit<=LIMIT,'Cell bank snapshot bound')
        self.root=Path(root);require(self.root.is_dir() and not self.root.is_symlink(),'Cell bank root kind')
        self.codec=codec;self.limit=limit;self.closed=False;self.loaded_bytes=self.lookup_blocks=0
        self.catalog=self.read('index.json',1048576);manifest=strict_json(self.catalog);self.manifest=manifest
        require(set(manifest)=={'format','windows','rows','blocks','parts','directory','tableSha256'} and manifest['format']==FORMAT,'Cell bank catalog schema')
        require(canonical(manifest['windows'])==canonical(windows),'Cell bank original query drift')
        self.grid=Cells(windows);matching(self.grid,codec)
        require(hashlib.sha256(self.grid.codes).hexdigest()==manifest['tableSha256'],'Cell bank grid table seal')
        require(type(manifest['rows']) is int and type(manifest['blocks']) is int and 0<manifest['rows']<=ROWS*(DIRECTORY_LIMIT//ENTRY.size) and manifest['blocks']==(manifest['rows']+ROWS-1)//ROWS,'Cell bank catalog counts')
        require(expected_rows is None or manifest['rows']==expected_rows,'Cell bank expected source count')
        require(isinstance(manifest['parts'],list) and 0<len(manifest['parts'])<=128,'Cell bank part count')
        descriptor=manifest['directory'];require(set(descriptor)=={'bytes','sha256'} and descriptor['bytes']==ENTRY.size*manifest['blocks']<=DIRECTORY_LIMIT,'Cell bank directory size')
        self.directory=self.read('directory.bin',DIRECTORY_LIMIT)
        require(len(self.directory)==descriptor['bytes'] and hashlib.sha256(self.directory).hexdigest()==descriptor['sha256'],'Cell bank directory seal')
        self.parts=[];self.ends=array('Q');previous=rows=block=0
        for number,part in enumerate(manifest['parts']):
            require(set(part)=={'bytes','sha256','rows','blocks','first','last'} and all(type(part[k]) is int for k in ('bytes','rows','blocks','first','last')),'Cell bank part descriptor')
            require(0<part['bytes']<=PART_LIMIT and 0<part['blocks']<=manifest['blocks'] and previous<part['first']<=part['last']<2**63,'Cell bank part bounds/order')
            payload=self.read(f'{number:04d}.bin',PART_LIMIT)
            require(len(payload)==part['bytes'] and hashlib.sha256(payload).hexdigest()==part['sha256'],'Cell bank immutable part seal')
            offset=part_rows=0;start_first=None
            for _ in range(part['blocks']):
                require(block<manifest['blocks'],'Cell bank extra block')
                end,start,size,count,owner,zero=ENTRY.unpack_from(self.directory,block*ENTRY.size)
                require(start==offset and owner==number and zero==0 and 0<size<=65576 and start+size<=len(payload),'Cell bank directory offsets')
                raw=payload[start:start+size];_,n,first,last=body(raw)
                require(count==n==min(ROWS,manifest['rows']-rows) and previous<first<=last==end,'Cell bank source block order/count')
                codec.lookup(raw,[first,last])
                if start_first is None:start_first=first
                self.ends.append(last);previous=last;rows+=n;part_rows+=n;offset+=size;block+=1
            require(offset==len(payload) and part_rows==part['rows'] and start_first==part['first'] and previous==part['last'],'Cell bank part closure')
            self.parts.append(payload)
        require(rows==manifest['rows'] and block==manifest['blocks'],'Cell bank whole snapshot closure')
        require({p.name for p in self.root.iterdir()}=={'index.json','directory.bin',*(f'{i:04d}.bin' for i in range(len(self.parts)))},'Cell bank unexpected files')
        self.parts=tuple(self.parts)

    def read(self,name,maximum):
        path=self.root/name;before=file_stamp(path)
        require(path.stat().st_nlink==1 and before[2]<=maximum and self.loaded_bytes+before[2]<=self.limit,'Cell bank snapshot allocation/type cap')
        raw=path.read_bytes();require(len(raw)==before[2] and file_stamp(path)==before,'Cell bank changed during snapshot')
        self.loaded_bytes+=len(raw);return raw

    def lookup(self,ids):
        require(not self.closed and len(ids)<=65536,'Cell bank lookup bound/closed')
        grouped={};answer=[None]*len(ids)
        for position,identity in enumerate(ids):
            require(type(identity) is int and 0<identity<2**63,'Cell bank typed reference')
            number=bisect_left(self.ends,identity);require(number<len(self.ends),'Cell bank missing node')
            grouped.setdefault(number,[]).append((position,identity))
        for number,requests in grouped.items():
            end,start,size,count,owner,zero=ENTRY.unpack_from(self.directory,number*ENTRY.size)
            raw=self.parts[owner][start:start+size];values=self.codec.lookup(raw,[identity for _,identity in requests]);self.lookup_blocks+=1
            require(len(values)==len(requests),'Cell bank returned reference count')
            for (position,_),value in zip(requests,values):answer[position]=value
        return answer

    def verify_files(self):
        require(not self.closed,'Cell bank closed verification')
        for name,raw in [('index.json',self.catalog),('directory.bin',self.directory)]:
            path=self.root/name;before=file_stamp(path)
            require(path.stat().st_nlink==1 and before[2]==len(raw) and path.read_bytes()==raw and file_stamp(path)==before,'Cell bank closed catalog drift')
        require({p.name for p in self.root.iterdir()}=={'index.json','directory.bin',*(f'{i:04d}.bin' for i in range(len(self.parts)))},'Cell bank closed unexpected files')
        for number,payload in enumerate(self.parts):
            path=self.root/f'{number:04d}.bin';before=file_stamp(path)
            require(path.stat().st_nlink==1 and before[2]==len(payload),'Cell bank closed file kind/size')
            with path.open('rb') as stream:pin=hashlib.file_digest(stream,'sha256').hexdigest()
            require(pin==self.manifest['parts'][number]['sha256'] and file_stamp(path)==before,'Cell bank closed part drift')

    def close(self):self.parts=();self.directory=b'';self.ends=array('Q');self.closed=True
