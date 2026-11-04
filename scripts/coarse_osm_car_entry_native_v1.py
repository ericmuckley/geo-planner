"""Typed ABI for sparse restriction metadata and source-to-CSR pair mapping."""
import ctypes
import hashlib
import os
from pathlib import Path


class NativeEntries:
    def __init__(self, path, pin):
        path = Path(path)
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 16777216:
            raise ValueError('Entry native artifact bound')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != pin:
                raise ValueError('Entry native artifact SHA')
        self.path, self.sha256 = path, pin
        self.lib = ctypes.CDLL(str(path.resolve()))
        self.lib.gp_car_entry_abi.restype = ctypes.c_uint32
        if self.lib.gp_car_entry_abi() != 0x10000:
            raise ValueError('Entry native ABI')
        q = ctypes.POINTER(ctypes.c_uint64)
        error = [ctypes.c_char_p, ctypes.c_size_t]
        self.lib.gp_car_entry_resolve.argtypes = [ctypes.c_char_p]*4+[q, q, *error]
        self.lib.gp_car_entry_resolve.restype = ctypes.c_int
        self.lib.gp_car_entry_augment.argtypes = [ctypes.c_char_p]*5+[q, q, *error]
        self.lib.gp_car_entry_augment.restype = ctypes.c_int

    def _call(self, function, paths, expected, width):
        if len(expected) not in (4, 5) or any(type(v) is not int or not 0 <= v < 2**64 for v in expected):
            raise ValueError('Entry native dimensions')
        dims = (ctypes.c_uint64*len(expected))(*expected)
        counts = (ctypes.c_uint64*width)()
        error = ctypes.create_string_buffer(2048)
        code = function(*(os.fsencode(p) for p in paths), dims, counts, error, len(error))
        if code:
            raise ValueError(error.value.decode())
        return list(counts)

    def resolve(self, source, rules, fallback, output, expected):
        if len(expected) != 5:
            raise ValueError('Entry resolver dimension shape')
        return self._call(self.lib.gp_car_entry_resolve, [source, rules, fallback, output], expected, 9)

    def augment(self, source, closed, pairs, routing, output, expected):
        if len(expected) != 4:
            raise ValueError('Entry augmentation dimension shape')
        return self._call(self.lib.gp_car_entry_augment, [source, closed, pairs, routing, output], expected, 6)
