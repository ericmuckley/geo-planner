"""Separate selection/native reconstruction; shares only bounded storage/validation primitives."""
import hashlib
import sys

from coarse_osm_bulk import Coordinates, checked_records, heap_size
from coarse_osm_records import canonical, normalize, strict_json
from coarse_timing_input import digest, require


def crossing(points, box):
    def code(p):
        return (1 if p[0] < box[0] else 2 if p[0] > box[2] else 0) | (4 if p[1] < box[1] else 8 if p[1] > box[3] else 0)
    for first, second in zip(points, points[1:]):
        a, b = list(first), list(second)
        for _ in range(10):
            ca, cb = code(a), code(b)
            if not (ca | cb): return True
            if ca & cb: break
            c = ca or cb
            if c & (4 | 8):
                y = box[1] if c & 4 else box[3]
                p = [a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]), y]
            else:
                x = box[0] if c & 1 else box[2]
                p = [x, a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0])]
            if c == ca: a = p
            else: b = p
        else: raise ValueError('Audit clipping did not converge')
    return False


def audit(reader, proposal, run):
    state = proposal['source']['proposedPublisherReplicationStateUtc']; caps = run.caps
    members = {w['id']: set() for w in proposal['windows']}; keys, ways, objects = set(), {}, {}
    occurrences = native_bytes = 0
    run.charge(heap_size((members, keys, ways, objects)))
    def add(window, key):
        nonlocal occurrences
        if key in members[window]: return
        before = sys.getsizeof(keys) + sys.getsizeof(members[window])
        keys.add(key); members[window].add(key); occurrences += 1
        run.charge(2 * heap_size(key) + sys.getsizeof(keys) + sys.getsizeof(members[window]) - before)
        require(len(keys) <= caps['selectedUniqueTypedElements'] and occurrences <= caps['selectedWindowElementOccurrences'], 'Audit selected caps')
    index = Coordinates(run.root / 'audit-nodes.sqlite', caps)
    def lookup(ids):
        locations = {}
        for offset in range(0, len(ids), 400):
            part = ids[offset:offset + 400]
            for row in index.db.execute('SELECT lon,lat,id FROM nodes WHERE id IN (' + ','.join('?' for _ in part) + ')', part):
                locations[row[2]] = [row[0], row[1]]
        require(all(i in locations for i in ids), 'Audit missing source coordinates')
        return [locations[i] for i in ids]
    try:
        for raw in checked_records(reader, run, state, 'audit-index-selection'):
            if raw['type'] == 'node': index.db.execute('INSERT INTO nodes(id,lon,lat) VALUES(?,?,?)', (raw['id'], raw['lon'], raw['lat']))
            if raw['type'] != 'way' or 'highway' not in (raw.get('tags') or {}): continue
            normalize(raw, state, caps['singleNormalizedElementBytes'])
            points = lookup(raw['nodes'])
            for window in proposal['windows']:
                if crossing(points, window['bbox']):
                    add(window['id'], ('way', raw['id']))
                    for i in raw['nodes']: add(window['id'], ('node', i))
            if ('way', raw['id']) in keys:
                ways[raw['id']] = canonical(raw); run.charge(heap_size((raw['id'], ways[raw['id']])) + 128)
        index.finish()
        for raw in checked_records(reader, run, state, 'audit-native-records'):
            key = raw['type'], raw['id']
            if key[0] == 'relation' and (raw.get('tags') or {}).get('type') == 'restriction':
                for window in members:
                    linked = {(m['type'], m['ref']) for m in raw['members'] if m['type'] in ('node', 'way')}
                    if not members[window].isdisjoint(linked): add(window, key)
            if key not in keys: continue
            if key[0] == 'way': require(canonical(raw) == ways[raw['id']], 'Audit way drift')
            if key[0] == 'node': require(lookup([raw['id']])[0] == [raw['lon'], raw['lat']], 'Audit coordinate drift')
            value = normalize(raw, state, caps['singleNormalizedElementBytes']); native_bytes += len(canonical(value))
            require(native_bytes <= caps['retainedNativeObjectBytes'], 'Audit retained native cap')
            require(key not in objects, 'Audit duplicate retained identity'); objects[key] = value
            run.charge(heap_size((key, value)) + 128)
        index.finish()
    finally: index.close()
    require(set(objects) == keys, 'Audit node/way/restriction closure')
    output = run.root / 'elements.jsonl'; count = total_bytes = 0
    with output.open('rb') as stream:
        for key, element in sorted(objects.items()):
            line = stream.readline(caps['singleNormalizedElementBytes'] + 1)
            require(line.endswith(b'\n') and len(line) <= caps['singleNormalizedElementBytes'], 'Audit output record/prefix bound')
            expected = {'publisherStateUtc': state, 'element': element, 'elementSha256': hashlib.sha256(canonical(element)).hexdigest(),
                'windowIds': [w for w in members if key in members[w]]}
            if key[0] == 'way':
                ordered_nodes = [objects['node', i] for i in element['nodes']]
                expected['geometryDependencySha256'] = hashlib.sha256(canonical([state, ordered_nodes])).hexdigest()
            require(strict_json(line) == expected and line == canonical(expected) + b'\n', 'Independent native/selection/dependency audit mismatch')
            count += 1; total_bytes += len(line)
        require(not stream.read(1), 'Audit extra normalized output')
    require(count == run.state['retainedElements'] and total_bytes == run.state['extractBytes'] <= caps['normalizedExtractBytes'], 'Audit extract accounting')
    require(occurrences == run.state['windowOccurrences'], 'Audit occurrence accounting')
    require(len(run.state['passes']) == 4 and all(p['status'] == 'eof' for p in run.state['passes']), 'Audit four full scans')
    require(all(p['counts'] == run.state['passes'][0]['counts'] for p in run.state['passes']), 'Audit pass row counts drift')
    run.check()
    return {'independentSelectionNativeIdentityAndOutputAudit': True, 'completeFromAcquiredFileOnly': True,
        'windows': [{'id': w, 'counts': {kind: sum(k[0] == kind for k in selected) for kind in ('node', 'way', 'relation')}} for w, selected in members.items()],
        'retainedElements': count, 'windowOccurrences': occurrences, 'extractBytes': total_bytes, 'outputSha256': digest(output),
        'sourceFeasibilityQualified': False, 'publisherBoundaryQualified': False, 'physicalIdentityVerified': False,
        'sharedPrimitives': 'Native validation/canonical hash/UTC, ordered stream counters and capped SQLite configuration. Separate SQL insertion/lookup, selection geometry/membership/reconstruction; shared optional Pyosmium decoder is not an independent source proof.'}
