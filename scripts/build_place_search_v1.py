"""Build the app's name search catalog from pinned Census and USGS public data."""
import csv
import hashlib
import io
import json
from pathlib import Path
import re
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'data/map-layers/place-search-v1'
OUTPUT = ROOT / 'public/places/search-us-v1.json'
SOURCES = {
    'census-places.zip': 'af678e2d990827c89ee39b98c82de6e90b693c7361ff0e559ae3076670dd2863',
    'gnis.zip': '1ccd7aaa8f50ba7e2340e131bce815154e6c8288df72bbff01e0e99033ac9acd',
}
LANDMARKS = {'Arch', 'Cliff', 'Crater', 'Falls', 'Spring', 'Summit', 'Valley'}


def rows(source, member):
    with ZipFile(INPUT / source) as archive:
        with archive.open(member) as data:
            yield from csv.DictReader(io.TextIOWrapper(data, encoding='utf-8-sig'), delimiter='|')


def position(lat, lon):
    lat, lon = float(lat), float(lon)
    if not (24 <= lat <= 50 and -125 <= lon <= -66):
        raise ValueError('Place outside the contiguous US search bounds')
    return round(lat, 5), round(lon, 5)


def main():
    for filename, expected in SOURCES.items():
        with (INPUT / filename).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                raise ValueError(f'Unexpected source snapshot for {filename}')

    states, census = {}, []
    for row in rows('census-places.zip', '2026_Gaz_place_national.txt'):
        state = row['USPS']
        if state in {'AK', 'HI', 'PR'}:
            continue
        states[row['GEOID'][:2]] = state
        name = re.sub(r' (?:borough|city|town|village|municipality|CDP)$', '', row['NAME'])
        lat, lon = position(row['INTPTLAT'], row['INTPTLONG'])
        census.append((name, state, lat, lon, 0))

    landmarks, excluded = set(), 0
    for row in rows('gnis.zip', 'Text/DomesticNames_National.txt'):
        state = states.get(row['state_numeric'])
        name = row['feature_name']
        if not state or row['feature_class'] not in LANDMARKS or not name:
            continue
        try:
            lat, lon = position(row['prim_lat_dec'], row['prim_long_dec'])
        except ValueError:
            excluded += 1
            continue
        landmarks.add((name, state, lat, lon, 1))

    catalog = sorted(set(census) | landmarks, key=lambda row: (row[0].casefold(), *row[1:]))
    if len(states) != 49 or len(census) < 30_000 or len(landmarks) < 50_000:
        raise ValueError('Incomplete place-search data')
    data = json.dumps(catalog, ensure_ascii=False, separators=(',', ':')).encode()
    with OUTPUT.open('xb') as stream:
        stream.write(data)
    print(json.dumps({'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                      'censusPlaces': len(set(census)), 'landmarks': len(landmarks),
                      'excludedLandmarkCoordinates': excluded, 'sourceSha256': SOURCES}, indent=2))


if __name__ == '__main__':
    main()
