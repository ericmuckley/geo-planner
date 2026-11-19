"""Verify the national output and place an attributed catalog in the public app."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re


REPO = Path(__file__).resolve().parents[1]
run = REPO / 'data/coarse-quality/us-osm-fuel-us-v1'
report = json.loads((run / 'report.json').read_bytes())
raw = (run / 'fuel-us-v1.json').read_bytes()
catalog = json.loads(raw)
points = catalog['stations']
assert report['status'] == 'fuel_inventory_complete' and report['sample'] is False
assert report['dataSha256'] == hashlib.sha256(raw).hexdigest()
assert report['sourceSha256'] == catalog['sourceSha256']
assert len(raw) == report['dataBytes'] <= 8*1024**2
assert len(points) == report['locations']
assert len(points) + sum(report['skipped'].values()) == sum(report['objectsByType'].values())
assert report['wayNodesRequested'] == report['wayNodesResolved']
identities, keys, bins = set(), set(), Counter()
for lon, lat, name, identity in points:
    assert math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90
    assert isinstance(name, str) and len(name) <= 160 and re.fullmatch(r'[nw][1-9][0-9]*', identity)
    key = lon, lat, name.casefold()
    assert identity not in identities and key not in keys
    identities.add(identity)
    keys.add(key)
    if -125 <= lon <= -66 and 24 <= lat <= 50:
        bins[f'{math.floor(lon/5)*5},{math.floor(lat/5)*5}'] += 1
catalog = {
    'attribution': '© OpenStreetMap contributors',
    'copyrightUrl': 'https://www.openstreetmap.org/copyright',
    'license': 'ODbL 1.0',
    'licenseUrl': 'https://opendatacommons.org/licenses/odbl/1-0/',
    **catalog,
}
asset = (json.dumps(catalog, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode()
output = REPO / 'public/places/fuel-us-v1.json'
output.parent.mkdir(parents=True, exist_ok=True)
if output.exists():
    assert output.read_bytes() == asset
else:
    with output.open('xb') as stream:
        stream.write(asset)
print(json.dumps({'publicFile': str(output.relative_to(REPO)), 'bytes': len(asset),
                  'sha256': hashlib.sha256(asset).hexdigest(),
                  'locations': len(points), 'conusRectangleLocations': sum(bins.values()),
                  'fiveDegreeBinsInConusRectangle': len(bins)}))
