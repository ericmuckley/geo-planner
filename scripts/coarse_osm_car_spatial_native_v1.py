"""ctypes adapter for a lossless spatial permutation of closed packed arrays."""
import ctypes
import hashlib
from pathlib import Path

FIELDS=['vertices','arcs','routingPayloadBytes','spatialCells','spatialIndexBytes','totalBytesIncludingOfflinePermutations','forbiddenTurnPairs']


class NativeSpatial:
    def __init__(self,path,pin):
        path=Path(path)
        with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if path.is_symlink() or actual!=pin:raise ValueError('Spatial native artifact binding')
        self.lib=ctypes.CDLL(str(path.resolve()));self.lib.gp_car_spatial_abi.restype=ctypes.c_uint32
        if self.lib.gp_car_spatial_abi()!=0x10000:raise ValueError('Spatial native ABI')
        self.lib.gp_car_spatial_encode.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.POINTER(ctypes.c_uint64),ctypes.c_char_p,ctypes.c_size_t]
        self.lib.gp_car_spatial_encode.restype=ctypes.c_int

    def encode(self,source,output):
        source=Path(source);output=Path(output)
        if not source.is_dir() or not output.is_dir() or any(output.iterdir()):raise ValueError('Spatial source/fresh output')
        result=(ctypes.c_uint64*7)();error=ctypes.create_string_buffer(2048)
        if self.lib.gp_car_spatial_encode(bytes(source),bytes(output),result,error,len(error)):
            raise ValueError(error.value.decode('utf8',errors='replace'))
        return dict(zip(FIELDS,result))
