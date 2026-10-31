"""Continuous native summary bridge and bounded source-ordinal index probe.

No source acquisition or national execution entry point. The predecessor's field
oracle, framing and lossless codec remain frozen and are reused read-only.
"""
from array import array
from copy import deepcopy
import ctypes
import hashlib
import os
from pathlib import Path
import struct
import time

from coarse_osm_bulk_pbf import framing, stat_key
from coarse_osm_delta_v1 import BLOCK, DIRECTORY, ENTRY, SHARD, FORMAT, ROWS, MAX_PAYLOAD, NativeCodec, ReferenceCodec
from coarse_osm_delta_v2 import Reader, Storage
from coarse_osm_projector_v1 import EncodedIndex, BLOCK_EVENT, CALLBACK, KINDS, MAX_FRAME, MAX_INPUT, SEAL_PREFIX, decode_frame
from coarse_osm_records import canonical
from coarse_timing_input import require, start_watchdog

SOURCE_COUNTS = (1606229364, 162688797, 1624265)
SOURCE_BYTES = 12229320016
MAX_VISITS = sum(SOURCE_COUNTS)
RECEIPT_NAMES = (
    'nodes', 'ways', 'relations', 'visits', 'nativeEof', 'fallbacks', 'blocks', 'semanticBytes', 'projectedFrames', 'checkpoints',
    'acceptedNodes', 'acceptedWays', 'acceptedRelations', 'maxNodeId', 'maxWayId', 'maxRelationId',
    'references', 'members', 'canonicalLowerBytes', 'canonicalUpperBytes', 'copyBytes', 'maxCopyBytes', 'tags', 'tagUtf8Bytes',
    'maxCanonicalLowerBytes', 'maxCanonicalUpperBytes', 'maxVersion', 'sourceEncodeRows', 'sourceDecodeRows', 'sourceCodecCalls',
    'highwayWays', 'longHighwayWays', 'outOfRangeHighwayWays', 'eligibleHighwayWays', 'traceWays', 'traceReferences',
    'witnessRows', 'maxReferences', 'maxMembers', 'examinedHighwayReferences', 'nextExcludedPriority', 'nextExcludedId', 'nextExcludedOrdinal',
    'nodeSpanStartNs', 'nodeSpanEndNs', 'waySpanStartNs', 'waySpanEndNs', 'relationSpanStartNs', 'relationSpanEndNs', 'maxTags',
    'nodeMembers', 'wayMembers', 'relationMembers',
)
assert len(RECEIPT_NAMES) == 53
LIMIT_NAMES = ('scanNodesPerPass', 'scanWaysPerPass', 'scanRelationsPerPass', 'scanObjectVisitsTotal',
               'sourceBytes', 'fallbackFrames', 'references', 'members', 'semanticBytes', 'sourceCodecRows', 'sourceCodecCalls', 'checkpointInterval')
TRACE_HEAD = struct.Struct('<QQQQI')
XY = struct.Struct('<qii')
MIB = 1024**2


def strata(shards):
    require(type(shards) is int and 0 < shards <= 766, 'Screen shard count')
    return sorted({k * (shards - 1) // 7 for k in range(8)})


def priority(identity):
    mask = 2**64 - 1
    value = ((identity ^ 0x47504C414E4E4552) + 0x9E3779B97F4A7C15) & mask
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
    return value ^ (value >> 31)


def default_limits(caps, source_bytes=MAX_INPUT):
    return dict(zip(LIMIT_NAMES, [*(caps[k] for k in LIMIT_NAMES[:4]), source_bytes, 65536,
                                 5330986500096, 13305978880, 3713103671940456, 3212458728, 2000000, 65536]))


class BoundedCodec(NativeCodec):
    def __init__(self, *args, calls=100000, **kwargs):
        super().__init__(*args, **kwargs)
        self.call_limit = calls

    def check_call(self):
        require(self.calls < self.call_limit, 'Screen codec call cap')

    def encode(self, rows):
        self.check_call()
        return super().encode(rows)

    def decode(self, *args):
        self.check_call()
        return super().decode(*args)


class NativeScreen:
    def __init__(self, path, sha, *, aggregate_visits=2000000, codec_rows=2000000):
        require(type(aggregate_visits) is int and 0 < aggregate_visits <= 2 * MAX_VISITS, 'Screen aggregate bound')
        self.codec = BoundedCodec(path, sha, row_budget=codec_rows)
        self.artifact_path, self.artifact_sha = str(Path(path).resolve()), sha
        self.library = self.codec.library
        abi = self.library.gp_country_screen_abi
        abi.argtypes = []
        abi.restype = ctypes.c_uint32
        require(abi() == 0x10000, 'Screen C ABI version')
        u64 = ctypes.POINTER(ctypes.c_uint64)
        common = [ctypes.c_char_p, ctypes.c_uint32, u64, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(ctypes.c_int64),
                  ctypes.c_uint32, CALLBACK, ctypes.c_void_p, u64, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32]
        self.frames = self.library.gp_country_screen_frames
        self.frames.argtypes = [ctypes.c_void_p, ctypes.c_uint64, *common]
        self.frames.restype = ctypes.c_int
        self.pbf = self.library.gp_country_screen_pbf
        self.pbf.argtypes = [ctypes.c_char_p, *common]
        self.pbf.restype = ctypes.c_int
        self.aggregate_limit, self.visits = aggregate_visits, 0
        self.active, self.last, self.source_codec_rows, self.source_codec_calls = False, None, 0, 0

    def _run(self, function, args, snapshot, caps, *, proof=False, selected=(), on_record=None, on_block=None,
             on_trace=None, on_witness=None, check=lambda: None, fallback=True, limits=None):
        require(not self.active, 'Screen reentrant scan')
        require(isinstance(snapshot, str) and len(snapshot) == 20 and snapshot.isascii() and '\0' not in snapshot, 'Screen snapshot boundary')
        element = caps['singleNormalizedElementBytes']
        require(type(element) is int and 0 < element <= MIB, 'Screen element cap')
        values = default_limits(caps) if limits is None else dict(limits)
        require(set(values) == set(LIMIT_NAMES) and all(type(v) is int and 0 < v < 2**64 for v in values.values()), 'Screen limit schema')
        remaining = self.aggregate_limit - self.visits
        require(remaining > 0, 'Screen aggregate exhausted')
        for name in LIMIT_NAMES[:4]:
            values[name] = min(values[name], remaining)
        values['sourceCodecRows'] = min(values['sourceCodecRows'], 2*remaining)
        values['sourceCodecCalls'] = min(values['sourceCodecCalls'], 2*remaining)
        require(len(selected) <= 250000 and all(type(v) is int and 0 < v < 2**63 and (i == 0 or v > selected[i-1]) for i, v in enumerate(selected)), 'Screen witness ID order')
        native_limits = (ctypes.c_uint64 * len(LIMIT_NAMES))(*(values[k] for k in LIMIT_NAMES))
        ids = (ctypes.c_int64 * len(selected))(*selected)
        receipt = (ctypes.c_uint64 * len(RECEIPT_NAMES))()
        error = ctypes.create_string_buffer(512)
        hashed = hashlib.sha256(SEAL_PREFIX)
        events = [0] * 7
        failure = []
        fallback_sizes = []
        witness_cursor = 0

        def callback(user, event, pointer, size):
            nonlocal witness_cursor
            try:
                require(event < 7 and size <= MAX_FRAME and (size == 0 or pointer), 'Screen callback frame')
                check()
                body = ctypes.string_at(pointer, size) if size else b''
                events[event] += 1
                if event == 0:
                    require(0 < size <= MIB, 'Screen semantic batch cap')
                    hashed.update(body)
                elif event == 1:
                    require(fallback and len(fallback_sizes) < values['fallbackFrames'], 'Screen canonical fallback unavailable/cap')
                    length = len(canonical(decode_frame(body)))
                    fallback_sizes.append(length)
                    require(length <= element, 'Screen exact canonical byte cap')
                elif event == 2:
                    require(proof, 'Screen unexpected ordinary projection')
                    if on_record is not None:
                        on_record(decode_frame(body))
                elif event == 3:
                    require(BLOCK_EVENT.size + 8 <= size <= BLOCK_EVENT.size + MAX_PAYLOAD, 'Screen block event cap')
                    if on_block is not None:
                        on_block(body)
                elif event == 4:
                    require(not body, 'Screen checkpoint body')
                elif event == 5:
                    require(TRACE_HEAD.size <= size <= TRACE_HEAD.size + 1024 * 8, 'Screen trace event cap')
                    identity, version, ordinal, rank, count = TRACE_HEAD.unpack_from(body)
                    require(2 <= count <= 1024 and size == TRACE_HEAD.size + 8 * count and events[5] <= 128, 'Screen trace shape')
                    refs = list(struct.unpack_from('<' + 'q' * count, body, TRACE_HEAD.size))
                    require(0 < identity < 2**63 and version > 0 and rank == priority(identity) and all(v > 0 for v in refs), 'Screen trace fields')
                    if on_trace is not None:
                        on_trace({'wayID': identity, 'version': version, 'sourceWayOrdinal': ordinal, 'priority': rank, 'references': refs})
                else:
                    require(0 < size <= ROWS * XY.size and size % XY.size == 0, 'Screen witness frame size')
                    for identity, x, y in XY.iter_unpack(body):
                        require(witness_cursor < len(selected) and identity == selected[witness_cursor], 'Screen witness source order')
                        require(-1800000000 <= x <= 1800000000 and -900000000 <= y <= 900000000, 'Screen witness XY')
                        witness_cursor += 1
                    if on_witness is not None:
                        on_witness(body)
                return 0
            except BaseException as exc:
                failure.append(exc)
                return -1

        handle = CALLBACK(callback)
        self.active, self._receipt, completed = True, receipt, False
        try:
            check()
            code = function(*args, snapshot.encode('ascii'), element, native_limits, len(LIMIT_NAMES), int(proof), ids, len(selected), handle, None,
                            receipt, len(RECEIPT_NAMES), error, len(error))
            check()
            completed = code == 0
        finally:
            self.active = False
            self.visits += receipt[3]
            self.source_codec_rows += receipt[27] + receipt[28]
            self.source_codec_calls += receipt[29]
            self.last = dict(zip(RECEIPT_NAMES, map(int, receipt)))
            self.last.update(counts={k: int(receipt[i]) for i, k in enumerate(KINDS) if receipt[i]},
                             nativeEof=bool(receipt[4]) and completed and not failure,
                             semanticSha256=hashed.hexdigest(), semanticFormat='geo-planner-projected-fields-v1',
                             error=error.value.decode('ascii'), pythonProjectionFrames=events[2], callbackEvents=events,
                             canonicalFallbackExactSizes=fallback_sizes,
                             semanticScope='Complete only on success; failure digest covers delivered batches only')
        if failure:
            raise failure[0]
        require(code == 0 and self.last['nativeEof'], 'Native screen stopped: ' + self.last['error'])
        try:
            require(self.visits <= self.aggregate_limit, 'Screen aggregate received count')
            require(self.source_codec_rows <= 2 * self.aggregate_limit and self.source_codec_calls <= 2000000, 'Screen aggregate source codec cap')
            require(receipt[5] == events[1] and receipt[6] == events[3] and receipt[8] == events[2] and receipt[9] == events[4]
                    and receipt[34] == events[5] and receipt[36] == witness_cursor == len(selected), 'Screen callback accounting')
        except BaseException:
            self.last['nativeEof'] = False
            raise
        return deepcopy(self.last)

    def progress(self):
        r = self._receipt if self.active else None
        return {'counts': {k: int(r[i]) for i, k in enumerate(KINDS) if r[i]}, 'visits': int(r[3])} if r is not None else {'counts': {}, 'visits': 0}

    def validate_frames(self, raw, snapshot, caps, **options):
        require(not self.active, 'Screen reentrant scan')
        self.last = None
        require(isinstance(raw, bytes) and len(raw) <= MAX_INPUT, 'Screen frame input cap')
        return self._run(self.frames, [ctypes.create_string_buffer(raw), len(raw)], snapshot, caps, **options)

    def scan(self, path, snapshot, caps, *, source=None, **options):
        require(not self.active, 'Screen reentrant scan')
        self.last = None
        path = Path(path)
        bound = MAX_INPUT if source is None else source['bytes']
        require(type(bound) is int and 0 < bound <= SOURCE_BYTES, 'Screen source byte binding')
        require(not path.is_symlink() and path.is_file() and path.stat().st_size <= bound, 'Screen source type/size')
        if source is not None:
            require(path.stat().st_size == bound, 'Screen exact source length')
        check = options.get('check', lambda: None)
        before = stat_key(path)
        began = time.monotonic()
        identity = framing(path, caps, snapshot, check)
        framing_seconds = time.monotonic() - began
        if source is not None:
            require(identity['sourceSha256'] == source['sha256'] and identity['sourceMd5'] == source['md5'], 'Screen source identity')
        limits = options.pop('limits', default_limits(caps, bound))
        require(limits['sourceBytes'] == bound, 'Screen native source bound')
        try:
            start = time.monotonic()
            result = self._run(self.pbf, [os.fsencode(path)], snapshot, caps, limits=limits, **options)
            loop_seconds = time.monotonic() - start
            start = time.monotonic()
            sha = hashlib.sha256()
            read = 0
            with path.open('rb') as stream:
                while body := stream.read(MIB):
                    check()
                    sha.update(body)
                    read += len(body)
                    require(read <= bound, 'Screen posthash byte bound')
            require(read == before[2] and sha.hexdigest() == identity['sourceSha256'] and stat_key(path) == before, 'Screen post-scan source drift')
            result.update(sourceIdentity=identity, framingSeconds=framing_seconds, nativeSeconds=loop_seconds,
                          postSourceHashSeconds=time.monotonic()-start, postSourceHashBytes=read,
                          knownGuardReadBytes=identity['framingBytesRead']+read)
            return result
        except BaseException:
            if self.last is not None:
                self.last['nativeEof'] = False
            raise


def owned_usage(root):
    root = Path(root)
    logical = allocated = entries = 0
    for path in [root, *root.rglob('*')]:
        require(not path.is_symlink() and (path.is_file() or path.is_dir()), 'Screen owned file kind')
        entry = path.stat()
        entries += 1
        allocated += entry.st_blocks * 512
        if path.is_file():
            require(entry.st_nlink == 1, 'Screen owned hardlink')
            logical += entry.st_size
    return {'logicalBytes': logical, 'allocatedBytes': allocated, 'entries': entries,
            'conservativeAllocatedBytes': allocated + entries * 8192 + MIB}


class OwnedStorage(Storage):
    def __init__(self, root, limit=768*MIB, file_limit=64*MIB, entries=1024):
        super().__init__(limit, file_limit)
        self.root, self.owned, self.entry_limit = Path(root).resolve(), {}, entries

    def write(self, path, raw):
        path = Path(path)
        require(path.resolve().is_relative_to(self.root), 'Screen write ownership')
        usage = owned_usage(self.root)
        require(usage['entries'] + 1 <= self.entry_limit and usage['conservativeAllocatedBytes'] + len(raw) <= self.limit, 'Screen allocation/namespace cap')
        super().write(path, raw)
        self.owned[path.resolve()] = len(raw)
        usage = owned_usage(self.root)
        require(usage['conservativeAllocatedBytes'] <= self.limit and usage['entries'] <= self.entry_limit, 'Screen post-write allocation cap')

    def remove(self, path, size):
        path = Path(path)
        require(self.owned.get(path.resolve()) == size and path.resolve().is_relative_to(self.root), 'Screen refuses unowned removal')
        super().remove(path, size)
        del self.owned[path.resolve()]


class Census:
    """Seal all would-be shards, persist only fixed source-ordinal shards.

    Smaller fixture block/shard counts exercise the same byte format in controls;
    the future production recipe must pin rows=4096 and blocks_per_shard=512.
    """
    def __init__(self, root, storage, codec, expected_nodes, *, replacing=None, blocks_per_shard=512, fixture_rows=ROWS,
                 directory_limit=16*MIB, catalog_limit=4*MIB, probe_limit=32*MIB):
        require(0 < blocks_per_shard <= 512 and 0 < fixture_rows <= ROWS and 0 < expected_nodes <= SOURCE_COUNTS[0], 'Screen census shape')
        self.root = Path(root)
        self.root.mkdir()
        self.storage, self.codec = storage, codec
        self.expected_nodes, self.block_rows, self.shard_blocks = expected_nodes, fixture_rows, blocks_per_shard
        count = (expected_nodes + fixture_rows*blocks_per_shard-1)//(fixture_rows*blocks_per_shard)
        self.selected = strata(count)
        self.directory_limit, self.catalog_limit = directory_limit, catalog_limit
        self.mini = EncodedIndex(self.root/'probe', storage, codec=codec, replacing=None if replacing is None else replacing.mini,
                                 blocks_per_shard=blocks_per_shard, index_limit=probe_limit, catalog_limit=catalog_limit)
        self.table, self.body = bytearray(), bytearray()
        self.shards, self.mapping, self.spread = [], [], []
        self.local, self.rows, self.blocks, self.total_bytes, self.last = [], 0, 0, 0, 0
        self.shard_first, self.shard_rows, self.shard_count, self.table_start = 0, 0, 0, 0
        self.finished, self.partial = False, False

    def append(self, event):
        require(not self.finished and not self.partial and BLOCK_EVENT.size+8 <= len(event) <= BLOCK_EVENT.size+MAX_PAYLOAD, 'Screen census event/state')
        count, first, last, size = BLOCK_EVENT.unpack_from(event)
        payload = event[BLOCK_EVENT.size:]
        require(0 < count <= self.block_rows and self.last < first <= last < 2**63 and size == len(payload), 'Screen census block fields')
        require(self.rows + count <= self.expected_nodes, 'Screen census row cap')
        self.partial = count < self.block_rows
        raw = BLOCK.pack(b'GPDB', 1, 0, count, first, last, size, 0, hashlib.sha256(payload).digest()) + payload
        require(len(self.table)+ENTRY.size+DIRECTORY.size <= self.directory_limit, 'Screen global directory cap')
        source_shard = len(self.shards)
        entry = ENTRY.pack(last, SHARD.size+len(self.body), len(raw), count, 0, source_shard, 0)
        if not self.shard_count:
            self.shard_first = first
        if source_shard in self.selected:
            self.codec.check_call()
            self.mini.append_encoded(event, self.codec)
            self.spread.append((self.shard_count, source_shard, first))
            if source_shard == self.selected[0] and len(self.local) < 1024:
                self.local.extend(row[0] for row in ReferenceCodec().decode(payload, count, first, last)[:1024-len(self.local)])
        self.table.extend(entry)
        self.body.extend(raw)
        require(len(self.body)+SHARD.size <= 35679872, 'Screen global shard buffer cap')
        self.rows += count
        self.blocks += 1
        self.last = last
        self.shard_rows += count
        self.shard_count += 1
        if self.shard_count == self.shard_blocks:
            self.flush()

    def flush(self):
        if not self.shard_count:
            return
        number = len(self.shards)
        table = bytes(self.table[self.table_start:])
        header = SHARD.pack(b'GPSHARD1', 1, 0, number, self.shard_count, 0, self.shard_rows, self.shard_first, self.last,
                            len(self.body), hashlib.sha256(self.body).digest(), hashlib.sha256(table).digest(), 0)
        digest = hashlib.sha256(header)
        digest.update(self.body)
        descriptor = {'first': self.shard_first, 'last': self.last, 'rows': self.shard_rows, 'blocks': self.shard_count,
                      'bytes': len(header)+len(self.body), 'sha256': digest.hexdigest()}
        self.shards.append(descriptor)
        if number in self.selected:
            self.mini.flush_shard()
            self.mapping.append({'source': number, 'mini': len(self.mapping), 'sourceDescriptor': descriptor,
                                 'miniDescriptor': self.mini.shards[-1]})
        self.total_bytes += descriptor['bytes']
        self.body.clear()
        self.table_start = len(self.table)
        self.shard_count = self.shard_rows = 0
        require(len(canonical(self.shards)) <= self.catalog_limit, 'Screen global catalog cap')

    def finish(self):
        require(not self.finished and self.rows == self.expected_nodes, 'Screen census incomplete nodes')
        self.flush()
        directory = DIRECTORY.pack(b'GPDIR1\0\0', 1, 0, ENTRY.size, self.blocks, self.rows, len(self.shards),
                                   hashlib.sha256(self.table).digest(), hashlib.sha256(canonical(self.shards)).digest(), b'\0'*24)+self.table
        manifest = {'format': FORMAT, 'rows': self.rows, 'blocks': self.blocks,
                    'directory': {'bytes': len(directory), 'sha256': hashlib.sha256(directory).hexdigest()}, 'shards': self.shards}
        raw = canonical(manifest)+b'\n'
        require(len(directory) <= self.directory_limit and len(raw) <= self.catalog_limit, 'Screen final global sidecar caps')
        self.storage.write(self.root/'global-directory.bin', directory)
        self.storage.write(self.root/'global-catalog.json', raw)
        self.mini.finish()
        self.total_bytes += len(directory)+len(raw)
        self.manifest, self.finished = manifest, True
        self.table.clear()
        return {'globalManifest': manifest, 'logicalWholeIndexBytes': self.total_bytes, 'mapping': self.mapping,
                'probeBytes': self.mini.generated_bytes, 'probeRows': self.mini.count}

    def cohorts(self, trace):
        require(self.finished, 'Screen queries before census EOF')
        spread = [row[2] for row in sorted(self.spread)]
        refs = [ref for row in trace for ref in row['references']]
        require(len(refs) <= 131072, 'Screen trace occurrence cap')
        return [list(reversed(self.local))+self.local[:128], spread+spread[:128], refs]


class ProbeReader(Reader):
    """Instrument the frozen full-shard policy without replacing its checks."""
    def __init__(self, *args, read_limit=4*1024**3, **kwargs):
        self.read_limit = read_limit
        self.hits = self.misses = self.evictions = self.catalog_bytes = 0
        self.hash_seconds = self.decode_seconds = 0.
        super().__init__(*args, **kwargs)

    def verify_catalogs(self):
        result = super().verify_catalogs()
        self.catalog_bytes += (self.root/'index.json').stat().st_size + len(self.directory)
        return result

    def snapshot(self, shard):
        charge = self.manifest['shards'][shard]['bytes']*(1 if shard in self.format_verified else 2)
        require(self.loaded_bytes+charge <= self.read_limit, 'Screen authenticated shard IO cap')
        start = time.monotonic()
        result = super().snapshot(shard)
        self.hash_seconds += time.monotonic()-start
        return result

    def from_snapshot(self, number, raw):
        hit = number in self.cache
        self.hits += int(hit)
        self.misses += int(not hit)
        self.evictions += int(not hit and len(self.cache) == self.cache_limit)
        start = time.monotonic()
        result = super().from_snapshot(number, raw)
        self.decode_seconds += time.monotonic()-start
        return result


def resource_metrics(cgroup=Path('/sys/fs/cgroup')):
    required = ('memory.current', 'memory.peak', 'memory.events', 'cpu.stat', 'memory.max', 'memory.swap.max')
    require(all((cgroup/name).is_file() for name in required), 'Screen required cgroup metrics unavailable')
    values = {name: (cgroup/name).read_text().strip() for name in required}
    require(int(values['memory.max']) == 4*1024**3 and int(values['memory.swap.max']) == 0, 'Screen cgroup limits')
    values['processIo'] = Path('/proc/self/io').read_text()
    return values


def lookup(probe, codec, cohorts, witnesses, *, check=lambda: None, seconds=300, read_limit=64*MIB):
    expected = {identity: (x, y) for identity, x, y in XY.iter_unpack(witnesses)}
    require(len(witnesses) <= 8*MIB and len(expected)*XY.size == len(witnesses), 'Screen witness uniqueness/size')
    reader = ProbeReader(probe, codec, index_limit=384*MIB, catalog_limit=4*MIB, read_limit=read_limit)
    began = time.monotonic()
    watchdog = start_watchdog(seconds)
    results = []
    try:
        for name, queries in zip(('local', 'spread', 'way-refs'), cohorts):
            require(len(queries) <= 131072, 'Screen lookup occurrence cap')
            reader.cache.clear()
            reader.format_verified.clear()
            for kind in ('cold-application', 'warm', 'repeat'):
                before = (reader.loaded_bytes, reader.hits, reader.misses, reader.evictions, reader.catalog_bytes, codec.calls, codec.decoded_rows)
                start = time.monotonic()
                digest = hashlib.sha256()
                for offset in range(0, len(queries), 65536):
                    check()
                    require(time.monotonic()-began < seconds, 'Screen lookup deadline')
                    batch = queries[offset:offset+65536]
                    actual = reader.points(batch)
                    for identity, point in zip(batch, actual):
                        require(identity in expected, 'Screen missing source witness')
                        x, y = expected[identity]
                        bits = struct.pack('<dd', x/10000000, y/10000000)
                        require(bits == struct.pack('<dd', *point), 'Screen source/index coordinate bits')
                        digest.update(bits)
                results.append({'cohort': name, 'kind': kind, 'seconds': time.monotonic()-start, 'occurrences': len(queries),
                                'uniqueIds': len(set(queries)), 'batches': (len(queries)+65535)//65536,
                                'authenticatedShardBytes': reader.loaded_bytes-before[0], 'hits': reader.hits-before[1],
                                'misses': reader.misses-before[2], 'evictions': reader.evictions-before[3], 'catalogBytes': reader.catalog_bytes-before[4],
                                'codecCalls': codec.calls-before[5], 'decodedRows': codec.decoded_rows-before[6], 'coordinateBitsSha256': digest.hexdigest()})
        return {'runs': results, 'authenticatedShardBytes': reader.loaded_bytes, 'hashAndFormatSeconds': reader.hash_seconds,
                'blockDecodeSeconds': reader.decode_seconds, 'seconds': time.monotonic()-began,
                'cacheScope': 'Application cache only; OS cache uncontrolled'}
    finally:
        reader.close()
        if watchdog.poll() is None:
            watchdog.terminate()
        watchdog.wait(timeout=5)


def audit_probe(probe, *, check=lambda: None):
    class Recorder(ReferenceCodec):
        def __init__(self):
            self.rows, self.digest = 0, hashlib.sha256()

        def decode(self, *args):
            values = super().decode(*args)
            for row in values:
                self.digest.update(XY.pack(*row))
            self.rows += len(values)
            return values

    codec = Recorder()
    reader = Reader(probe, codec, index_limit=384*MIB, catalog_limit=4*MIB)
    try:
        reader.verify_catalogs()
        for number in range(len(reader.manifest['shards'])):
            check()
            reader.validate_shard(number)
        reader.verify_catalogs()
        require(codec.rows == reader.manifest['rows'], 'Screen independent probe row count')
        return {'rows': codec.rows, 'idXYRowsSha256': codec.digest.hexdigest(), 'shardBytesRead': reader.loaded_bytes,
                'scope': 'Independent frozen Python payload decoder and full format/checksum audit, not a second national metadata oracle'}
    finally:
        reader.close()


def run_pair(path, counts, caps, snapshot, root, engine, source, *, check=lambda: None,
             pass_seconds=60, lookup_seconds=60, minimum_ways=64, before_second=lambda: None,
             probe_limit=32*MIB, lookup_rows=2000000, lookup_io=64*MIB):
    """Shared bounded pipeline. Execution requires a separately frozen runner recipe."""
    root = Path(root)
    root.mkdir()
    storage = OwnedStorage(root)
    passes, trace, witness = [], [], bytearray()
    first = second = None
    began = time.monotonic()
    try:
        selected = []
        cohorts = None
        for number in range(2):
            if number:
                before_second()
            folder = root/('pass-a' if number == 0 else 'pass-b')
            census = Census(folder, storage, engine.codec, counts['node'], replacing=first, probe_limit=probe_limit)
            if number == 0:
                first = census
            else:
                second = census
            trace = []
            witness = bytearray()

            def receive_trace(row):
                trace.append(row)
                require(len(canonical(trace)) <= 4*MIB, 'Screen trace JSON cap')

            def receive_witness(raw):
                require(len(witness)+len(raw) <= 8*MIB, 'Screen witness byte cap')
                witness.extend(raw)

            watchdog = start_watchdog(pass_seconds)
            start = time.monotonic()
            try:
                def phase_check():
                    check()
                    require(time.monotonic()-start < pass_seconds, 'Screen protected pass deadline')
                receipt = engine.scan(path, snapshot, caps, source=source, selected=selected, check=phase_check,
                                      on_block=census.append, on_trace=receive_trace, on_witness=receive_witness)
                require({k: receipt['counts'].get(k, 0) for k in KINDS} == {k: counts.get(k, 0) for k in KINDS}, 'Screen exact per-type EOF counts')
                summary = census.finish()
                require(receipt['blocks'] == census.blocks and receipt['projectedFrames'] == 0, 'Screen summary suppression/block count')
                require(len(trace) == receipt['traceWays'] and len(trace) >= minimum_ways, 'Screen insufficient eligible highway trace')
                order = [(r['priority'], r['wayID'], r['sourceWayOrdinal']) for r in trace]
                require(order == sorted(order) and len(set(order)) == len(order), 'Screen trace order/duplicates')
                storage.write(folder/'way-trace.json', canonical(trace)+b'\n')
                if number:
                    storage.write(folder/'source-witness.bin', witness)
                phase_check()
                summary.update(receipt=receipt, protectedSeconds=time.monotonic()-start)
                storage.write(folder/'summary.json', canonical(summary)+b'\n')
                passes.append(summary)
                if number == 0:
                    cohorts = census.cohorts(trace)
                    selected = sorted(set(identity for cohort in cohorts for identity in cohort))
                    require(len(selected) <= 136146, 'Screen query witness ID cap')
                else:
                    require(cohorts == census.cohorts(trace), 'Screen trace/query pass drift')
                    require(passes[0]['globalManifest'] == summary['globalManifest'] and passes[0]['mapping'] == summary['mapping'], 'Screen census/replacement drift')
                    invariant = [n for n in RECEIPT_NAMES if 'Span' not in n and n != 'witnessRows']
                    require(all(passes[0]['receipt'][n] == receipt[n] for n in invariant), 'Screen native count/metadata pass drift')
                    require(passes[0]['receipt']['semanticSha256'] == receipt['semanticSha256'], 'Screen whole-field semantic drift')
            finally:
                if watchdog.poll() is None:
                    watchdog.terminate()
                watchdog.wait(timeout=5)
        codec = BoundedCodec(engine.artifact_path, engine.artifact_sha,
                             row_budget=lookup_rows, calls=100000)
        actual_lookup = lookup(second.mini.root, codec, cohorts, witness, check=check, seconds=lookup_seconds, read_limit=lookup_io)
        independent = audit_probe(second.mini.root, check=check)
        storage.write(root/'lookup.json', canonical(actual_lookup)+b'\n')
        storage.write(root/'reference-audit.json', canonical(independent)+b'\n')
        result = {'status': 'passed_bounded_country_screen_pipeline', 'passes': passes, 'lookup': actual_lookup,
                  'referenceAudit': independent, 'ownedStorage': owned_usage(root), 'trackedStoragePeakBytes': storage.peak,
                  'objectReceipts': sum(p['receipt']['visits'] for p in passes), 'seconds': time.monotonic()-began,
                  'nationalPhysicalIndexAllocated': False, 'wholeRoadExtractionQualified': False, 'modelChanged': False}
        storage.write(root/'result.json', canonical(result)+b'\n')
        return result
    except BaseException as error:
        # The root is new and exclusively owned. Failed material is retained as untrusted.
        body = {'status': 'stopped', 'error': str(error)[:1000], 'errorType': type(error).__name__, 'eof': False,
                'indexesTrusted': False, 'completedPasses': len(passes), 'lastNativeReceipt': engine.last, 'objectReceipts': engine.visits}
        if not (root/'partial-result.json').exists():
            storage.write(root/'partial-result.json', canonical(body)+b'\n')
        raise
    finally:
        for census in (first, second):
            if census is not None:
                census.mini.close()
