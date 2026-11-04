"""Bounded native coordinate closure and independent decoder/partition audit."""
import ctypes
import hashlib
import sys

from coarse_osm_country_wire_v4 import CALLBACK
from coarse_osm_topology_source_v1 import NativeScreen
from coarse_osm_water_reference_store_v1 import Reader
from coarse_timing_input import require

COUNTERS=('requested','present','missing','encodedBytes','canonicalBytes','missingBytes','complete','reserved7')


class WaterCoordinates(NativeScreen):
    def __init__(self,path,pin,*,requested,id_chunks,store,check=lambda:None,**options):
        super().__init__(path,pin,**options)
        require(type(requested) is int and 0<=requested<=150000000 and sys.byteorder=='little','Water coordinate input/platform')
        self.requested=requested;self.id_chunks=id_chunks;self.store=store;self.check=check;self.begun=False
        lib=self.library;lib.gp_water_coords_abi.restype=ctypes.c_uint32
        require(lib.gp_water_coords_abi()==0x10000,'Water coordinate ABI')
        for old,name in ((self.frames,'gp_water_coords_frames'),(self.pbf,'gp_water_coords_pbf')):
            native=getattr(lib,name);native.argtypes,native.restype=old.argtypes,old.restype
            if name.endswith('frames'):self.frames=self._proxy(native)
            else:self.pbf=self._proxy(native)
        for prefix in ('gp_water_coords','gp_water_coords_audit'):
            begin=getattr(lib,prefix+'_begin');begin.argtypes=[ctypes.c_uint64];begin.restype=ctypes.c_int
            append=getattr(lib,prefix+'_append');append.argtypes=[ctypes.POINTER(ctypes.c_uint64),ctypes.c_uint32];append.restype=ctypes.c_int
            seal=getattr(lib,prefix+'_seal');seal.argtypes=[];seal.restype=ctypes.c_int
            release=getattr(lib,prefix+'_release');release.argtypes=[];release.restype=None
        lib.gp_water_coords_finish.argtypes=[ctypes.POINTER(ctypes.c_uint64),ctypes.c_uint32,ctypes.c_char_p,ctypes.c_uint32]
        lib.gp_water_coords_finish.restype=ctypes.c_int
        lib.gp_water_coords_audit_feed.argtypes=[ctypes.c_void_p,ctypes.c_uint32,CALLBACK,ctypes.c_void_p,ctypes.c_char_p,ctypes.c_uint32]
        lib.gp_water_coords_audit_feed.restype=ctypes.c_int
        lib.gp_water_coords_audit_finish.argtypes=[ctypes.POINTER(ctypes.c_uint64),ctypes.c_uint32,CALLBACK,ctypes.c_void_p,ctypes.c_char_p,ctypes.c_uint32]
        lib.gp_water_coords_audit_finish.restype=ctypes.c_int

    def _proxy(self,native):
        def run(*args):
            outer=args[-6];values=list(args);failed=[]
            def callback(user,event,data,size):
                if event not in (30,31,32):return outer(user,event,data,size)
                try:
                    self.check();require(0<size<=1048576,'Water coordinate native chunk')
                    self.store.accept(event,ctypes.string_at(data,size));return 0
                except BaseException as error:failed.append(error);return -1
            handle=CALLBACK(callback);values[-6]=handle;code=native(*values)
            if failed:raise failed[0]
            return code
        return run

    def load_ids(self,prefix):
        total=0;lib=self.library
        for raw in self.id_chunks():
            self.check();require(isinstance(raw,bytes) and 0<len(raw)<=1048576 and len(raw)%8==0,'Water coordinate input ID byte chunk')
            count=len(raw)//8;total+=count;require(total<=self.requested,'Water coordinate input ID count cap')
            values=(ctypes.c_uint64*count).from_buffer_copy(raw)
            require(getattr(lib,prefix+'_append')(values,count)==0,'Water coordinate native sorted-ID input')
        require(total==self.requested and getattr(lib,prefix+'_seal')()==0,'Water coordinate complete ID input seal')

    def begin(self):
        require(not self.begun and self.library.gp_water_coords_begin(self.requested)==0,'Water coordinate exclusive capture')
        self.begun=True
        try:self.load_ids('gp_water_coords')
        except BaseException:self.release();raise

    def finish(self):
        require(self.begun and not self.active and self.last is not None and self.last['nativeEof'],'Water coordinate complete source before finish')
        values=(ctypes.c_uint64*len(COUNTERS))();error=ctypes.create_string_buffer(512)
        code=self.library.gp_water_coords_finish(values,len(values),error,len(error))
        require(code==0 and values[6]==1,'Water coordinate finish: '+error.value.decode('ascii'))
        counts=dict(zip(COUNTERS,map(int,values)))
        return {'capture':counts,'stored':self.store.finish(counts)}

    def release(self):
        require(not self.active,'Water coordinate release during source callback')
        if self.begun:self.library.gp_water_coords_release();self.begun=False


def audit_store(engine,root,stored,capture,check=lambda:None,*,chunk_bytes=1048576):
    require(not engine.begun and not engine.active and 0<chunk_bytes<=1048576,'Water coordinate audit needs released source buffers/bounded chunks')
    lib=engine.library;require(lib.gp_water_coords_audit_begin(engine.requested)==0,'Water coordinate independent audit begin')
    errors=[];digest=hashlib.sha256();canonical_bytes=missing_bytes=0
    try:
        engine.load_ids('gp_water_coords_audit')
        with Reader(root,stored['missing']) as missing:
            def callback(_,event,data,size):
                nonlocal canonical_bytes,missing_bytes
                try:
                    check();require(event in (31,32) and 0<size<=1048576,'Water coordinate audit output event/chunk')
                    raw=ctypes.string_at(data,size)
                    if event==31:
                        require(size%8==0 and missing.read(size)==raw,'Water coordinate independently exact missing-ID partition');missing_bytes+=size
                    else:
                        require(size%16==0,'Water coordinate audit canonical row width');digest.update(raw);canonical_bytes+=size
                    return 0
                except BaseException as error:errors.append(error);return -1
            handle=CALLBACK(callback);error=ctypes.create_string_buffer(512)
            with Reader(root,stored['encoded']) as encoded:
                while raw:=encoded.read(chunk_bytes):
                    check();buffer=ctypes.create_string_buffer(raw)
                    code=lib.gp_water_coords_audit_feed(buffer,len(raw),handle,None,error,len(error))
                    if errors:raise errors[0]
                    require(code==0,'Water coordinate independent decoder: '+error.value.decode('ascii'))
                require(encoded.finished,'Water coordinate encoded EOF')
            values=(ctypes.c_uint64*len(COUNTERS))()
            code=lib.gp_water_coords_audit_finish(values,len(values),handle,None,error,len(error))
            if errors:raise errors[0]
            require(code==0,'Water coordinate independent decoder EOF: '+error.value.decode('ascii'))
            require(not missing.read(1) and missing.finished,'Water coordinate missing-ID EOF')
        counts=dict(zip(COUNTERS,map(int,values)))
        require(counts==capture and counts['requested']==engine.requested and canonical_bytes==stored['sourceShadow']['bytes']==counts['canonicalBytes'] and
                missing_bytes==counts['missingBytes'] and digest.hexdigest()==stored['sourceShadow']['sha256'],'Water coordinate every canonical source byte/count/partition independently exact')
        return {'requestedIdsIndependentlyPartitioned':counts['requested'],'presentCoordinatesIndependentlyDecoded':counts['present'],
                'missingIdsIndependentlyCompared':counts['missing'],'allCanonicalSourceIdXYBytesCompared':canonical_bytes,
                'canonicalSourceShadowSha256':digest.hexdigest(),'sourceCoordinatesChangedOrRingsConstructed':False}
    finally:lib.gp_water_coords_audit_release()
