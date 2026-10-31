"""Generic bounded native-record extraction. No live acquisition on import."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
import time

from coarse_osm_input import absolute_timeout
from coarse_osm_records import canonical, intersects, normalize, positive, utc
from coarse_timing_input import digest, json_bytes, require


ORDER = {'node': 0, 'way': 1, 'relation': 2}


def heap_size(value):
    if isinstance(value, dict): return sys.getsizeof(value) + sum(heap_size(k) + heap_size(v) for k, v in value.items())
    if isinstance(value, (tuple, list, set)): return sys.getsizeof(value) + sum(map(heap_size, value))
    return sys.getsizeof(value)


class Run:
    def __init__(self, root, proposal, clock=time.monotonic, reserved_input_bytes=0):
        self.root = Path(root).resolve(); self.caps = proposal['proposedCaps']; self.clock = clock; self.started = clock(); self.reserved_input_bytes = reserved_input_bytes
        require(type(reserved_input_bytes) is int and reserved_input_bytes >= 0, 'External input reservation')
        require(self.root.is_dir() and not any(self.root.iterdir()), 'Run refuses overwrite')
        self.state = {'status': 'running', 'stage': 'preflight', 'passes': [], 'windows': [{'id': w['id'], 'status': 'unmeasured'} for w in proposal['windows']],
            'sourceFeasibilityQualified': False, 'publisherBoundaryQualified': False, 'sourceAdapterImplemented': False,
            'nativeDecoderQualified': False, 'routingProviderRequests': 0, 'scanObjectVisits': 0, 'extractBytes': 0,
            'retainedElements': 0, 'windowOccurrences': 0, 'hashFramingBytesRead': 0,
            'counterScope': 'Projected native records counted on receipt; decoder failures before projection can leave unknown raw-object counts.'}
        self.memory = self.native_bytes = 0; self.checkpoint()

    def check(self, storage=True):
        require(self.clock() - self.started < self.caps['wallSeconds'], 'Global elapsed cap')
        if storage: require(self.storage() + self.caps['tmpBytes'] + 8388608 <= self.caps['workingBytesIncludingTmp'], 'Working storage cap')

    def storage(self):
        total = 0
        for p in self.root.rglob('*'):
            require(not p.is_symlink(), 'Symlink in owned output')
            if p.is_file(): total += p.stat().st_size
        return total + self.reserved_input_bytes

    def charge(self, amount):
        self.memory += amount; require(self.memory <= self.caps['pythonSelectionStateBytes'], 'Selection heap-accounting cap')

    def save(self, name, value):
        raw = json_bytes(value); require(len(raw) <= 2097152, 'Report/ledger bound')
        self.check(); require(self.storage() + len(raw) + self.caps['tmpBytes'] + 8388608 <= self.caps['workingBytesIncludingTmp'], 'Report storage cap')
        p = self.root / name; require(p.parent == self.root and not p.exists(), 'Report path/reuse')
        with p.open('xb') as stream: stream.write(raw)

    def checkpoint(self):
        self.state['elapsedSeconds'] = self.clock() - self.started
        raw = json_bytes(self.state); require(len(raw) <= 2097152, 'State ledger bound')
        p = self.root / 'state.json.partial'; require(not p.is_symlink(), 'State symlink')
        p.write_bytes(raw); p.replace(self.root / 'state.json')


class Coordinates:
    def __init__(self, path, caps):
        self.path = Path(path); self.caps = caps
        with self.path.open('xb'): pass
        self.db = sqlite3.connect(self.path)
        try:
            settings = {'page_size': caps['sqlitePageBytes'], 'max_page_count': caps['sqliteMaxPagesEach'],
                'cache_size': -(caps['sqliteCacheBytesEach'] // 1024), 'mmap_size': 0, 'temp_store': 2, 'journal_mode': 'OFF'}
            for name, value in settings.items():
                self.db.execute(f'PRAGMA {name}={value}')
                observed = self.db.execute(f'PRAGMA {name}').fetchone()[0]
                require(str(observed).lower() == str(value).lower(), 'SQLite setting not enforced: ' + name)
            require('TEMP_STORE=0' not in {r[0] for r in self.db.execute('PRAGMA compile_options')}, 'SQLite temp-memory override')
            require(caps['sqliteMaxPagesEach'] * caps['sqlitePageBytes'] <= caps['sqliteIndexBytesEach'], 'SQLite index arithmetic')
            self.db.execute('CREATE TABLE nodes(id INTEGER PRIMARY KEY, lon REAL NOT NULL, lat REAL NOT NULL)')
        except BaseException:
            self.db.close(); raise

    def add(self, raw): self.db.execute('INSERT INTO nodes VALUES(?,?,?)', (raw['id'], raw['lon'], raw['lat']))

    def points(self, ids):
        found = {}
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            query = 'SELECT id,lon,lat FROM nodes WHERE id IN (' + ','.join('?' for _ in chunk) + ')'
            found.update((i, [x, y]) for i, x, y in self.db.execute(query, chunk))
        require(all(i in found for i in ids), 'Missing source way-node geometry')
        return [found[i] for i in ids]

    def finish(self):
        self.db.commit(); require(self.db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'Derived index integrity failure')
        require(self.path.stat().st_size <= self.caps['sqliteIndexBytesEach'], 'SQLite file cap')

    def close(self): self.db.close()


def checked_records(reader, run, publisher_state, label):
    counts = Counter(); last = (-1, -1)
    record = {'label': label, 'status': 'running', 'counts': {}}
    run.state['passes'].append(record); run.state['stage'] = label; run.checkpoint()
    for raw in reader():
        run.check(storage=False)
        kind = raw.get('type', 'unknown') if isinstance(raw, dict) else 'unknown'
        counts[kind] += 1; run.state['scanObjectVisits'] += 1; record['counts'] = dict(counts)
        require(isinstance(raw, dict) and len(canonical(raw)) <= run.caps['singleNormalizedElementBytes'], 'Native record size/type')
        kind = raw.get('type'); require(kind in ORDER and positive(raw.get('id')) and positive(raw.get('version')), 'Native identity')
        key = ORDER[kind], raw['id']; require(key > last, 'Duplicate/out-of-order source identity'); last = key
        require(raw.get('visible', True) is True and utc(raw.get('timestamp')) <= utc(publisher_state), 'Native state/deletion drift')
        tags = raw.get('tags')
        require(tags is None or isinstance(tags, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in tags.items()), 'Native tags')
        if kind == 'node': normalize(raw, publisher_state, run.caps['singleNormalizedElementBytes'])
        elif kind == 'way':
            require(isinstance(raw.get('nodes'), list) and len(raw['nodes']) >= 2 and all(positive(i) for i in raw['nodes']), 'Native way references')
        else:
            require(isinstance(raw.get('members'), list), 'Native relation members')
            for m in raw['members']:
                require(isinstance(m, dict) and m.get('type') in ORDER and positive(m.get('ref')) and isinstance(m.get('role'), str), 'Native typed member')
        require(counts[kind] <= run.caps[{'node': 'scanNodesPerPass', 'way': 'scanWaysPerPass', 'relation': 'scanRelationsPerPass'}[kind]], 'Upstream per-pass row cap')
        require(run.state['scanObjectVisits'] <= run.caps['scanObjectVisitsTotal'], 'Upstream visit cap')
        if run.state['scanObjectVisits'] % 128 == 0: run.check(); run.checkpoint()
        yield raw
    run.check(); record['status'] = 'eof'; run.checkpoint()


class Selection:
    def __init__(self, windows, run):
        self.run = run; self.members = {w['id']: set() for w in windows}; self.keys = set(); self.objects = {}; self.ways = {}
        run.charge(heap_size(self.members) + heap_size(self.keys) + heap_size(self.objects) + heap_size(self.ways))
        self.occurrences = 0

    def add(self, window, key):
        if key in self.members[window]: return
        require(self.occurrences < self.run.caps['selectedWindowElementOccurrences'], 'Selected window occurrence cap')
        if key not in self.keys:
            require(len(self.keys) < self.run.caps['selectedUniqueTypedElements'], 'Selected unique element cap')
            before = sys.getsizeof(self.keys); self.keys.add(key)
            self.run.charge(heap_size(key) + sys.getsizeof(self.keys) - before)
        before = sys.getsizeof(self.members[window]); self.members[window].add(key)
        self.run.charge(heap_size(key) + sys.getsizeof(self.members[window]) - before); self.occurrences += 1

    def keep(self, raw):
        value = normalize(raw, self.run.state['publisherStateUtc'], self.run.caps['singleNormalizedElementBytes'])
        key = value['type'], value['id']
        require(key not in self.objects, 'Duplicate retained typed identity')
        size = len(canonical(value)); self.run.native_bytes += size
        require(self.run.native_bytes <= self.run.caps['retainedNativeObjectBytes'], 'Retained native-byte cap')
        before = sys.getsizeof(self.objects); self.objects[key] = deepcopy(value)
        self.run.charge(heap_size((key, value)) + sys.getsizeof(self.objects) - before)


def primary(reader, proposal, run):
    state = proposal['source']['proposedPublisherReplicationStateUtc']; run.state['publisherStateUtc'] = state
    selection = Selection(proposal['windows'], run); index = Coordinates(run.root / 'primary-nodes.sqlite', run.caps)
    try:
        for raw in checked_records(reader, run, state, 'primary-index-selection'):
            if raw['type'] == 'node': index.add(raw)
            elif raw['type'] == 'way' and 'highway' in (raw.get('tags') or {}):
                normalize(raw, state, run.caps['singleNormalizedElementBytes'])
                points = index.points(raw['nodes']); selected = False
                for window in proposal['windows']:
                    if intersects(points, window['bbox']):
                        selected = True; selection.add(window['id'], ('way', raw['id']))
                        for node in raw['nodes']: selection.add(window['id'], ('node', node))
                if selected:
                    value = deepcopy(raw); before = sys.getsizeof(selection.ways); selection.ways[raw['id']] = value
                    run.charge(heap_size((raw['id'], value)) + sys.getsizeof(selection.ways) - before)
        index.finish()
        for raw in checked_records(reader, run, state, 'primary-native-records'):
            key = raw['type'], raw['id']
            if raw['type'] == 'relation' and (raw.get('tags') or {}).get('type') == 'restriction':
                for window, keys in selection.members.items():
                    if any((m['type'], m['ref']) in keys and m['type'] in ('node', 'way') for m in raw['members']): selection.add(window, key)
            if key in selection.keys:
                if raw['type'] == 'node': require(index.points([raw['id']])[0] == [raw['lon'], raw['lat']], 'Node coordinate changed between passes')
                if raw['type'] == 'way': require(raw == selection.ways[raw['id']], 'Way changed between passes')
                selection.keep(raw)
        require(set(selection.objects) == selection.keys, 'Missing selected native records')
        index.finish()
    finally: index.close()
    run.state['windowOccurrences'] = selection.occurrences
    return selection


def records(selection, state):
    for key, element in sorted(selection.objects.items()):
        record = {'publisherStateUtc': state, 'element': element, 'elementSha256': hashlib.sha256(canonical(element)).hexdigest(),
            'windowIds': [w for w, keys in selection.members.items() if key in keys]}
        if element['type'] == 'way':
            nodes = [selection.objects['node', i] for i in element['nodes']]
            record['geometryDependencySha256'] = hashlib.sha256(canonical([state, nodes])).hexdigest()
        yield record


def extract(reader, proposal, root, *, clock=time.monotonic, source_identity=None, alarm=absolute_timeout, reserved_input_bytes=0):
    run = Run(root, proposal, clock, reserved_input_bytes)
    try:
        require(source_identity is not None and source_identity['publisherStateUtc'] == proposal['source']['proposedPublisherReplicationStateUtc'], 'Missing/drifted source identity')
        run.state['sourceIdentity'] = source_identity
        run.state['externalInputReservationBytes'] = reserved_input_bytes
        run.state['hashFramingBytesRead'] = source_identity.get('framingBytesRead', 0)
        with alarm(max(.001, run.caps['wallSeconds'] - (run.clock() - run.started))):
            selection = primary(reader, proposal, run)
            output = run.root / 'elements.jsonl'
            with output.open('xb') as stream:
                for record in records(selection, run.state['publisherStateUtc']):
                    encoded = canonical(record) + b'\n'; run.check()
                    require(len(encoded) <= run.caps['singleNormalizedElementBytes'], 'Single normalized-record cap')
                    require(run.state['extractBytes'] + len(encoded) <= run.caps['normalizedExtractBytes'], 'Normalized extract cap')
                    require(run.storage() + len(encoded) + run.caps['tmpBytes'] + 8388608 <= run.caps['workingBytesIncludingTmp'], 'Extract working-storage cap')
                    stream.write(encoded); stream.flush(); run.state['extractBytes'] += len(encoded); run.state['retainedElements'] += 1
                    run.checkpoint()
            # Audit must reconstruct from reader, not the primary selection or its coordinate DB.
            del selection; run.memory = run.native_bytes = 0
            from coarse_osm_bulk_audit import audit
            audited = audit(reader, proposal, run)
            run.save('audit.json', audited)
            run.state.update(status='extracted_publisher_file_analysis_pending', stage='complete', outputSha256=digest(output), independentAuditComplete=True)
            for window in run.state['windows']: window['status'] = 'complete_from_acquired_file_only'
    except Exception as error:
        run.state.update(status='stopped', errorType=type(error).__name__, error=str(error)[:2000], derivedIndexesTrusted=False,
            independentAuditComplete=False, hardStopCountersMayBePartial=False, rawDecodedObjectCountsMayBePartial=True)
        for window in run.state['windows']: window['status'] = 'unqualified_after_stop'
    run.checkpoint(); return run.state


def extract_pbf(path, proposal, root, *, native_factory=None):
    from coarse_osm_bulk_pbf import framing, native_records, stat_key
    require(Path(root).is_dir() and not any(Path(root).iterdir()), 'PBF output refuses overwrite')
    began = time.monotonic(); path = Path(path); before = stat_key(path)
    try:
        with absolute_timeout(proposal['proposedCaps']['wallSeconds']):
            identity = framing(path, proposal['proposedCaps'], proposal['source']['proposedPublisherReplicationStateUtc'])
        require(before[2] == proposal['source']['listedBodyBytes'] and identity['sourceMd5'] == proposal['source']['publisherMd5'], 'Exact PBF source identity drift')
    except Exception as error:
        root = Path(root)
        with (root / 'preflight-failure.json').open('xb') as output:
            output.write(json_bytes({'status': 'stopped', 'error': str(error)[:2000], 'sourceFeasibilityQualified': False, 'sourcePreserved': True,
                'windows': [{'id': w['id'], 'status': 'unmeasured_after_preflight_stop'} for w in proposal['windows']],
                'rawDecodedObjectCountsMayBePartial': True}))
        raise
    factory = native_records if native_factory is None else native_factory
    def reader():
        require(stat_key(path) == before, 'Immutable PBF file drift')
        yield from factory(path, proposal['proposedCaps']['singleNormalizedElementBytes'])
        require(stat_key(path) == before, 'Immutable PBF file drift')
    # Framing/hash IO belongs to the same wall allowance as decoding, not a fresh data budget.
    identity['nativeDecoderQualified'] = False
    identity['framingElapsedSeconds'] = time.monotonic() - began
    # Use an offset clock so extraction retains the already-spent framing interval.
    class ElapsedClock:
        first = True
        def __call__(self):
            if self.first:
                self.first = False; return began
            return time.monotonic()
    reservation = before[2]
    if native_factory is None:
        reservation += proposal['resourceArithmetic']['storageComponents']['toolArchivesAndInstalledTree'] + proposal['resourceArithmetic']['storageComponents']['metadata']
    return extract(reader, proposal, root, source_identity=identity, clock=ElapsedClock(), reserved_input_bytes=reservation)
