"""Typed pure-policy ABI controls. The national stream must call the header directly."""
import ctypes
import hashlib
from pathlib import Path
import struct

from coarse_timing_input import require

REASONS = [None, 'outside-major-profile', 'vehicle-ferry', 'access', 'area-ford-driveway-parking',
           'conditional-or-way-restriction', 'lane-access', 'unsupported-oneway', 'unsupported-speed', 'directional-access']
STATUSES = ['unrelated', 'non-car', 'via-node', 'closed-unsupported']
TURNS = ['no_left_turn', 'no_right_turn', 'no_straight_on', 'no_u_turn', 'no_entry', 'no_exit',
         'only_left_turn', 'only_right_turn', 'only_straight_on', 'only_u_turn']


def frame(kind, tags, members=()):
    require(kind in ('node', 'way', 'relation') and len(tags) <= 65536 and len(members) <= 65536, 'Policy input schema')
    raw = bytearray(b'GCP1')
    raw.append(('node', 'way', 'relation').index(kind))
    raw += struct.pack('<I', len(tags))
    def text(value):
        require(isinstance(value, str), 'Policy source text')
        value = value.encode('utf-8')
        raw.extend(struct.pack('<I', len(value)))
        raw.extend(value)
    for key, value in sorted(tags.items()):
        text(key)
        text(value)
    if kind == 'relation':
        raw += struct.pack('<I', len(members))
        for member in members:
            raw.extend(struct.pack('<BQ', ('node', 'way', 'relation').index(member['type']), member['ref']))
            text(member['role'])
    require(len(raw) <= 4194304, 'Policy frame byte cap')
    return bytes(raw)


class NativePolicy:
    def __init__(self, path, pin):
        path = Path(path)
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 16777216, 'Policy shared artifact bound')
        with path.open('rb') as stream:
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == pin, 'Policy artifact checksum')
        library = ctypes.CDLL(str(path.resolve()))
        library.gp_car_policy_abi.restype = ctypes.c_uint32
        require(library.gp_car_policy_abi() == 0x10000, 'Policy ABI')
        self.call = library.gp_car_policy_frame
        self.call.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint64), ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32]
        self.call.restype = ctypes.c_int

    def decode(self, raw):
        require(isinstance(raw, bytes) and len(raw) <= 4194305, 'Policy ABI input bound')
        output = (ctypes.c_uint64 * 8)()
        error = ctypes.create_string_buffer(512)
        code = self.call(raw, len(raw), output, 8, error, len(error))
        require(code == 0, 'Native policy: ' + error.value.decode('utf-8', errors='replace'))
        return list(output)

    def classify(self, kind, tags, members=()):
        words = self.decode(frame(kind, tags, members))
        if kind == 'node':
            return {'blocked': bool(words[0] & 1), 'signal': bool(words[0] & 2), 'tagged': bool(words[0] & 4)}
        if kind == 'way':
            def number(word):
                return struct.unpack('<d', struct.pack('<Q', word))[0]
            return {'reason': REASONS[words[0]], 'forward': number(words[4]) if words[1] & 1 else None,
                    'backward': number(words[5]) if words[1] & 2 else None,
                    'forward_default': bool(words[2] & 1), 'backward_default': bool(words[2] & 2)}
        return {'status': STATUSES[words[0]], 'kind': TURNS[words[1]] if words[1] < len(TURNS) else None,
                'fromWay': words[2], 'via': words[3], 'toWay': words[4],
                'reason': {0: None, 1: 'via-way', 2: 'unsupported-or-conditional'}[words[5]]}
