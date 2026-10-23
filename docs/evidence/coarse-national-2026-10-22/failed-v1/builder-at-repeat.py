"""Offline Census augmentation of fixed v4 anchors; never activates the pilot."""

import argparse
import base64
from collections import Counter
import hashlib
import importlib.util
import json
import math
import struct
import sys
from pathlib import Path

from coarse_census import ROOT, SPEEDS, checked_file, load_tool, part_key, road_parts

BASE = ROOT / "src/server/data/coarse-grid-v4.json"
BASE_SHA256 = "6905fa38d198f6c89201fb731db484a1b7ff911078648c005165b5ba7be654f3"
spec = importlib.util.spec_from_file_location("v4", Path(__file__).with_name("build-coarse-grid-v4.py"))
v4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v4)
spec = importlib.util.spec_from_file_location("v3", Path(__file__).with_name("build-coarse-grid-v3.py"))
v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)


def pack_visits(visits):
    """Lossless relative to the existing 1e-5 degree quantized visit format."""
    cells, speeds, anchors, starts, offsets = bytearray(), bytearray(), bytearray(), bytearray(struct.pack("<I", 0)), bytearray()
    for visit in visits:
        cells.extend(struct.pack("<I", visit["cell"]))
        speeds.append(visit["speedKph"])
        anchors.extend(struct.pack("<I", visit["anchorIndex"]))
        for point in visit["offsets"]:
            offsets.extend(struct.pack("<hh", *point))
        starts.extend(struct.pack("<I", len(offsets) // 4))

    def encode(values):
        return base64.b64encode(values).decode()

    return {"encoding": "cell-visits-le-v1", "cells": encode(cells),
            "speeds": encode(speeds), "anchors": encode(anchors),
            "starts": encode(starts), "offsets": encode(offsets)}


def visit_edges(visits, width):
    """Union partition edges at shared canonical cells, never join separate parts."""
    for a, b in zip(visits, visits[1:]):
        if a is None or b is None:
            continue
        delta = (b[0] % width - a[0] % width, b[0] // width - a[0] // width)
        start = a[0]
        if delta not in v4.v2.DIRECTIONS:
            start, delta = b[0], (-delta[0], -delta[1])
        assert delta in v4.v2.DIRECTIONS, "Road sampling skipped a neighboring cell"
        yield start * 4 + v4.v2.DIRECTIONS[delta], a, b


def charged_edge(anchor_a, anchor_b, point_a, point_b, road_km, speed, geography):
    # Only an explicit source arc may cross water. Transfers to the unchanged
    # canonical positions must be continuous land, paid at the local speed.
    if not geography.land_segment(anchor_a, point_a) or not geography.land_segment(point_b, anchor_b):
        return None
    local_km = v4.v2.distance_km(anchor_a, point_a) + v4.v2.distance_km(point_b, anchor_b)
    cost = max(1, math.ceil((local_km / 25 + road_km / speed) * 36000))
    assert cost / 36000 * 105 + 1e-6 >= v4.v2.distance_km(anchor_a, anchor_b)
    assert cost <= 65535, "Source step exceeds the encoded road-time range"
    return cost, local_km


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-lock", action="append", default=[])
    parser.add_argument("--source-manifest")
    parser.add_argument("--deduplicate", action="store_true", help="Exact geometry/class dedup; always enabled for a national manifest")
    parser.add_argument("--tool-lock", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = ROOT / args.output
    assert output.resolve().is_relative_to((ROOT / "data/coarse-quality").resolve()), "Keep offline candidates outside production data"
    assert not output.exists(), "Use a fresh output; preserve prior candidates"
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_SHA256
    data = json.loads(BASE.read_text())
    sources = [json.loads((ROOT / path).read_text()) for path in args.source_lock]
    if args.source_manifest:
        manifest_bytes = (ROOT / args.source_manifest).read_bytes()
        manifest = json.loads(manifest_bytes)
        assert manifest["release"] == "TIGER/Line 2026" and len(manifest["sources"]) == 49
        checked_file(manifest["catalog"])
        sources.extend(manifest["sources"])
    assert sources, "Pass source locks or a national source manifest"
    sources.sort(key=lambda row: row["sha256"])
    assert len({s["sha256"] for s in sources}) == len(sources), "Duplicate source partition"
    shapefile, tool = load_tool(args.tool_lock)
    width, height, step = data["width"], data["height"], data["step"]
    size = width * height
    traversable = base64.b64decode(data["traversable"])
    offsets = struct.unpack(f"<{size * 2}h", base64.b64decode(data["anchorOffsets"]))
    times = list(struct.unpack(f"<{size * 4}H", base64.b64decode(data["roadDeciseconds"])))
    links = bytearray(base64.b64decode(data["links"]))
    geography = v3.Geography(data["boundary"], data["lakes"], data["bounds"][1], step, height)

    def center(cell):
        return [data["bounds"][0] + (cell % width + .5) * step,
                data["bounds"][1] + (cell // width + .5) * step]

    def position(cell):
        p = center(cell)
        return [p[k] + offsets[cell * 2 + k] / 100000 for k in (0, 1)]

    owners, priorities, changed, seen_parts = {}, {}, {}, {}
    counts, classes = Counter(), Counter()
    partitions = []
    for source in sources:
        records = set()
        source_points = source_parts = duplicates = 0
        for part in road_parts(source, shapefile):
            records.add(part["record"])
            counts["parts"] += 1
            counts["sourcePoints"] += len(part["points"])
            source_parts += 1
            source_points += len(part["points"])
            classes[part["class"]] += 1
            if args.deduplicate or args.source_manifest:
                key = part_key(part)
                if key in seen_parts:
                    counts["duplicateParts"] += 1
                    counts["crossPartitionDuplicateParts"] += seen_parts[key] != source["sha256"]
                    duplicates += 1
                    continue
                seen_parts[key] = source["sha256"]
            speed = SPEEDS[part["class"]]
            visits = v4.v2.road_visits(part["points"], data["bounds"], step, width, lambda *_: None)
            for visit in visits:
                if visit is None:
                    continue
                cell = visit[0]
                if not traversable[cell]:
                    counts["visitRejectedUntraversable"] += 1
                    continue
                priority = (speed, visit[2] - visit[1])
                if priority <= priorities.get(cell, (-1, -1)):
                    continue
                c, midpoint = center(cell), v4.v2.visit_point(visit)
                delta = [round((midpoint[k] - c[k]) * 100000) for k in (0, 1)]
                quantized = [c[k] + delta[k] / 100000 for k in (0, 1)]
                if not geography.land_segment(quantized, position(cell)):
                    counts["visitRejectedTransfer"] += 1
                    continue
                anchor_index, points = v4.visit_geometry(visit, c, delta)
                if len(points) < 2:
                    continue
                priorities[cell] = priority
                owners[cell] = ({"cell": cell, "speedKph": speed, "anchorIndex": anchor_index,
                                 "offsets": points}, visit[2] - visit[1])
            for key, a, b in visit_edges(visits, width):
                counts["sourceEdgeVisits"] += 1
                if not traversable[a[0]] or not traversable[b[0]]:
                    counts["edgeRejectedUntraversable"] += 1
                    continue
                pa, pb = v4.v2.visit_point(a), v4.v2.visit_point(b)
                km = (b[1] + b[2] - a[1] - a[2]) / 2
                result = charged_edge(position(a[0]), position(b[0]), pa, pb, km, speed, geography)
                if result is None:
                    counts["edgeRejectedTransfer"] += 1
                    continue
                cost, local_km = result
                if not times[key] or cost < times[key]:
                    changed[key] = {"key": key, "a": a[0], "b": b[0], "pointA": pa, "pointB": pb,
                                    "roadKm": km, "localKm": local_km, "speedKph": speed,
                                    "deciseconds": cost, "sourceSha256": source["sha256"], "sourceId": part["id"], "part": part["part"]}
                    times[key], links[key] = cost, speed
        counts["records"] += len(records)
        partitions.append({"sourceSha256": source["sha256"], "records": len(records), "parts": source_parts,
                           "sourcePoints": source_points, "duplicateParts": duplicates})
        print(f"Processed partition {len(partitions)}/{len(sources)}: {Path(source['path']).name}; {len(records)} records, {source_points} points, {duplicates} exact duplicate parts", file=sys.stderr, flush=True)

    retained = [row for _, (row, _) in sorted(owners.items())]
    original_visits = data["roadVisits"]
    packed_base, packed_new = pack_visits(original_visits), pack_visits(retained)
    geometry_errors = []
    for cell, (row, original_km) in sorted(owners.items()):
        c = center(cell)
        points = [[c[k] + p[k] / 100000 for k in (0, 1)] for p in row["offsets"]]
        quantized_km = sum(v4.v2.distance_km(a, b) for a, b in zip(points, points[1:]))
        geometry_errors.append(quantized_km - original_km)
    data.update({
        "version": "natural-earth-census-2026-augmentation-pilot-v1",
        "baseArtifactSha256": BASE_SHA256,
        "links": base64.b64encode(links).decode(),
        "roadDeciseconds": base64.b64encode(struct.pack(f"<{len(times)}H", *times)).decode(),
        "roadVisits": packed_base,
        "supplementalRoadVisits": packed_new,
        "censusSources": sources,
        "censusRoadSpeedsKph": SPEEDS,
        "augmentationModel": "Offline partition pilot; fixed v4 anchors/masks/shore paths and all existing roads retained. Census source arcs plus continuous-land transfers to canonical anchors at 25 km/h; only lower edge costs retained. One supplemental source visit per cell by class speed then source arc length, with a checked paid transfer to the canonical anchor. Packed visits preserve every quantized bend. NAD83 used as approximate geographic degrees. No turn/access/grade topology inference; not activated or nationally qualified.",
    })
    if args.source_manifest:
        data.update({"version": "natural-earth-census-2026-augmentation-national-v1",
                     "censusSourceManifestSha256": hashlib.sha256(manifest_bytes).hexdigest(),
                     "augmentationModel": "All contiguous-US state partitions plus DC processed with exact direction-independent geometry/class deduplication; partition links share unchanged canonical grid anchors with paid continuous-land transfers at 25 km/h and source arcs at assumed class speeds. Natural Earth roads, masks, shores and owner visits retained. No turn/access/grade topology inference or driving accuracy qualification. Packed visits retain all quantized bends; NAD83 treated as approximate geographic degrees. Offline candidate, not activated."})
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(data, separators=(",", ":")) + "\n").encode()
    output.write_bytes(raw)
    original_times = struct.unpack(f"<{size * 4}H", base64.b64decode(json.loads(BASE.read_text())["roadDeciseconds"]))
    print(json.dumps({"artifact": str(output.relative_to(ROOT)), "artifactSha256": hashlib.sha256(raw).hexdigest(),
                      "artifactBytes": len(raw), "baseSha256": BASE_SHA256, "sources": sources, "tool": tool,
                      "counts": dict(counts), "classParts": dict(classes), "partitions": partitions,
                      "newLinkSlots": sum(not original_times[key] for key in changed),
                      "improvedExistingLinkSlots": sum(bool(original_times[key]) for key in changed),
                      "geometry": {"baseVisits": len(original_visits), "supplementalVisits": len(retained),
                                   "supplementalPoints": sum(len(row["offsets"]) for row in retained),
                                   "baseNaiveJsonBytes": len(json.dumps(original_visits, separators=(",", ":")).encode()),
                                   "basePackedJsonBytes": len(json.dumps(packed_base, separators=(",", ":")).encode()),
                                   "supplementalNaiveJsonBytes": len(json.dumps(retained, separators=(",", ":")).encode()),
                                   "supplementalPackedJsonBytes": len(json.dumps(packed_new, separators=(",", ":")).encode()),
                                   "quantizedVisitArcDeltaKm": sum(geometry_errors),
                                   "sumAbsoluteQuantizedVisitArcDeltaKm": sum(map(abs, geometry_errors)),
                                   "maxAbsoluteQuantizedVisitArcDeltaKm": max(map(abs, geometry_errors), default=0)},
                      "changedLinks": [changed[key] for key in sorted(changed)],
                      "scope": "Offline source partition augmentation, fixed anchors and paid land transfers; retains v4 even where Census is missing. Source/geometry bytes do not establish nationwide size or real driving accuracy. Original visits are losslessly packed; supplemental visits keep bends at the existing 1e-5 degree quantization. No hosted/reference calls or production activation."}, indent=2))


if __name__ == "__main__":
    main()
