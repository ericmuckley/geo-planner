"""Recheck wider v3 identity, preserved graphs, crossing diagnostics and cut witnesses."""

from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "routing"))
from crossing_audit import route_evidence
from maneuver_graph import ManeuverGraph, replay
from native_support import decode_labels
from state_graph import StateGraph

LOCAL = ROOT / "data/barrier-pilot/san-diego-tijuana-wide-v3"
PREVIOUS = ROOT / "data/import-pilot/stream-v1-wide-v2"
SOURCE = ROOT / "data/regional-pilot/san-diego-tijuana-v2/car-roads.osm"


def load(path): return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream: return hashlib.file_digest(stream, "sha256").hexdigest()


manifest, summary = load(HERE / "build-manifest.json"), load(HERE / "build-summary.json")
native, rebuild = load(HERE / "native-verification.json"), load(HERE / "rebuild-verification.json")
assert sha(LOCAL / "manifest.json") == sha(HERE / "build-manifest.json")
assert sha(HERE / "build-summary.json") == manifest["artifacts"]["summary.json"]["sha256"]
for name, expected in manifest["artifacts"].items():
    assert (LOCAL / name).stat().st_size == expected["bytes"] and sha(LOCAL / name) == expected["sha256"]
for name, expected in manifest["scripts"].items():
    assert sha(ROOT / "routing" / name) == expected and sha(LOCAL / "recipe" / name) == expected
assert sha(SOURCE) == manifest["sourceXmlSha256"]
assert sha(PREVIOUS / "report.json") == manifest["previousReportSha256"]
previous_report = load(PREVIOUS / "report.json")
for name, expected in previous_report["artifacts"].items():
    assert (PREVIOUS / name).stat().st_size == expected["bytes"] and sha(PREVIOUS / name) == expected["sha256"]
for name, expected in previous_report["scripts"].items(): assert sha(ROOT / "routing" / name) == expected
assert native["sourceManifestSha256"] == rebuild["sourceManifestSha256"] == sha(HERE / "build-manifest.json")
assert native["sourceRunId"] == rebuild["sourceRunId"] == manifest["runId"]
assert native["graphIdentity"] == rebuild["graphIdentity"] == manifest["graphIdentity"]
assert sha(ROOT / "routing/barriers_native.py") == native["workerSha256"]
assert sha(ROOT / "routing/wide.py") == rebuild["workerSha256"]
assert sha(ROOT / "routing/native-network.sb") == native["networkPolicySha256"]
assert sha(LOCAL / "native_search") == native["compilation"]["binarySha256"] == sha(PREVIOUS / "native_search")
for name, actual in rebuild["identicalArtifactSha256"].items(): assert actual == manifest["artifacts"][name]["sha256"]
for report in (summary, rebuild):
    checkpoint = report["resourceCheckpoints"]["complete"]
    assert int(checkpoint["memory.max"]) == 4 * 1024**3
    assert int(checkpoint["memory.peak"]) <= int(checkpoint["memory.max"])
    assert all(int(checkpoint["memory.events"][name]) == 0 for name in ("max", "oom", "oom_kill"))
data, previous = load(LOCAL / "graph.json"), load(PREVIOUS / "graph.json")
assert data["roads"] == previous["roads"] and data["patterns"] == previous["patterns"]
assert data["states"] == previous["states"] and data["initialStates"] == previous["initialStates"]
assert data["graphIdentity"] != previous["graphIdentity"]
audit = load(LOCAL / "import-audit.json")
opened = {row["id"] for row in audit["barrierPolicy"]["decisions"] if row["open"] and not row["blockedByModel"]}
added, added_nodes = 0, set()
for index, (before, after) in enumerate(zip(previous["transitions"], data["transitions"], strict=True)):
    old, new = set(map(tuple, before)), set(map(tuple, after))
    assert old <= new
    if new - old:
        node = data["roads"][data["states"][index]["road"]]["to"]
        assert node in opened
        added += len(new - old)
        added_nodes.add(node)
del previous
graph = ManeuverGraph(StateGraph(data["roads"], data["baseTransitions"], [], [], data["baseIdentity"]), data["states"],
                      data["initialStates"], data["transitions"], data["patterns"], [], data["graphIdentity"])
origins = {row["origin"]: row for row in summary["origins"]}
uncertain = audit["sourceCrossingUncertainties"]
assert {row["id"] for row in uncertain} == {114198251, 185333061, 577149752}
routes = summary["sampledRoutes"] + summary["uncertainBranchRoutes"]
for route in routes:
    assert route_evidence(graph, origins[route["origin"]], route, uncertain, opened) == route["accessEvidence"]
# A previously recovered Otay journey remains a legal, explicitly warned v3 witness.
old_trace = load(ROOT / "docs/evidence/streaming-import-2026-10-16/wide-border-route-diagnostic.json")[0]
assert old_trace["origin"] == "tijuana" and old_trace["destination"] == "san-diego"
by_id = {road["id"]: index for index, road in enumerate(graph.base.roads)}
indices = [by_id[road] for road in old_trace["roadIds"]]
offset = next(Fraction(fraction) for road, fraction in origins["tijuana"]["starts"] if road == indices[0])
trace = replay(graph, indices, offset)
assert trace["allowed"]
last_cost = graph.base.roads[indices[-1]]["costMs"]
cost = trace["costMs"] - last_cost + math.ceil(last_cost * Fraction(old_trace["targetFraction"]))
assert cost == old_trace["costMs"]
retained = {"origin": "tijuana", "destination": "san-diego", "costMs": cost, "states": trace["states"],
            "roadIds": old_trace["roadIds"], "targetRoadId": old_trace["targetRoadId"], "targetFraction": old_trace["targetFraction"],
            "purpose": "Replay of the preserved v2 Otay witness; not a minimum-cost v3 journey."}
retained["accessEvidence"] = route_evidence(graph, origins["tijuana"], retained, uncertain, opened)
assert 114198251 in retained["accessEvidence"]["sourceUncertaintyWayIds"]
(HERE / "retained-otay-route.json").write_text(json.dumps(retained, indent=2) + "\n")
private = 1228835396
assert any(row["id"] == private and row["blockedByModel"] for row in audit["barrierPolicy"]["decisions"])
assert all(not row for state, row in zip(graph.states, graph.adjacency) if graph.base.roads[state["road"]]["to"] == private)
cuts = set(audit["cutExitNodes"])
cut_states = [index for index, state in enumerate(graph.states) if graph.base.roads[state["road"]]["to"] in cuts]
witnesses = []
for origin in summary["origins"]:
    labels = decode_labels((LOCAL / "oracles" / f"{origin['origin']}.u64le").read_bytes(), len(graph.states))
    cost, state = min((labels[index], index) for index in cut_states)
    assert cost == origin["firstCutExitMs"]
    witnesses.append({"origin": origin["origin"], "costMs": cost, "road": graph.base.roads[graph.states[state]["road"]]})
features = []
for route in routes + [retained]:
    if route["costMs"] is None: continue
    road_indices = [graph.states[state]["road"] for state in route["states"]]
    roads = [graph.base.roads[index] for index in road_indices]
    offset = next(Fraction(fraction) for road, fraction in origins[route["origin"]]["starts"] if road == road_indices[0])
    def interpolate(road, fraction):
        return [a + (b - a) * float(fraction) for a, b in zip(road["fromPoint"], road["toPoint"], strict=True)]
    coordinates = [interpolate(roads[0], offset)] + [road["toPoint"] for road in roads[:-1]] + [interpolate(roads[-1], Fraction(route["targetFraction"]))]
    snap = origins[route["origin"]]["snap"]
    if snap: assert all(abs(a - b) < 1e-9 for a, b in zip(coordinates[0], snap["snapped"], strict=True))
    features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coordinates},
                     "properties": {"kind": "route", "origin": route["origin"], "destination": route["destination"], "costMs": route["costMs"],
                                    "purpose": route.get("purpose", "Qualified model witness"), **route["accessEvidence"]}})
for witness in witnesses:
    features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": witness["road"]["toPoint"]},
                     "properties": {"kind": "cut-exit", "origin": witness["origin"], "costMs": witness["costMs"], "roadId": witness["road"]["id"]}})
(HERE / "route-and-cut-evidence.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")) + "\n")
active_nodes = {node for route in summary["sampledRoutes"] for node in route["accessEvidence"].get("qualifiedStaticBarrierNodesTraversed", [])}
barrier_tags = {row["id"]: row for row in audit["barrierPolicy"]["decisions"]}
crossing_nodes = {node for node in active_nodes if barrier_tags[node]["tags"]["barrier"] == "border_control"}
way_ids = {road["way"] for road in graph.base.roads if road["from"] in crossing_nodes or road["to"] in crossing_nodes}
way_xml, way_records, node_ids = [], [], set(crossing_nodes)
parser = ET.iterparse(SOURCE, events=("start", "end")); _, root = next(parser)
for event, element in parser:
    if event == "end" and element.tag in {"node", "way", "relation"}:
        if element.tag == "way" and int(element.get("id")) in way_ids:
            way_xml.append(ET.tostring(element))
            node_ids.update(int(node.get("ref")) for node in element.findall("nd"))
            way_records.append({"id": int(element.get("id")), "tags": {tag.get("k"): tag.get("v") for tag in element.findall("tag")}})
        root.remove(element)
source_excerpt = HERE / "city-crossings-source.osm"
with source_excerpt.open("wb") as stream:
    stream.write(b'<osm version="0.6">\n')
    parser = ET.iterparse(SOURCE, events=("start", "end")); _, root = next(parser)
    for event, element in parser:
        if event == "end" and element.tag in {"node", "way", "relation"}:
            if element.tag == "node" and int(element.get("id")) in node_ids: stream.write(ET.tostring(element))
            root.remove(element)
    for element in way_xml: stream.write(element)
    stream.write(b'</osm>\n')
rows = []
for budget in summary["profile"]["budgetsMs"]:
    cases = [row for row in native["cases"] if row["budgetMs"] == budget]
    rows.append({"budgetMs": budget, "originsWithCutFlag": sum(row["boundaryReachedWithinBudget"] for row in cases),
                 "medianOfOriginSearchP50Ms": statistics.median(row["modes"]["membership"]["timings"]["searchMs"]["p50"] for row in cases),
                 "medianOfOriginPipeP50Ms": statistics.median(row["modes"]["membership"]["timings"]["childRoundTripMs"]["p50"] for row in cases)})
report = {"runId": manifest["runId"], "previousWideGraphUnchanged": True, "nativeBinaryUnchanged": True, "roadsPatternsStatesUnchanged": True,
          "transitionsAdded": added, "nodesWithAddedTransitions": len(added_nodes), "transitionsRemovedOrReweighted": 0,
          "reproducedArtifacts": list(rebuild["identicalArtifactSha256"]), "cutWitnesses": witnesses,
          "cityRoutes": [{"origin": row["origin"], "destination": row["destination"], "costMs": row["costMs"], **row["accessEvidence"]} for row in summary["sampledRoutes"]],
          "uncertainBranchRoutes": [{"costMs": row["costMs"], **row["accessEvidence"]} for row in summary["uncertainBranchRoutes"]],
          "retainedOtayWitness": {"costMs": retained["costMs"], **retained["accessEvidence"]},
          "cityCrossingNodes": [barrier_tags[node] for node in sorted(crossing_nodes)], "cityCrossingSourceWays": way_records,
          "cityCrossingExcerptSha256": sha(source_excerpt), "uncertainWayIds": sorted(row["id"] for row in uncertain),
          "routeAndCutGeojsonSha256": sha(HERE / "route-and-cut-evidence.geojson"),
          "nativeAggregates": rows, "nativeCostComparisons": native["costComparisons"], "nativeMembershipComparisons": native["membershipComparisons"],
          "nativeInteriorComparisons": native["interiorDestinationComparisons"], "publicApiCalls": 0,
          "limits": "Exactness refers to the imported v3 model. Source hints are incomplete, commercial context does not establish per-edge car eligibility, border waits/delays are absent, and selected long queries reach cut exits."}
(HERE / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
