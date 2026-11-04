"""Typed-buffer interface to the bounded topology sort/count kernel."""
from array import array
import ctypes
import hashlib
import os
from pathlib import Path
import struct

from coarse_timing_input import require

REF=struct.Struct('<QQII')
FIELDS=('references','totalDegree','endpointOccurrences','uniqueNodes','anchors','contractedEdges','primitiveEdges',
        'taggedSelectedNodes','relationNodeSelectedNodes','relationWaySelectedNodes','degreeNotTwoNodes','wayEndUniqueNodes',
        'allTaggedNodeIds','routingArrayBytes','fullGeometryArrayBytes','combinedArrayBytes','internalAnchorOccurrences','complete')


class Kernel:
    def __init__(self,path,sha256):
        path=Path(path)
        with path.open('rb') as stream:require(hashlib.file_digest(stream,'sha256').hexdigest()==sha256,'Topology kernel binding')
        self.library=ctypes.CDLL(str(path.resolve()));abi=self.library.gp_topology_abi;abi.restype=ctypes.c_uint32;abi.argtypes=[]
        require(abi()==0x10000,'Topology kernel C ABI')
        self.sort_refs=self.library.gp_topology_sort_refs;self.sort_ids=self.library.gp_topology_sort_ids
        for function in (self.sort_refs,self.sort_ids):function.argtypes=[ctypes.c_void_p,ctypes.c_uint64,ctypes.c_char_p,ctypes.c_uint32];function.restype=ctypes.c_int
        self.count_files=self.library.gp_topology_count_files
        ptr=ctypes.POINTER(ctypes.c_uint64);paths=ctypes.POINTER(ctypes.c_char_p)
        self.count_files.argtypes=[paths,ctypes.c_uint32,paths,ctypes.c_uint32,ptr,ctypes.c_uint64,ptr,ctypes.c_uint64,
            ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint64,ptr,ctypes.c_uint32,ctypes.c_char_p,ctypes.c_uint32]
        self.count_files.restype=ctypes.c_int

    def sort(self,raw,*,ids=False):
        require(isinstance(raw,bytearray) and len(raw)%(8 if ids else REF.size)==0,'Topology typed sort buffer')
        buf=(ctypes.c_uint64*((len(raw)+7)//8)).from_buffer(raw)
        error=ctypes.create_string_buffer(512);function=self.sort_ids if ids else self.sort_refs
        require(function(buf,len(raw)//(8 if ids else REF.size),error,len(error))==0,'Topology sort stopped: '+error.value.decode('ascii'))
        return raw

    def count(self,parts,tags,relation_nodes,relation_ways,*,references,ways,tagged_nodes):
        require(all(isinstance(ids,array) and ids.typecode=='Q' and ids.itemsize==8 for ids in (relation_nodes,relation_ways)),'Topology typed metadata arrays')
        packed=[(ctypes.c_char_p*len(paths))(*(os.fsencode(p) for p in paths)) for paths in (parts,tags)]
        metadata=[(ctypes.c_uint64*len(ids)).from_buffer(ids) for ids in (relation_nodes,relation_ways)]
        receipt=(ctypes.c_uint64*len(FIELDS))();error=ctypes.create_string_buffer(512)
        code=self.count_files(packed[0],len(parts),packed[1],len(tags),metadata[0],len(relation_nodes),metadata[1],len(relation_ways),references,ways,tagged_nodes,receipt,len(receipt),error,len(error))
        require(code==0 and receipt[-1]==1,'Topology count stopped: '+error.value.decode('ascii'))
        return dict(zip(FIELDS,map(int,receipt)))
