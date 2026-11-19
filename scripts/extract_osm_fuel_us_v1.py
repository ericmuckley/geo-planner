"""Extract mapped fuel locations from the checksum-bound cached US OSM snapshot."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import time

from extract_osm_fuel_sample import interior_point


MAX_OBJECTS = 300_000
MAX_WAY_REFS = 3_000_000


def source_stat(path):
    info = path.stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def station_name(tags):
    return ' '.join((tags.get('name') or tags.get('brand') or '').split())[:160]


def bucket(lon, lat):
    return math.floor(lon * 100), math.floor(lat * 100)


def inside_ring(lon, lat, ring):
    spans = (
        lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
        for (x1, y1), (x2, y2) in zip(ring, ring[1:])
        if (y1 > lat) != (y2 > lat)
    )
    return sum(spans) % 2 == 1


def contains_duplicate_node(ring, nodes_by_bucket, name):
    west, east = min(p[0] for p in ring), max(p[0] for p in ring)
    south, north = min(p[1] for p in ring), max(p[1] for p in ring)
    x0, y0 = bucket(west, south)
    x1, y1 = bucket(east, north)
    # Huge or ambiguous source outlines are never used as duplicate evidence.
    if (x1 - x0 + 1) * (y1 - y0 + 1) > 64:
        return False
    contained = [
        node for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)
        for node in nodes_by_bucket.get((x, y), ())
        if inside_ring(node[0], node[1], ring)
    ]
    if len(contained) != 1:
        return False
    other = contained[0][2]
    return not name or not other or name.casefold() == other.casefold()


def extract(source):
    import osmium

    kind_count, skipped = Counter(), Counter()
    points, ways, refs, seen = [], [], set(), set()
    way_ref_rows = 0
    nodes_by_bucket = defaultdict(list)
    pool = osmium.io.ThreadPool(2, 2)
    reader = osmium.FileProcessor(source, thread_pool=pool)
    reader.with_filter(osmium.filter.TagFilter(('amenity', 'fuel')))
    for obj in reader:
        kind = obj.type_str()
        identity = f'{kind}{obj.id}'
        if obj.id <= 0 or identity in seen or len(seen) == MAX_OBJECTS:
            raise ValueError('Unbounded or duplicate matched fuel record')
        seen.add(identity)
        kind_count[kind] += 1
        if (obj.tags.get('access') or '').lower() in ('no', 'private'):
            skipped['restrictedAccess'] += 1
            continue
        name = station_name(obj.tags)
        if kind == 'n':
            if not obj.location.valid():
                skipped['invalidPoint'] += 1
                continue
            record = (obj.location.lon, obj.location.lat, name, identity)
            points.append(record)
            nodes_by_bucket[bucket(*record[:2])].append(record)
        elif kind == 'w':
            if not 4 <= len(obj.nodes) <= 512 or obj.nodes[0].ref != obj.nodes[-1].ref:
                skipped['unsupportedWay'] += 1
                continue
            members = tuple(node.ref for node in obj.nodes)
            way_ref_rows += len(members)
            if way_ref_rows > MAX_WAY_REFS:
                raise ValueError('Fuel-outline reference cap exceeded')
            refs.update(members)
            ways.append((members, name, identity))
        else:
            skipped['relation'] += 1

    print(json.dumps({'phase': 'inventory', 'sourceObjects': dict(kind_count),
                      'selectedWayNodes': len(refs)}), flush=True)
    coordinates = {}
    if refs:
        nodes = osmium.FileProcessor(source, entities=osmium.osm.NODE, thread_pool=pool)
        nodes.with_filter(osmium.filter.IdFilter(sorted(refs)))
        for node in nodes:
            if node.location.valid():
                coordinates[node.id] = (node.location.lon, node.location.lat)

    for members, name, identity in ways:
        if not all(node in coordinates for node in members):
            skipped['missingWayNodes'] += 1
            continue
        ring = [coordinates[node] for node in members]
        point = interior_point(ring)
        if point is None:
            skipped['invalidWay'] += 1
        elif contains_duplicate_node(ring, nodes_by_bucket, name):
            skipped['duplicateOutline'] += 1
        else:
            points.append((*point, name, identity))

    rows, point_keys = [], set()
    for lon, lat, name, identity in sorted(points, key=lambda row: row[3]):
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError('Invalid station coordinate')
        lon, lat = round(lon, 6), round(lat, 6)
        key = (lon, lat, name.casefold())
        if key in point_keys:
            skipped['duplicatePoint'] += 1
            continue
        point_keys.add(key)
        rows.append((lon, lat, name, identity))
    if len(rows) + skipped.total() != kind_count.total():
        raise ValueError('Incomplete fuel inventory')
    return rows, kind_count, skipped, len(refs), len(coordinates)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('sha256')
    parser.add_argument('--sample', action='store_true')
    args = parser.parse_args()
    start = time.monotonic()
    original = source_stat(args.source)
    if not (0 < original[2] <= 16 * 1024**2 if args.sample else original[2] == 12229320016):
        raise ValueError('Unexpected source size')
    with args.source.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != args.sha256:
            raise ValueError('Cached source checksum mismatch')
    print(json.dumps({'phase': 'source checksum verified'}), flush=True)
    rows, objects, skipped, wanted, resolved = extract(str(args.source))
    if source_stat(args.source) != original:
        raise ValueError('Read-only source identity changed')
    data = {'version': 1, 'sourceDate': '2026-10-25' if not args.sample else None,
            'sourceSha256': args.sha256, 'stations': rows}
    with (args.output / 'fuel-us-v1.json').open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    asset = args.output / 'fuel-us-v1.json'
    with asset.open('rb') as stream:
        data_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {'status': 'fuel_inventory_complete', 'sample': args.sample,
              'sourceSha256': args.sha256, 'sourceBytes': original[2],
              'objectsByType': dict(objects), 'skipped': dict(skipped), 'locations': len(rows),
              'wayNodesRequested': wanted, 'wayNodesResolved': resolved,
              'dataBytes': asset.stat().st_size, 'dataSha256': data_sha,
              'secondsIncludingSourceHashAndBothPasses': time.monotonic() - start}
    with (args.output / 'report.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
