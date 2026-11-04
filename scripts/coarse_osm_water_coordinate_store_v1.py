"""Exact coordinate/missing shards and an unretained canonical source shadow."""
import hashlib

from coarse_osm_water_reference_store_v1 import Budget, Shards
from coarse_timing_input import require


class CoordinateStore:
    def __init__(self,root,requested,*,encoded_budget,missing_budget):
        require(type(requested) is int and 0<=requested<=150000000,'Water coordinate input capacity')
        self.requested=requested;self.closed=False;self.shadow=hashlib.sha256();self.shadow_bytes=0
        self.encoded=Shards(root,'water-coordinates.wxy',Budget(encoded_budget))
        self.missing=Shards(root,'missing-node-ids.u64',Budget(missing_budget))

    def __enter__(self):return self
    def __exit__(self,*_):self.encoded.close();self.missing.close()

    def accept(self,event,raw):
        require(not self.closed and 0<len(raw)<=1048576,'Water coordinate output state/chunk')
        if event==30:
            require(self.encoded.raw_bytes+len(raw)<=4+self.requested*19,'Water coordinate raw encoded bound')
            self.encoded.write(raw)
        elif event==31:
            require(len(raw)%8==0 and self.missing.raw_bytes+len(raw)<=self.requested*8,'Water coordinate missing-ID byte bound')
            self.missing.write(raw)
        else:
            require(event==32 and len(raw)%16==0 and self.shadow_bytes+len(raw)<=self.requested*16,'Water coordinate source-shadow byte bound')
            self.shadow.update(raw);self.shadow_bytes+=len(raw)

    def finish(self,counts):
        require(not self.closed and counts['complete']==1 and counts['requested']==self.requested and
                counts['present']+counts['missing']==self.requested and self.encoded.raw_bytes==counts['encodedBytes'] and
                self.missing.raw_bytes==counts['missingBytes']==counts['missing']*8 and
                self.shadow_bytes==counts['canonicalBytes']==counts['present']*16,'Water coordinate exact source byte/count accounting')
        encoded=self.encoded.finish();missing=self.missing.finish();self.closed=True
        return {'encoded':encoded,'missing':missing,'sourceShadow':{'bytes':self.shadow_bytes,'sha256':self.shadow.hexdigest()},
                'compressedBytes':encoded['compressedBytes']+missing['compressedBytes'],'coordinatesRetained':True,'ringsConstructed':False}
