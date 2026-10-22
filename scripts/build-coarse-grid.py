"""Build the small, road-informed lower-48 grid from pinned public-domain inputs.

This is a geographic approximation: cells merge nearby roads and overland access
is estimated. It is deliberately separate from the detailed routing experiment.
"""

import base64
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/coarse-sources/natural-earth-v5.1.2"
OUTPUT = ROOT / "src/server/data/coarse-grid-v1.json"
HASHES = {
    "countries": "239eec57ac17f100a11e2536cffc56752c318b50ae765b0918ff7aab4ce8f255",
    "lakes": "2d036f53dedec578001c5c30c2959ee7d4eebc1306900fa4367c49929ec8f2d9",
    "roads": "66a0c7b438e92fd124822cc5921cfa11042f48c294ade5e0f03f2c6640fd0248",
}
WEST, SOUTH, EAST, NORTH, STEP = -125, 24, -66, 50, 0.1
WIDTH, HEIGHT = round((EAST - WEST) / STEP), round((NORTH - SOUTH) / STEP)
SIZE = WIDTH * HEIGHT
# Store each undirected link once: east, northeast, north, northwest.
DIRECTIONS = {(1, 0): 0, (1, 1): 1, (0, 1): 2, (-1, 1): 3}
SPEEDS = {"Major Highway": 90, "Beltway": 80, "Bypass": 70,
          "Secondary Highway": 65, "Road": 45}


def load(name):
    path = SOURCE / f"{name}.geojson"
    if not path.exists():
        raise ValueError(f"Missing {path}; see docs/local-development.md for source downloads")
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != HASHES[name]:
            raise ValueError(f"Pinned source differs: {name}")
    return json.loads(path.read_text())["features"]


def polygons(geometry):
    return [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]


def rasterize(polygon):
    """Even-odd scanline fill, including holes, at cell centers."""
    result = []
    low = max(0, math.floor((min(p[1] for p in polygon[0]) - SOUTH) / STEP))
    high = min(HEIGHT, math.ceil((max(p[1] for p in polygon[0]) - SOUTH) / STEP))
    for y in range(low, high):
        lat = SOUTH + (y + 0.5) * STEP
        crossings = []
        for ring in polygon:
            for a, b in zip(ring, ring[1:]):
                if (a[1] > lat) != (b[1] > lat):
                    crossings.append(a[0] + (lat - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
        crossings.sort()
        for left, right in zip(crossings[::2], crossings[1::2]):
            start = max(0, math.ceil((left - WEST) / STEP - 0.5))
            stop = min(WIDTH, math.ceil((right - WEST) / STEP - 0.5))
            result.extend(y * WIDTH + x for x in range(start, stop))
    return result


def simplify(ring, tolerance=0.005):
    # Retain a compact geographic boundary for origin validation, separately from
    # the grid's cell-center land mask. Natural Earth is already generalized.
    kept = [ring[0]]
    for point in ring[1:-1]:
        if math.hypot(point[0] - kept[-1][0], point[1] - kept[-1][1]) >= tolerance:
            kept.append(point)
    kept.append(kept[0])
    return [[round(x, 5), round(y, 5)] for x, y in kept] if len(kept) >= 4 else ring


def inside_bounds(point):
    return WEST <= point[0] < EAST and SOUTH <= point[1] < NORTH


def cell(point):
    return math.floor((point[0] - WEST) / STEP), math.floor((point[1] - SOUTH) / STEP)


def main():
    countries = load("countries")
    usa = next(row for row in countries if row["properties"]["ADM0_A3"] == "USA")
    boundary = [poly for poly in polygons(usa["geometry"])
                if any(inside_bounds(point) for point in poly[0])]
    land = bytearray(SIZE)
    for polygon in boundary:
        for index in rasterize(polygon):
            land[index] = 1
    lakes, lake_boundary = load("lakes"), []
    for row in lakes:
        for polygon in polygons(row["geometry"]):
            if not any(inside_bounds(p) for p in polygon[0]):
                continue
            indexes = rasterize(polygon)
            if any(land[index] for index in indexes):
                lake_boundary.append([simplify(ring) for ring in polygon])
            for index in indexes:
                land[index] = 0
    roads = load("roads")
    links = bytearray(SIZE * 4)
    traversable = bytearray(land)
    used = 0
    for row in roads:
        props = row["properties"]
        if props["sov_a3"] != "USA" or props["type"] not in SPEEDS:
            continue
        speed = SPEEDS[props["type"]]
        paths = [row["geometry"]["coordinates"]] if row["geometry"]["type"] == "LineString" else row["geometry"]["coordinates"]
        used_here = False
        for path in paths:
            previous = None
            for a, b in zip(path, path[1:]):
                count = max(1, math.ceil(max(abs(b[0]-a[0]), abs(b[1]-a[1])) / (STEP / 4)))
                for part in range(count + 1):
                    point = [a[k] + (b[k] - a[k]) * part / count for k in (0, 1)]
                    if not inside_bounds(point):
                        previous = None
                        continue
                    current = cell(point)
                    if previous is not None and current != previous:
                        dx, dy = current[0]-previous[0], current[1]-previous[1]
                        start, delta = previous, (dx, dy)
                        if delta not in DIRECTIONS:
                            start, delta = current, (-dx, -dy)
                        if delta in DIRECTIONS:
                            i, j = previous[1]*WIDTH+previous[0], current[1]*WIDTH+current[0]
                            # Road-only water cells allow generalized bridge alignments.
                            # They never gain general overland neighbors or filled area.
                            traversable[i] = traversable[j] = 1
                            key = (start[1]*WIDTH+start[0])*4+DIRECTIONS[delta]
                            links[key] = max(links[key], speed)
                            used_here = True
                    previous = current
        used += used_here
    result = {
        "version": "natural-earth-5.1.2-road-grid-v1", "bounds": [WEST, SOUTH, EAST, NORTH],
        "step": STEP, "width": WIDTH, "height": HEIGHT, "localSpeedKph": 25,
        "roadSpeedsKph": SPEEDS, "roadFeatures": used, "landCells": sum(land),
        "roadLinks": sum(bool(speed) for speed in links),
        "land": base64.b64encode(land).decode(),
        "traversable": base64.b64encode(traversable).decode(),
        "links": base64.b64encode(links).decode(),
        "boundary": [[simplify(ring) for ring in poly] for poly in boundary],
        "lakes": lake_boundary,
        "sources": {name: {"url": f"https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_{'admin_0_countries' if name == 'countries' else name}.geojson", "sha256": value} for name, value in HASHES.items()},
        "sourceRelease": "Natural Earth v5.1.2; generalized cartographic roads, not a current routable road inventory",
        "license": "Public domain", "attribution": "Made with Natural Earth",
    }
    OUTPUT.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    print(json.dumps({"output": str(OUTPUT.relative_to(ROOT)), "bytes": OUTPUT.stat().st_size,
                      **{key: result[key] for key in ("landCells", "roadFeatures", "roadLinks")}}, indent=2))


if __name__ == "__main__":
    main()
