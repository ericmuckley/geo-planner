"""Match frozen path edges to NE source attributes; no candidate/search/fitting."""
from collections import Counter, defaultdict
import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))
load = lambda p: json.loads(p.read_text())
data = load(root / "src/server/data/coarse-grid-v8.json")
width, size = data["width"], data["width"] * data["height"]
regional = load(root / "docs/evidence/coarse-finer-2026-10-23/paths.json")
frontier = json.loads(gzip.decompress((root / "docs/evidence/coarse-frontier-reference-2026-10-23/paths.json.gz").read_bytes()))
benchmark = load(root / "docs/evidence/coarse-benchmark-reference-2026-10-24/comparison.json")
raw = (root / "data/coarse-quality/resolution-0025-base-v1/links.json.gz").read_bytes()
frozen = load(root / "docs/evidence/coarse-finer-2026-10-23/base-build.json")
assert hashlib.sha256(raw).hexdigest() == frozen["linkProof"]["sha256"]
proofs = {r["key"]: r for r in json.loads(gzip.decompress(raw))}
paths, targets = {}, {}
for case in benchmark["cases"]:
    group, id_ = case["id"].split("/", 1)
    edges = next(r["path"] for r in (frontier if group == "frontier" else regional[group]) if r["id"] == id_)
    selected = []
    for edge in edges:
        if edge["kind"] != "road":
            continue
        a, b = (edge["from"], edge["to"]) if group == "frontier" else (edge["cell"], edge["target"])
        if a >= size or b >= size:
            continue
        a, b = sorted([a, b])
        key = a * 4 + {1: 0, width + 1: 1, width: 2, width - 1: 3}[b - a]
        proof = proofs[key]
        if proof["kind"] == "natural-earth" and proof["speedKph"] == 105:
            assert abs(edge["minutes"] - proof["deciseconds"] / 600) < 1e-8
            targets[key] = proof
            selected.append((key, edge["minutes"]))
    paths[case["id"]] = selected
del proofs
spec = importlib.util.spec_from_file_location("saved_geometry_helpers", root / "scripts/build-coarse-augmentation.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
roads_raw = (root / "data/coarse-sources/natural-earth-v5.1.2/roads.geojson").read_bytes()
assert hashlib.sha256(roads_raw).hexdigest() == data["sources"]["roads"]["sha256"]
attributes = defaultdict(set)
for feature in json.loads(roads_raw)["features"]:
    props, geometry = feature["properties"], feature["geometry"]
    if props["sov_a3"] != "USA" or props["type"] != "Major Highway":
        continue
    sections = [geometry["coordinates"]] if geometry["type"] == "LineString" else geometry["coordinates"]
    for section in sections:
        visits = helpers.v4.v2.road_visits(section, data["bounds"], data["step"], width, lambda *_: None)
        for key, a, b in helpers.visit_edges(visits, width):
            if key not in targets:
                continue
            proof = targets[key]
            pa, pb = helpers.v4.v2.visit_point(a), helpers.v4.v2.visit_point(b)
            expected_a, expected_b = (proof["pointA"], proof["pointB"]) if proof["a"] == a[0] else (proof["pointB"], proof["pointA"])
            if max(abs(x - y) for x, y in zip(pa + pb, expected_a + expected_b, strict=True)) > 1e-9:
                continue
            if abs(helpers.bounded_arc_km(a, b) - proof["roadKm"]) > 1e-9:
                continue
            attributes[key].add((props["expressway"], props["level"], props["scalerank"]))
rows = []
for case in benchmark["cases"]:
    costs = Counter()
    for key, minutes in paths[case["id"]]:
        options = {a[0] for a in attributes[key]}
        label = f"expressway={next(iter(options))}" if len(options) == 1 else "ambiguous" if options else "unmatched"
        costs[label] += minutes
    rows.append({"id":case["id"], "v8SignedMinutes":case["v8"]["signedMinutes"], "neMajorMinutesByFlag":dict(costs)})
print(json.dumps({"targetEdges":len(targets), "matchedEdges":sum(bool(attributes[k]) for k in targets),
    "ambiguousExpresswayEdges":sum(len({a[0] for a in attributes[k]}) > 1 for k in targets),
    "rows":rows,
    "scope":"Descriptive source-attribute matching on saved v8-selected NE major-highway edges; public fixture IDs are validation only. Ambiguous/unmatched edges remain explicit. No new graph/search/provider/key/env/DB call, speed policy, optimization or causal ETA claim."},indent=2))
