"""Native union census over the sealed full-source and water bridges."""
import ctypes

from coarse_osm_water_census_v2 import WaterCensus
from coarse_timing_input import require

COUNTERS=('unionWays','unionReferences','closedUnionWays','openUnionWays','taggedWays','taggedReferences',
          'memberWaysFound','memberWayReferences','taggedMemberOverlapWays','taggedMemberOverlapReferences',
          'memberOnlyWays','memberOnlyReferences','maximumUnionWayReferences','unionEncodedBytes',
          'missingMemberWays','firstUnionWayId','lastUnionWayId','requestedMemberWays','complete','reserved19')


class WaterUnion(WaterCensus):
    def __init__(self,path,pin,*,member_ids=(),**options):
        super().__init__(path,pin,**options)
        require(len(member_ids)<=1000000,'Water union member input count')
        previous=0
        for identity in member_ids:
            require(type(identity) is int and previous<identity<2**63,'Water union sorted unique native IDs')
            previous=identity
        self.member_ids=(ctypes.c_uint64*len(member_ids))(*member_ids)
        lib=self.library
        lib.gp_water_union_abi.restype=ctypes.c_uint32
        require(lib.gp_water_union_abi()==0x10000,'Water union ABI')
        for old,name in ((self.frames,'gp_water_union_frames'),(self.pbf,'gp_water_union_pbf')):
            function=getattr(lib,name);function.argtypes,function.restype=old.argtypes,old.restype
            if name.endswith('frames'):self.frames=function
            else:self.pbf=function
        lib.gp_water_union_begin.argtypes=[ctypes.POINTER(ctypes.c_uint64),ctypes.c_uint32]
        lib.gp_water_union_begin.restype=ctypes.c_int
        lib.gp_water_union_finish.argtypes=[ctypes.POINTER(ctypes.c_uint64),ctypes.c_uint32,ctypes.c_char_p,ctypes.c_uint32]
        lib.gp_water_union_finish.restype=ctypes.c_int
        lib.gp_water_union_missing.argtypes=[ctypes.POINTER(ctypes.c_uint64),ctypes.c_uint32]
        lib.gp_water_union_missing.restype=ctypes.c_int
        lib.gp_water_union_release.argtypes=[];lib.gp_water_union_release.restype=None

    def begin(self):
        require(not self.begun and self.library.gp_water_union_begin(self.member_ids,len(self.member_ids))==0,'Water union exclusive session')
        self.begun=True

    def finish(self):
        water=super().finish()
        values=(ctypes.c_uint64*len(COUNTERS))();error=ctypes.create_string_buffer(512)
        code=self.library.gp_water_union_finish(values,len(values),error,len(error))
        require(code==0 and values[18]==1,'Water union finish: '+error.value.decode('ascii'))
        union=dict(zip(COUNTERS,map(int,values)))
        require(union['taggedWays']==water['waterWays'] and union['taggedReferences']==water['waterWayReferences'],'Water union independent tagged counter parity')
        missing=(ctypes.c_uint64*union['missingMemberWays'])()
        require(self.library.gp_water_union_missing(missing,len(missing))==0,'Water union missing ID export')
        return {**water,'union':union,'missingMemberWayIds':list(map(int,missing))}

    def release(self):
        require(not self.active,'Water union release during callback')
        if self.begun:self.library.gp_water_union_release();self.begun=False
