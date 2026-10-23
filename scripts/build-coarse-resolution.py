"""Build a fresh configurable-resolution NE+Census candidate; never activate it."""

import argparse
from array import array
import base64
from collections import Counter
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import resource
import sys
import time

from coarse_census import ROOT, SPEEDS, checked_file, load_tool, part_key, road_parts


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


# Reuse pure helpers; do not mutate or rerun sealed historical producers.
original = module("resolution_sources", "build-coarse-grid.py")
augmentation = module("resolution_augmentation", "build-coarse-augmentation.py")
v2, v3, v4 = augmentation.v4.v2, augmentation.v3, augmentation.v4
BASE_SHA256 = "b5a53b44fa42073e22575203d4848c7c6185e8eebd4688b504cefa04ff441cd4"


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(values):
    if isinstance(values, array) and sys.byteorder != "little":
        values = values[:]
        values.byteswap()
    return base64.b64encode(values).decode()


def rasterize(polygon, bounds, step, width, height):
    """Even-odd center sampling, with holes, at the requested resolution."""
    west, south, _, _ = bounds
    low = max(0, math.floor((min(p[1] for p in polygon[0]) - south) / step))
    high = min(height, math.ceil((max(p[1] for p in polygon[0]) - south) / step))
    for y in range(low, high):
        latitude = south + (y + .5) * step
        crossings = sorted(a[0] + (latitude - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                           for ring in polygon for a, b in zip(ring, ring[1:])
                           if (a[1] > latitude) != (b[1] > latitude))
        for left, right in zip(crossings[::2], crossings[1::2]):
            start = max(0, math.ceil((left - west) / step - .5))
            stop = min(width, math.ceil((right - west) / step - .5))
            yield from range(y * width + start, y * width + stop)


def add_shores(data, land, traversable, display, offsets, geography):
    """Rebuild mixed-cell representatives and checked local links, as in v3."""
    bounds, step, width, height = data["bounds"], data["step"], data["width"], data["height"]
    west, south, east, north = bounds

    def center(cell):
        return [west + (cell % width + .5) * step, south + (cell // width + .5) * step]

    def position(cell):
        return [v + offsets[cell * 2 + k] / 100000 for k, v in enumerate(center(cell))]

    candidates, boundary_points = set(), {}
    for polygon in data["boundary"] + data["lakes"]:
        for ring in polygon:
            for a, b in zip(ring, ring[1:]):
                count = max(1, math.ceil(max(abs(a[0] - b[0]), abs(a[1] - b[1])) / (step / 4)))
                for part in range(count + 1):
                    p = [a[k] + (b[k] - a[k]) * part / count for k in (0, 1)]
                    if not (west <= p[0] < east and south <= p[1] < north):
                        continue
                    x, y = math.floor((p[0] - west) / step), math.floor((p[1] - south) / step)
                    boundary_points.setdefault(y * width + x, []).append(p)
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            if 0 <= x + dx < width and 0 <= y + dy < height:
                                candidates.add((y + dy) * width + x + dx)
    added = 0
    for cell in sorted(candidates):
        if traversable[cell]:
            continue
        c = center(cell)
        points = [[c[0] + dx * step, c[1] + dy * step]
                  for dx in (-.4, -.2, 0, .2, .4) for dy in (-.4, -.2, 0, .2, .4)]
        for p in boundary_points.get(cell, []):
            points.extend([[p[0] + dx * .0001, p[1] + dy * .0001]
                           for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]])
        points = [p for p in points if abs(p[0] - c[0]) < step / 2 and abs(p[1] - c[1]) < step / 2]
        points.sort(key=lambda p: v2.distance_km(c, p))
        for p in points:
            delta = [round((p[k] - c[k]) * 100000) for k in (0, 1)]
            if geography.on_land([c[k] + delta[k] / 100000 for k in (0, 1)]):
                offsets[cell * 2:cell * 2 + 2] = array("h", delta)
                traversable[cell] = display[cell] = 1
                added += 1
                break
    shore_links = bytearray(width * height)
    for cell in range(width * height):
        if not traversable[cell]:
            continue
        x, y = cell % width, cell // width
        for direction, (dx, dy) in enumerate(v3.DIRECTIONS):
            if not (0 <= x + dx < width and 0 <= y + dy < height):
                continue
            target = (y + dy) * width + x + dx
            if traversable[target] and not (land[cell] and land[target]) and geography.land_segment(position(cell), position(target)):
                shore_links[cell] |= 1 << direction
    return shore_links, added


def visit_row(visit, speed, center, offset, step):
    anchor, points = v4.visit_geometry(visit, center, offset)
    assert all(abs(value) <= step * 50000 + 1 for p in points for value in p)
    return {"cell": visit[0], "speedKph": speed, "anchorIndex": anchor, "offsets": points}


def build(step, source_manifest, tool_lock, output):
    started = time.perf_counter()
    output = output.resolve()
    base_raw = (ROOT / "src/server/data/coarse-grid-v5.json").read_bytes()
    assert sha256(base_raw) == BASE_SHA256, "Preserve the v5 comparison artifact"
    baseline = json.loads(base_raw)
    bounds = baseline["bounds"]
    west, south, east, north = bounds
    assert 0 < step <= .1
    width, height = round((east - west) / step), round((north - south) / step)
    assert abs(width * step - (east - west)) < 1e-9 and abs(height * step - (north - south)) < 1e-9
    size = width * height
    manifest_raw = source_manifest.read_bytes()
    manifest = json.loads(manifest_raw)
    assert manifest["release"] == "TIGER/Line 2026" and len(manifest["sources"]) == 49
    checked_file(manifest["catalog"])
    sources = sorted(manifest["sources"], key=lambda source: source["sha256"])
    assert len({s["sha256"] for s in sources}) == 49
    shapefile, tool = load_tool(tool_lock)
    assert output.resolve().is_relative_to((ROOT / "data/coarse-quality").resolve())
    output.mkdir()  # Refuse overwrites, including failed attempts.
    inside = lambda p: west <= p[0] < east and south <= p[1] < north
    usa = next(row for row in original.load("countries") if row["properties"]["ADM0_A3"] == "USA")
    country = [p for p in original.polygons(usa["geometry"]) if any(inside(x) for x in p[0])]
    land = bytearray(size)
    for polygon in country:
        for cell in rasterize(polygon, bounds, step, width, height):
            land[cell] = 1
    lakes = []
    for feature in original.load("lakes"):
        for polygon in original.polygons(feature["geometry"]):
            if not any(inside(p) for p in polygon[0]):
                continue
            cells = list(rasterize(polygon, bounds, step, width, height))
            if any(land[cell] for cell in cells):
                lakes.append([original.simplify(ring) for ring in polygon])
            for cell in cells:
                land[cell] = 0
    data = {"bounds": bounds, "step": step, "width": width, "height": height,
            "boundary": [[original.simplify(ring) for ring in p] for p in country], "lakes": lakes}
    del usa, country, baseline, base_raw
    geography = v3.Geography(data["boundary"], lakes, south, step, height)
    display, traversable = bytearray(land), bytearray(land)
    offsets, times = array("h", [0]) * (size * 2), array("H", [0]) * (size * 4)
    links = bytearray(size * 4)

    def center(cell):
        return [west + (cell % width + .5) * step, south + (cell // width + .5) * step]

    def position(cell):
        return [v + offsets[cell * 2 + k] / 100000 for k, v in enumerate(center(cell))]

    def on_point(point, cell, _row):
        if not display[cell] and geography.on_land(point):
            display[cell] = 1

    owners, priorities, edges = {}, {}, []
    for road in original.load("roads"):
        props = road["properties"]
        if props["sov_a3"] != "USA" or props["type"] not in v2.ROAD_SPEEDS:
            continue
        speed = v2.ROAD_SPEEDS[props["type"]]
        geometry = road["geometry"]
        paths = [geometry["coordinates"]] if geometry["type"] == "LineString" else geometry["coordinates"]
        for path in paths:
            visits = v2.road_visits(path, bounds, step, width, on_point)
            for visit in visits:
                if visit is None:
                    continue
                cell = visit[0]
                priority = (speed, visit[2] - visit[1])
                if priority > priorities.get(cell, (-1, -1)):
                    priorities[cell], owners[cell] = priority, (speed, visit)
            for key, a, b in augmentation.visit_edges(visits, width):
                traversable[a[0]] = traversable[b[0]] = 1
                edges.append((key, a[0], b[0], v2.visit_point(a), v2.visit_point(b), augmentation.bounded_arc_km(a, b), speed))
    for cell, (_, visit) in owners.items():
        c, p = center(cell), v2.visit_point(visit)
        offsets[cell * 2:cell * 2 + 2] = array("h", [round((p[k] - c[k]) * 100000) for k in (0, 1)])
    proofs = {}
    for key, a, b, pa, pb, road_km, speed in edges:
        anchor_a, anchor_b = position(a), position(b)
        local_km = v2.distance_km(anchor_a, pa) + v2.distance_km(pb, anchor_b)
        cost = v2.road_time(anchor_a, anchor_b, pa, pb, road_km, speed)
        if not times[key] or cost < times[key]:
            times[key], links[key] = cost, speed
            proofs[key] = {"key": key, "a": a, "b": b, "pointA": pa, "pointB": pb,
                           "roadKm": road_km, "localKm": local_km, "speedKph": speed,
                           "deciseconds": cost, "kind": "natural-earth"}
    del edges, priorities
    road_visits, access = [], {}
    for cell, (speed, visit) in sorted(owners.items()):
        if not traversable[cell]:
            continue
        c, anchor = center(cell), position(cell)
        row = visit_row(visit, speed, c, offsets[cell * 2:cell * 2 + 2], step)
        if len(row["offsets"]) >= 2:
            road_visits.append(row)
        midpoint, middle = v2.visit_point(visit), (visit[1] + visit[2]) / 2
        for distance, point in visit[3]:
            p = [round(value, 5) for value in point]
            if not geography.on_land(p) or geography.land_segment(p, anchor):
                continue
            km = math.ceil((abs(distance - middle) + v2.distance_km(anchor, midpoint) + v2.distance_km(point, p)) * 1000) / 1000
            assert km + 1e-6 >= v2.distance_km(p, anchor)
            key = (cell, *p)
            access[key] = min(access.get(key, math.inf), km)
    del owners
    print(f"Natural Earth rebuilt: {size} cells, {len(road_visits)} owner visits", file=sys.stderr, flush=True)
    shore_links, shore_added = add_shores(data, land, traversable, display, offsets, geography)
    supplemental, priorities, seen = {}, {}, set()
    counts = Counter()
    for partition, source in enumerate(sources):
        for part in road_parts(source, shapefile):
            counts["sourceParts"] += 1
            counts["sourcePoints"] += len(part["points"])
            identity = part_key(part)
            if identity in seen:
                counts["duplicateParts"] += 1
                continue
            seen.add(identity)
            speed = SPEEDS[part["class"]]
            visits = v2.road_visits(part["points"], bounds, step, width, lambda *_: None)
            for visit in visits:
                if visit is None or not traversable[visit[0]]:
                    continue
                cell = visit[0]
                priority = (speed, visit[2] - visit[1])
                if priority <= priorities.get(cell, (-1, -1)):
                    continue
                c, midpoint = center(cell), v2.visit_point(visit)
                delta = [round((midpoint[k] - c[k]) * 100000) for k in (0, 1)]
                if not geography.land_segment([c[k] + delta[k] / 100000 for k in (0, 1)], position(cell)):
                    counts["visitRejectedTransfer"] += 1
                    continue
                row = visit_row(visit, speed, c, delta, step)
                if len(row["offsets"]) >= 2:
                    priorities[cell], supplemental[cell] = priority, row
            for key, a, b in augmentation.visit_edges(visits, width):
                if not traversable[a[0]] or not traversable[b[0]]:
                    counts["edgeRejectedUntraversable"] += 1
                    continue
                pa, pb = v2.visit_point(a), v2.visit_point(b)
                road_km = augmentation.bounded_arc_km(a, b)
                result = augmentation.charged_edge(position(a[0]), position(b[0]), pa, pb, road_km, speed, geography)
                if result is None:
                    counts["edgeRejectedTransfer"] += 1
                    continue
                cost, local_km = result
                if not times[key] or cost < times[key]:
                    times[key], links[key] = cost, speed
                    proofs[key] = {"key": key, "a": a[0], "b": b[0], "pointA": pa, "pointB": pb,
                                   "roadKm": road_km, "localKm": local_km, "speedKph": speed,
                                   "deciseconds": cost, "kind": "census"}
        if partition % 10 == 0 or partition == len(sources) - 1:
            print(f"Census partitions {partition + 1}/{len(sources)}", file=sys.stderr, flush=True)
    data.update({
        "version": f"natural-earth-census-2026-resolution-{step:g}-v1",
        "localSpeedKph": 25, "roadSpeedsKph": v2.ROAD_SPEEDS, "censusRoadSpeedsKph": SPEEDS,
        "land": encode(land), "traversable": encode(traversable), "displayLand": encode(display),
        "links": encode(links), "roadDeciseconds": encode(times), "anchorOffsets": encode(offsets),
        "shoreLinks": encode(shore_links), "roadAccess": [[*key, km] for key, km in sorted(access.items())],
        "roadVisits": augmentation.pack_visits(road_visits),
        "supplementalRoadVisits": augmentation.pack_visits([row for _, row in sorted(supplemental.items())]),
        "landCells": sum(land), "roadLinks": sum(bool(t) for t in times),
        "shoreLandCells": shore_added, "shoreLocalLinks": sum(v.bit_count() for v in shore_links),
        "sources": {name: {"url": f"https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_{'admin_0_countries' if name == 'countries' else name}.geojson", "sha256": value} for name, value in original.HASHES.items()},
        "censusSources": sources, "censusSourceManifestSha256": sha256(manifest_raw),
        "sourceRelease": "Natural Earth v5.1.2 + U.S. Census Bureau 2026 TIGER/Line primary and secondary roads; derived coarse grid, not a routable road inventory",
        "license": "Natural Earth: public domain. U.S. Census Bureau TIGER/Line: U.S. government work, freely reproducible; TIGER/Line is a registered trademark of the U.S. Census Bureau.",
        "attribution": "Made with Natural Earth and U.S. Census Bureau 2026 TIGER/Line data. Geo Planner has modified and repackaged Census data into a coarse travel model. This product is not an official Census Bureau product; the Census Bureau has not reviewed or endorsed these estimates.",
        "resolutionModel": "Masks, anchors, shore/access links and source visits rebuilt at the stated step. Same assumed speeds, one NE owner and one Census visit per cell. NE legacy connectors pay road-class speed; Census connectors require continuous land and pay 25 km/h. Source arcs retain bends and a physical chord lower bound. No traffic/turn/access/grade topology or national accuracy qualification.",
    })
    artifact = (json.dumps(data, separators=(",", ":")) + "\n").encode()
    (output / "grid.json").write_bytes(artifact)
    proof_bytes = gzip.compress((json.dumps([proofs[key] for key in sorted(proofs)], separators=(",", ":")) + "\n").encode(), mtime=0)
    (output / "links.json.gz").write_bytes(proof_bytes)
    report = {"artifact": str((output / "grid.json").relative_to(ROOT)), "artifactSha256": sha256(artifact),
              "artifactBytes": len(artifact), "step": step, "width": width, "height": height,
              "landCells": sum(land), "roadLinks": len(proofs), "roadVisits": len(road_visits),
              "supplementalVisits": len(supplemental), "supplementalPoints": sum(len(row["offsets"]) for row in supplemental.values()),
              "shoreLandCells": shore_added, "shoreLocalLinks": data["shoreLocalLinks"], "counts": dict(counts),
              "linkProof": {"path": str((output / "links.json.gz").relative_to(ROOT)), "sha256": sha256(proof_bytes), "bytes": len(proof_bytes)},
              "sourceManifestSha256": sha256(manifest_raw), "tool": tool,
              "wallSeconds": time.perf_counter() - started, "processMaxRssNative": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "platform": sys.platform, "scope": "New offline resolution candidate, no activation/download/reference/service. RSS is whole producer (native units: bytes on macOS, KiB on Linux), not runtime/Vercel memory. Original artifacts/producers remain unchanged."}
    (output / "build.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", type=float, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--tool-lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.step, args.source_manifest, args.tool_lock, args.output), indent=2))
