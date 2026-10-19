"""Reproduce import resource comparisons and preservation/equality checks."""

import hashlib
import json
from pathlib import Path
import struct
import sys
import math
from fractions import Fraction
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "routing"))
from maneuver_graph import ManeuverGraph
from native_support import decode_labels
from regional_support import route_to_interior
from state_graph import StateGraph


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = ("downtown-v2", "corridor-v2", "corridor-v3", "wide-v2")
REFERENCES = {"downtown-v2": "model-pilot/downtown-maneuvers-v2", "corridor-v2": "regional-pilot/san-diego-tijuana-corridor-v2",
              "corridor-v3": "barrier-pilot/san-diego-tijuana-barriers-v3", "wide-v2": "regional-pilot/san-diego-tijuana-v2"}


def load(path): return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream: return hashlib.file_digest(stream, "sha256").hexdigest()


rows = []
for case in CASES:
    report = load(HERE / f"{case}.json")
    local = ROOT / "data/import-pilot" / f"stream-v1-{case}"
    assert sha(local / "report.json") == sha(HERE / f"{case}.json")
    previous_dir = ROOT / "data" / REFERENCES[case]
    previous_path = previous_dir / ("run-identity.json" if case == "wide-v2" else "manifest.json")
    assert report["previousManifestSha256"] == sha(previous_path)
    previous = load(previous_path)
    for name, expected in report["scripts"].items():
        assert sha(ROOT / "routing" / name) == expected
        assert sha(local / "recipe" / name) == expected
    for name, expected in previous.get("artifacts", {}).items():
        path = previous_dir / name
        assert path.stat().st_size == expected["bytes"] and sha(path) == expected["sha256"]
    source = (ROOT / "data/reference-pilot/downtown-static-v1/roads.osm" if case == "downtown-v2" else
              ROOT / "data/regional-pilot/san-diego-tijuana-corridor-v2/car-roads.osm" if case == "corridor-v3" else previous_dir / "car-roads.osm")
    assert sha(source) == report["sourceXmlSha256"]
    if case != "wide-v2":
        for name, actual in report["identicalArtifactSha256"].items(): assert actual == previous["artifacts"][name]["sha256"]
        assert report["graphIdentity"] == previous["graphIdentity"]
        for name, expected in previous["scripts"].items(): assert sha(ROOT / "routing" / name) == expected
    else:
        for name, expected in report["artifacts"].items():
            assert (local / name).stat().st_size == expected["bytes"] and sha(local / name) == expected["sha256"]
        frozen_failure = ROOT / "docs/evidence/regional-capacity-2026-10-16"
        for name, saved in (("failure.json", "failed-failure.json"), ("car-filter.json", "failed-car-filter.json"), ("oom-events.jsonl", "failed-oom-events.jsonl")):
            assert sha(previous_dir / name) == sha(frozen_failure / saved)
        assert load(previous_dir / "car-filter.json")["sha256"] == report["sourceXmlSha256"]
        assert report["profile"] == previous["profile"]
        assert report["costComparisons"] == report["states"] * len(report["origins"])
        assert report["boundedCostComparisons"] == report["costComparisons"] * len(report["profile"]["budgetsMs"])
    complete = report["resourceCheckpoints"]["complete"]
    assert int(complete["memory.max"]) == 4 * 1024**3
    assert int(complete["memory.peak"]) <= int(complete["memory.max"])
    assert int(complete["memory.events"]["oom"]) == int(complete["memory.events"]["oom_kill"]) == 0
    assert int(complete["memory.events"]["max"]) == 0
    rows.append({"case": case, "states": report["states"], "transitions": report["transitions"], "importMs": report["importMs"],
                 "workerWallMs": report["workerWallMs"], "workerMaxRssGiB": complete["workerMaxRssKiB"] / 1024**2,
                 "containerObservedPeakGiB": int(complete["memory.peak"]) / 1024**3,
                 "originalArtifactsEqual": case != "wide-v2", "importStages": report["importStages"]})
native = load(HERE / "native-verification.json")
wide = load(HERE / "wide-v2.json")
wide_dir = ROOT / "data/import-pilot/stream-v1-wide-v2"
assert native["sourceReportSha256"] == sha(HERE / "wide-v2.json")
assert native["sourceRunId"] == wide["runId"] and native["graphIdentity"] == wide["graphIdentity"]
assert native["workerSha256"] == sha(ROOT / "routing/import_native.py")
assert native["networkPolicySha256"] == sha(ROOT / "routing/native-network.sb")
assert native["compilation"]["binarySha256"] == sha(wide_dir / "native_search")
assert sha(wide_dir / "native_search") == sha(ROOT / "data/barrier-pilot/san-diego-tijuana-barriers-v3/native_search")
assert native["costComparisons"] == wide["costComparisons"] + wide["boundedCostComparisons"]
assert native["membershipComparisons"] == wide["boundedCostComparisons"]
data = load(wide_dir / "graph.json")
audit = load(wide_dir / "import-audit.json")
cuts = set(audit["cutExitNodes"])
cut_states = [index for index, state in enumerate(data["states"]) if data["roads"][state["road"]]["to"] in cuts]
cut_witnesses = []
for origin in wide["origins"]:
    values = struct.unpack(f"<{len(data['states'])}Q", (wide_dir / origin["oracleArtifact"]).read_bytes())
    cost, state = min((values[index], index) for index in cut_states)
    assert cost == origin["firstCutExitMs"]
    cut_witnesses.append({"origin": origin["origin"], "costMs": cost, "state": state, "road": data["roads"][data["states"][state]["road"]]})
graph = ManeuverGraph(StateGraph(data["roads"], data["baseTransitions"], [], [], data["baseIdentity"]), data["states"],
                      data["initialStates"], data["transitions"], data["patterns"], [], data["graphIdentity"])
blocked_nodes = set(audit["blockedNodes"])
origins = {row["origin"]: row for row in wide["origins"]}
border_routes = []
for source, target in (("tijuana", "san-diego"), ("san-diego", "tijuana")):
    origin, destination = origins[source], origins[target]
    labels = decode_labels((wide_dir / origin["oracleArtifact"]).read_bytes(), len(graph.states))
    candidates = [(route_to_interior(graph, labels, origin["seeds"], origin["starts"], road, fraction), road, fraction) for road, fraction in destination["starts"]]
    finite = [row for row in candidates if row[0]["costMs"] is not None]
    trace = {"costMs": None}
    if finite:
        trace, road, fraction = min(finite, key=lambda row: row[0]["costMs"])
        trace = {**trace, "targetRoadId": graph.base.roads[road]["id"], "targetFraction": fraction}
        path = trace["states"]
        cost = dict(origin["seeds"])[path[0]]
        for left, right in zip(path, path[1:]):
            cost += next(weight for target, weight in graph.adjacency[left] if target == right)
            assert graph.base.roads[graph.states[left]["road"]]["to"] not in blocked_nodes
        cost += math.ceil(graph.base.roads[road]["costMs"] * Fraction(fraction)) - graph.base.roads[road]["costMs"]
        assert cost == trace["costMs"]
    border_routes.append({"origin": source, "destination": target, **trace})
(HERE / "wide-border-route-diagnostic.json").write_text(json.dumps(border_routes, indent=2) + "\n")
assert len(border_routes) == 2
route_ways = {int(road.split(':')[0]) for row in border_routes for road in row.get("roadIds", [])}
assert 114198251 in route_ways
del data, graph, labels
source_file = ROOT / "data/regional-pilot/san-diego-tijuana-v2/car-roads.osm"
selected = {114198251, 114198229, 114198254, 238843379, 1468444496, 1468444517}
assert selected <= route_ways
selected_xml, selected_tags, node_ids = [], [], set()
parser = ET.iterparse(source_file, events=("start", "end")); _, root = next(parser)
for event, element in parser:
    if event == "end" and element.tag in {"node", "way", "relation"}:
        if element.tag == "way" and int(element.get("id")) in selected:
            selected_xml.append(ET.tostring(element))
            node_ids.update(int(node.get("ref")) for node in element.findall("nd"))
            selected_tags.append({"id": int(element.get("id")), "tags": {tag.get("k"): tag.get("v") for tag in element.findall("tag")}})
        root.remove(element)
uncertain = next(row for row in selected_tags if row["id"] == 114198251)
assert "barrier" in uncertain["tags"]["fixme"] and "access" in uncertain["tags"]["fixme"]
excerpt = HERE / "otay-uncertain-crossing-source.osm"
with excerpt.open("wb") as stream:
    stream.write(b'<osm version="0.6">\n')
    parser = ET.iterparse(source_file, events=("start", "end")); _, root = next(parser)
    for event, element in parser:
        if event == "end" and element.tag in {"node", "way", "relation"}:
            if element.tag == "node" and int(element.get("id")) in node_ids: stream.write(ET.tostring(element))
            root.remove(element)
    for element in selected_xml: stream.write(element)
    stream.write(b'</osm>\n')
baselines = []
for case, path in (("corridor-v2", "docs/evidence/regional-capacity-2026-10-16/rebuild-verification.json"),
                   ("corridor-v3", "docs/evidence/barrier-access-2026-10-16/rebuild-verification.json")):
    old = load(ROOT / path)
    row = next(row for row in rows if row["case"] == case)
    baselines.append({"case": case, "oldImportMs": old["importMs"], "oldWorkerMaxRssGiB": old["workerMaxRssKiB"] / 1024**2,
                      "newImportMs": row["importMs"], "newWorkerMaxRssGiB": row["workerMaxRssGiB"],
                      "workerRssReductionPercent": 100 * (1 - row["workerMaxRssGiB"] / (old["workerMaxRssKiB"] / 1024**2))})
report = {"measurements": rows, "rebuildComparisons": baselines, "previousGraphsAndFailurePreserved": True, "nativeBinaryUnchanged": True,
          "wideSourceSha256": wide["sourceXmlSha256"], "wideGraphIdentity": wide["graphIdentity"],
          "wideCutWitnesses": cut_witnesses,
          "wideBorderRouteDiagnostic": [{key: row[key] for key in ("origin", "destination", "costMs")} for row in border_routes],
          "unqualifiedOtayCrossing": {"sourceExcerptSha256": sha(excerpt), "sourceWays": selected_tags, "carEligibilityVerified": False,
                                      "finding": "Recovered v2 route traverses inspection-facility ways; source way 114198251 explicitly marks missing barrier and uncertain access. No inference that hgv=designated alone excludes cars."},
          "wideCutFindings": [{"origin": row["origin"], "snapMeters": row["snap"]["distanceMeters"], "firstCutExitMs": row["firstCutExitMs"],
                               "fullReachableStates": row["fullReachableStates"], "budgets": row["budgets"]} for row in wide["origins"]],
          "nativeCostComparisons": native["costComparisons"], "nativeMembershipComparisons": native["membershipComparisons"], "publicApiCalls": 0,
          "limits": "Single capped-container observation per import; not a distribution or national memory forecast. Old observations report worker RSS only; new cgroup peaks include other container-accounted memory. Byte equality preserves model behavior, including conservative v2 barriers; it does not prove real-world correctness or complete coverage."}
(HERE / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
