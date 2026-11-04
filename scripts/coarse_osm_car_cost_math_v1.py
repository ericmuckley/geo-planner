"""Typed pure geometry/cost ABI; bounds remain enforced in native code."""
from array import array
import ctypes
import hashlib
from pathlib import Path

from coarse_timing_input import require


class NativeCosts:
    def __init__(self, path, pin):
        path = Path(path)
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 16777216, 'Cost artifact bound')
        with path.open('rb') as stream:
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == pin, 'Cost artifact hash')
        self.library = ctypes.CDLL(str(path.resolve()))
        self.library.gp_car_cost_math_abi.restype = ctypes.c_uint32
        require(self.library.gp_car_cost_math_abi() == 0x10000, 'Cost math ABI')
        self.batch = self.library.gp_car_cost_math_batch
        word = ctypes.POINTER(ctypes.c_uint64)
        self.batch.argtypes = [ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_double),
                               ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint32, word, ctypes.c_char_p, ctypes.c_uint32]
        self.batch.restype = ctypes.c_int
        self.summer = self.library.gp_car_cost_math_sum
        self.summer.argtypes = [word, ctypes.c_uint32, word, ctypes.c_char_p, ctypes.c_uint32]
        self.summer.restype = ctypes.c_int

    def costs(self, coordinates, speeds, same):
        require(isinstance(coordinates, array) and coordinates.typecode == 'i' and coordinates.itemsize == 4 and
                isinstance(speeds, array) and speeds.typecode == 'd' and speeds.itemsize == 8 and
                isinstance(same, bytearray) and len(coordinates) == 4*len(speeds) and len(same) == len(speeds) <= 2000000, 'Cost typed batch shape')
        inputs = [(kind*len(values)).from_buffer(values) for kind, values in
                  ((ctypes.c_int32, coordinates), (ctypes.c_double, speeds), (ctypes.c_uint8, same))]
        out = array('Q', [0])*len(speeds)
        target = (ctypes.c_uint64*len(out)).from_buffer(out)
        error = ctypes.create_string_buffer(512)
        code = self.batch(*inputs, len(out), target, error, len(error))
        require(code == 0, 'Native primitive costs: '+error.value.decode('ascii'))
        return out

    def sum(self, values):
        require(len(values) <= 2000000 and all(type(v) is int and 0 <= v < 2**64 for v in values), 'Cost sum unsigned integer input')
        source = (ctypes.c_uint64*len(values))(*values)
        out = (ctypes.c_uint64*2)()
        error = ctypes.create_string_buffer(512)
        code = self.summer(source, len(values), out, error, len(error))
        require(code == 0, 'Native cost sum: '+error.value.decode('ascii'))
        return tuple(out)
