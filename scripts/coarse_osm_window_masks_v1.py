"""Bounded native conservative masks; audit never consumes the primary table."""
import ctypes
from itertools import accumulate

from coarse_osm_delta_v1 import NativeCodec
from coarse_timing_input import require


class Masks:
    def __init__(self,path,sha,grid,*,reference_budget=2000000,call_budget=100000):
        require(type(reference_budget) is int and 0<reference_budget<=10**12 and type(call_budget) is int and 0<call_budget<=100000000,'Cell mask budgets')
        self.native=NativeCodec(path,sha);self.library=self.native.library;self.grid=grid
        self.references=self.calls=0;self.reference_budget=reference_budget;self.call_budget=call_budget
        abi=self.library.gp_window_masks_abi;abi.argtypes=[];abi.restype=ctypes.c_uint32;require(abi()==0x10000,'Cell masks ABI')
        self.table=(ctypes.c_uint8*len(grid.codes)).from_buffer_copy(grid.codes)
        slots=[value for left,bottom,right,top in grid.boxes for value in (2*grid.x.index(left)+1,2*grid.y.index(bottom)+1,2*grid.x.index(right)+1,2*grid.y.index(top)+1)]
        self.boxes=(ctypes.c_uint16*len(slots))(*slots)
        u8=ctypes.POINTER(ctypes.c_uint8);u16=ctypes.POINTER(ctypes.c_uint16);u32=ctypes.POINTER(ctypes.c_uint32)
        self.primary=self.library.gp_window_primary_masks;self.primary.argtypes=[u8,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32,u16,ctypes.c_uint32,u32,ctypes.c_uint32,u32,ctypes.c_uint32];self.primary.restype=ctypes.c_int
        self.audit=self.library.gp_window_audit_masks;self.audit.argtypes=[u16,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32,u16,ctypes.c_uint32,u32,ctypes.c_uint32,u32,ctypes.c_uint32];self.audit.restype=ctypes.c_int

    def masks(self,cells,counts,*,audit=False):
        require(type(audit) is bool and 0<len(counts)<=32768 and all(type(n) is int and 2<=n<=65536 for n in counts),'Cell mask way count')
        require(sum(counts)==len(cells)<=65536 and all(type(v) is int and 0<=v<self.grid.count for v in cells),'Cell mask references')
        require(self.calls<self.call_budget and self.references+len(cells)<=self.reference_budget,'Cell mask reference/call cap')
        self.calls+=1;self.references+=len(cells)
        values=(ctypes.c_uint16*len(cells))(*cells);ends=(ctypes.c_uint32*len(counts))(*accumulate(counts));out=(ctypes.c_uint32*len(counts))()
        if audit:code=self.audit(self.boxes,len(self.grid.ids),self.grid.width,self.grid.height,values,len(cells),ends,len(counts),out,len(counts))
        else:code=self.primary(self.table,len(self.table),len(self.grid.ids),self.grid.count,values,len(cells),ends,len(counts),out,len(counts))
        require(code==0 and all(mask<1<<len(self.grid.ids) for mask in out),'Cell native mask refused')
        return list(out)
