"""Project fuel stations from a small cached OSM extract to point features."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time


def interior_point(ring):
    """Find a point on an interior interval of a closed way's middle scanline."""
    latitudes = sorted({lat for _, lat in ring})
    if len(latitudes) < 2:
        return None
    middle = len(latitudes) // 2
    lat = (latitudes[middle - 1] + latitudes[middle]) / 2
    crossings = sorted(
        lon_a + (lat - lat_a) * (lon_b - lon_a) / (lat_b - lat_a)
        for (lon_a, lat_a), (lon_b, lat_b) in zip(ring, ring[1:])
        if (lat_a < lat) != (lat_b < lat)
    )
    if not crossings or len(crossings) % 2:
        return None
    west, east = max(zip(crossings[::2], crossings[1::2]), key=lambda pair: pair[1] - pair[0])
    return ((west + east) / 2, lat) if east > west else None


def extract(source):
    import osmium

    pool = osmium.io.ThreadPool(1, 2)
    fuel = osmium.FileProcessor(str(source), thread_pool=pool)
    fuel.with_filter(osmium.filter.TagFilter(('amenity', 'fuel')))
    features, ways, refs = [], [], set()
    objects, skipped = Counter(), Counter()

    def feature(properties, point):
        return {
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': point},
            'properties': properties,
        }

    for obj in fuel:
        kind = obj.type_str()
        objects[kind] += 1
        if objects.total() > 50000:
            raise ValueError('Too many fuel source objects for this pilot')
        properties = {'osm': f'{kind}{obj.id}', 'name': obj.tags.get('name') or obj.tags.get('brand')}
        if kind == 'n' and obj.location.valid():
            features.append(feature(properties, (obj.location.lon, obj.location.lat)))
        elif kind == 'w' and 4 <= len(obj.nodes) <= 512:
            node_ids = tuple(node.ref for node in obj.nodes)
            if node_ids[0] != node_ids[-1]:
                skipped['openWay'] += 1
                continue
            refs.update(node_ids)
            if len(refs) > 200000:
                raise ValueError('Too many referenced nodes for this pilot')
            ways.append((properties, node_ids))
        else:
            skipped[kind] += 1

    locations = {}
    if refs:
        nodes = osmium.FileProcessor(str(source), entities=osmium.osm.NODE, thread_pool=pool)
        nodes.with_filter(osmium.filter.IdFilter(sorted(refs)))
        for node in nodes:
            if node.location.valid():
                locations[node.id] = (node.location.lon, node.location.lat)
    for properties, node_ids in ways:
        if not all(node in locations for node in node_ids):
            skipped['missingWayNodes'] += 1
            continue
        point = interior_point([locations[node] for node in node_ids])
        if point is None:
            skipped['invalidWay'] += 1
            continue
        features.append(feature(properties, point))
    features.sort(key=lambda item: item['properties']['osm'])
    if len({item['properties']['osm'] for item in features}) != len(features):
        raise ValueError('Duplicate source feature ID')
    return {'type': 'FeatureCollection', 'features': features}, objects, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('sha256')
    args = parser.parse_args()
    began = time.monotonic()
    if not (0 < args.source.stat().st_size <= 16 * 1024**2):
        raise ValueError('Only small cached extracts fit this pilot')
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != args.sha256:
        raise ValueError('Cached extract checksum mismatch')
    collection, objects, skipped = extract(args.source)
    print(json.dumps({
        'sourceSha256': args.sha256,
        'sourceObjectsByType': objects,
        'skipped': skipped,
        'runtimeSeconds': time.monotonic() - began,
        'points': collection,
    }, ensure_ascii=False, allow_nan=False, separators=(',', ':')))


if __name__ == '__main__':
    main()
