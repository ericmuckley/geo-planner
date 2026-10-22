"""Add geometry-based road times and road-supported shore cells to the v1 grid.

The original artifact remains an immutable comparison input. No source download
or detailed graph build is part of this small, standard-library-only builder.
"""

import argparse
import base64
import hashlib
import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "src/server/data/coarse-grid-v1.json"
BASE_SHA256 = "7dfd3b30965c21a57fcca408a97a4d95e455bda33d09ecc7a29953346c23d8c4"
SOURCE = ROOT / "data/coarse-sources/natural-earth-v5.1.2"
DIRECTIONS = {(1, 0): 0, (1, 1): 1, (0, 1): 2, (-1, 1): 3}


def distance_km(a, b):
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(math.radians(b[0] - a[0]) / 2) ** 2
    return 12742 * math.asin(min(1, math.sqrt(h)))


def polygons(geometry):
    return [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]


def edge_rows(shapes, south, step, height):
    """Index polygon edges by latitude band for the few road-only water cells."""
    rows = [[] for _ in range(height)]
    for number, polygon in enumerate(shapes):
        for ring in polygon:
            for a, b in zip(ring, ring[1:]):
                if a[1] == b[1]:
                    continue
                start = max(0, math.floor((min(a[1], b[1]) - south) / step))
                stop = min(height, math.floor((max(a[1], b[1]) - south) / step) + 1)
                for row in range(start, stop):
                    rows[row].append((number, a, b))
    return rows


def contains(point, edges):
    x, y = point
    inside = set()
    for number, a, b in edges:
        if (a[1] > y) != (b[1] > y) and x < a[0] + (y-a[1]) * (b[0]-a[0]) / (b[1]-a[1]):
            if number in inside:
                inside.remove(number)
            else:
                inside.add(number)
    return bool(inside)


def road_visits(path, bounds, step, width, on_point):
    """Cell visits carry cumulative road distance at their first/last samples."""
    west, south, east, north = bounds
    visits, previous, traveled = [], None, 0.0
    for a, b in zip(path, path[1:]):
        count = max(1, math.ceil(max(abs(b[0]-a[0]), abs(b[1]-a[1])) / (step / 4)))
        for part in range(count + 1):
            point = [a[k] + (b[k]-a[k]) * part / count for k in (0, 1)]
            if previous is not None:
                traveled += distance_km(previous, point)
            previous = point
            if not (west <= point[0] < east and south <= point[1] < north):
                if visits and visits[-1] is not None:
                    visits.append(None)
                continue
            x, y = math.floor((point[0]-west) / step), math.floor((point[1]-south) / step)
            cell = y * width + x
            on_point(point, cell, y)
            if visits and visits[-1] is not None and visits[-1][0] == cell:
                visits[-1][2] = traveled
            else:
                visits.append([cell, traveled, traveled])
    return visits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="src/server/data/coarse-grid-v2.json")
    args = parser.parse_args()
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_SHA256, "Original v1 artifact changed"
    data = json.loads(BASE.read_text())

    def load(name):
        path = SOURCE / f"{name}.geojson"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == data["sources"][name]["sha256"], f"Pinned {name} source differs"
        return json.loads(path.read_text())["features"]

    west, south, _, _ = data["bounds"]
    width, height, step = data["width"], data["height"], data["step"]
    size = width * height
    land = base64.b64decode(data["land"])
    display_land = bytearray(land)
    times = [0] * (size * 4)
    usa = next(row for row in load("countries") if row["properties"]["ADM0_A3"] == "USA")
    country_edges = edge_rows(polygons(usa["geometry"]), south, step, height)
    lake_shapes = [poly for row in load("lakes") for poly in polygons(row["geometry"])]
    lake_edges = edge_rows(lake_shapes, south, step, height)

    def on_point(point, cell, row):
        if not display_land[cell] and contains(point, country_edges[row]) and not contains(point, lake_edges[row]):
            display_land[cell] = 1

    for road in load("roads"):
        props = road["properties"]
        if props["sov_a3"] != "USA" or props["type"] not in data["roadSpeedsKph"]:
            continue
        speed = data["roadSpeedsKph"][props["type"]]
        geometry = road["geometry"]
        paths = [geometry["coordinates"]] if geometry["type"] == "LineString" else geometry["coordinates"]
        for path in paths:
            visits = road_visits(path, data["bounds"], step, width, on_point)
            for a, b in zip(visits, visits[1:]):
                if a is None or b is None:
                    continue
                delta = (b[0] % width - a[0] % width, b[0] // width - a[0] // width)
                start = a[0]
                if delta not in DIRECTIONS:
                    start, delta = b[0], (-delta[0], -delta[1])
                assert delta in DIRECTIONS, "Road sampling skipped a neighboring cell"
                # Midpoints along the road replace the artificial center-to-center
                # zigzag. Junctions/nearby roads still merge within each coarse cell.
                km = (b[1] + b[2] - a[1] - a[2]) / 2
                deciseconds = max(1, round(km / speed * 36000))
                assert deciseconds <= 65535, "Road step does not fit the encoded time"
                key = start * 4 + DIRECTIONS[delta]
                times[key] = min(times[key], deciseconds) if times[key] else deciseconds

    original_links = base64.b64decode(data["links"])
    assert all(bool(a) == bool(b) for a, b in zip(original_links, times)), "v2 changed road connectivity"
    data.update({
        "version": "natural-earth-5.1.2-road-grid-v2",
        "roadDeciseconds": base64.b64encode(struct.pack(f"<{len(times)}H", *times)).decode(),
        "displayLand": base64.b64encode(display_land).decode(),
        "shoreRoadCells": sum(display_land) - sum(land),
        "roadCostModel": "Road-geometry distance between consecutive cell-visit midpoints; unchanged class speeds; minimum 0.1 second per link; within-cell roads merge",
        "baseArtifactSha256": BASE_SHA256,
    })
    output = ROOT / args.output
    assert output.resolve() != BASE.resolve(), "Never overwrite the v1 comparison artifact"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(json.dumps({"output": str(output.relative_to(ROOT)), "bytes": output.stat().st_size,
                      "roadLinks": data["roadLinks"], "shoreRoadCells": data["shoreRoadCells"],
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}, indent=2))


if __name__ == "__main__":
    main()
