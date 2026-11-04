"""Strict cached area adapter for already joined native-ID rings; no mask policy."""
import ctypes
import hashlib
from pathlib import Path
import struct

from coarse_timing_input import require


class Point(ctypes.Structure):
    _fields_=[('identity',ctypes.c_uint64),('x',ctypes.c_int32),('y',ctypes.c_int32)]


class WaterArea:
    def __init__(self,path,pin):
        with Path(path).open('rb') as stream:require(hashlib.file_digest(stream,'sha256').hexdigest()==pin,'Water area artifact binding')
        self.library=ctypes.CDLL(str(Path(path).resolve()))
        self.library.gp_water_area_abi.restype=ctypes.c_uint32
        require(self.library.gp_water_area_abi()==0x10000 and ctypes.sizeof(Point)==16,'Water area ABI')
        self.callback=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32)
        self.run=self.library.gp_water_area
        self.run.argtypes=[ctypes.POINTER(Point),ctypes.c_uint64,ctypes.POINTER(ctypes.c_uint64),ctypes.POINTER(ctypes.c_uint8),ctypes.c_uint32,self.callback,ctypes.c_void_p,ctypes.c_char_p,ctypes.c_uint32]
        self.run.restype=ctypes.c_int

    def assemble(self,rings):
        require(0<len(rings)<=100000,'Water area ring count')
        count=sum(len(nodes) for _,nodes in rings);require(count<=2000000,'Water area point cap')
        points=(Point*count)();offsets=(ctypes.c_uint64*(len(rings)+1))();roles=(ctypes.c_uint8*len(rings))()
        cursor=0
        for rank,(role,nodes) in enumerate(rings):
            require(type(role) is int and role in (0,1),'Water area explicit role')
            roles[rank]=role;offsets[rank]=cursor
            for identity,x,y in nodes:
                require(type(identity) is int and 0<identity<2**63 and type(x) is int and -2**31<=x<2**31 and type(y) is int and -2**31<=y<2**31,'Water area exact input field types/ranges')
                points[cursor]=Point(identity,x,y);cursor+=1
        offsets[len(rings)]=cursor
        output=[];expected=0;errors=[]
        def receive(_,event,data,size):
            nonlocal expected
            try:
                require(0<size<=65536,'Water area bounded callback')
                raw=ctypes.string_at(data,size)
                if event==40:
                    require(expected==0 and len(raw)==16,'Water area header order/size')
                    role,parent,expected=struct.unpack('<IIQ',raw)
                    require(role in (0,1) and 4<=expected<=count and (role==0 and parent==len(output) or role==1 and parent<len(output) and output[parent]['role']==0),'Water area output ring fields')
                    output.append({'role':role,'parent':parent,'nodes':[]})
                else:
                    require(event==41 and expected>0 and size%16==0 and size//16<=expected,'Water area point order/width/count')
                    output[-1]['nodes'].extend(struct.iter_unpack('<Qii',raw));expected-=size//16
                return 0
            except BaseException as error:errors.append(error);return -1
        callback=self.callback(receive);error=ctypes.create_string_buffer(512)
        code=self.run(points,count,offsets,roles,len(rings),callback,None,error,len(error))
        if errors:raise errors[0]
        if code:
            require(not output,'Water area partial output is unadmitted')
            return {'accepted':False,'reason':error.value.decode('ascii'),'rings':[]}
        require(expected==0 and len(output)==len(rings) and sum(len(r['nodes']) for r in output)==count,'Water area complete output population')
        return {'accepted':True,'reason':None,'rings':output}
