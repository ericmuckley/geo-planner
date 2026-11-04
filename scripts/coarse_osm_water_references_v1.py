"""Native selected-byte capture with independently decoded reference/index audit."""
import ctypes
import hashlib
from array import array
import struct

from coarse_osm_country_wire_v4 import CALLBACK, decode_frame
from coarse_osm_water_union_v1 import WaterUnion
from coarse_osm_water_reference_store_v1 import Reader
from coarse_timing_input import require

COUNTERS=('ways','references','rawGpfBytes','uniqueNodes','wayChunks','nodeChunks','complete','reserved7')


class WaterReferences(WaterUnion):
    def __init__(self,path,pin,*,expected_ways,expected_references,store,check=lambda:None,**options):
        super().__init__(path,pin,**options)
        self.expected_ways=expected_ways;self.expected_references=expected_references
        self.store=store;self.check=check
        lib=self.library;lib.gp_water_refs_abi.restype=ctypes.c_uint32
        require(lib.gp_water_refs_abi()==0x10000,'Water reference ABI')
        for old,name in ((self.frames,'gp_water_refs_frames'),(self.pbf,'gp_water_refs_pbf')):
            native=getattr(lib,name);native.argtypes,native.restype=old.argtypes,old.restype
            proxy=self._proxy(native)
            if name.endswith('frames'):self.frames=proxy
            else:self.pbf=proxy
        lib.gp_water_refs_begin.argtypes=[ctypes.POINTER(ctypes.c_uint64),ctypes.c_uint32,ctypes.c_uint64,ctypes.c_uint64]
        lib.gp_water_refs_begin.restype=ctypes.c_int
        lib.gp_water_refs_finish.argtypes=[ctypes.POINTER(ctypes.c_uint64),ctypes.c_uint32,CALLBACK,ctypes.c_void_p,ctypes.c_char_p,ctypes.c_uint32]
        lib.gp_water_refs_finish.restype=ctypes.c_int
        lib.gp_water_refs_release.argtypes=[];lib.gp_water_refs_release.restype=None
        lib.gp_water_refs_audit_begin.argtypes=[ctypes.c_uint64];lib.gp_water_refs_audit_begin.restype=ctypes.c_int
        lib.gp_water_refs_audit_append.argtypes=[ctypes.POINTER(ctypes.c_uint64),ctypes.c_uint32];lib.gp_water_refs_audit_append.restype=ctypes.c_int
        lib.gp_water_refs_audit_finish.argtypes=[CALLBACK,ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint64)]
        lib.gp_water_refs_audit_finish.restype=ctypes.c_int
        lib.gp_water_refs_audit_release.argtypes=[];lib.gp_water_refs_audit_release.restype=None

    def _proxy(self,native):
        def run(*args):
            outer=args[-6];values=list(args);failed=[]
            def callback(user,event,data,size):
                if event!=20:return outer(user,event,data,size)
                try:
                    self.check();require(0<size<=1048576,'Water reference source byte chunk')
                    self.store.way_chunk(ctypes.string_at(data,size));return 0
                except BaseException as error:failed.append(error);return -1
            handle=CALLBACK(callback);values[-6]=handle
            code=native(*values)
            if failed:raise failed[0]
            return code
        return run

    def begin(self):
        require(not self.begun and 0<=self.expected_ways<=4000000 and 0<=self.expected_references<=150000000 and
                self.library.gp_water_refs_begin(self.member_ids,len(self.member_ids),self.expected_ways,self.expected_references)==0,'Water reference exclusive bounded capture')
        self.begun=True

    def finish(self):
        water=super().finish();union=water['union']
        require(union['unionWays']==self.expected_ways and union['unionReferences']==self.expected_references,'Water reference frozen union dimensions')
        self.store.prepare_nodes();failed=[]
        def callback(_,event,data,size):
            try:
                self.check();require(event==21 and 0<size<=1048576 and size%8==0,'Water reference unique ID chunk')
                self.store.node_chunk(ctypes.string_at(data,size));return 0
            except BaseException as error:failed.append(error);return -1
        handle=CALLBACK(callback);values=(ctypes.c_uint64*len(COUNTERS))();error=ctypes.create_string_buffer(512)
        code=self.library.gp_water_refs_finish(values,len(values),handle,None,error,len(error))
        if failed:raise failed[0]
        require(code==0 and values[6]==1,'Water reference finish: '+error.value.decode('ascii'))
        result=dict(zip(COUNTERS,map(int,values)))
        require(result['rawGpfBytes']==union['unionEncodedBytes']+4*union['unionWays'],'Water reference exact union frame bytes')
        return {**water,'referenceCapture':result,'referenceStore':self.store.finish(result['uniqueNodes'])}

    def release(self):
        require(not self.active,'Water reference release during callback')
        if self.begun:self.library.gp_water_refs_release();self.begun=False


def audit_store(engine,root,stored,capture,union,member_ids,check=lambda:None):
    """Decode every saved GPF field independently and rebuild its unique node set."""
    require(not engine.active and not engine.begun,'Water reference audit requires released capture buffers')
    lib=engine.library;expected=capture['references']
    require(lib.gp_water_refs_audit_begin(expected)==0,'Water reference independent sorter begin')
    ways=refs=previous=encoded=tagged=tagged_refs=found=found_refs=overlap=overlap_refs=closed=0
    member_ids=set(member_ids)
    try:
        with Reader(root,stored['ways']) as reader:
            while prefix:=reader.read(4):
                check();require(len(prefix)==4,'Water reference audit length prefix')
                size=struct.unpack('<I',prefix)[0];require(0<size<=8388608,'Water reference audit frame cap')
                body=reader.read(size);require(len(body)==size,'Water reference audit truncated frame')
                row=decode_frame(body);identity=row['id'];tags=row['tags']
                water=tags.get('natural')=='water' or tags.get('waterway')=='riverbank' or tags.get('landuse')=='reservoir'
                member=identity in member_ids
                require(row['type']=='way' and identity>previous and (water or member),'Water reference independent source selector/order/type')
                nodes=row['nodes'];ways+=1;refs+=len(nodes);encoded+=size;previous=identity
                closed+=nodes[0]==nodes[-1]
                if water:tagged+=1;tagged_refs+=len(nodes)
                if member:found+=1;found_refs+=len(nodes)
                if water and member:overlap+=1;overlap_refs+=len(nodes)
                require(ways<=capture['ways'] and refs<=expected,'Water reference audit exact row/ref caps')
                for cursor in range(0,len(nodes),131072):
                    batch=array('Q',nodes[cursor:cursor+131072]);values=(ctypes.c_uint64*len(batch)).from_buffer(batch)
                    require(lib.gp_water_refs_audit_append(values,len(batch))==0,'Water reference independently decoded ID batch')
            require(reader.finished,'Water reference complete GPF EOF')
        checks={'unionWays':ways,'unionReferences':refs,'unionEncodedBytes':encoded,'closedUnionWays':closed,'openUnionWays':ways-closed,
                'taggedWays':tagged,'taggedReferences':tagged_refs,'memberWaysFound':found,'memberWayReferences':found_refs,
                'taggedMemberOverlapWays':overlap,'taggedMemberOverlapReferences':overlap_refs}
        require(all(union[k]==v for k,v in checks.items()),'Water reference independent all-union counters')
        failures=[];digest=hashlib.sha256();raw_bytes=0
        with Reader(root,stored['nodes']) as reader:
            def compare(_,event,data,size):
                nonlocal raw_bytes
                try:
                    check();require(event==22 and 0<size<=1048576 and size%8==0,'Water reference audit sorted-ID chunk')
                    expected_bytes=ctypes.string_at(data,size)
                    require(reader.read(size)==expected_bytes,'Water reference every unique ID independently exact')
                    digest.update(expected_bytes);raw_bytes+=size;return 0
                except BaseException as error:failures.append(error);return -1
            callback=CALLBACK(compare);count=ctypes.c_uint64()
            code=lib.gp_water_refs_audit_finish(callback,None,ctypes.byref(count))
            if failures:raise failures[0]
            require(code==0 and not reader.read(1) and reader.finished,'Water reference independent node-ID EOF')
        require(count.value==stored['uniqueNodes']==capture['uniqueNodes'] and raw_bytes==count.value*8 and digest.hexdigest()==stored['nodes']['rawSha256'],'Water reference independent unique set dimensions/seal')
        return {'allWayRecordsAndFieldsDecoded':ways,'allReferenceOccurrencesChecked':refs,'allUniqueNodeIdsIndependentlyCompared':count.value,
                'allSavedGpfBytesChecked':stored['ways']['rawBytes'],'allRawIdBytesCompared':raw_bytes,'coordinatesOrRingsConstructed':False}
    finally:lib.gp_water_refs_audit_release()
