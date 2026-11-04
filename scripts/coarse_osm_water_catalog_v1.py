"""Bounded ctypes bridge for the saved-water typed geometry tables."""
import ctypes
import hashlib

from coarse_osm_water_area_v1 import Point,WaterArea
from coarse_timing_input import require

COUNTERS=('nodes','ways','references','taggedWays','coordinatesSealed','waysSealed','backingBytes','failed')


class WaterCatalog(WaterArea):
    def __init__(self,path,pin):
        super().__init__(path,pin);lib=self.library
        lib.gp_water_catalog_abi.restype=ctypes.c_uint32
        require(lib.gp_water_catalog_abi()==0x10000,'Water catalog ABI')
        signatures={
            'begin':[ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint64],
            'points':[ctypes.POINTER(Point),ctypes.c_uint32],
            'points_seal':[self.callback,ctypes.c_void_p],
            'way':[ctypes.c_void_p,ctypes.c_uint32],
            'ways_seal':[self.callback,ctypes.c_void_p],
            'gather':[ctypes.POINTER(ctypes.c_uint64),ctypes.POINTER(ctypes.c_int8),ctypes.c_uint32,ctypes.POINTER(Point),ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32)]}
        for name,args in signatures.items():
            fn=getattr(lib,'gp_water_catalog_'+name);fn.argtypes=args+[ctypes.c_char_p,ctypes.c_uint32];fn.restype=ctypes.c_int
        lib.gp_water_catalog_release.argtypes=[];lib.gp_water_catalog_release.restype=None
        lib.gp_water_catalog_stats.argtypes=[ctypes.POINTER(ctypes.c_uint64),ctypes.c_uint32];lib.gp_water_catalog_stats.restype=ctypes.c_int

    def call(self,name,*args):
        error=ctypes.create_string_buffer(512);code=getattr(self.library,'gp_water_catalog_'+name)(*args,error,len(error))
        require(code==0,'Water catalog '+name+': '+error.value.decode('ascii'))

    def begin(self,nodes,ways,references):self.call('begin',nodes,ways,references)
    def release(self):self.library.gp_water_catalog_release()

    def append_points(self,raw):
        require(isinstance(raw,bytes) and 0<len(raw)<=1048576 and len(raw)%16==0,'Water catalog canonical point chunk')
        values=(Point*(len(raw)//16)).from_buffer_copy(raw);self.call('points',values,len(values))

    def append_way(self,raw):
        require(isinstance(raw,bytes) and 0<len(raw)<=8388608,'Water catalog GPF chunk')
        buffer=ctypes.create_string_buffer(raw);self.call('way',buffer,len(raw))

    def seal(self,kind):
        require(kind in ('points','ways'),'Water catalog seal kind')
        digest=hashlib.sha256();total=0;errors=[]
        def receive(_,event,data,size):
            nonlocal total
            try:
                require(event==(32 if kind=='points' else 50) and 0<size<=65536,'Water catalog audit event/bound')
                raw=ctypes.string_at(data,size);total+=size;digest.update(raw);return 0
            except BaseException as error:errors.append(error);return -1
        callback=self.callback(receive);self.call(kind+'_seal',callback,None)
        if errors:raise errors[0]
        return {'bytes':total,'sha256':digest.hexdigest()}

    def gather(self,chain,capacity):
        require(0<len(chain)<=100000 and type(capacity) is int and 0<capacity<=2000000,'Water catalog bounded source chain')
        for identity,direction in chain:require(type(identity) is int and 0<identity<2**63 and type(direction) is int and direction in (-1,1),'Water catalog member identity/direction')
        ids=(ctypes.c_uint64*len(chain))(*(i for i,_ in chain));directions=(ctypes.c_int8*len(chain))(*(d for _,d in chain))
        output=(Point*capacity)();written=ctypes.c_uint32();self.call('gather',ids,directions,len(chain),output,capacity,ctypes.byref(written))
        return [(p.identity,p.x,p.y) for p in output[:written.value]]

    def stats(self):
        values=(ctypes.c_uint64*len(COUNTERS))();require(self.library.gp_water_catalog_stats(values,len(values))==0,'Water catalog statistics')
        return dict(zip(COUNTERS,map(int,values)))
