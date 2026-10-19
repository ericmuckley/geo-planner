"""Check source transformations, graph changes, route witnesses and preserved inputs."""

from collections import defaultdict
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import statistics
import struct
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "data/barrier-pilot/san-diego-tijuana-barriers-v3"
PREVIOUS = ROOT / "data/regional-pilot/san-diego-tijuana-corridor-v2"


def load(path): return json.loads(path.read_text())


def sha(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20): hasher.update(chunk)
    return hasher.hexdigest()


def objects(path, opened=()):
    parser = ET.iterparse(path, events=("start", "end")); _, root = next(parser)
    depth = 1
    for event, element in parser:
        if event == "start": depth += 1; continue
        if depth == 2:
            children = [(child.tag, child.attrib) for child in element if not
                        (element.tag == "node" and int(element.get("id")) in opened and child.tag == "tag" and child.get("k") == "barrier")]
            yield element.tag, element.attrib, children
            root.remove(element)
        depth -= 1


def source_excerpt(selected, filename):
    node_ids, ways, records = set(selected), [], []
    for kind, attrs, children in objects(PREVIOUS / "car-roads.osm"):
        if kind == "way" and any(tag == "nd" and int(props["ref"]) in selected for tag, props in children):
            element = ET.Element(kind, attrs)
            for tag, props in children:
                ET.SubElement(element, tag, props)
                if tag == "nd": node_ids.add(int(props["ref"]))
            ways.append(ET.tostring(element))
            records.append({"id": int(attrs["id"]), "tags": {props["k"]: props["v"] for tag, props in children if tag == "tag"}})
    path = HERE / filename
    with path.open("wb") as stream:
        stream.write(b'<osm version="0.6">\n')
        for kind, attrs, children in objects(PREVIOUS / "car-roads.osm"):
            if kind == "node" and int(attrs["id"]) in node_ids:
                element = ET.Element(kind, attrs)
                for tag, props in children: ET.SubElement(element, tag, props)
                stream.write(ET.tostring(element))
        for element in ways: stream.write(element)
        stream.write(b'</osm>\n')
    return {"file": filename, "sha256": sha(path), "sourceWays": records}


manifest = load(HERE / "build-manifest.json")
native = load(HERE / "native-verification.json")
rebuild = load(HERE / "rebuild-verification.json")
summary = load(HERE / "build-summary.json")
assert sha(LOCAL / "manifest.json") == sha(HERE / "build-manifest.json")
assert sha(HERE / "build-summary.json") == manifest["artifacts"]["summary.json"]["sha256"]
for name, artifact in manifest["artifacts"].items():
    assert (LOCAL / name).stat().st_size == artifact["bytes"] and sha(LOCAL / name) == artifact["sha256"]
for name, expected in manifest["scripts"].items(): assert sha(ROOT / "routing" / name) == expected
assert manifest["previousManifestSha256"] == sha(PREVIOUS / "manifest.json")
previous_manifest = load(PREVIOUS / "manifest.json")
for name, artifact in previous_manifest["artifacts"].items():
    assert (PREVIOUS / name).stat().st_size == artifact["bytes"] and sha(PREVIOUS / name) == artifact["sha256"]
for name, expected in previous_manifest["scripts"].items(): assert sha(ROOT / "routing" / name) == expected
assert native["sourceManifestSha256"] == sha(HERE / "build-manifest.json")
assert native["sourceRunId"] == manifest["runId"] and native["graphIdentity"] == manifest["graphIdentity"]
assert sha(ROOT / "routing/barriers_native.py") == native["workerSha256"]
assert sha(ROOT / "routing/native-network.sb") == native["networkPolicySha256"]
assert rebuild["sourceManifestSha256"] == sha(HERE / "build-manifest.json")
assert rebuild["sourceRunId"] == manifest["runId"] and rebuild["graphIdentity"] == manifest["graphIdentity"]
assert sha(ROOT / "routing/barriers_rebuild.py") == rebuild["workerSha256"]
for name, expected in rebuild["identicalArtifactSha256"].items(): assert manifest["artifacts"][name]["sha256"] == expected
assert sha(LOCAL / "native_search") == native["compilation"]["binarySha256"]
assert sha(LOCAL / "native_search") == sha(PREVIOUS / "native_search")
audit = load(LOCAL / "import-audit.json")
opened = {row["id"] for row in audit["barrierPolicy"]["decisions"] if row["open"]}
count = 0
from itertools import zip_longest
for original, prepared in zip_longest(objects(PREVIOUS / "car-roads.osm", opened), objects(LOCAL / "barrier-roads.osm")):
    assert original == prepared
    count += 1
old, data = load(PREVIOUS / "graph.json"), load(LOCAL / "graph.json")
assert old["roads"] == data["roads"]
assert old["patterns"] == data["patterns"]
assert old["states"] == data["states"] and old["initialStates"] == data["initialStates"]
assert old["graphIdentity"] != data["graphIdentity"]
changes = []
for state, (before, after) in enumerate(zip(old["transitions"], data["transitions"], strict=True)):
    assert set(map(tuple, before)).issubset(set(map(tuple, after)))
    added = set(map(tuple, after)) - set(map(tuple, before))
    if added:
        road = data["roads"][data["states"][state]["road"]]
        assert road["to"] in opened
        for target, weight in sorted(added):
            following = data["roads"][data["states"][target]["road"]]
            assert road["to"] == following["from"]
            changes.append({"fromState": state, "toState": target, "node": road["to"], "weightMs": weight})
old_blocked = set(load(PREVIOUS / "import-audit.json")["blockedNodes"])
new_blocked = set(audit["blockedNodes"])
assert new_blocked.issubset(old_blocked) and old_blocked - new_blocked <= opened
private = next(row for row in audit["barrierPolicy"]["decisions"] if row["id"] == 1228835396)
assert private["tags"] == {"barrier": "gate", "vehicle": "private"} and private["blockedByModel"]
private_in = [index for index, road in enumerate(data["roads"]) if road["to"] == private["id"]]
private_out = [index for index, road in enumerate(data["roads"]) if road["from"] == private["id"]]
private_pairs = [(left, right) for left in private_in for right in private_out if data["roads"][left]["from"] != data["roads"][right]["to"]]
assert len(private_pairs) == 2
assert all(not data["transitions"][index] for index, state in enumerate(data["states"]) if state["road"] in private_in)
private_proof = {**private, "blockedThroughPairs": [[data["roads"][left]["id"], data["roads"][right]["id"]] for left, right in private_pairs]}
private_proof["sourceExcerpt"] = source_excerpt({private["id"]}, "private-gate-source.osm")
origins = {row["origin"]: row for row in summary["origins"]}
checked_routes = []
for route in summary["sampledRoutes"]:
    if route["costMs"] is None: continue
    path = route["states"]
    assert path, "These separated city attachments must use graph transitions"
    cost = dict(origins[route["origin"]]["seeds"])[path[0]]
    crossed = []
    for left, right in zip(path, path[1:]):
        cost += next(weight for target, weight in data["transitions"][left] if target == right)
        node = data["roads"][data["states"][left]["road"]]["to"]
        if node in opened: crossed.append(node)
    full = data["roads"][data["states"][path[-1]]["road"]]["costMs"]
    cost += math.ceil(full * Fraction(route["targetFraction"])) - full
    assert cost == route["costMs"]
    checked_routes.append({"origin": route["origin"], "destination": route["destination"], "costMs": cost, "openedBarrierNodesTraversed": crossed})
crossing_ids = {node for row in checked_routes for node in row["openedBarrierNodesTraversed"]}
assert crossing_ids == {8181606580, 9357332258}
crossing_proofs = []
for node in crossing_ids:
    decision = next(row for row in audit["barrierPolicy"]["decisions"] if row["id"] == node)
    assert decision["open"] and not decision["blockedByModel"] and decision["tags"]["barrier"] == "border_control"
    ins = [index for index, road in enumerate(data["roads"]) if road["to"] == node]
    outs = [index for index, road in enumerate(data["roads"]) if road["from"] == node]
    assert len(ins) == len(outs) == 1
    assert any(data["states"][target]["road"] == outs[0] for target, _ in data["transitions"][data["initialStates"][ins[0]]])
    assert all(road["id"].endswith(":f") for index in ins + outs for road in [data["roads"][index]])
    crossing_proofs.append({**decision, "incomingRoadId": data["roads"][ins[0]]["id"], "outgoingRoadId": data["roads"][outs[0]]["id"]})
crossing_excerpt = source_excerpt(crossing_ids, "sampled-crossings-source.osm")
assert all(row["tags"]["oneway"] == "yes" for row in crossing_excerpt["sourceWays"])
incoming, outgoing = defaultdict(list), defaultdict(list)
for index, state in enumerate(data["states"]):
    road = data["roads"][state["road"]]
    incoming[road["to"]].append(index)
    outgoing[road["from"]].append(index)
port_status, frontier = [], []
port_area = [row for row in audit["barrierPolicy"]["decisions"] if -117.06 <= row["point"][0] <= -117.0 and 32.53 <= row["point"][1] <= 32.56]
INF = (1 << 64) - 1
for origin in summary["origins"]:
    labels = struct.unpack(f"<{len(data['states'])}Q", (LOCAL / "oracles" / f"{origin['origin']}.u64le").read_bytes())
    port_status.append({"origin": origin["origin"], "incomingCostMs": min((labels[state] for state in incoming[2859219644]), default=INF),
                        "outgoingCostMs": min((labels[state] for state in outgoing[2859219644]), default=INF)})
    for node in port_area:
        arrivals, departures = incoming[node["id"]], outgoing[node["id"]]
        arrival = min((labels[state] for state in arrivals), default=INF)
        if node["blockedByModel"] and arrival < INF and any(labels[state] == INF for state in departures):
            frontier.append({"origin": origin["origin"], "id": node["id"], "point": node["point"], "tags": node["tags"], "reason": node["reason"],
                             "minArrivalCostMs": arrival, "incomingStates": arrivals, "outgoingStates": departures})
rows = []
for budget in summary["profile"]["budgetsMs"]:
    cases = [row for row in native["cases"] if row["budgetMs"] == budget]
    rows.append({"budgetMs": budget, "originsWithCutFlag": sum(row["boundaryReachedWithinBudget"] for row in cases),
                 "medianOfOriginSearchP50Ms": statistics.median(row["modes"]["membership"]["timings"]["searchMs"]["p50"] for row in cases),
                 "medianOfOriginPipeP50Ms": statistics.median(row["modes"]["membership"]["timings"]["childRoundTripMs"]["p50"] for row in cases)})
report = {"runId": manifest["runId"], "previousGraphUnchanged": True, "nativeBinaryUnchanged": True, "sourceObjectsCompared": count,
          "reproducedArtifacts": list(rebuild["identicalArtifactSha256"]),
          "onlyQualifiedBarrierTagsChanged": True, "roadsPatternsStatesUnchanged": True, "transitionsRemoved": 0, "transitionsAdded": len(changes),
          "nodesWithAddedTransitions": sorted({row["node"] for row in changes}), "nodesOpened": len(opened),
          "routeWitnesses": checked_routes, "prohibitedSourceExample": private_proof, "sampledCrossingExamples": crossing_proofs,
          "sampledCrossingSource": crossing_excerpt, "portReachability": port_status, "closedPortFrontiers": frontier,
          "nativeAggregates": rows, "publicApiCalls": 0,
          "limits": "Finite costs are static-model values without control-point delay or queues. Closed frontiers are reachable barriers with some unreachable outgoing states; they do not prove the sole cause of a disconnected pair or current real-world availability."}
(HERE / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({key: value for key, value in report.items() if key != "closedPortFrontiers"}, indent=2))
