"""Native geometry-capacity adapter; never constructs Python country node objects."""
import ctypes
import hashlib
from pathlib import Path

COUNTS=['selectedCoordinates','sourceGeometryReferences','majorWays','preClosureArcs','postClosureArcs',
        'activePhysicalSpans','sourceInteriorOccurrences','simplifiedInteriorOccurrences','curvedSpans',
        'spansLongerThan1000m','zeroGeometricLengthSpans','maximumSourcePointsPerSpan','maximumKeptPointsPerSpan',
        'pointSegmentComparisons','coordinateVarintBytesWorstOrientation','packedShapeAndPrefixBytesForecast','longSpanIndexBytesForecast']
LIMITS=[100,250,500,1000,2500,5000,10000,25000,50000,100000,None]


class NativeGeometry:
    def __init__(self,path,pin):
        path=Path(path)
        with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if path.is_symlink() or actual!=pin:raise ValueError('Geometry artifact binding')
        self.lib=ctypes.CDLL(str(path.resolve()));self.lib.gp_car_geometry_abi.restype=ctypes.c_uint32
        if self.lib.gp_car_geometry_abi()!=0x10000:raise ValueError('Geometry ABI')
        i=ctypes.POINTER(ctypes.c_int32);q=ctypes.POINTER(ctypes.c_uint64);d=ctypes.POINTER(ctypes.c_double);error=[ctypes.c_char_p,ctypes.c_size_t]
        self.lib.gp_car_geometry_distance.argtypes=[i,d,*error];self.lib.gp_car_geometry_distance.restype=ctypes.c_int
        self.lib.gp_car_geometry_simplify.argtypes=[i,ctypes.c_uint32,ctypes.c_double,ctypes.POINTER(ctypes.c_uint8),q,d,*error];self.lib.gp_car_geometry_simplify.restype=ctypes.c_int
        self.lib.gp_car_geometry_probe.argtypes=[ctypes.c_char_p,q,q,d,*error];self.lib.gp_car_geometry_probe.restype=ctypes.c_int

    def distance(self,p,a,b):
        xy=(ctypes.c_int32*6)(*p,*a,*b);out=ctypes.c_double();error=ctypes.create_string_buffer(2048)
        if self.lib.gp_car_geometry_distance(xy,ctypes.byref(out),error,len(error)):raise ValueError(error.value.decode())
        return out.value

    def simplify(self,points,tolerance=100):
        if not 2<=len(points)<=1048576:raise ValueError('Geometry fixture point count')
        xy=(ctypes.c_int32*(2*len(points)))(*(v for p in points for v in p));flags=(ctypes.c_uint8*len(points))()
        work=ctypes.c_uint64();maximum=ctypes.c_double();error=ctypes.create_string_buffer(2048)
        if self.lib.gp_car_geometry_simplify(xy,len(points),tolerance,flags,ctypes.byref(work),ctypes.byref(maximum),error,len(error)):raise ValueError(error.value.decode())
        return {'kept':[i for i,value in enumerate(flags) if value],'comparisons':work.value,'maximumDiscardedErrorMeters':maximum.value}

    def probe(self,root,expected):
        if not Path(root).is_dir() or len(expected)!=6 or any(not isinstance(n,int) or not 0<=n<2**64 for n in expected):raise ValueError('Geometry input dimensions/root')
        dimensions=(ctypes.c_uint64*6)(*expected);counts=(ctypes.c_uint64*28)();values=(ctypes.c_double*3)();error=ctypes.create_string_buffer(2048)
        if self.lib.gp_car_geometry_probe(bytes(Path(root)),dimensions,counts,values,error,len(error)):raise ValueError(error.value.decode())
        result=dict(zip(COUNTS,counts))
        result['lengthHistogram']=[{'maximumMeters':limit,'physicalSpans':counts[17+i]} for i,limit in enumerate(LIMITS)]
        result.update(totalActiveRoadMeters=values[0],maximumPhysicalSpanMeters=values[1],maximumDiscardedPointErrorMeters=values[2])
        return result
