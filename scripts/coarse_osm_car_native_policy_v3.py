"""V3 static conditional-speed ABI adapter; legacy wire/decoding remain shared."""
import ctypes
import hashlib
from pathlib import Path

from coarse_osm_car_native_policy_v1 import frame
from coarse_osm_car_native_policy_v2 import NativePolicy as LegacyPolicy
from coarse_timing_input import require


class NativePolicy(LegacyPolicy):
    def __init__(self, path, pin):
        path = Path(path)
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 16777216, 'Policy shared artifact bound')
        with path.open('rb') as stream:
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == pin, 'Policy artifact checksum')
        library = ctypes.CDLL(str(path.resolve()))
        library.gp_car_policy_abi.restype = ctypes.c_uint32
        require(library.gp_car_policy_abi() == 0x30000, 'Policy V3 ABI')
        self.call = library.gp_car_policy_frame
        self.call.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint64), ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32]
        self.call.restype = ctypes.c_int

    def classify(self, kind, tags, members=()):
        if kind == 'relation' and self.decode(frame(kind, tags, members))[0] == 4:
            return {'status': 'invalid-unlocatable', 'kind': None, 'fromWay': 0, 'via': 0, 'toWay': 0,
                    'reason': 'unlocatable-source-record'}
        return super().classify(kind, tags, members)
