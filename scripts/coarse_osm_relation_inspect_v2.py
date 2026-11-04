"""Bounded native type/ID filtering for source-quality diagnosis, not routing."""
import hashlib
import json
from pathlib import Path
import time

from coarse_osm_bulk_pbf import stat_key
from coarse_osm_native_smoke import STATE, write_xml
from coarse_timing_input import require


def selected_relations(path, targets):
    import osmium
    require(0 < len(targets) <= 16 and len(set(targets)) == len(targets) and
            all(type(n) is int and 0 < n < 2**63 for n in targets), 'Relation inspection target bound')
    pool = osmium.io.ThreadPool(2, 2)
    processor = osmium.FileProcessor(osmium.io.File(str(path), 'pbf'), entities=osmium.osm.RELATION, thread_pool=pool)
    processor.with_filter(osmium.filter.IdFilter(targets))
    records = []
    for obj in processor:
        require(obj.type_str() == 'r' and obj.id in targets and len(records) < len(targets), 'Relation native filter scope')
        raw = {'type': 'relation', 'id': int(obj.id), 'version': int(obj.version),
               'timestamp': obj.timestamp.strftime('%Y-%m-%dT%H:%M:%SZ'), 'visible': bool(obj.visible), 'tags': {}, 'members': []}
        charged = 256
        for tag in obj.tags:
            charged += len(tag.k.encode()) + len(tag.v.encode()) + 64
            require(charged <= 1048576 and tag.k not in raw['tags'], 'Relation inspection tag bound')
            raw['tags'][str(tag.k)] = str(tag.v)
        for member in obj.members:
            charged += len(member.role.encode()) + 128
            require(charged <= 1048576, 'Relation inspection member bound')
            raw['members'].append({'type': {'n': 'node', 'w': 'way', 'r': 'relation'}[member.type], 'ref': int(member.ref), 'role': str(member.role)})
        records.append(raw)
    require({r['id'] for r in records} == set(targets), 'Relation inspection missing/duplicate source target')
    return records


def self_test(root):
    import osmium
    from coarse_timing_input import PilotError
    base = {'version': 1, 'timestamp': STATE, 'visible': True}
    rows = [base | {'type': 'node', 'id': 1, 'lat': 0., 'lon': 0., 'tags': {}},
            base | {'type': 'way', 'id': 1, 'nodes': [1, 1], 'tags': {'highway': 'primary'}}]
    rows += [base | {'type': 'relation', 'id': i, 'tags': {'type': 'restriction', 'name': 'fixture 雪'}, 'members': []} for i in (1, 2, 3)]
    xml = root/'filter-fixture.osm'
    pbf = root/'filter-fixture.bin'
    write_xml(xml, rows)
    header = osmium.io.Header()
    header.set('osmosis_replication_timestamp', STATE)
    with osmium.SimpleWriter(osmium.io.File(str(pbf), 'pbf'), bufsz=65536, header=header) as writer:
        for row in osmium.FileProcessor(str(xml)):
            writer.add(row)
    require(selected_relations(pbf, [1, 3]) == [rows[2], rows[4]], 'Relation native type/ID and complete metadata control')
    for targets in ([], [1, 1], [0], [True]):
        try:
            selected_relations(pbf, targets)
            raise AssertionError('Invalid relation target accepted')
        except PilotError:
            pass
    return {'checks': 3, 'successful': True, 'controls': ['type and ID filtering', 'all selected metadata including Unicode', 'empty/duplicate/invalid target rejection']}


def audit():
    root = Path('/work')
    started = time.monotonic()
    controls = self_test(root)
    repo = Path('/repo')
    source = repo/'data/coarse-quality/us-osm-input-v3/download/http/001.bin'
    parent = repo/'data/coarse-quality/us-osm-car-capacity-run-v3'
    receipt = json.loads((parent/'receipt.json').read_bytes())
    require(receipt['nativeEof'] and receipt['sourceIdentity']['sourceSha256'] == '1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff', 'Relation inspection completed parent source binding')
    from array import array
    ids = array('Q')
    ids.frombytes((parent/'way-facts/unlocatable-restrictions.u64').read_bytes())
    require(len(ids) == 2 and source.stat().st_size == 12229320016, 'Relation inspection source/target denominator')
    before = stat_key(source)
    records = selected_relations(source, list(ids))
    require(before == stat_key(source), 'Relation inspection source changed')
    return {'status': 'completed_native_selected_relation_diagnosis', 'selfTests': controls, 'targets': list(ids), 'records': records,
            'pythonObjectsProjectedFromCountry': len(records), 'method': 'Cached pyosmium relation-only reader and native IdFilter. No location store or national Python OSM projection. Parent complete source seals reused; source stats unchanged before/after. This is a selected-record diagnosis, not a new whole-source hash/semantic qualification.',
            'parentReceiptSha256': hashlib.sha256((parent/'receipt.json').read_bytes()).hexdigest(),
            'secondsIncludingTinyControlsAndSelectedSourceRead': time.monotonic()-started,
            'sourcePbfReads': 1, 'newSourceDownloads': 0, 'networkRequests': 0, 'applicationDbReads': 0,
            'modelChanged': False, 'policyChanged': False}
