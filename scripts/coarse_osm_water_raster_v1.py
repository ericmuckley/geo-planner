"""Typed bridge for exact source-water data rasterization, without routing policy."""
import ctypes
import hashlib
from pathlib import Path
import sys

from coarse_osm_water_area_v1 import Point
from coarse_timing_input import require

COUNTERS=('features','rings','points','excludedBoxes','incompleteBoxes','maxFeatureCrossings','planeBytes','nativeBackingBytes','finished','failed','activeFeature')


class WaterRaster:
    def __init__(self,path,pin):
        with Path(path).open('rb') as f:require(hashlib.file_digest(f,'sha256').hexdigest()==pin,'Water raster artifact binding')
        require(sys.byteorder=='little' and ctypes.sizeof(Point)==16,'Water raster canonical point platform')
        self.library=ctypes.CDLL(str(Path(path).resolve()));lib=self.library
        lib.gp_wgrid_abi.restype=ctypes.c_uint32;require(lib.gp_wgrid_abi()==0x10000,'Water raster ABI')
        signatures={'begin':[ctypes.c_int64,ctypes.c_int64,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32],
                    'feature':[ctypes.c_uint32],'ring':[ctypes.c_uint8,ctypes.c_uint32,ctypes.c_uint32],
                    'points':[ctypes.POINTER(Point),ctypes.c_uint32],'feature_finish':[],
                    'box':[ctypes.c_int32,ctypes.c_int32,ctypes.c_int32,ctypes.c_int32,ctypes.c_uint8],
                    'finish':[ctypes.c_uint64]*5}
        for name,args in signatures.items():
            fn=getattr(lib,'gp_wgrid_'+name);fn.argtypes=args+[ctypes.c_char_p,ctypes.c_uint32];fn.restype=ctypes.c_int
        lib.gp_wgrid_copy.argtypes=[ctypes.c_uint8,ctypes.c_void_p,ctypes.c_uint64];lib.gp_wgrid_copy.restype=ctypes.c_int
        lib.gp_wgrid_stats.argtypes=[ctypes.POINTER(ctypes.c_uint64),ctypes.c_uint32];lib.gp_wgrid_stats.restype=ctypes.c_int
        lib.gp_wgrid_release.argtypes=[];lib.gp_wgrid_release.restype=None

    def call(self,name,*args):
        error=ctypes.create_string_buffer(512);code=getattr(self.library,'gp_wgrid_'+name)(*args,error,len(error))
        require(code==0,'Water raster '+name+': '+error.value.decode('ascii'))

    def begin(self,x,y,step,width,height):
        require(all(type(v) is int for v in (x,y,step,width,height)) and -1800000000<=x<=1800000000 and -900000000<=y<=900000000 and 0<step<2**32 and 0<width<2**32 and 0<height<2**32,'Water raster grid fields')
        self.call('begin',x,y,step,width,height)

    def append_points(self,raw):
        require(isinstance(raw,bytes) and 0<len(raw)<=1048576 and len(raw)%16==0,'Water raster canonical point chunk')
        values=(Point*(len(raw)//16)).from_buffer_copy(raw);self.call('points',values,len(values))

    def box(self,bounds,complete):
        require(isinstance(bounds,(list,tuple)) and len(bounds)==4 and all(type(n) is int and -2**31<=n<2**31 for n in bounds) and type(complete) is bool,'Water raster explicit box fields/completeness')
        self.call('box',*bounds,int(complete))

    def stats(self):
        values=(ctypes.c_uint64*len(COUNTERS))();require(self.library.gp_wgrid_stats(values,len(values))==0,'Water raster statistics')
        return dict(zip(COUNTERS,map(int,values)))

    def planes(self):
        stats=self.stats();require(stats['finished']==1 and stats['failed']==0 and stats['planeBytes']%2==0 and stats['nativeBackingBytes']==stats['planeBytes'],'Water raster released scratch before export')
        result=[]
        for plane in (0,1):
            raw=ctypes.create_string_buffer(stats['planeBytes']//2)
            require(self.library.gp_wgrid_copy(plane,raw,len(raw))==0,'Water raster complete plane copy')
            result.append(raw.raw)
        return result

    def release(self):self.library.gp_wgrid_release()
