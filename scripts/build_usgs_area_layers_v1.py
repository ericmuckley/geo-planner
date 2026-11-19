"""Prepare compact 2 km Web Mercator layers from the checked USGS exports."""
import hashlib
import json
import math
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'data/map-layers/usgs-area-v1'
OUTPUT = ROOT / 'public/overlays'
SIZE = (3350, 1900)
BOUNDS = (-14_000_000, 2_700_000, -7_300_000, 6_500_000)
SHA256 = {
    'pad-us.png': 'd43079f3eb6a8d1702c51183ef153fb94282b7d903edded88fba80af23fc723e',
    '3dep.tif': '5cbdc2ec3006ac7b0f9ea97358e0e6457d8cc341d318cce027b6da9f1319e8fc',
}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(image, filename):
    target = OUTPUT / filename
    with target.open('xb') as stream:
        image.save(stream, format='PNG', optimize=True)
    return {'bytes': target.stat().st_size, 'sha256': digest(target)}


def land():
    metadata = json.loads((INPUT / 'export.json').read_text())
    extent = metadata['extent']
    if (metadata['width'], metadata['height']) != SIZE or tuple(
        extent[key] for key in ('xmin', 'ymin', 'xmax', 'ymax')
    ) != BOUNDS or extent['spatialReference']['latestWkid'] != 3857:
        raise ValueError('Public lands export extent changed')
    with Image.open(INPUT / 'pad-us.png') as source:
        if source.mode != 'RGBA' or source.size != SIZE:
            raise ValueError('Unexpected PAD-US image')
        return source.getchannel('A').point([0] * 128 + [255] * 128, mode='1')


def elevation():
    with Image.open(INPUT / '3dep.tif') as source:
        if (
            source.mode != 'F' or source.size != SIZE
            or source.tag_v2[33550][:2] != (2000, 2000)
            or source.tag_v2[33922][3:5] != (BOUNDS[0], BOUNDS[3])
            or source.tag_v2[42113] != '-9999'
        ):
            raise ValueError('3DEP grid or nodata tag changed')
        data = bytearray(SIZE[0] * SIZE[1] * 3)
        valid = 0
        for i, meters in enumerate(source.getdata()):
            if not math.isfinite(meters) or meters == -9999:
                continue
            if not -1000 <= meters <= 6000:
                raise ValueError('3DEP value out of range')
            # Reserve zero for no data. The two channels preserve signed whole meters.
            encoded = round(meters) + 32768
            offset = i * 3
            data[offset] = encoded >> 8
            data[offset + 1] = encoded & 255
            valid += 1
    return Image.frombytes('RGB', SIZE, bytes(data)), valid


def main():
    for name, expected in SHA256.items():
        if digest(INPUT / name) != expected:
            raise ValueError(f'Source checksum mismatch for {name}')
    land_image = land()
    elevation_image, valid = elevation()
    count = land_image.convert('L').histogram()[255]
    print(json.dumps({
        'grid': {'bbox': BOUNDS, 'size': SIZE, 'projection': 'EPSG:3857'},
        'land': {**write(land_image, 'public-lands-us-v1.png'), 'sampledPixels': count},
        'elevation': {**write(elevation_image, 'elevation-us-v1.png'), 'sampledPixels': valid},
        'sourceSha256': SHA256,
    }, indent=2))


if __name__ == '__main__':
    main()
