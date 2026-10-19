"""Reproduce capacity aggregates, route witnesses and preservation checks."""

import hashlib
import json
from pathlib import Path
import statistics
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "data/regional-pilot/san-diego-tijuana-corridor-v2"


def load(path):
    return json.loads(path.read_text())


def sha(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20): hasher.update(chunk)
    return hasher.hexdigest()


repeat = load(HERE / "build-manifest.json")
rebuild = load(HERE / "rebuild-verification.json")
assert rebuild["sourceRunId"] == repeat["runId"] and rebuild["graphIdentity"] == repeat["graphIdentity"]
assert rebuild["sourceManifestSha256"] == sha(HERE / "build-manifest.json")
stable = list(rebuild["identicalArtifactSha256"])
assert all(rebuild["identicalArtifactSha256"][name] == repeat["artifacts"][name]["sha256"] for name in stable)
assert sha(HERE / "build-summary.json") == repeat["artifacts"]["summary.json"]["sha256"]
for name, artifact in repeat["artifacts"].items():
    path = LOCAL / name
    assert path.stat().st_size == artifact["bytes"] and sha(path) == artifact["sha256"]
for name, expected in repeat["scripts"].items(): assert sha(ROOT / "routing" / name) == expected
for directory in ("reference-pilot/downtown-static-v1", "model-pilot/downtown-maneuvers-v2"):
    path = ROOT / "data" / directory
    manifest = load(path / "manifest.json")
    for name, artifact in manifest["artifacts"].items():
        assert (path / name).stat().st_size == artifact["bytes"] and sha(path / name) == artifact["sha256"]
summary = load(HERE / "build-summary.json")
native = load(HERE / "native-verification.json")
assert native["sourceManifestSha256"] == sha(HERE / "build-manifest.json")
assert native["sourceRunId"] == repeat["runId"] and native["graphIdentity"] == repeat["graphIdentity"]
assert sha(ROOT / "routing/regional_native.py") == native["workerSha256"]
assert sha(ROOT / "routing/regional_rebuild.py") == rebuild["workerSha256"]
assert sha(ROOT / "routing/native-network.sb") == native["networkPolicySha256"]
assert sha(LOCAL / "native_search") == native["compilation"]["binarySha256"]
assert native["compilation"]["binarySha256"] == load(ROOT / "docs/evidence/native-routing-2026-10-16/repeat-summary.json")["compilation"]["binarySha256"]
data = load(LOCAL / "graph.json")
origins = {origin["origin"]: origin for origin in summary["origins"]}
from fractions import Fraction
for origin in origins.values():
    if origin["snap"]:
        assert any(0 < Fraction(fraction) < 1 for _, fraction in origin["starts"])
for route in summary["sampledRoutes"]:
    if route["costMs"] is None: continue
    origin = origins[route["origin"]]
    path = route["states"]
    if not path: continue
    seeds = dict(origin["seeds"])
    cost = seeds[path[0]]
    for left, right in zip(path, path[1:]):
        cost += next(weight for target, weight in data["transitions"][left] if target == right)
    # The final arc includes its full road; replace with the specified partial traversal.
    from fractions import Fraction
    import math
    full = data["roads"][data["states"][path[-1]]["road"]]["costMs"]
    cost += math.ceil(full * Fraction(route["targetFraction"])) - full
    assert cost == route["costMs"]
cut_nodes = set(load(LOCAL / "import-audit.json")["cutExitNodes"])
raw = (LOCAL / "oracles/san-diego.u64le").read_bytes()
labels = struct.unpack(f"<{len(data['states'])}Q", raw)
eligible = [(labels[i], i) for i, state in enumerate(data["states"]) if data["roads"][state["road"]]["to"] in cut_nodes]
cost, state = min(eligible)
cut = {"costMs": cost, "state": state, "road": data["roads"][data["states"][state]["road"]]}
import xml.etree.ElementTree as ET
blocked = set(load(LOCAL / "import-audit.json")["blockedNodes"])
border_nodes = []
for _, element in ET.iterparse(LOCAL / "car-roads.osm", events=("end",)):
    if element.tag == "node":
        lon, lat = float(element.get("lon")), float(element.get("lat"))
        if -117.06 <= lon <= -117.0 and 32.53 <= lat <= 32.56:
            tags = {tag.get("k"): tag.get("v") for tag in element.findall("tag")}
            if tags.get("barrier") or tags.get("highway") == "border_control":
                node_id = int(element.get("id"))
                border_nodes.append({"id": node_id, "point": [lon, lat], "tags": tags, "blockedByModel": node_id in blocked})
    if element.tag == "way" and int(element.get("id")) == cut["road"]["way"]:
        cut["sourceWayTags"] = {tag.get("k"): tag.get("v") for tag in element.findall("tag")}
    if element.tag in {"node", "way", "relation"}: element.clear()
for node in border_nodes:
    node["retainedIncidentRoads"] = sum(road["from"] == node["id"] or road["to"] == node["id"] for road in data["roads"])
rows = []
for budget in summary["profile"]["budgetsMs"]:
    cases = [case for case in native["cases"] if case["budgetMs"] == budget]
    row = {"budgetMs": budget, "originsWithCutFlag": sum(case["boundaryReachedWithinBudget"] for case in cases)}
    for mode in ("labels", "membership"):
        row[mode] = {key: statistics.median(case["formats"][mode]["timings"][key]["p50"] for case in cases)
                     for key in ("searchMs", "setupAndSearchMs", "encodeMs", "roundTripAndDecodeMs")}
    rows.append(row)
report = {"runId": repeat["runId"], "identicalArtifacts": stable, "previousGraphsUnchanged": True,
          "legalRouteWitnessesChecked": sum(route["costMs"] is not None for route in summary["sampledRoutes"]),
          "defaultFirstCut": cut, "nativeAggregates": rows, "publicApiCalls": 0,
          "sanYsidroTaggedNodes": border_nodes,
          "aggregation": "Median of eight per-origin p50s, five sequential samples per case/mode; p95 is each case maximum."}
(HERE / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
