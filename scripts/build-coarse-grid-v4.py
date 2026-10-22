"""Add compact source-road visits for charged input access; preserve the v3 graph."""

import argparse
import base64
import hashlib
import importlib.util
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "src/server/data/coarse-grid-v3.json"
BASE_SHA256 = "8cfa5616b52138c16d5a8cb8f84fd1ee4345f7e4026e88c104365cad25c523e0"
spec = importlib.util.spec_from_file_location("v2", Path(__file__).with_name("build-coarse-grid-v2.py"))
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)


def visit_geometry(visit, center, anchor_offset):
    """Keep every bend and insert the unchanged anchor at its source arc position."""
    middle = (visit[1] + visit[2]) / 2
    samples = [(distance, point, False) for distance, point in visit[3]]
    anchor = [center[k] + anchor_offset[k] / 100000 for k in (0, 1)]
    assert v2.distance_km(anchor, v2.visit_point(visit)) < .001
    samples.append((middle, anchor, True))
    samples.sort(key=lambda item: item[0])
    points, anchor_index = [], None
    for _, point, is_anchor in samples:
        offset = list(anchor_offset) if is_anchor else [round((point[k] - center[k]) * 100000) for k in (0, 1)]
        assert all(-5001 <= value <= 5001 for value in offset)
        if not points or points[-1] != offset:
            points.append(offset)
        if is_anchor:
            anchor_index = len(points) - 1
    assert anchor_index is not None and points[anchor_index] == list(anchor_offset)
    return anchor_index, points


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="src/server/data/coarse-grid-v4.json")
    args = parser.parse_args()
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_SHA256, "Preserve the v3 comparison input"
    data = json.loads(BASE.read_text())
    width, height, step = data["width"], data["height"], data["step"]
    west, south, _, _ = data["bounds"]
    offsets = struct.unpack(f"<{width * height * 2}h", base64.b64decode(data["anchorOffsets"]))
    # V3's new land representatives may overwrite positions in formerly
    # untraversable cells. Only pre-existing v2 cells retain source-road anchors.
    road_base = ROOT / "src/server/data/coarse-grid-v2.json"
    assert hashlib.sha256(road_base.read_bytes()).hexdigest() == data["baseArtifactSha256"]
    traversable = base64.b64decode(json.loads(road_base.read_text())["traversable"])
    source = v2.SOURCE / "roads.geojson"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == data["sources"]["roads"]["sha256"]
    owners, priorities = {}, {}
    for road in json.loads(source.read_text())["features"]:
        props = road["properties"]
        if props["sov_a3"] != "USA" or props["type"] not in data["roadSpeedsKph"]:
            continue
        speed = data["roadSpeedsKph"][props["type"]]
        geometry = road["geometry"]
        paths = [geometry["coordinates"]] if geometry["type"] == "LineString" else geometry["coordinates"]
        for path in paths:
            for visit in v2.road_visits(path, data["bounds"], step, width, lambda *_: None):
                if visit is None or not traversable[visit[0]]:
                    continue
                priority = (speed, visit[2] - visit[1])
                if priority > priorities.get(visit[0], (-1, -1)):
                    priorities[visit[0]] = priority
                    owners[visit[0]] = (speed, visit)
    visits = []
    for cell, (speed, visit) in sorted(owners.items()):
        center = [west + (cell % width + .5) * step, south + (cell // width + .5) * step]
        anchor_index, points = visit_geometry(visit, center, offsets[cell * 2:cell * 2 + 2])
        if len(points) >= 2:
            visits.append({"cell": cell, "speedKph": speed, "anchorIndex": anchor_index, "offsets": points})
    data.update({
        "version": "natural-earth-5.1.2-road-grid-v4",
        "roadVisits": visits,
        "attachmentModel": "Input-cell source visit owning the unchanged road anchor; local access to checked land points at 25 km/h plus quantized source-polyline distance to the anchor at its existing road class speed, rounded up to 0.1 second; v3 graph and legacy shore access unchanged",
        "baseArtifactSha256": BASE_SHA256,
    })
    output = ROOT / args.output
    assert output.name not in [f"coarse-grid-v{i}.json" for i in (1, 2, 3)], "Preserve comparison inputs"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(json.dumps({"output": str(output.relative_to(ROOT)), "bytes": output.stat().st_size,
                      "roadVisits": len(visits), "roadVisitPoints": sum(len(row["offsets"]) for row in visits),
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}, indent=2))


if __name__ == "__main__":
    main()
