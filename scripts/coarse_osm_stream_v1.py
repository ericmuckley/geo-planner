"""Two-pass extraction prototype and fused native validation; never a launcher."""
from collections import Counter
from copy import deepcopy
from datetime import timezone
import hashlib
from pathlib import Path

from coarse_osm_bulk import Run, Selection, heap_size, records
from coarse_osm_bulk_audit import crossing
from coarse_osm_bulk_pbf import stat_key
from coarse_osm_compact_v1 import Index, Storage, coordinate
from coarse_osm_input import absolute_timeout
from coarse_osm_records import canonical, intersects, normalize, positive, strict_json
from coarse_osm_validation_v4 import checked_records, utc
from coarse_timing_input import digest, require


class NativeValidator:
    def __init__(self, snapshot, limit, caps, consume):
        self.snapshot = utc(snapshot).replace(tzinfo=timezone.utc)
        self.limit, self.caps, self.consume = limit, caps, consume
        self.counts, self.visits, self.last = Counter(), 0, (-1, -1)
        self.eof = False

    def see(self, obj):
        kind = {'n': 'node', 'w': 'way', 'r': 'relation'}[obj.type_str()]
        self.counts[kind] += 1
        self.visits += 1
        key = ('node', 'way', 'relation').index(kind), int(obj.id)
        require(positive(obj.id) and positive(obj.version) and key > self.last, 'Native identity/order')
        self.last = key
        require(self.visits <= self.caps['scanObjectVisitsTotal'] and self.counts[kind] <= self.caps[{'node': 'scanNodesPerPass', 'way': 'scanWaysPerPass', 'relation': 'scanRelationsPerPass'}[kind]], 'Native row/visit cap')
        stamp = obj.timestamp
        require(stamp.microsecond == 0 and stamp.utcoffset() is not None and stamp.utcoffset().total_seconds() == 0, 'Native precision/zone')
        text = stamp.strftime('%Y-%m-%dT%H:%M:%SZ')
        require(len(text) == 20 and stamp <= self.snapshot and obj.visible is True, 'Native snapshot/visibility')
        raw = {'type': kind, 'id': int(obj.id), 'version': int(obj.version), 'timestamp': text, 'visible': True}
        charged, tags = 256, {}
        for tag in obj.tags:
            charged += len(tag.k.encode()) + len(tag.v.encode()) + 64
            require(charged <= self.limit and tag.k not in tags, 'Native tag-copy bound/duplicate')
            tags[str(tag.k)] = str(tag.v)
        raw['tags'] = tags
        if kind == 'node':
            raw.update(lon=float(obj.location.lon), lat=float(obj.location.lat))
            require(coordinate(raw['lon'], 180) == obj.location.x and coordinate(raw['lat'], 90) == obj.location.y, 'Native coordinate exactness')
        elif kind == 'way':
            refs = []
            for node in obj.nodes:
                charged += 32
                require(charged <= self.limit and positive(node.ref), 'Native reference bound/identity')
                refs.append(int(node.ref))
            require(len(refs) >= 2, 'Native short way')
            raw['nodes'] = refs
        else:
            members = []
            for member in obj.members:
                charged += len(member.role.encode()) + 128
                require(charged <= self.limit and member.type in ('n', 'w', 'r') and positive(member.ref), 'Native member bound/identity')
                members.append({'type': {'n': 'node', 'w': 'way', 'r': 'relation'}[member.type], 'ref': int(member.ref), 'role': str(member.role)})
            raw['members'] = members
        line = canonical(raw)
        require(len(line) <= self.limit, 'Native canonical byte cap')
        self.consume(raw, line + b'\n')


def native_scan(path, validator):
    import osmium
    before = stat_key(path)
    class Handler(osmium.SimpleHandler):
        def node(self, obj): validator.see(obj)
        def way(self, obj): validator.see(obj)
        def relation(self, obj): validator.see(obj)
    Handler().apply_file(str(path), locations=False)
    require(before == stat_key(path), 'Native source changed')
    validator.eof = True


class Audit:
    """Source-built membership/objects, separate from primary selection state."""
    def __init__(self, proposal, run):
        self.proposal, self.run = proposal, run
        self.members = {w['id']: set() for w in proposal['windows']}
        self.keys, self.objects = set(), {}
        self.occurrences = self.native_bytes = 0
        run.charge(heap_size((self.members, self.keys, self.objects)))

    def add(self, window, key):
        if key in self.members[window]:
            return
        self.members[window].add(key)
        self.keys.add(key)
        self.occurrences += 1
        self.run.charge(2 * heap_size(key) + 256)
        require(len(self.keys) <= self.run.caps['selectedUniqueTypedElements'] and self.occurrences <= self.run.caps['selectedWindowElementOccurrences'], 'Audit selected caps')

    def keep(self, raw):
        value = normalize(raw, self.proposal['source']['proposedPublisherReplicationStateUtc'], self.run.caps['singleNormalizedElementBytes'])
        key = value['type'], value['id']
        require(key not in self.objects, 'Audit duplicate object')
        self.native_bytes += len(canonical(value))
        require(self.native_bytes <= self.run.caps['retainedNativeObjectBytes'], 'Audit retained bytes')
        self.objects[key] = deepcopy(value)
        self.run.charge(heap_size((key, value)) + 256)

    def way(self, raw, index):
        normalize(raw, self.proposal['source']['proposedPublisherReplicationStateUtc'], self.run.caps['singleNormalizedElementBytes'])
        points = index.points(raw['nodes'])
        for window in self.proposal['windows']:
            if crossing(points, window['bbox']):
                self.add(window['id'], ('way', raw['id']))
                for identity in raw['nodes']:
                    self.add(window['id'], ('node', identity))
        if ('way', raw['id']) in self.keys:
            self.keep(raw)

    def relation(self, raw):
        linked = {(m['type'], m['ref']) for m in raw['members'] if m['type'] in ('node', 'way')}
        for window in self.members:
            if not self.members[window].isdisjoint(linked):
                self.add(window, ('relation', raw['id']))
        if ('relation', raw['id']) in self.keys:
            self.keep(raw)

    def compare(self, path):
        require(set(self.objects) == self.keys, 'Audit missing/extra materialization hints')
        count = total = 0
        snapshot = self.proposal['source']['proposedPublisherReplicationStateUtc']
        with path.open('rb') as stream:
            for key, element in sorted(self.objects.items()):
                expected = {'publisherStateUtc': snapshot, 'element': element, 'elementSha256': hashlib.sha256(canonical(element)).hexdigest(),
                    'windowIds': [w for w in self.members if key in self.members[w]]}
                if key[0] == 'way':
                    nodes = [self.objects['node', i] for i in element['nodes']]
                    expected['geometryDependencySha256'] = hashlib.sha256(canonical([snapshot, nodes])).hexdigest()
                line = stream.readline(self.run.caps['singleNormalizedElementBytes'] + 1)
                require(line == canonical(expected) + b'\n', 'Independent two-pass output/geometry/membership mismatch')
                count += 1
                total += len(line)
            require(not stream.read(1), 'Audit extra output')
        require(count == self.run.state['retainedElements'] and total == self.run.state['extractBytes'], 'Audit output accounting')
        require(self.occurrences == self.run.state['windowOccurrences'], 'Audit occurrence accounting')


def extract(reader, proposal, root, **options):
    with absolute_timeout(proposal['proposedCaps']['wallSeconds']):
        return _extract(reader, proposal, root, **options)


def _extract(reader, proposal, root, *, rows_per_shard=65536, primary_hook=None):
    """Synthetic/raw-record prototype. The full-source native launcher is absent."""
    run = Run(root, proposal)
    state = proposal['source']['proposedPublisherReplicationStateUtc']
    run.state['publisherStateUtc'] = state
    storage = Storage(run.caps['workingBytesIncludingTmp'] - run.caps['tmpBytes'] - 8388608, run.caps['sqliteIndexBytesEach'])
    first = Index(run.root / 'primary-index', storage, rows_per_shard=rows_per_shard, index_limit=run.caps['sqliteIndexBytesEach'])
    second = None
    hashes = []
    try:
        primary = Selection(proposal['windows'], run)
        for_pass = hashlib.sha256()
        for raw in checked_records(reader, run, state, 'primary-selection'):
            for_pass.update(canonical(raw) + b'\n')
            if raw['type'] == 'node':
                first.add(raw)
                continue
            first.finish()
            if raw['type'] == 'way' and 'highway' in (raw.get('tags') or {}):
                normalize(raw, state, run.caps['singleNormalizedElementBytes'])
                points = first.points(raw['nodes'])
                for window in proposal['windows']:
                    if intersects(points, window['bbox']):
                        primary.add(window['id'], ('way', raw['id']))
                        for identity in raw['nodes']:
                            primary.add(window['id'], ('node', identity))
                if ('way', raw['id']) in primary.keys:
                    primary.ways[raw['id']] = deepcopy(raw)
                    run.charge(heap_size((raw['id'], raw)) + 256)
        first.finish()
        hashes.append(for_pass.hexdigest())
        if primary_hook is not None:
            primary_hook(primary)
        audit = Audit(proposal, run)
        second = Index(run.root / 'audit-index', storage, rows_per_shard=rows_per_shard, index_limit=run.caps['sqliteIndexBytesEach'], replacing=first)
        for_pass = hashlib.sha256()
        for raw in checked_records(reader, run, state, 'materialize-independent-audit'):
            for_pass.update(canonical(raw) + b'\n')
            key = raw['type'], raw['id']
            if key[0] == 'node':
                second.add(raw)
                if key in primary.keys:
                    audit.keep(raw)
            else:
                second.finish()
            if key[0] == 'way' and 'highway' in (raw.get('tags') or {}):
                audit.way(raw, second)
            if key[0] == 'relation' and (raw.get('tags') or {}).get('type') == 'restriction':
                audit.relation(raw)
                for window in primary.members:
                    if any((m['type'], m['ref']) in primary.members[window] and m['type'] in ('node', 'way') for m in raw['members']):
                        primary.add(window, key)
            if key in primary.keys:
                if key[0] == 'way':
                    require(raw == primary.ways[raw['id']], 'Primary way drift')
                primary.keep(raw)
        second.finish()
        hashes.append(for_pass.hexdigest())
        require(hashes[0] == hashes[1], 'Two-pass full-record drift')
        require(set(audit.objects) == audit.keys, 'Audit missing/extra materialization hints')
        require(set(primary.objects) == primary.keys, 'Primary dependency closure')
        run.state['windowOccurrences'] = primary.occurrences
        path = run.root / 'elements.jsonl'
        with path.open('xb') as output:
            for row in records(primary, state):
                line = canonical(row) + b'\n'
                require(len(line) <= run.caps['singleNormalizedElementBytes'] and run.state['extractBytes'] + len(line) <= run.caps['normalizedExtractBytes'], 'Two-pass output byte cap')
                run.check()
                output.write(line)
                run.state['extractBytes'] += len(line)
                run.state['retainedElements'] += 1
        audit.compare(path)
        require(len(run.state['passes']) == 2 and all(p['status'] == 'eof' and p['counts'] == run.state['passes'][0]['counts'] for p in run.state['passes']), 'Two-pass EOF/count drift')
        run.state.update(status='passed_two_pass_prototype', independentAuditComplete=True, outputSha256=digest(path),
            sourceRecordHashes=hashes, coordinateStoragePeakBytes=storage.peak,
            coordinateStorageLiveBytes=storage.live, wholeExtractionQualified=False)
    except Exception as error:
        run.state.update(status='stopped', errorType=type(error).__name__, error=str(error), independentAuditComplete=False, derivedIndexesTrusted=False)
    finally:
        first.close()
        if second is not None:
            second.close()
    run.checkpoint()
    return run.state
