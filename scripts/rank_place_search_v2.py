"""Keep the checked name catalog and order equally named communities by Census land area."""
import hashlib
import json

from build_place_search_v1 import INPUT, ROOT, SOURCES, position, rows

INPUT_CATALOG = INPUT / 'search-us-v1.json'
INPUT_SHA256 = '86b2d47ceab14e6c26c705f6b5d6e29426d02475714eb4db75f197fc7344b29b'
OUTPUT = ROOT / 'public/places/search-us-v2.json'


def main():
    with (INPUT / 'census-places.zip').open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != SOURCES['census-places.zip']:
            raise ValueError('Census snapshot checksum mismatch')
    raw = INPUT_CATALOG.read_bytes()
    if hashlib.sha256(raw).hexdigest() != INPUT_SHA256:
        raise ValueError('Name catalog checksum mismatch')
    land_areas = {}
    for row in rows('census-places.zip', '2026_Gaz_place_national.txt'):
        state = row['USPS']
        if state in {'AK', 'HI', 'PR'}:
            continue
        point = (state, *position(row['INTPTLAT'], row['INTPTLONG']))
        land_areas[point] = max(land_areas.get(point, 0), int(row['ALAND']))

    catalog = json.loads(raw)
    # The app's name relevance sort is stable and uses this order for equal matches.
    catalog.sort(key=lambda place: -land_areas[tuple(place[1:4])] if place[4] == 0 else 0)
    data = json.dumps(catalog, ensure_ascii=False, separators=(',', ':')).encode()
    with OUTPUT.open('xb') as stream:
        stream.write(data)
    print(json.dumps({
        'sourceCatalogSha256': INPUT_SHA256, 'censusSourceSha256': SOURCES['census-places.zip'],
        'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'records': len(catalog),
    }, indent=2))


if __name__ == '__main__':
    main()
