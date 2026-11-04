"""Native paid-geometry adapter; source coordinates stay in typed native arrays."""
import ctypes
import hashlib
from pathlib import Path

FIELDS=['selectedCoordinates','sourceAnchors','majorWays','geometryReferences','preClosureArcs','postClosureArcs',
        'physicalSpans','curvedSpans','interiorPoints','longSpans','runtimeBytes','offlineProvenanceBytes',
        'lengthOverflows','packetBytes','totalOutputBytes','comparisons']


class NativePaidGeometry:
    def __init__(self,path,pin):
        path=Path(path)
        with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if path.is_symlink() or actual!=pin:raise ValueError('Paid geometry artifact binding')
        self.lib=ctypes.CDLL(str(path.resolve()));self.lib.gp_car_paid_geometry_abi.restype=ctypes.c_uint32
        if self.lib.gp_car_paid_geometry_abi()!=0x10000:raise ValueError('Paid geometry ABI')
        q=ctypes.POINTER(ctypes.c_uint64);d=ctypes.POINTER(ctypes.c_double);error=[ctypes.c_char_p,ctypes.c_size_t]
        self.lib.gp_car_paid_project.argtypes=[ctypes.POINTER(ctypes.c_int32),d,*error];self.lib.gp_car_paid_project.restype=ctypes.c_int
        self.lib.gp_car_paid_simplify.argtypes=[ctypes.POINTER(ctypes.c_int32),ctypes.c_uint32,q,q,ctypes.POINTER(ctypes.c_uint8),q,d,*error];self.lib.gp_car_paid_simplify.restype=ctypes.c_int
        self.lib.gp_car_paid_geometry_build.argtypes=[ctypes.c_char_p]*4+[q,q,d,*error];self.lib.gp_car_paid_geometry_build.restype=ctypes.c_int

    def project(self,p,a,b):
        xy=(ctypes.c_int32*6)(*p,*a,*b);values=(ctypes.c_double*2)();error=ctypes.create_string_buffer(2048)
        if self.lib.gp_car_paid_project(xy,values,error,len(error)):raise ValueError(error.value.decode())
        return tuple(values)

    def simplify(self,points,forward,backward):
        if not 2<=len(points)<=1048576 or len(forward)!=len(points) or len(backward)!=len(points):raise ValueError('Paid fixture dimensions')
        if any(not isinstance(v,int) or not -(2**31)<=v<2**31 for p in points for v in p):raise ValueError('Paid fixture coordinate words')
        if any(not isinstance(v,int) or not 0<=v<2**64 for v in [*forward,*backward]):raise ValueError('Paid fixture prefix words')
        xy=(ctypes.c_int32*(len(points)*2))(*(v for p in points for v in p));f=(ctypes.c_uint64*len(points))(*forward);b=(ctypes.c_uint64*len(points))(*backward)
        flags=(ctypes.c_uint8*len(points))();work=ctypes.c_uint64();errors=(ctypes.c_double*2)();error=ctypes.create_string_buffer(2048)
        if self.lib.gp_car_paid_simplify(xy,len(points),f,b,flags,ctypes.byref(work),errors,error,len(error)):raise ValueError(error.value.decode())
        return {'kept':[i for i,value in enumerate(flags) if value],'comparisons':work.value,
                'maximumDiscardedGeometryErrorMeters':errors[0],'maximumDiscardedTimeErrorMs':errors[1]}

    def build(self,source,offsets,arc_map,output,expected):
        output=Path(output)
        if not Path(source).is_dir() or not output.is_dir() or any(output.iterdir()):raise ValueError('Paid source/fresh output')
        if len(expected)!=6 or any(not isinstance(v,int) or not 0<=v<2**64 for v in expected):raise ValueError('Paid source expected dimensions')
        dims=(ctypes.c_uint64*6)(*expected);counts=(ctypes.c_uint64*16)();values=(ctypes.c_double*3)();error=ctypes.create_string_buffer(2048)
        if self.lib.gp_car_paid_geometry_build(bytes(Path(source)),bytes(Path(offsets)),bytes(Path(arc_map)),bytes(output),dims,counts,values,error,len(error)):raise ValueError(error.value.decode())
        result=dict(zip(FIELDS,counts));result.update(maximumDiscardedGeometryErrorMeters=values[0],maximumDiscardedTimeErrorMs=values[1],maximumFullSpanMeters=values[2]);return result
