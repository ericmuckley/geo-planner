"""V2: authenticate one bounded immutable shard snapshot for every lookup batch."""
from array import array
from collections import OrderedDict
import hashlib

from coarse_osm_delta_v1 import (BLOCK,ENTRY,SHARD,DIRECTORY,ROWS,MAX_ID,MAX_PAYLOAD,ReferenceCodec,
    NativeCodec,Storage,encode_block,decode_block,read_file,Reader as ReaderV1,Index as IndexV1,SCALE)
from coarse_timing_input import require


class Reader(ReaderV1):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.format_verified=set()

    def snapshot(self,shard):
        if shard not in self.format_verified:
            # The frozen parser verifies the header/table and every block payload.
            self.validate_shard(shard)
            self.format_verified.add(shard)
        raw=read_file(self.path(shard),self.index_limit)
        entry=self.manifest['shards'][shard]
        require(len(raw)==entry['bytes'] and hashlib.sha256(raw).hexdigest()==entry['sha256'],'Delta V2 per-query shard checksum')
        self.loaded_bytes+=len(raw)
        return raw

    def from_snapshot(self,number,raw):
        if number in self.cache:
            self.cache.move_to_end(number);return self.cache[number]
        end,start,size,count,_,_,_=self.entry(number)
        values=decode_block(raw[start:start+size],self.codec)
        require(len(values)==count and values[-1][0]==end,'Delta V2 authenticated block mismatch')
        decoded=(array('q',(r[0] for r in values)),array('i',(v for r in values for v in r[1:])))
        if self.cache_limit:
            self.cache[number]=decoded
            while len(self.cache)>self.cache_limit:self.cache.popitem(last=False)
        return decoded

    def block(self,number):
        require(not self.closed,'Delta V2 reader closed')
        self.verify_catalogs();shard=self.entry(number)[5]
        return self.from_snapshot(number,self.snapshot(shard))

    def points(self,ids):
        require(not self.closed and len(ids)<=65536,'Delta V2 lookup batch/closed')
        self.verify_catalogs();grouped={};found={}
        for identity in ids:
            require(type(identity) is int and 0<identity<=MAX_ID,'Delta V2 query identity')
            lo,hi=0,self.manifest['blocks']
            while lo<hi:
                mid=(lo+hi)//2
                if self.entry(mid)[0]<identity:lo=mid+1
                else:hi=mid
            require(lo<self.manifest['blocks'],'Delta V2 missing node')
            grouped.setdefault(self.entry(lo)[5],{}).setdefault(lo,[]).append(identity)
        for shard,blocks in grouped.items():
            raw=self.snapshot(shard)
            for number,keys in blocks.items():
                values,xy=self.from_snapshot(number,raw)
                for identity in keys:
                    lo,hi=0,len(values)
                    while lo<hi:
                        mid=(lo+hi)//2
                        if values[mid]<identity:lo=mid+1
                        else:hi=mid
                    require(lo<len(values) and values[lo]==identity,'Delta V2 missing node')
                    found[identity]=[xy[2*lo]/SCALE,xy[2*lo+1]/SCALE]
            del raw
        return [found[i] for i in ids]


class Index(IndexV1):
    def finish(self):
        if self.finished:return super().finish()
        super().finish()
        self.reader.close()
        self.reader=Reader(self.root,self.codec,index_limit=self.index_limit,catalog_limit=self.catalog_limit)
