"""Qualify explicitly permitted control points against the frozen regional v2 source."""

import argparse
from collections import defaultdict
import fcntl
from fractions import Fraction
import gzip
import hashlib
import json
import math
from pathlib import Path
import resource
import struct
import time
import xml.etree.ElementTree as ET

from anchors import atomic_write, digest, file_hash, load_json, save_json
from barrier_policy import MODEL_ID, import_barriers
from cell_experiment import checked_artifact
from import_roads import tags
from maneuver_graph import destination_oracle, interior_destination, replay, source_seeds
from native_support import UINT64_MAX, membership_bytes, pack_graph
from regional_support import route_to_interior, snap_attachments
from state_graph import bellman_ford, dijkstra


PORT = 2859219644
SOURCE_NODES = {PORT, 2091673581, 2666304927, 9425876180, 2984024603}


def source_examples(source, output, graph, audit):
    """Retain original node/incident-way tags and directed, history-aware transition evidence."""
    incoming, outgoing = defaultdict(list), defaultdict(list)
    for index, road in enumerate(graph.base.roads):
        incoming[road["to"]].append(index)
        outgoing[road["from"]].append(index)
    selected = {row["id"]: row for row in audit["barrierPolicy"]["decisions"] if row["id"] in SOURCE_NODES}
    if set(selected) != SOURCE_NODES: raise ValueError("A source-backed barrier fixture is missing")
    for node, decision in selected.items():
        decision["incomingRoadIds"] = [graph.base.roads[index]["id"] for index in incoming[node]]
        decision["outgoingRoadIds"] = [graph.base.roads[index]["id"] for index in outgoing[node]]
        decision["transitions"] = [{"fromRoadId": graph.base.roads[left]["id"], "toRoadId": graph.base.roads[right]["id"],
                                    **replay(graph, [left, right])} for left in incoming[node] for right in outgoing[node]]
        if decision["blockedByModel"] and any(row["allowed"] for row in decision["transitions"]):
            raise ValueError("Closed source-backed barrier has a through transition")
    port = selected[PORT]
    if not port["open"] or port["blockedByModel"] or not any(row["allowed"] for row in port["transitions"]):
        raise ValueError("Explicit car permission did not admit the real port transition")
    node_ids, ways = set(SOURCE_NODES), []
    parser = ET.iterparse(source, events=("start", "end")); _, root = next(parser)
    for event, element in parser:
        if event == "end" and element.tag in {"node", "way", "relation"}:
            if element.tag == "way":
                refs = {int(node.get("ref")) for node in element.findall("nd")}
                matches = refs.intersection(SOURCE_NODES)
                if matches:
                    ways.append(ET.tostring(element))
                    node_ids.update(refs)
                    for node in matches:
                        selected[node].setdefault("sourceWays", []).append({"id": int(element.get("id")), "tags": tags(element)})
            root.remove(element)
    with output.open("wb") as target:
        target.write(b'<osm version="0.6">\n')
        parser = ET.iterparse(source, events=("start", "end")); _, root = next(parser)
        for event, element in parser:
            if event == "end" and element.tag in {"node", "way", "relation"}:
                if element.tag == "node" and int(element.get("id")) in node_ids: target.write(ET.tostring(element))
                root.remove(element)
        for way in ways: target.write(way)
        target.write(b'</osm>\n')
    return list(selected.values()), incoming[PORT], outgoing[PORT]


def qualify(output, graph, audit, profile, old_summary, examples, port_incoming, port_outgoing):
    by_id = {road["id"]: index for index, road in enumerate(graph.base.roads)}
    rules = {rule["id"]: rule for rule in graph.patterns}
    maneuvers = []
    for previous in old_summary["sourceSamples"]:
        original = previous["restriction"]
        rule = rules[original["id"]]
        if rule["roadIds"] != original["roadIds"]: raise ValueError("Qualified maneuver geometry changed")
        other_index = by_id[old_summary["alternativeRoadIds"][str(original["id"])]]
        blocked, allowed = replay(graph, rule["roads"]), replay(graph, [other_index] + rule["roads"][1:])
        if blocked["allowed"] or not allowed["allowed"]: raise ValueError("Prior maneuver decision changed")
        maneuvers.append({"restriction": rule, "alternativeRoadId": graph.base.roads[other_index]["id"], "blocked": blocked, "allowed": allowed})
    origins = []
    for origin in profile["origins"]:
        starts, seeds, snap = snap_attachments(graph, [origin["lon"], origin["lat"]], profile["sourceSnapMaxMeters"])
        origins.append({"id": origin["id"], "starts": starts, "seeds": seeds, "snap": snap})
    permitted = [(left, right) for left in port_incoming for right in port_outgoing if replay(graph, [left, right])["allowed"]]
    left, port_target = permitted[0]
    starts = [(left, Fraction(1, 2))]
    origins.append({"id": "port-incoming", "starts": starts, "seeds": source_seeds(graph, starts), "snap": None})
    cut_nodes = set(audit["cutExitNodes"])
    cut_states = [index for index, state in enumerate(graph.states) if graph.base.roads[state["road"]]["to"] in cut_nodes]
    counts = {"costComparisons": 0, "boundedCostComparisons": 0, "interiorDestinationComparisons": 0}
    checks, routes, destinations, artifacts = [], [], [], []
    (output / "oracles").mkdir(exist_ok=True)
    for origin in origins:
        before = time.perf_counter()
        result = dijkstra(graph.adjacency, origin["seeds"])
        search_ms = (time.perf_counter() - before) * 1000
        before = time.perf_counter()
        exact = bellman_ford(graph.adjacency, origin["seeds"])
        oracle_ms = (time.perf_counter() - before) * 1000
        if result.labels != exact: raise ValueError("Dijkstra/Bellman-Ford disagree on v3")
        counts["costComparisons"] += len(exact)
        name = f"oracles/{origin['id']}.u64le"
        atomic_write(output / name, struct.pack(f"<{len(exact)}Q", *(UINT64_MAX if value == math.inf else value for value in exact)))
        artifacts.append(name)
        boundary = min((exact[state] for state in cut_states), default=math.inf)
        budgets = []
        for budget in profile["budgetsMs"]:
            bounded = dijkstra(graph.adjacency, origin["seeds"], budget)
            if bounded.labels != [value if value <= budget else math.inf for value in exact]: raise ValueError("Bounded v3 costs disagree")
            counts["boundedCostComparisons"] += len(exact)
            budgets.append({"budgetMs": budget, "reachableStates": bounded.settled_states, "scannedArcs": bounded.scanned_arcs,
                            "boundaryReachedWithinBudget": boundary <= budget, "membershipSha256": hashlib.sha256(membership_bytes(exact, budget)).hexdigest()})
        # A sink oracle independently verifies the real permitted crossing's interior target.
        if origin["id"] == "port-incoming":
            actual = interior_destination(graph, exact, port_target, Fraction(1, 2), origin["starts"])
            expected = destination_oracle(graph, origin["seeds"], port_target, Fraction(1, 2), origin["starts"])
            if actual != expected or not math.isfinite(actual): raise ValueError("Real port interior destination failed")
            destinations.append({"origin": origin["id"], "roadId": graph.base.roads[port_target]["id"], "fraction": "1/2", "costMs": actual})
            counts["interiorDestinationComparisons"] += 1
        if origin["snap"]:
            for destination in origins:
                if not destination["snap"] or destination["id"] == origin["id"]: continue
                candidates = []
                for road, fraction in destination["starts"]:
                    if not 0 < fraction < 1: raise ValueError("Sample requires a strict interior attachment")
                    trace = route_to_interior(graph, exact, origin["seeds"], origin["starts"], road, fraction)
                    if trace["costMs"] is not None: candidates.append((trace["costMs"], road, fraction, trace))
                if candidates:
                    cost, road, fraction, trace = min(candidates, key=lambda value: value[0])
                    routes.append({"origin": origin["id"], "destination": destination["id"], **trace,
                                   "targetRoadId": graph.base.roads[road]["id"], "targetFraction": str(fraction)})
                else:
                    routes.append({"origin": origin["id"], "destination": destination["id"], "costMs": None, "status": "unreachable in this imported model"})
        checks.append({"origin": origin["id"], "starts": [[road, str(fraction)] for road, fraction in origin["starts"]],
                       "seeds": origin["seeds"], "snap": origin["snap"], "fullReachableStates": result.settled_states,
                       "firstCutExitMs": boundary if math.isfinite(boundary) else None, "fullSearchMs": search_ms, "bellmanFordMs": oracle_ms, "budgets": budgets})
        print(f"Qualified {origin['id']}: {result.settled_states} reachable states; first cut {boundary} ms", flush=True)
    return {"graphIdentity": graph.identity, "profile": profile, "baseRoads": len(graph.base.roads), "states": len(graph.states),
            "transitions": sum(map(len, graph.adjacency)), "viaWayRestrictions": len(graph.patterns), "barrierExamples": examples,
            "barrierDecisionCounts": audit["barrierPolicy"]["decisionCounts"], "sourceSamples": maneuvers,
            "origins": checks, "sampledRoutes": routes, "interiorDestinations": destinations, "oracleArtifacts": artifacts, **counts,
            "publicApiCalls": 0, "coverageVerified": False, "network": "none", "borderPolicy": profile["borderPolicy"]}


def run(args):
    started = time.perf_counter()
    output, previous, recipe = Path(args.output), Path(args.previous), Path(__file__).parent
    with (output / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        old = load_json(previous / "manifest.json")
        for name in old["artifacts"]: checked_artifact(previous, old, name)
        reference = Path(args.model_reference)
        fixture_manifest = load_json(reference / "manifest.json")
        for name in fixture_manifest["artifacts"]: checked_artifact(reference, fixture_manifest, name)
        if fixture_manifest["regionArtifact"] != old["regionArtifact"]: raise ValueError("Maneuver fixture uses a different OSM source")
        old_summary = load_json(previous / "summary.json")
        profile = {**old_summary["profile"], "id": "san-diego-tijuana-barriers-v3", "model": {**old_summary["profile"]["model"], "id": MODEL_ID},
                   "budgetsMs": [300000, 900000, 3600000, 7200000, 43200000], "nativeRepetitions": 5,
                   "borderPolicy": "Explicit static car permission at qualified control points; no queues, delay, documents, citizenship or current availability. Unknown barriers remain closed."}
        scripts = {name: file_hash(recipe / name) for name in ("barriers.py", "barrier_policy.py", "import_roads.py", "import_maneuvers.py", "maneuver_graph.py",
                   "regional_support.py", "state_graph.py", "anchors.py", "native_support.py", "cell_experiment.py", "cell_index.py", "reference.py")}
        identity = {"previousRunId": old["runId"], "previousManifestSha256": file_hash(previous / "manifest.json"),
                    "sourceArtifact": old["artifacts"]["car-roads.osm"], "fixtureManifestSha256": file_hash(reference / "manifest.json"),
                    "profile": profile, "scripts": scripts, "imageId": args.image_id,
                    "network": "none", "memoryLimit": "4g", "cpus": 2}
        run_id = digest(identity)
        identity_path = output / "run-identity.json"
        if identity_path.exists() and load_json(identity_path)["runId"] != run_id: raise ValueError("Inputs/code changed; use a new run name")
        if (output / "manifest.json").exists(): raise ValueError("Completed run exists; preserve it and use a new run name")
        save_json(identity_path, {"runId": run_id, **identity})
        before = time.perf_counter()
        graph, audit = import_barriers(previous / "car-roads.osm", output / "barrier-roads.osm", profile["bbox"], profile["model"])
        import_ms = (time.perf_counter() - before) * 1000
        print(f"Imported {len(graph.states)} v3 states in {import_ms:.1f} ms", flush=True)
        # Recover alternative IDs from the immutable small reference, avoiding index assumptions across models.
        fixture_summary = load_json(reference / "summary.json")
        old_summary["alternativeRoadIds"] = {str(row["restriction"]["id"]): row["alternativeRoadId"] for row in fixture_summary["sourceSamples"]}
        examples, incoming, outgoing = source_examples(previous / "car-roads.osm", output / "barrier-source-samples.osm", graph, audit)
        summary = qualify(output, graph, audit, profile, old_summary, examples, incoming, outgoing)
        save_json(output / "graph.json", {"graphIdentity": graph.identity, "baseIdentity": graph.base.identity, "model": profile["model"],
                  "roads": graph.base.roads, "baseTransitions": graph.base.adjacency, "states": graph.states,
                  "initialStates": graph.initial_states, "patterns": graph.patterns, "transitions": graph.adjacency})
        save_json(output / "import-audit.json", audit)
        packed = pack_graph(graph.adjacency, graph.identity)
        atomic_write(output / "graph.csr", packed)
        atomic_write(output / "graph.csr.gz", gzip.compress(packed, mtime=0))
        summary.update({"runId": run_id, "importMs": import_ms, "workerWallMs": (time.perf_counter() - started) * 1000,
                        "workerMaxRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "memoryLimit": "4g"})
        save_json(output / "summary.json", summary)
        names = ["graph.json", "graph.csr", "graph.csr.gz", "summary.json", "import-audit.json", "barrier-roads.osm", "barrier-source-samples.osm"] + summary["oracleArtifacts"]
        save_json(output / "manifest.json", {"runId": run_id, **identity, "graphIdentity": graph.identity,
                  "artifacts": {name: {"bytes": (output / name).stat().st_size, "sha256": file_hash(output / name)} for name in names}})
        (output / "recipe").mkdir(exist_ok=True)
        for name in scripts: atomic_write(output / "recipe" / name, (recipe / name).read_bytes())
        print(json.dumps({key: summary[key] for key in ("states", "transitions", "importMs", "workerWallMs", "workerMaxRssKiB", "barrierDecisionCounts", "publicApiCalls")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--output", default="/output")
    parser.add_argument("--previous", default="/previous")
    parser.add_argument("--model-reference", default="/model-reference")
    run(parser.parse_args())
