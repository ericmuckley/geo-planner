"""ctypes adapter for typed native encoding of closed cost facts."""
import ctypes
import hashlib
from pathlib import Path

FIELDS = ['selectedNodes', 'vertices', 'majorWays', 'preClosureArcs', 'postClosureArcs',
          'sourceTurnRecords', 'costOverflowEntries', 'reverseOverflowEntries',
          'forbiddenTurnPairs', 'payloadBytes', 'maximumOutDegree', 'relevantSourceTurnRecords']


class NativePacked:
    def __init__(self, path, pin):
        path = Path(path)
        with path.open('rb') as stream:actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if path.is_symlink() or actual != pin:raise ValueError('Packed native artifact binding')
        self.lib = ctypes.CDLL(str(path.resolve()))
        self.lib.gp_car_packed_abi.restype = ctypes.c_uint32
        if self.lib.gp_car_packed_abi() != 0x10000:raise ValueError('Packed native ABI')
        self.lib.gp_car_packed_encode.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64), ctypes.c_char_p, ctypes.c_size_t]
        self.lib.gp_car_packed_encode.restype = ctypes.c_int

    def encode(self, source, output, expected):
        source = Path(source);output = Path(output)
        if len(expected) != 6 or not source.is_dir() or not output.is_dir() or any(output.iterdir()):
            raise ValueError('Packed native source/fresh output/dimensions')
        if any(not isinstance(value, int) or value < 0 or value > 2**64-1 for value in expected):
            raise ValueError('Packed native expected count')
        counts = (ctypes.c_uint64*6)(*expected);result = (ctypes.c_uint64*12)();error = ctypes.create_string_buffer(2048)
        if self.lib.gp_car_packed_encode(bytes(source), bytes(output), counts, result, error, len(error)):
            raise ValueError(error.value.decode('utf8', errors='replace'))
        return dict(zip(FIELDS, result))
