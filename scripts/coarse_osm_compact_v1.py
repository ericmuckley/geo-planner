"""Bounded, lossless coordinate shards. Experimental; no production imports."""
from bisect import bisect_left
import hashlib
import math
from pathlib import Path
import struct

from coarse_osm_records import canonical
from coarse_timing_input import require

ROW = struct.Struct('<qii')
HEADER = struct.Struct('<8sQQQ32s')
MAGIC = b'GPCOOR1\0'
SCALE = 10000000


def coordinate(value, bound):
    require(type(value) in (int, float) and math.isfinite(value) and -bound <= value <= bound, 'Compact coordinate range/type')
    integer = round(value * SCALE)
    require(struct.pack('<d', integer / SCALE) == struct.pack('<d', value), 'Compact coordinate precision/negative zero')
    return integer


class Storage:
    def __init__(self, limit, file_limit):
        self.limit, self.file_limit = limit, file_limit
        self.live = self.peak = 0

    def write(self, path, raw):
        require(len(raw) <= self.file_limit and self.live + len(raw) <= self.limit, 'Compact file/working cap')
        require(not path.exists() and not path.is_symlink(), 'Compact refuses overwrite')
        self.live += len(raw)
        self.peak = max(self.peak, self.live)
        with path.open('xb') as stream:
            stream.write(raw)

    def remove(self, path, size):
        require(not path.is_symlink() and path.stat().st_size == size, 'Compact removal identity')
        path.unlink()
        self.live -= size


class Index:
    def __init__(self, root, storage, *, rows_per_shard=65536, index_limit=33554432, catalog_limit=1048576, replacing=None):
        self.root = Path(root)
        self.root.mkdir()
        require(type(rows_per_shard) is int and 0 < rows_per_shard <= 65536, 'Compact shard row bound')
        self.storage, self.rows_per_shard = storage, rows_per_shard
        self.index_limit, self.catalog_limit = index_limit, catalog_limit
        self.replacing = replacing
        self.entries, self.ends = [], []
        self.buffer = bytearray()
        self.first = self.last = self.count = self.generated_bytes = 0
        self.cache_number = self.cache = None
        self.finished = self.closed = False
        self.catalog_bytes = 128

    def add(self, raw):
        require(not self.closed and not self.finished, 'Compact writer closed/finished')
        identity = raw['id']
        require(type(identity) is int and self.last < identity < 2**63, 'Compact identity order/range')
        x, y = coordinate(raw['lon'], 180), coordinate(raw['lat'], 90)
        if not self.buffer:
            self.first = identity
        self.buffer.extend(ROW.pack(identity, x, y))
        self.last = identity
        self.count += 1
        if len(self.buffer) == self.rows_per_shard * ROW.size:
            self.flush()

    def path(self, number):
        return self.root / f'{number:08d}.bin'

    def flush(self):
        if not self.buffer:
            return
        payload = bytes(self.buffer)
        raw = HEADER.pack(MAGIC, len(payload) // ROW.size, self.first, self.last, hashlib.sha256(payload).digest()) + payload
        require(self.generated_bytes + len(raw) <= self.index_limit, 'Compact index byte cap')
        number = len(self.entries)
        entry = {'first': self.first, 'last': self.last, 'rows': len(payload) // ROW.size, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        self.catalog_bytes += len(canonical(entry)) + 1
        require(self.catalog_bytes <= self.catalog_limit, 'Compact catalog cap')
        self.storage.write(self.path(number), raw)
        self.entries.append(entry)
        self.ends.append(self.last)
        self.generated_bytes += len(raw)
        self.buffer.clear()
        if self.replacing is not None:
            old = self.replacing
            require(number < len(old.entries) and entry == old.entries[number], 'Compact source/index drift during replacement')
            old.cache_number = old.cache = None
            old.read(number)
            old.cache_number = old.cache = None
            self.storage.remove(old.path(number), entry['bytes'])

    def finish(self):
        require(not self.closed, 'Compact index closed')
        if self.finished:
            return
        self.flush()
        if self.replacing is not None:
            require(self.entries == self.replacing.entries, 'Compact replacement count drift')
        manifest = canonical({'format': 'ordered-id64-xy32-v1', 'rows': self.count, 'entries': self.entries}) + b'\n'
        require(len(manifest) <= self.catalog_limit and self.generated_bytes + len(manifest) <= self.index_limit, 'Compact final catalog/index cap')
        self.storage.write(self.root / 'index.json', manifest)
        self.generated_bytes += len(manifest)
        self.finished = True

    def read(self, number):
        require(not self.closed and self.finished and 0 <= number < len(self.entries), 'Compact lookup state')
        if number == self.cache_number:
            return self.cache
        entry = self.entries[number]
        path = self.path(number)
        require(not path.is_symlink() and path.stat().st_size == entry['bytes'], 'Compact shard size/type')
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == entry['sha256'], 'Compact shard checksum')
        magic, count, first, last, digest = HEADER.unpack_from(raw)
        payload = raw[HEADER.size:]
        require(magic == MAGIC and count == entry['rows'] and (first, last) == (entry['first'], entry['last']), 'Compact shard header')
        require(len(payload) == count * ROW.size and hashlib.sha256(payload).digest() == digest, 'Compact shard payload')
        self.cache_number, self.cache = number, payload
        return payload

    def points(self, ids):
        require(self.finished and not self.closed, 'Compact unfinished lookup')
        # Preserve reference order and duplicates; group lookups to bound shard reads.
        grouped, found = {}, {}
        for identity in ids:
            require(type(identity) is int and identity > 0, 'Compact lookup identity')
            number = bisect_left(self.ends, identity)
            require(number < len(self.entries), 'Compact missing node')
            grouped.setdefault(number, []).append(identity)
        for number, identities in grouped.items():
            payload = self.read(number)
            for identity in identities:
                lo, hi = 0, len(payload) // ROW.size
                while lo < hi:
                    mid = (lo + hi) // 2
                    if ROW.unpack_from(payload, mid * ROW.size)[0] < identity:
                        lo = mid + 1
                    else:
                        hi = mid
                require(lo < len(payload) // ROW.size, 'Compact missing node')
                key, x, y = ROW.unpack_from(payload, lo * ROW.size)
                require(key == identity, 'Compact missing node')
                found[identity] = [x / SCALE, y / SCALE]
        return [found[i] for i in ids]

    def close(self):
        self.cache_number = self.cache = None
        self.buffer.clear()
        self.closed = True
