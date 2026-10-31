"""V7 bounded two-million selected-ID extraction bridge and whole-source bridge and execution accounting; V1 evidence remains frozen."""
from array import array
from copy import deepcopy
import ctypes
import hashlib
import os
from pathlib import Path
import struct
import time

from coarse_osm_bulk_pbf import framing, stat_key
from coarse_osm_projector_v1 import BLOCK_EVENT, CALLBACK, KINDS, MAX_INPUT, SEAL_PREFIX
from coarse_osm_country_wire_v4 import MAX_FRAME, decode_frame
from coarse_osm_delta_v1 import ROWS, MAX_PAYLOAD
from coarse_osm_records import canonical, utc
from coarse_timing_input import require, start_watchdog
from coarse_osm_country_screen_v1 import (SOURCE_COUNTS, SOURCE_BYTES, MAX_VISITS, LIMIT_NAMES,
    BoundedCodec, Census, OwnedStorage, XY, MIB, default_limits, priority, owned_usage, lookup, audit_probe, resource_metrics)

from coarse_osm_country_screen_v1 import RECEIPT_NAMES as BASE_RECEIPTS
RECEIPT_NAMES = (*BASE_RECEIPTS, 'batchWays', 'batchReferences', 'wayBatches')
BATCH_HEAD = struct.Struct('<4sIII')

def decode_way_batch(body, *, scope="probe"):
    require(scope in ("probe","all"),"Way batch selection scope")
    require(isinstance(body,bytes) and BATCH_HEAD.size<=len(body)<=MAX_FRAME,'Way batch byte bound')
    magic,count,references,size=BATCH_HEAD.unpack_from(body)
    require(magic==b'GWB1' and 0<count<=32768 and 2*count<=references<=65536 and size==len(body)-BATCH_HEAD.size,'Way batch header')
    position=BATCH_HEAD.size;rows=[];refs=0;previous=0
    for _ in range(count):
        require(position+4<=len(body),'Way batch truncated length')
        size=struct.unpack_from('<I',body,position)[0];position+=4
        require(0<size<=len(body)-position,'Way batch frame length')
        row=decode_frame(body[position:position+size]);position+=size
        require(row['type']=='way' and 'highway' in row['tags'] and previous<row['id'] and 2<=len(row['nodes'])<=(1024 if scope=='probe' else 65536),'Way batch selected object')
        require(scope!='all' or row['tags']['highway'],'Extraction nonempty highway class')
        previous=row['id'];refs+=len(row['nodes']);rows.append(row)
    require(position==len(body) and refs==references,'Way batch closure')
    return rows

META = struct.Struct('<I7Q20s20s')
TRACE_HEAD = struct.Struct('<QQQQI')

class NativeScreen:
    def __init__(self, path, sha, *, aggregate_visits=2000000, codec_rows=2000000, codec_calls=100000, aggregate_caps=None):
        require(type(aggregate_visits) is int and 0 < aggregate_visits <= 2 * MAX_VISITS, 'Screen aggregate bound')
        require(type(codec_calls) is int and 0<codec_calls<=100000000,'Extraction codec call bound')
        self.codec = BoundedCodec(path, sha, row_budget=codec_rows, calls=codec_calls)
        self.artifact_path, self.artifact_sha = str(Path(path).resolve()), sha
        self.library = self.codec.library
        abi = self.library.gp_country_screen_abi
        abi.argtypes = []
        abi.restype = ctypes.c_uint32
        require(abi() == 0x60000, 'Screen V7 C ABI version')
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
        defaults = {'sourceCodecRows': 2*aggregate_visits, 'sourceCodecCalls': 2000000, 'references': 2*5330986500096,
                    'members': 2*13305978880, 'semanticBytes': 2*3713103671940456, 'fallbackFrames': 131072}
        aggregate_caps = {} if aggregate_caps is None else aggregate_caps
        require(set(aggregate_caps) <= set(defaults), 'Screen aggregate budget keys')
        require(all(type(v) is int and 0 < v <= defaults[k] for k, v in aggregate_caps.items()), 'Screen aggregate budget values')
        self.aggregate_caps = defaults | aggregate_caps
        self.totals = dict.fromkeys(defaults, 0)

    def _run(self, function, args, snapshot, caps, *, proof=False, selected=(), on_record=None, on_block=None,
             on_trace=None, on_witness=None, on_way_batch=None, batch_caps=None, batch_scope="probe", check=lambda: None, fallback=True, limits=None):
        require(not self.active, 'Screen reentrant scan')
        require(isinstance(snapshot, str) and len(snapshot) == 20 and snapshot.isascii() and '\0' not in snapshot, 'Screen snapshot boundary')
        element = caps['singleNormalizedElementBytes']
        require(type(element) is int and 0 < element <= 4*MIB, 'Screen element cap')
        values = default_limits(caps) if limits is None else dict(limits)
        require(set(values) == set(LIMIT_NAMES) and all(type(v) is int and 0 < v < 2**64 for v in values.values()), 'Screen limit schema')
        remaining = self.aggregate_limit - self.visits
        require(remaining > 0, 'Screen aggregate exhausted')
        for name in LIMIT_NAMES[:4]:
            values[name] = min(values[name], remaining)
        values['sourceCodecRows'] = min(values['sourceCodecRows'], 2*remaining)
        values['sourceCodecCalls'] = min(values['sourceCodecCalls'], 2*remaining)
        for name, cap in self.aggregate_caps.items():
            left = cap-self.totals[name]
            require(left > 0, 'Screen aggregate '+name+' exhausted before native call')
            values[name] = min(values[name], left)
        require(len(selected) <= 2000000 and all(type(v) is int and 0 < v < 2**63 and (i == 0 or v > selected[i-1]) for i, v in enumerate(selected)), 'Screen witness ID order')
        require(on_way_batch is None or callable(on_way_batch) and not proof, 'Way batch callback/proof mode')
        require(batch_scope in ('probe','all') and (batch_scope!='all' or on_way_batch is not None),'Way batch scope/callback')
        batch_caps = {'ways':2000000,'references':8000000,'batches':2048} if batch_caps is None else dict(batch_caps)
        require(set(batch_caps)=={'ways','references','batches'} and all(type(n) is int and 0<n<=bound for n,bound in zip((batch_caps['ways'],batch_caps['references'],batch_caps['batches']),(162688797,5330986500096,1000000))),'Way batch aggregate budget')
        native_limits = (ctypes.c_uint64 * len(LIMIT_NAMES))(*(values[k] for k in LIMIT_NAMES))
        packed_ids=array('q',selected)
        require(packed_ids.itemsize==8,'Screen selected-ID word width')
        ids=(ctypes.c_int64*len(selected)).from_buffer_copy(packed_ids)
        receipt = (ctypes.c_uint64 * len(RECEIPT_NAMES))()
        error = ctypes.create_string_buffer(512)
        hashed = hashlib.sha256(SEAL_PREFIX)
        events = [0] * 9
        metadata = {}
        failure = []
        fallback_sizes = []
        witness_cursor = 0
        batch_ways = batch_refs = last_way = 0
        projected_nodes = projected_restrictions = 0

        def callback(user, event, pointer, size):
            nonlocal witness_cursor,batch_ways,batch_refs,last_way,projected_nodes,projected_restrictions
            try:
                require(event < 9 and size <= MAX_FRAME and (size == 0 or pointer), 'Screen callback frame')
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
                    require(proof or batch_scope=='all', 'Screen unexpected ordinary projection')
                    row=decode_frame(body)
                    if not proof:
                        if row['type']=='node':
                            require(projected_nodes<len(selected) and row['id']==selected[projected_nodes],'Extraction selected-node field order')
                            projected_nodes+=1
                        else:
                            require(row['type']=='relation' and row['tags'].get('type')=='restriction','Extraction restriction field kind')
                            projected_restrictions+=1
                    if on_record is not None:on_record(row)
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
                elif event == 6:
                    require(0 < size <= ROWS * XY.size and size % XY.size == 0, 'Screen witness frame size')
                    for identity, x, y in XY.iter_unpack(body):
                        require(witness_cursor < len(selected) and identity == selected[witness_cursor], 'Screen witness source order')
                        require(-1800000000 <= x <= 1800000000 and -900000000 <= y <= 900000000, 'Screen witness XY')
                        witness_cursor += 1
                    if on_witness is not None:
                        on_witness(body)
                elif event == 7:
                    require(size == META.size and len(metadata) < 3, 'Screen per-type summary frame')
                    kind, count, tag_bytes, tags, version, copied, refs, members, low, high = META.unpack(body)
                    require(kind < 3 and KINDS[kind] not in metadata and count > 0, 'Screen per-type summary identity')
                    low, high = low.decode('ascii'), high.decode('ascii')
                    require(utc(low) <= utc(high) <= utc(snapshot), 'Screen per-type summary timestamps')
                    require(max(tag_bytes, tags, copied, refs, members) <= 4*MIB and 0 < version < 2**63, 'Screen per-type summary bounds')
                    metadata[KINDS[kind]] = dict(count=count, minTimestamp=low, maxTimestamp=high, maxTagUtf8Bytes=tag_bytes,
                                                 maxTags=tags, maxVersion=version, maxCopyBytes=copied, maxReferences=refs, maxMembers=members)
                else:
                    require(on_way_batch is not None,'Unexpected way batch')
                    rows=decode_way_batch(body,scope=batch_scope);count=len(rows);refs=sum(len(row['nodes']) for row in rows)
                    require(last_way<rows[0]['id'],'Way batch cross-frame order')
                    batch_ways+=count;batch_refs+=refs;last_way=rows[-1]['id']
                    require(batch_ways<=batch_caps['ways'] and batch_refs<=batch_caps['references'] and events[8]<=batch_caps['batches'],'Way batch aggregate cap')
                    on_way_batch(rows)
                return 0
            except BaseException as exc:
                failure.append(exc)
                return -1

        handle = CALLBACK(callback)
        self.active, self._receipt, completed = True, receipt, False
        try:
            check()
            code = function(*args, snapshot.encode('ascii'), element, native_limits, len(LIMIT_NAMES), (3 if batch_scope=='all' else 2) if on_way_batch is not None else int(proof), ids, len(selected), handle, None,
                            receipt, len(RECEIPT_NAMES), error, len(error))
            check()
            completed = code == 0
        finally:
            self.active = False
            self.visits += receipt[3]
            self.source_codec_rows += receipt[27] + receipt[28]
            self.source_codec_calls += receipt[29]
            charged = {'sourceCodecRows': receipt[27]+receipt[28], 'sourceCodecCalls': receipt[29],
                       'references': receipt[16], 'members': receipt[17], 'semanticBytes': receipt[7], 'fallbackFrames': receipt[5]}
            for name, amount in charged.items():self.totals[name] += amount
            self.last = dict(zip(RECEIPT_NAMES, map(int, receipt)))
            self.last.update(counts={k: int(receipt[i]) for i, k in enumerate(KINDS) if receipt[i]},
                             nativeEof=bool(receipt[4]) and completed and not failure,
                             semanticSha256=hashed.hexdigest(), semanticFormat='geo-planner-projected-fields-v1',
                             error=error.value.decode('ascii'), pythonProjectionFrames=events[2], callbackEvents=events,
                             canonicalFallbackExactSizes=fallback_sizes, metadata=metadata,
                             deliveredBatchWays=batch_ways, deliveredBatchReferences=batch_refs,
                             selectedNodeProjections=projected_nodes, restrictionProjections=projected_restrictions,
                             semanticScope='Complete only on success; failure digest covers delivered batches only')
        if failure:
            raise failure[0]
        require(code == 0 and self.last['nativeEof'], 'Native screen stopped: ' + self.last['error'])
        try:
            require(self.visits <= self.aggregate_limit, 'Screen aggregate received count')
            require(all(self.totals[k] <= v for k,v in self.aggregate_caps.items()), 'Screen aggregate counter cap')
            require(set(metadata) == {k for i,k in enumerate(KINDS) if receipt[10+i]}, 'Screen missing per-type summary')
            require(all(metadata[k]['count'] == receipt[10+KINDS.index(k)] for k in metadata), 'Screen per-type summary count')
            require(receipt[53]==batch_ways and receipt[54]==batch_refs and receipt[55]==events[8], 'Way batch receipt accounting')
            require(on_way_batch is None or batch_ways==receipt[30 if batch_scope=='all' else 33], 'Way batch eligible completeness')
            require(batch_scope!='all' or projected_nodes==len(selected) and projected_nodes+projected_restrictions==receipt[8],'Extraction selected field completeness')
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

