"""C bisect over checked typed IDs; frozen V2 snapshot/cache integrity is retained."""
from array import array
from bisect import bisect_left

from coarse_osm_country_screen_v1 import ProbeReader
from coarse_osm_delta_v1 import MAX_ID, SCALE
from coarse_timing_input import require


class Reader(ProbeReader):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        # The full admitted directory is <=16 MiB: its 32-byte entries need
        # at most 4 MiB of 8-byte search keys. Catalogs are still checked per call.
        self.block_ends=array('Q',(self.entry(i)[0] for i in range(self.manifest['blocks'])))
        require(self.block_ends.itemsize==8 and len(self.block_ends)*8<=4*1024**2,'Lookup typed-end allocation cap')

    def points(self,ids):
        require(not self.closed and len(ids)<=65536,'Lookup V3 batch/closed')
        self.verify_catalogs()
        grouped={};found={}
        for identity in ids:
            require(type(identity) is int and 0<identity<=MAX_ID,'Lookup V3 query identity')
            number=bisect_left(self.block_ends,identity)
            require(number<len(self.block_ends),'Lookup V3 missing node')
            grouped.setdefault(self.entry(number)[5],{}).setdefault(number,[]).append(identity)
        for shard,blocks in grouped.items():
            raw=self.snapshot(shard)
            for number,keys in blocks.items():
                values,xy=self.from_snapshot(number,raw)
                for identity in keys:
                    position=bisect_left(values,identity)
                    require(position<len(values) and values[position]==identity,'Lookup V3 missing node')
                    found[identity]=[xy[2*position]/SCALE,xy[2*position+1]/SCALE]
            del raw
        return [found[identity] for identity in ids]
