"""Qualify a separate maneuver-history/interior-destination model on cached OSM."""

import argparse
import fcntl
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import resource
import struct
import time
import xml.etree.ElementTree as ET

from anchors import atomic_write, digest, file_hash, load_json, save_json
from cell_experiment import checked_artifact
from import_maneuvers import import_maneuvers
from maneuver_graph import destination_oracle, interior_destination, replay, source_seeds
from native_support import UINT64_MAX, membership_bytes, pack_graph
from reference import snap_source
from state_graph import bellman_ford, dijkstra


def sample_maneuvers(graph):
    samples, checked = [], []
    incoming = {}
    for road, row in enumerate(graph.base.adjacency):
        for target, _ in row:
            incoming.setdefault(target, []).append(road)
    for rule in graph.patterns:
        sequence = rule["roads"]
        blocked = replay(graph, sequence)
        if blocked["allowed"]:
            raise ValueError("Imported forbidden maneuver was allowed")
        checked.append({"restrictionId": rule["id"], **blocked})
        if len(samples) == 2 or blocked["blockedStep"] != len(sequence) - 1:
            continue
        for other in incoming.get(sequence[1], []):
            if graph.base.roads[other]["way"] == graph.base.roads[sequence[0]]["way"]:
                continue
            allowed = replay(graph, [other] + sequence[1:])
            if allowed["allowed"]:
                samples.append({"restriction": rule, "alternativeRoad": other,
                                "alternativeRoadId": graph.base.roads[other]["id"], "blocked": blocked, "allowed": allowed})
                break
    if not samples:
        raise ValueError("No real via-way example with an allowed different arrival was found")
    return samples, checked


def snapshot_samples(osm, samples):
    original = ET.parse(osm).getroot()
    selected_relations = {sample["restriction"]["id"] for sample in samples}
    selected_ways = {way for sample in samples for way in sample["restriction"]["ways"]}
    selected_ways.update(int(sample["alternativeRoadId"].split(":")[0]) for sample in samples)
    ways = [way for way in original.findall("way") if int(way.get("id")) in selected_ways]
    selected_nodes = {int(node.get("ref")) for way in ways for node in way.findall("nd")}
    root = ET.Element("osm", {"version": "0.6", "generator": "Geo Planner offline source snapshot"})
    root.extend(node for node in original.findall("node") if int(node.get("id")) in selected_nodes)
    root.extend(ways)
    root.extend(relation for relation in original.findall("relation") if int(relation.get("id")) in selected_relations)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def run(args):
    started = time.perf_counter()
    reference, output, recipe = Path(args.reference), Path(args.output), Path(__file__).parent
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source = load_json(reference / "manifest.json")
        for name in source["artifacts"]:
            checked_artifact(reference, source, name)
        extraction = load_json(reference / "extract.json")
        osm = reference / "roads.osm"
        if file_hash(osm) != extraction["osmSha256"] or extraction["identity"]["source"] != source["regionArtifact"]:
            raise ValueError("Frozen XML/source checksum mismatch")
        profile = load_json(recipe / "profiles/model-downtown-v2.json")
        scripts = {name: file_hash(recipe / name) for name in ("model.py", "maneuver_graph.py", "import_maneuvers.py",
                    "import_roads.py", "state_graph.py", "reference.py", "native_support.py", "anchors.py", "cell_experiment.py", "cell_index.py")}
        identity = {"profile": profile, "sourceReferenceRunId": source["runId"], "sourceGraphIdentity": source["graphIdentity"],
                    "sourceXmlSha256": extraction["osmSha256"], "regionArtifact": source["regionArtifact"],
                    "sourceManifest": source["sourceManifest"], "bbox": source["profile"]["bbox"], "scripts": scripts,
                    "imageId": args.image_id, "network": "none", "cpus": 2, "memoryLimit": "2g"}
        run_id = digest(identity)
        identity_path = output / "run-identity.json"
        if identity_path.exists() and load_json(identity_path)["runId"] != run_id:
            raise ValueError("Model/code/source changed; preserve this run and use a new --run-name")
        if not identity_path.exists(): save_json(identity_path, {"runId": run_id, **identity})
        before = time.perf_counter()
        graph, audit = import_maneuvers(osm, source["profile"]["bbox"], profile["model"])
        import_ms = (time.perf_counter() - before) * 1000
        if audit["previousGraphIdentity"] != source["graphIdentity"]:
            raise ValueError("Re-imported v1 graph differs from the frozen baseline")
        samples, replay_checks = sample_maneuvers(graph)
        atomic_write(output / "source-samples.osm", snapshot_samples(osm, samples))
        original_graph = load_json(reference / "graph.json")
        original_summary = load_json(reference / "summary.json")
        roads_by_id = {road["id"]: index for index, road in enumerate(graph.base.roads)}
        raw_seeds, snap = snap_source(graph.base, [source["profile"]["origin"]["lon"], source["profile"]["origin"]["lat"]])
        starts = []
        for road, _ in raw_seeds:
            edge = graph.base.roads[road]
            a, b, point = edge["fromPoint"], edge["toPoint"], snap["snapped"]
            dx, dy = b[0] - a[0], b[1] - a[1]
            fraction = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy)
            starts.append((road, Fraction(str(round(max(0, min(1, fraction)), 12)))))
        origins = [("san-diego", starts)]
        for origin in original_summary["oracleChecks"][1:profile["holdoutCount"] + 1]:
            old_road = original_graph["roads"][origin["seeds"][0][0]]["id"]
            origins.append((origin["origin"], [(roads_by_id[old_road], Fraction(1, 3))]))
        for sample in samples:
            rule = sample["restriction"]
            origins.extend([(f"restriction-{rule['id']}-from", [(rule["roads"][0], Fraction(1, 3))]),
                            (f"restriction-{rule['id']}-other", [(sample["alternativeRoad"], Fraction(1, 3))])])
        targets = sorted({road for _, attachments in origins for road, _ in attachments} |
                         {sample["restriction"]["roads"][-1] for sample in samples})
        cut_nodes = set(audit["cutExitNodes"])
        cut_states = [state for state, value in enumerate(graph.states) if graph.base.roads[value["road"]]["to"] in cut_nodes]
        cost_checks = budget_checks = destination_checks = bounded_destination_checks = 0
        checks, destinations = [], []
        oracle_dir = output / "oracles"
        oracle_dir.mkdir(exist_ok=True)
        for name, attachments in origins:
            seeds = source_seeds(graph, attachments)
            before = time.perf_counter()
            labels = dijkstra(graph.adjacency, seeds).labels
            search_ms = (time.perf_counter() - before) * 1000
            exact = bellman_ford(graph.adjacency, seeds)
            if labels != exact: raise ValueError("History-state Dijkstra/Bellman-Ford disagreement")
            cost_checks += len(labels)
            oracle = struct.pack(f"<{len(exact)}Q", *(UINT64_MAX if value == math.inf else value for value in exact))
            atomic_write(oracle_dir / f"{name}.u64le", oracle)
            boundary = min((labels[state] for state in cut_states), default=math.inf)
            budgets, bounded_fields = [], []
            for budget in profile["budgetsMs"]:
                bounded = dijkstra(graph.adjacency, seeds, budget)
                if bounded.labels != [cost if cost <= budget else math.inf for cost in exact]:
                    raise ValueError("Bounded history-state costs disagree")
                budget_checks += len(labels)
                bounded_fields.append((budget, bounded.labels))
                budgets.append({"budgetMs": budget, "reachableStates": bounded.settled_states,
                                "scannedArcs": bounded.scanned_arcs, "boundaryReachedWithinBudget": boundary <= budget,
                                "membershipSha256": hashlib.sha256(membership_bytes(exact, budget)).hexdigest()})
            for road in targets:
                for fraction_text in profile["destinationFractions"]:
                    fraction = Fraction(fraction_text)
                    actual = interior_destination(graph, labels, road, fraction, attachments)
                    expected = destination_oracle(graph, seeds, road, fraction, attachments)
                    if actual != expected: raise ValueError("Interior destination/sink oracle disagreement")
                    destination_checks += 1
                    for budget, bounded_labels in bounded_fields:
                        partial = interior_destination(graph, bounded_labels, road, fraction, attachments)
                        if (partial <= budget) != (expected <= budget):
                            raise ValueError("Bounded interior-destination membership disagrees")
                        bounded_destination_checks += 1
                    destinations.append({"origin": name, "roadId": graph.base.roads[road]["id"], "fraction": fraction_text,
                                         "costMs": actual if math.isfinite(actual) else None})
            checks.append({"origin": name, "starts": [[road, str(fraction)] for road, fraction in attachments], "seeds": seeds,
                           "fullSearchMs": search_ms, "costsCompared": len(labels), "budgets": budgets,
                           "firstCutExitMs": boundary if math.isfinite(boundary) else None})
            print(f"Qualified maneuver model: {name}", flush=True)
        graph_data = {"graphIdentity": graph.identity, "baseIdentity": graph.base.identity, "model": profile["model"],
                      "roads": graph.base.roads, "baseTransitions": graph.base.adjacency,
                      "states": graph.states, "initialStates": graph.initial_states,
                      "patterns": graph.patterns, "transitions": graph.adjacency}
        save_json(output / "graph.json", graph_data)
        save_json(output / "import-audit.json", audit)
        atomic_write(output / "graph.csr", pack_graph(graph.adjacency, graph.identity))
        summary = {"runId": run_id, "graphIdentity": graph.identity, "profile": profile, "baseRoads": len(graph.base.roads),
                   "states": len(graph.states), "transitions": sum(map(len, graph.adjacency)), "importMs": import_ms,
                   "restoredWays": len(audit["restoredWayIds"]), "restoredDirectedRoads": len(audit["restoredDirectedRoadIds"]),
                   "viaWayRestrictions": len(graph.patterns), "unsupportedRestrictions": len(audit["unsupportedRestrictions"]),
                   "blockedHistoryTransitions": len(graph.blocked_turns), "replayChecks": replay_checks, "sourceSamples": samples,
                   "sourceSnap": snap, "sourceAttachments": checks[0]["starts"], "origins": checks, "interiorDestinations": destinations,
                   "costComparisons": cost_checks, "boundedCostComparisons": budget_checks, "interiorDestinationComparisons": destination_checks,
                   "boundedDestinationMembershipComparisons": bounded_destination_checks,
                   "publicApiCalls": 0, "network": "none", "coverageVerified": False,
                   "workerMaxRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "workerWallMs": (time.perf_counter() - started) * 1000,
                   "limitations": ["Exactness applies to this simplified static imported graph, not real driving times or complete geography.",
                                   "Only unambiguous prohibited via-way maneuvers are supported; other rules retain audited conservative closures.",
                                   "Destination sinks share imported legal transitions; oracle agreement does not independently prove OSM semantics.",
                                   "Directed interior destination fractions exclude junction endpoints and geographic polygon construction.",
                                   "Cut flags and conservative exclusions still prevent complete long-range coverage; no WASM/Vercel/browser integration."]}
        save_json(output / "summary.json", summary)
        names = ["graph.json", "import-audit.json", "graph.csr", "summary.json", "source-samples.osm"] + [f"oracles/{name}.u64le" for name, _ in origins]
        save_json(output / "manifest.json", {"runId": run_id, **identity, "graphIdentity": graph.identity,
                  "artifacts": {name: {"bytes": (output / name).stat().st_size, "sha256": file_hash(output / name)} for name in names}})
        snapshots = output / "recipe"
        snapshots.mkdir(exist_ok=True)
        for name in scripts: atomic_write(snapshots / name, (recipe / name).read_bytes())
        print(json.dumps({key: summary[key] for key in ("baseRoads", "states", "transitions", "restoredWays", "viaWayRestrictions",
                         "costComparisons", "boundedCostComparisons", "interiorDestinationComparisons", "workerWallMs")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    run(parser.parse_args())
