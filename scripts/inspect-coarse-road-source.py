"""Inspect a pinned Census road archive without changing the application dataset."""

import argparse
import base64
from collections import Counter
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("access", Path(__file__).with_name("build-coarse-grid-v4.py"))
access = importlib.util.module_from_spec(spec)
spec.loader.exec_module(access)


def checked_file(lock):
    path = ROOT / lock["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == lock["sha256"], f"Changed input: {path}"
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-lock", required=True)
    parser.add_argument("--tool-lock", required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    source = json.loads((ROOT / args.source_lock).read_text())
    tool = json.loads((ROOT / args.tool_lock).read_text())
    archive_path, wheel = checked_file(source), checked_file(tool)
    assert tool["name"] == "pyshp" and tool["version"] == "2.3.1"
    sys.path.insert(0, str(wheel))
    import shapefile

    baseline = json.loads((ROOT / "docs/evidence/coarse-access-2026-10-22/diagnostics.json").read_text())
    endpoints = [{"point": s["point"], "naturalEarthKm": s["nearestEligibleSourceRoad"]["approximateKm"], "nearest": None}
                 for s in baseline["endpointSourceCoverage"]]
    grid = json.loads((ROOT / "src/server/data/coarse-grid-v4.json").read_text())
    width, step = grid["width"], grid["step"]
    old_links = base64.b64decode(grid["links"])
    owners, priorities, links = {}, {}, set()
    classes = Counter()
    records = points_count = parts_count = 0
    speeds = {"S1100": 105, "S1200": 80}  # Existing class assumptions, not fitted here.
    with zipfile.ZipFile(archive_path) as archive:
        shp_name, = [name for name in archive.namelist() if name.endswith(".shp")]
        stem = shp_name[:-4]
        projection = archive.read(stem + ".prj").decode()
        assert 'GEOGCS["GCS_North_American_1983"' in projection, "Pilot requires geographic NAD83 input"
        reader = shapefile.Reader(shp=io.BytesIO(archive.read(shp_name)), dbf=io.BytesIO(archive.read(stem + ".dbf")))
        declared_records = len(reader)
        for feature in reader.iterShapeRecords():
            props = feature.record.as_dict()
            assert feature.shape.shapeType == shapefile.POLYLINE
            assert props["MTFCC"] in speeds, "Unexpected class in primary/secondary archive"
            records += 1
            classes[props["MTFCC"]] += 1
            speed = speeds[props["MTFCC"]]
            shape = feature.shape
            points_count += len(shape.points)
            breaks = list(shape.parts) + [len(shape.points)]
            for start, stop in zip(breaks, breaks[1:]):
                path = shape.points[start:stop]
                parts_count += 1
                visits = access.v2.road_visits(path, grid["bounds"], step, width, lambda *_: None)
                for visit in visits:
                    if visit is None:
                        continue
                    priority = (speed, visit[2] - visit[1])
                    if priority > priorities.get(visit[0], (-1, -1)):
                        priorities[visit[0]] = priority
                        owners[visit[0]] = (speed, visit)
                for a, b in zip(visits, visits[1:]):
                    if a is None or b is None:
                        continue
                    dx, dy = b[0] % width - a[0] % width, b[0] // width - a[0] // width
                    cell = a[0]
                    if (dx, dy) not in access.v2.DIRECTIONS:
                        cell, dx, dy = b[0], -dx, -dy
                    links.add(cell * 4 + access.v2.DIRECTIONS[(dx, dy)])
                for endpoint in endpoints:
                    point = endpoint["point"]
                    lon, lat = point["lon"], point["lat"]
                    west, south, east, north = shape.bbox
                    if not (west - .75 <= lon <= east + .75 and south - .75 <= lat <= north + .75):
                        continue
                    scale = math.cos(math.radians(lat))
                    for a, b in zip(path, path[1:]):
                        if not (min(a[0], b[0]) - .75 <= lon <= max(a[0], b[0]) + .75 and min(a[1], b[1]) - .75 <= lat <= max(a[1], b[1]) + .75):
                            continue
                        dx, dy = (b[0] - a[0]) * scale, b[1] - a[1]
                        length = dx * dx + dy * dy
                        t = max(0, min(1, ((lon - a[0]) * scale * dx + (lat - a[1]) * dy) / length)) if length else 0
                        projected = [a[0] + (b[0] - a[0]) * t, a[1] + dy * t]
                        km = access.v2.distance_km([lon, lat], projected)
                        if endpoint["nearest"] is None or km < endpoint["nearest"]["approximateKm"]:
                            endpoint["nearest"] = {"approximateKm": km, "name": props["FULLNAME"], "class": props["MTFCC"], "sourceId": props["LINEARID"]}
        assert records == declared_records
    compact = []
    for cell, (speed, visit) in sorted(owners.items()):
        center = [grid["bounds"][0] + (cell % width + .5) * step, grid["bounds"][1] + (cell // width + .5) * step]
        p = access.v2.visit_point(visit)
        offset = [round((p[k] - center[k]) * 100000) for k in (0, 1)]
        anchor_index, coordinates = access.visit_geometry(visit, center, offset)
        if len(coordinates) >= 2:
            compact.append({"cell": cell, "speedKph": speed, "anchorIndex": anchor_index, "offsets": coordinates})
    print(json.dumps({
        "source": source, "tool": tool, "projection": projection,
        "records": records, "classes": dict(classes), "sourcePoints": points_count, "parts": parts_count,
        "gridRoadCells": len(owners), "gridRoadLinkSlots": len(links),
        "linkSlotsAbsentFromNaturalEarth": sum(not old_links[key] for key in links),
        "selectedVisits": len(compact), "selectedVisitPoints": sum(len(v["offsets"]) for v in compact),
        "selectedVisitJsonBytes": len(json.dumps(compact, separators=(",", ":")).encode()),
        "endpointCoverage": endpoints, "wallSeconds": time.perf_counter() - started,
        "scope": "One state source-coverage/raster-size pilot. NAD83 coordinates are used as geographic degrees for approximate nearest-segment observations, not survey-grade transformed positions or actual accessible-road snaps. Multipart boundaries remain separate. Grid links/selected visits are unmasked source candidates, not a routing graph or tested travel times. Regional bytes cannot establish nationwide bundle size. No runtime artifact, deployment or reference was changed; no routing request, traffic/turn/access inference, nationwide completeness or accuracy claim.",
    }, indent=2))


if __name__ == "__main__":
    main()
