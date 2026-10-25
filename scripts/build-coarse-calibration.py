"""Reprice all pinned source-road alternatives on unchanged v8 geometry."""

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

BASELINE = ROOT / "src/server/data/coarse-grid-v8.json"
BASELINE_SHA256 = "2beb2fb6d9af6e07f37c5ba53acdeca2da1334c31a5fadd1371efd5453134910"
MANIFEST_SHA256 = "c03379192c584e7b4fdd55ad6534ab9339db4551d5ee3720c7d12489990fb782"
SPEED_MAPPING = {55: 55, 80: 85, 90: 90, 105: 95}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(value, code="B"):
    raw = gzip.decompress(base64.b64decode(value[5:])) if value.startswith("gzip:") else base64.b64decode(value)
    values = array(code)
    values.frombytes(raw)
    if sys.byteorder != "little":
        values.byteswap()
    return values


def encode(values):
    if sys.byteorder != "little":
        values = values[:]
        values.byteswap()
    return "gzip:" + base64.b64encode(gzip.compress(values.tobytes(), mtime=0)).decode()


def price(road_km, connector_km, speed, legacy):
    """NE legacy connectors follow class speed; Census connectors stay at25."""
    hours = ((road_km + connector_km) / speed if legacy
               else connector_km / 25 + road_km / speed)
    result = max(1, math.ceil(hours * 36000))
    assert result <= 65535
    return result


def build(source_manifest, tool_lock, output):
    started = time.perf_counter()
    raw = BASELINE.read_bytes()
    assert sha(raw) == BASELINE_SHA256
    data = json.loads(raw)
    manifest_raw = source_manifest.read_bytes()
    assert sha(manifest_raw) == MANIFEST_SHA256 == data["censusSourceManifestSha256"]
    manifest = json.loads(manifest_raw)
    assert len(manifest["sources"]) == 49
    checked_file(manifest["catalog"])
    shapefile, tool = load_tool(tool_lock)
    output = output.resolve()
    assert output.is_relative_to((ROOT / "data/coarse-quality").resolve())
    output.mkdir()  # Never overwrite a completed or failed experiment.
    (output / "policy.json").write_text(json.dumps({"baselineSha256": BASELINE_SHA256,
        "speedMapping": SPEED_MAPPING, "localSpeedKph": 25,
        "scope": "Source-based costs only; all geometry/topology/owners frozen. No runtime activation or network."}, indent=2) + "\n")

    # Import pure geometry/charging helpers, without editing sealed producers.
    spec = importlib.util.spec_from_file_location("calibration_helpers", Path(__file__).with_name("build-coarse-augmentation.py"))
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    v2 = helpers.v4.v2
    width, height, step = data["width"], data["height"], data["step"]
    size = width * height
    traversable = decode(data["traversable"])
    base_offsets = decode(data["anchorOffsets"], "h")
    layer_offsets = decode(data["roadLayer"]["anchorOffsets"], "h")
    transfers = decode(data["roadLayer"]["transferDeciseconds"], "H")
    geography = helpers.v3.Geography(data["boundary"], data["lakes"], data["bounds"][1], step, height)
    original_base, original_layer = array("H", [0]) * (size * 4), array("H", [0]) * (size * 4)
    original_speeds, speeds = array("B", [0]) * (size * 4), array("B", [0]) * (size * 4)
    times, layer_times = array("H", [0]) * (size * 4), array("H", [0]) * (size * 4)
    proofs, layer_proofs = {}, {}
    counts = Counter()

    def position(cell, offsets):
        return [data["bounds"][0] + (cell % width + .5) * step + offsets[cell * 2] / 100000,
                data["bounds"][1] + (cell // width + .5) * step + offsets[cell * 2 + 1] / 100000]

    def consider(key, a, b, pa, pb, road_km, speed, kind, in_layer=False):
        offsets = layer_offsets if in_layer else base_offsets
        anchor_a, anchor_b = position(a, offsets), position(b, offsets)
        legacy = kind == "natural-earth"
        if legacy:
            old_cost = v2.road_time(anchor_a, anchor_b, pa, pb, road_km, speed)
            local_km = v2.distance_km(anchor_a, pa) + v2.distance_km(pb, anchor_b)
        else:
            charged = helpers.charged_edge(anchor_a, anchor_b, pa, pb, road_km, speed, geography)
            if charged is None:
                counts["rejectedLayerConnector" if in_layer else "rejectedBaseConnector"] += 1
                return
            old_cost, local_km = charged
        old_times = original_layer if in_layer else original_base
        if not old_times[key] or old_cost < old_times[key]:
            old_times[key] = old_cost
            if not in_layer:
                original_speeds[key] = speed
        new_speed = SPEED_MAPPING[speed]
        cost = price(road_km, local_km, new_speed, legacy)
        assert cost / 36000 * 95 + 1e-6 >= v2.distance_km(anchor_a, anchor_b)
        new_times, new_proofs = (layer_times, layer_proofs) if in_layer else (times, proofs)
        if not new_times[key] or cost < new_times[key]:
            new_times[key] = cost
            if not in_layer:
                speeds[key] = new_speed
            new_proofs[key] = {"key": key, "a": a, "b": b, "pointA": pa, "pointB": pb,
                               "roadKm": road_km, "localKm": local_km, "speedKph": new_speed,
                               "deciseconds": cost, "kind": kind}

    roads_path = ROOT / "data/coarse-sources/natural-earth-v5.1.2/roads.geojson"
    roads_raw = roads_path.read_bytes()
    assert sha(roads_raw) == data["sources"]["roads"]["sha256"]
    for road in json.loads(roads_raw)["features"]:
        props, geometry = road["properties"], road["geometry"]
        if props["sov_a3"] != "USA" or props["type"] not in data["roadSpeedsKph"]:
            continue
        speed = data["roadSpeedsKph"][props["type"]]
        paths = [geometry["coordinates"]] if geometry["type"] == "LineString" else geometry["coordinates"]
        for path in paths:
            visits = v2.road_visits(path, data["bounds"], step, width, lambda *_: None)
            for key, a, b in helpers.visit_edges(visits, width):
                consider(key, a[0], b[0], v2.visit_point(a), v2.visit_point(b), helpers.bounded_arc_km(a, b), speed, "natural-earth")
    print("Natural Earth alternatives repriced", file=sys.stderr, flush=True)
    seen = set()
    for partition, source in enumerate(sorted(manifest["sources"], key=lambda row: row["sha256"])):
        for part in road_parts(source, shapefile):
            counts["sourceParts"] += 1
            counts["sourcePoints"] += len(part["points"])
            identity = part_key(part)
            if identity in seen:
                counts["duplicateParts"] += 1
                continue
            seen.add(identity)
            visits = v2.road_visits(part["points"], data["bounds"], step, width, lambda *_: None)
            speed = SPEEDS[part["class"]]
            for key, a, b in helpers.visit_edges(visits, width):
                pa, pb = v2.visit_point(a), v2.visit_point(b)
                road_km = helpers.bounded_arc_km(a, b)
                if traversable[a[0]] and traversable[b[0]]:
                    consider(key, a[0], b[0], pa, pb, road_km, speed, "census")
                if transfers[a[0]] and transfers[b[0]]:
                    consider(key, a[0], b[0], pa, pb, road_km, speed, "census", True)
        if partition % 10 == 0 or partition == 48:
            print(f"Repriced Census partitions {partition + 1}/49", file=sys.stderr, flush=True)

    assert original_base == decode(data["roadDeciseconds"], "H"), "Baseline base-cost reproduction failed"
    assert original_layer == decode(data["roadLayer"]["roadDeciseconds"], "H"), "Baseline layer-cost reproduction failed"
    assert original_speeds == decode(data["links"]), "Baseline speed-tag reproduction failed"
    assert all(bool(a) == bool(b) for a, b in zip(times, original_base))
    assert all(bool(a) == bool(b) for a, b in zip(layer_times, original_layer))
    data["version"] = "natural-earth-census-2026-class-calibration-v1"
    data["links"], data["roadDeciseconds"] = encode(speeds), encode(times)
    data["roadLayer"]["roadDeciseconds"] = encode(layer_times)
    for name in ["roadVisits", "supplementalRoadVisits"]:
        data[name]["speeds"] = encode(array("B", (SPEED_MAPPING[s] for s in decode(data[name]["speeds"]))))
    for name in ["roadSpeedsKph", "censusRoadSpeedsKph"]:
        data[name] = {key: SPEED_MAPPING[value] for key, value in data[name].items()}
    data["calibrationBaselineSha256"] = BASELINE_SHA256
    data["calibrationModel"] = "Source classes105→95 and80→85km/h everywhere;55/90 unchanged. Geometry/topology/resolution and fixed25km/h costs unchanged; source alternatives recomputed, not aggregate-cost scaling. Offline unqualified candidate, no activation."
    data["connectionModel"] = "Same v8 state/geometry/paid-transfer rules with separately calibrated source-class costs."
    data["resolutionModel"] = "Unchanged v8 0.025-degree geometry; independently repriced source road/legacy-connector costs, fixed25km/h local Census connectors and layer transfers."
    artifact = (json.dumps(data, separators=(",", ":")) + "\n").encode()
    (output / "grid.json").write_bytes(artifact)
    proof_records = {}
    for name, rows in [("base", proofs), ("layer", layer_proofs)]:
        packed = gzip.compress((json.dumps([rows[k] for k in sorted(rows)], separators=(",", ":")) + "\n").encode(), mtime=0)
        path = output / f"{name}-links.json.gz"
        path.write_bytes(packed)
        proof_records[name] = {"path": str(path.relative_to(ROOT)), "sha256": sha(packed), "links": len(rows)}
    report = {"artifact": str((output / "grid.json").relative_to(ROOT)), "artifactSha256": sha(artifact),
              "artifactBytes": len(artifact), "baselineSha256": BASELINE_SHA256,
              "baselineCostAndSpeedTagReproduction": True, "speedMapping": SPEED_MAPPING,
              "proofs": proof_records, "counts": dict(counts), "tool": tool,
              "wallSeconds": time.perf_counter() - started, "processMaxRssNative": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "platform": sys.platform, "scope": "New offline source-class cost experiment on frozen v8 geometry. All old source alternatives reproduce v8 exactly before repricing. No runtime activation, download, provider/key/env/DB access. RSS measures the producer, not Vercel."}
    (output / "build.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--tool-lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source_manifest, args.tool_lock, args.output), indent=2))
