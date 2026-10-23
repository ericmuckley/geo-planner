"""Add independently connected Census states to v6; preserve every base option."""

import argparse
from array import array
import base64
from collections import Counter
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import math
import sys
import time

from coarse_census import ROOT, SPEEDS, checked_file, load_tool, part_key, road_parts

spec = importlib.util.spec_from_file_location("layer_helpers", Path(__file__).with_name("build-coarse-augmentation.py"))
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
v2 = helpers.v4.v2
BASE_SHA256 = "a1ba5ae3eb7419feb458641f00da1886802fc16ec11af86e3d61d42a3b8b3f99"
MANIFEST_SHA256 = "c03379192c584e7b4fdd55ad6534ab9339db4551d5ee3720c7d12489990fb782"


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def numbers(encoded, code):
    result = array(code)
    result.frombytes(base64.b64decode(encoded))
    if sys.byteorder != "little":
        result.byteswap()
    return result


def encoded(values):
    if sys.byteorder != "little":
        values = values[:]
        values.byteswap()
    return base64.b64encode(values).decode()


def build(manifest_path, tool_lock, output, base_path=None, base_sha256=BASE_SHA256):
    started = time.perf_counter()
    output = output.resolve()
    assert output.is_relative_to((ROOT / "data/coarse-quality").resolve())
    custom_base = base_path is not None
    base_path = base_path or ROOT / "src/server/data/coarse-grid-v6.json"
    raw = base_path.read_bytes()
    assert sha256(raw) == base_sha256, "Base artifact must match its explicit hash"
    data = json.loads(raw)
    assert "roadLayer" not in data, "Add the road layer to a base graph only"
    manifest_raw = manifest_path.read_bytes()
    assert sha256(manifest_raw) == MANIFEST_SHA256 == data["censusSourceManifestSha256"]
    manifest = json.loads(manifest_raw)
    assert len(manifest["sources"]) == 49
    checked_file(manifest["catalog"])
    shapefile, tool = load_tool(tool_lock)
    output.mkdir()  # Preserve completed and failed runs.
    width, height, step = data["width"], data["height"], data["step"]
    size = width * height
    base_offsets = numbers(data["anchorOffsets"], "h")
    owners = data["supplementalRoadVisits"]
    assert owners["encoding"] == "cell-visits-le-v1"
    cells, anchors, starts = (numbers(owners[key], "I") for key in ["cells", "anchors", "starts"])
    source_offsets = numbers(owners["offsets"], "h")
    positions = array("h", [0]) * (size * 2)
    transfers = array("H", [0]) * size
    times = array("H", [0]) * (size * 4)
    geography = helpers.v3.Geography(data["boundary"], data["lakes"], data["bounds"][1], step, height)

    def position(cell, offsets):
        return [data["bounds"][0] + (cell % width + .5) * step + offsets[cell * 2] / 100000,
                data["bounds"][1] + (cell // width + .5) * step + offsets[cell * 2 + 1] / 100000]

    for row, cell in enumerate(cells):
        index = 2 * (starts[row] + anchors[row])
        positions[cell * 2:cell * 2 + 2] = source_offsets[index:index + 2]
        a, b = position(cell, positions), position(cell, base_offsets)
        assert geography.land_segment(a, b), "Source-to-base transfer must remain on continuous land"
        transfers[cell] = max(1, math.ceil(v2.distance_km(a, b) / data["localSpeedKph"] * 36000))
    del source_offsets, base_offsets
    proofs, seen = {}, set()
    counts = Counter()
    for partition, source in enumerate(sorted(manifest["sources"], key=lambda s: s["sha256"])):
        for part in road_parts(source, shapefile):
            counts["parts"] += 1
            counts["points"] += len(part["points"])
            identity = part_key(part)
            if identity in seen:
                counts["duplicateParts"] += 1
                continue
            seen.add(identity)
            speed = SPEEDS[part["class"]]
            visits = v2.road_visits(part["points"], data["bounds"], step, width, lambda *_: None)
            for key, a, b in helpers.visit_edges(visits, width):
                counts["sourceEdgeVisits"] += 1
                if not transfers[a[0]] or not transfers[b[0]]:
                    counts["missingRoadState"] += 1
                    continue
                pa, pb = v2.visit_point(a), v2.visit_point(b)
                road_km = helpers.bounded_arc_km(a, b)
                result = helpers.charged_edge(position(a[0], positions), position(b[0], positions), pa, pb, road_km, speed, geography)
                if result is None:
                    counts["rejectedLandTransfer"] += 1
                    continue
                cost, local_km = result
                if not times[key] or cost < times[key]:
                    times[key] = cost
                    proofs[key] = {"key": key, "a": a[0], "b": b[0], "pointA": pa, "pointB": pb,
                                   "roadKm": road_km, "localKm": local_km, "speedKph": speed,
                                   "deciseconds": cost}
        if partition % 10 == 0 or partition == 48:
            print(f"Census road-layer partitions {partition + 1}/49", file=sys.stderr, flush=True)
    data.update({
        "version": (f"natural-earth-census-2026-road-layer-{step:g}-v2" if custom_base
                    else "natural-earth-census-2026-road-layer-v1"),
        "roadLayer": {"encoding": "census-road-layer-le-v1", "anchorOffsets": encoded(positions),
                      "roadDeciseconds": encoded(times), "transferDeciseconds": encoded(transfers)},
        "roadLayerBaseSha256": base_sha256,
        "connectionModel": "Independent Census state per retained supplemental visit, with all v6 base geometry/costs/options preserved. All national Census arcs are reconsidered; source bends plus both continuous-land connectors are paid at class/local speeds. Transfers between Census and base states pay checked distance at 25 km/h, rounded up to at least 0.1 second. Staying on a Census road does not require returning to the NE/base anchor in every cell. One Census representative per cell still merges crossings and may require detours. No new driving accuracy qualification.",
    })
    if custom_base:
        data["connectionModel"] = data["connectionModel"].replace("all v6 base", "all input base")
    artifact = (json.dumps(data, separators=(",", ":")) + "\n").encode()
    (output / "grid.json").write_bytes(artifact)
    proof = gzip.compress((json.dumps([proofs[k] for k in sorted(proofs)], separators=(",", ":")) + "\n").encode(), mtime=0)
    (output / "links.json.gz").write_bytes(proof)
    report = {"artifact": str((output / "grid.json").relative_to(ROOT)), "artifactSha256": sha256(artifact),
              "artifactBytes": len(artifact), "baseSha256": base_sha256, "sourceManifestSha256": sha256(manifest_raw),
              "roadStates": len(cells), "roadLinks": len(proofs), "counts": dict(counts),
              "linkProof": {"path": str((output / "links.json.gz").relative_to(ROOT)), "sha256": sha256(proof), "bytes": len(proof)},
              "tool": tool, "wallSeconds": time.perf_counter() - started,
              "scope": "New offline additive Census road-state graph at unchanged v6 resolution/anchors/masks/speeds. Full pinned national source pass, no source download, old producer rerun, activation, reference/provider/DB request. All base options remain available; new links/transfers pay physical geometry."}
    if custom_base:
        report["baseArtifact"] = str(base_path.resolve().relative_to(ROOT))
        report["scope"] = report["scope"].replace("unchanged v6", "unchanged input-base")
    (output / "build.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--tool-lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--base-sha256")
    args = parser.parse_args()
    if bool(args.base) != bool(args.base_sha256):
        parser.error("Pass --base and --base-sha256 together")
    print(json.dumps(build(args.source_manifest, args.tool_lock, args.output,
                           args.base, args.base_sha256 or BASE_SHA256), indent=2))
