"""Native OSM capture validation and inventory; no routing/access interpretation."""
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
import re

from coarse_timing_input import require


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite JSON constant: ' + value)
    def number(value):
        result = float(value)
        require(math.isfinite(result), 'Nonfinite JSON number')
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid, parse_float=number)


def utc(value):
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value), 'Invalid UTC timestamp')
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')


def positive(value):
    return type(value) is int and value > 0


def normalize(raw, snapshot, limit):
    require(isinstance(raw, dict) and len(canonical(raw)) <= limit, 'Single source element cap/type')
    kind = raw.get('type')
    require(kind in ('node', 'way', 'relation') and positive(raw.get('id')) and positive(raw.get('version')), 'Invalid typed source identity')
    require('visible' not in raw or raw['visible'] is True, 'Deleted/invisible source element')
    require(utc(raw.get('timestamp')) <= utc(snapshot), 'Element newer than requested snapshot')
    tags = raw.get('tags')
    require('tags' not in raw or isinstance(tags, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in tags.items()), 'Invalid raw tags')
    result = {k: raw[k] for k in ('type', 'id', 'version', 'timestamp')}
    if 'visible' in raw: result['visible'] = raw['visible']
    result['tags'] = tags
    if kind == 'node':
        require(all(type(raw.get(k)) in (int, float) and math.isfinite(raw[k]) for k in ('lat', 'lon')), 'Invalid node coordinates')
        require(-90 <= raw['lat'] <= 90 and -180 <= raw['lon'] <= 180, 'Node coordinates outside range')
        result.update(lat=float(raw['lat']), lon=float(raw['lon']))
    elif kind == 'way':
        require(isinstance(raw.get('nodes'), list) and len(raw['nodes']) >= 2 and all(positive(i) for i in raw['nodes']), 'Invalid ordered way nodes')
        require(isinstance(tags, dict) and isinstance(tags.get('highway'), str) and tags['highway'], 'Returned non-highway way')
        result['nodes'] = raw['nodes']
    else:
        require(isinstance(tags, dict) and tags.get('type') == 'restriction' and isinstance(raw.get('members'), list), 'Returned non-restriction relation')
        members = []
        for m in raw['members']:
            require(isinstance(m, dict) and m.get('type') in ('node', 'way', 'relation') and positive(m.get('ref')) and isinstance(m.get('role'), str), 'Invalid relation reference')
            members.append({k: m[k] for k in ('type', 'ref', 'role')})
        result['members'] = members
    return result


def intersects(points, box):
    for a, b in zip(points, points[1:]):
        lo, hi = 0., 1.
        for axis in (0, 1):
            delta = b[axis] - a[axis]
            if delta == 0:
                if not box[axis] <= a[axis] <= box[axis + 2]:
                    hi = -1; break
            else:
                first, last = sorted(((box[axis] - a[axis]) / delta, (box[axis + 2] - a[axis]) / delta))
                lo, hi = max(lo, first), min(hi, last)
        if lo <= hi: return True
    return False


def batch(raw, snapshot, box, caps, expected_generator=None):
    root = strict_json(raw)
    require(isinstance(root, dict) and root.get('version') == .6 and type(root.get('version')) in (int, float), 'Invalid response schema version')
    require('remark' not in root and 'error' not in root, 'Overpass remark/error')
    generator = root.get('generator')
    require(isinstance(generator, str) and generator.startswith('Overpass API ') and len(generator) <= 512, 'Invalid source generator')
    require(expected_generator is None or generator == expected_generator, 'Source generator changed')
    info = root.get('osm3s')
    require(isinstance(info, dict) and utc(info.get('timestamp_osm_base')) >= utc(snapshot), 'Source base older than snapshot')
    require(isinstance(info.get('copyright'), str) and 0 < len(info['copyright']) <= 4096, 'Missing source attribution')
    elements = root.get('elements')
    require(isinstance(elements, list) and elements and all(isinstance(e, dict) for e in elements), 'Missing source elements/final count')
    require(sum(e.get('type') == 'count' for e in elements) == 1 and elements[-1].get('type') == 'count', 'Missing/duplicate/nonterminal final count')
    require(len(elements) - 1 <= caps['elementOccurrencesAllWindows'], 'Response element occurrence cap')
    final = elements[-1]
    require(type(final.get('id')) is int and final['id'] == 0 and isinstance(final.get('tags'), dict), 'Invalid final count')
    counts = final['tags']
    require(set(counts) in ({'nodes', 'ways', 'relations', 'total'}, {'nodes', 'ways', 'relations', 'areas', 'total'}), 'Invalid count keys')
    require(all(isinstance(v, str) and re.fullmatch(r'0|[1-9]\d*', v) for v in counts.values()), 'Invalid count values')
    require(int(counts.get('areas', '0')) == 0, 'Unexpected area elements')
    objects = {}
    for item in elements[:-1]:
        value = normalize(item, snapshot, caps['singleNormalizedElementBytes'])
        key = value['type'], value['id']
        require(key not in objects, 'Duplicate typed element within response')
        objects[key] = value
    actual = Counter(k[0] + 's' for k in objects)
    require(all(int(counts[k]) == actual[k] for k in ('nodes', 'ways', 'relations')) and int(counts['total']) == len(objects), 'Final count mismatch')
    needed = {i for e in objects.values() if e['type'] == 'way' for i in e['nodes']}
    present = {i for kind, i in objects if kind == 'node'}
    require(needed == present, 'Missing way node or unrelated returned node')
    records, external, highway, tag_keys = [], [], Counter(), Counter()
    for key, e in sorted(objects.items()):
        record = {'snapshotUtc': snapshot, 'element': e, 'elementSha256': hashlib.sha256(canonical(e)).hexdigest()}
        if e['type'] == 'way':
            nodes = [objects['node', i] for i in e['nodes']]
            require(intersects([[n['lon'], n['lat']] for n in nodes], box), 'Returned way misses frozen bbox')
            record['geometryDependencySha256'] = hashlib.sha256(canonical([snapshot, nodes])).hexdigest()
            highway.update([e['tags']['highway']]); tag_keys.update(e['tags'].keys())
        if e['type'] == 'relation':
            require(any((m['type'], m['ref']) in objects for m in e['members']), 'Unrelated restriction relation')
            external.extend({'relationId': e['id'], **m} for m in e['members'] if (m['type'], m['ref']) not in objects)
        records.append(record)
    return {'generator': generator, 'sourceBaseTimestamp': info['timestamp_osm_base'], 'copyright': info['copyright'],
        'records': records, 'counts': {k: actual[k] for k in ('nodes', 'ways', 'relations')},
        'externalRestrictionMemberCount': len(external), 'externalRestrictionMembersSha256': hashlib.sha256(canonical(external)).hexdigest(),
        'rawHighwayCounts': dict(highway), 'wayTagKeyOccurrences': dict(tag_keys)}
