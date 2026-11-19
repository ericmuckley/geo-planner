"""Extract trailheads and campgrounds from the cached US OSM snapshot."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
import time

import osmium
from extract_osm_fuel_sample import interior_point
from extract_osm_fuel_us_v1 import bucket, contains_duplicate_node, source_stat

TAGS = {'trailheads': ('highway', 'trailhead'), 'campgrounds': ('tourism', 'camp_site')}
SOURCE_SHA = '1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff'
SOURCE_DATE = '2026-10-25'


def inventory(source):
    pool = osmium.io.ThreadPool(2, 2)
    reader = osmium.FileProcessor(source, thread_pool=pool)
    reader.with_filter(osmium.filter.TagFilter(*TAGS.values()))
    counts = {kind: Counter() for kind in TAGS}
    points = {kind: [] for kind in TAGS}
    nodes_by_bucket = {kind: defaultdict(list) for kind in TAGS}
    ways, seen, refs = [], set(), set()
    ref_rows = 0
    for obj in reader:
        element = obj.type_str()
        identity = f'{element}{obj.id}'
        if obj.id <= 0 or identity in seen or len(seen) >= 300_000:
            raise ValueError('Too many matched places or a repeated OSM ID')
        seen.add(identity)
        kinds = [kind for kind, (key, value) in TAGS.items() if obj.tags.get(key) == value]
        name = ' '.join((obj.tags.get('name') or '').split())[:160]
        for kind in kinds:
            counts[kind][element] += 1
            if (obj.tags.get('access') or '').lower() in ('no', 'private'):
                counts[kind]['restricted'] += 1
            elif element == 'n':
                if not obj.location.valid():
                    counts[kind]['invalidPoint'] += 1
                    continue
                row = (obj.location.lon, obj.location.lat, name, identity)
                points[kind].append(row)
                nodes_by_bucket[kind][bucket(*row[:2])].append(row)
            elif element == 'w':
                if not 4 <= len(obj.nodes) <= 512 or obj.nodes[0].ref != obj.nodes[-1].ref:
                    counts[kind]['unsupportedWay'] += 1
                    continue
                members = tuple(node.ref for node in obj.nodes)
                ref_rows += len(members)
                if ref_rows > 3_000_000:
                    raise ValueError('Outdoor outline reference cap exceeded')
                refs.update(members)
                ways.append((kind, members, name, identity))
            else:
                counts[kind]['unsupportedRelation'] += 1

    print(json.dumps({'matchedObjects': len(seen), 'requestedWayNodes': len(refs)}), flush=True)
    coordinates = {}
    if refs:
        reader = osmium.FileProcessor(source, entities=osmium.osm.NODE, thread_pool=pool)
        reader.with_filter(osmium.filter.IdFilter(sorted(refs)))
        for node in reader:
            if node.location.valid():
                coordinates[node.id] = (node.location.lon, node.location.lat)

    for kind, members, name, identity in ways:
        if not all(ref in coordinates for ref in members):
            counts[kind]['missingWayNodes'] += 1
            continue
        ring = [coordinates[ref] for ref in members]
        point = interior_point(ring)
        if point is None:
            counts[kind]['invalidWay'] += 1
        elif contains_duplicate_node(ring, nodes_by_bucket[kind], name):
            counts[kind]['duplicateOutline'] += 1
        else:
            points[kind].append((*point, name, identity))

    catalogs = {}
    for kind, records in points.items():
        keys, rows = set(), []
        for lon, lat, name, identity in sorted(records, key=lambda row: row[3]):
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise ValueError('Invalid place coordinates')
            lon, lat = round(lon, 6), round(lat, 6)
            key = (lon, lat, name.casefold())
            if key in keys:
                counts[kind]['duplicatePoint'] += 1
                continue
            keys.add(key)
            rows.append((lon, lat, name, identity))
        objects = sum(counts[kind][element] for element in ('n', 'w', 'r'))
        skipped = sum(count for key, count in counts[kind].items() if key not in ('n', 'w', 'r'))
        if objects != skipped + len(rows):
            raise ValueError(f'Incomplete inventory for {kind}')
        catalogs[kind] = rows
    return catalogs, counts, len(refs), len(coordinates)


def main(source, output):
    start = time.monotonic()
    original = source_stat(source)
    with source.open('rb') as stream:
        if original[2] != 12_229_320_016 or hashlib.file_digest(stream, 'sha256').hexdigest() != SOURCE_SHA:
            raise ValueError('Cached US source does not match the pinned snapshot')
    catalogs, counts, requested, resolved = inventory(source)
    if source_stat(source) != original:
        raise ValueError('Source identity changed during extraction')
    assets = {}
    for kind, rows in catalogs.items():
        if not rows:
            raise ValueError(f'No mapped locations for {kind}')
        path = output / f'{kind}-us-v1.json'
        data = json.dumps({
            'version': 1,
            'sourceDate': SOURCE_DATE,
            'sourceSha256': SOURCE_SHA,
            'attribution': '© OpenStreetMap contributors',
            'license': 'https://opendatacommons.org/licenses/odbl/1-0/',
            'places': rows,
        }, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
        with path.open('xb') as stream:
            stream.write(data)
        assets[path.name] = {'rows': len(rows), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    report = {
        'status': 'outdoor_places_inventory_complete', 'sourceSha256': SOURCE_SHA,
        'sourceDate': SOURCE_DATE, 'sourceBytes': original[2], 'counts': counts,
        'wayNodesRequested': requested, 'wayNodesResolved': resolved, 'assets': assets,
        'secondsIncludingSourceHashAndBothPasses': time.monotonic() - start,
    }
    with (output / 'report.json').open('x') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main(*(Path(arg) for arg in sys.argv[1:]))
