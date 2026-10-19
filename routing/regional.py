"""Resource-bounded expansion from cached California/Baja roads, without network."""

import argparse
from fractions import Fraction
import fcntl
import gzip
import hashlib
import json
import math
from pathlib import Path
import resource
import struct
import subprocess
import time

from anchors import atomic_write, digest, file_hash, load_json, save_json
from cell_experiment import checked_artifact
from import_maneuvers import import_maneuvers
from maneuver_graph import destination_oracle, interior_destination, replay, source_seeds
from native_support import UINT64_MAX, membership_bytes, pack_graph
from reference import extract
from regional_support import cached_extract, check_bounds, route_to_interior, snap_attachments, supported_xml
from state_graph import bellman_ford, dijkstra


def qualify(output, osm, profile, source, model_reference, run_id):
    before = time.perf_counter()
    graph, audit = import_maneuvers(osm, profile["bbox"], profile["model"])
    import_ms = (time.perf_counter() - before) * 1000
    print(f"Imported {len(graph.base.roads)} roads / {len(graph.states)} states in {import_ms:.1f} ms", flush=True)
    old = load_json(model_reference / "manifest.json")
    for name in old["artifacts"]: checked_artifact(model_reference, old, name)
    if old["regionArtifact"] != source: raise ValueError("Semantic reference uses different OSM")
    old_summary = load_json(model_reference / "summary.json")
    by_id = {road["id"]: index for index, road in enumerate(graph.base.roads)}
    rules = {rule["id"]: rule for rule in graph.patterns}
    origins, errors, samples = [], [], []
    for origin in profile["origins"]:
        try:
            starts, seeds, snap = snap_attachments(graph, [origin["lon"], origin["lat"]], profile["sourceSnapMaxMeters"])
            origins.append({"id": origin["id"], "starts": starts, "seeds": seeds, "snap": snap})
        except ValueError as error:
            errors.append({"origin": origin, "error": str(error)})
    for previous in old_summary["sourceSamples"]:
        previous_rule = previous["restriction"]
        if previous_rule["id"] not in rules or rules[previous_rule["id"]]["roadIds"] != previous_rule["roadIds"]:
            raise ValueError("Expanded graph lost a qualified maneuver fixture")
        rule, other = rules[previous_rule["id"]], by_id[previous["alternativeRoadId"]]
        blocked, allowed = replay(graph, rule["roads"]), replay(graph, [other] + rule["roads"][1:])
        if blocked["allowed"] or not allowed["allowed"]: raise ValueError("Qualified maneuver decision changed")
        samples.append({"restriction": rule, "alternativeRoad": other, "blocked": blocked, "allowed": allowed})
        for suffix, road in (("from", rule["roads"][0]), ("other", other)):
            starts = [(road, Fraction(1, 3))]
            origins.append({"id": f"restriction-{rule['id']}-{suffix}", "starts": starts, "seeds": source_seeds(graph, starts), "snap": None})
    if not any(origin["id"] == "san-diego" for origin in origins): raise ValueError("Default source failed to snap")
    targets = sorted({sample["restriction"]["roads"][-1] for sample in samples})
    cut_nodes = set(audit["cutExitNodes"])
    cut_states = [i for i, state in enumerate(graph.states) if graph.base.roads[state["road"]]["to"] in cut_nodes]
    oracles, checks, destinations, routes = [], [], [], []
    counts = {"costComparisons": 0, "boundedCostComparisons": 0, "interiorDestinationComparisons": 0, "boundedDestinationMembershipComparisons": 0}
    (output / "oracles").mkdir(exist_ok=True)
    for origin in origins:
        name, starts, seeds = origin["id"], origin["starts"], origin["seeds"]
        before = time.perf_counter()
        result = dijkstra(graph.adjacency, seeds)
        search_ms = (time.perf_counter() - before) * 1000
        before = time.perf_counter()
        exact = bellman_ford(graph.adjacency, seeds)
        oracle_ms = (time.perf_counter() - before) * 1000
        if result.labels != exact: raise ValueError("Regional Dijkstra/Bellman-Ford disagreement")
        counts["costComparisons"] += len(exact)
        oracle_name = f"oracles/{name}.u64le"
        atomic_write(output / oracle_name, struct.pack(f"<{len(exact)}Q", *(UINT64_MAX if value == math.inf else value for value in exact)))
        oracles.append(oracle_name)
        boundary = min((exact[state] for state in cut_states), default=math.inf)
        budgets, fields = [], []
        for budget in profile["budgetsMs"]:
            before = time.perf_counter()
            bounded = dijkstra(graph.adjacency, seeds, budget)
            elapsed = (time.perf_counter() - before) * 1000
            if bounded.labels != [cost if cost <= budget else math.inf for cost in exact]: raise ValueError("Regional bounded costs disagree")
            counts["boundedCostComparisons"] += len(exact)
            fields.append((budget, bounded.labels))
            budgets.append({"budgetMs": budget, "reachableStates": bounded.settled_states, "scannedArcs": bounded.scanned_arcs,
                            "pythonSetupAndSearchMs": elapsed, "boundaryReachedWithinBudget": boundary <= budget,
                            "membershipSha256": hashlib.sha256(membership_bytes(exact, budget)).hexdigest()})
        for road in targets:
            for fraction in profile["destinationFractions"]:
                actual = interior_destination(graph, exact, road, fraction, starts)
                expected = destination_oracle(graph, seeds, road, fraction, starts)
                if actual != expected: raise ValueError("Regional interior/sink disagreement")
                counts["interiorDestinationComparisons"] += 1
                for budget, labels in fields:
                    if (interior_destination(graph, labels, road, fraction, starts) <= budget) != (expected <= budget):
                        raise ValueError("Regional bounded interior membership disagreement")
                    counts["boundedDestinationMembershipComparisons"] += 1
                destinations.append({"origin": name, "roadId": graph.base.roads[road]["id"], "fraction": fraction,
                                     "costMs": actual if math.isfinite(actual) else None})
        if origin["snap"]:
            for destination in origins:
                if not destination["snap"] or destination["id"] == name: continue
                candidates = []
                for road, fraction in destination["starts"]:
                    if 0 < fraction < 1:
                        trace = route_to_interior(graph, exact, seeds, starts, road, fraction)
                        if trace["costMs"] is not None: candidates.append((trace["costMs"], road, fraction, trace))
                if not candidates:
                    routes.append({"origin": name, "destination": destination["id"], "costMs": None,
                                   "status": "unreachable in imported model or unsupported endpoint attachment"})
                    continue
                cost, road, fraction, trace = min(candidates, key=lambda value: value[0])
                if cost != interior_destination(graph, exact, road, fraction, starts): raise ValueError("Recovered route cost differs")
                routes.append({"origin": name, "destination": destination["id"], **trace,
                               "targetRoadId": graph.base.roads[road]["id"], "targetFraction": str(fraction),
                               "withinBudgetsMs": [budget for budget in profile["budgetsMs"] if cost <= budget]})
        checks.append({"origin": name, "starts": [[road, str(fraction)] for road, fraction in starts], "seeds": seeds, "snap": origin["snap"],
                       "fullSearchMs": search_ms, "bellmanFordMs": oracle_ms, "fullReachableStates": result.settled_states,
                       "firstCutExitMs": boundary if math.isfinite(boundary) else None, "budgets": budgets})
        print(f"Qualified {name}: {len(exact)} costs; cut at {boundary} ms", flush=True)
    save_json(output / "graph.json", {"graphIdentity": graph.identity, "baseIdentity": graph.base.identity, "model": profile["model"],
              "roads": graph.base.roads, "baseTransitions": graph.base.adjacency, "states": graph.states,
              "initialStates": graph.initial_states, "patterns": graph.patterns, "transitions": graph.adjacency})
    save_json(output / "import-audit.json", audit)
    packed = pack_graph(graph.adjacency, graph.identity)
    atomic_write(output / "graph.csr", packed)
    atomic_write(output / "graph.csr.gz", gzip.compress(packed, mtime=0))
    atomic_write(output / "source-samples.osm", (model_reference / "source-samples.osm").read_bytes())
    return {"runId": run_id, "graphIdentity": graph.identity, "profile": profile, "baseRoads": len(graph.base.roads), "states": len(graph.states),
            "transitions": sum(map(len, graph.adjacency)), "importMs": import_ms, "restoredWays": len(audit["restoredWayIds"]),
            "viaWayRestrictions": len(graph.patterns), "unsupportedRestrictions": len(audit["unsupportedRestrictions"]),
            "excludedWayCounts": audit["excludedWayCounts"], "sourceSamples": samples, "origins": checks, "failedOrigins": errors,
            "interiorDestinations": destinations, "sampledRoutes": routes, "oracleArtifacts": oracles, **counts,
            "publicApiCalls": 0, "network": "none", "coverageVerified": False, "borderPolicy": profile["borderPolicy"]}


def run(args):
    started = time.perf_counter()
    directory, output, recipe = Path(args.data), Path(args.output), Path(__file__).parent
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        build = load_json(directory / "build-complete.json")
        if build["manifest"]["id"] != args.expected_graph: raise ValueError("Selected graph differs from source manifest")
        profile = load_json(recipe / "profiles/regional-border-v1.json")
        check_bounds(profile["bbox"], build["manifest"]["bbox"])
        scripts = {name: file_hash(recipe / name) for name in ("regional.py", "regional_support.py", "reference.py", "import_maneuvers.py", "maneuver_graph.py",
                    "import_roads.py", "state_graph.py", "anchors.py", "native_support.py", "cell_experiment.py", "cell_index.py")}
        identity = {"sourceManifest": build["manifest"], "regionArtifact": build["artifacts"]["region.osm.pbf"], "profile": profile,
                    "scripts": scripts, "imageId": args.image_id, "network": "none", "cpus": 2, "memoryLimit": "4g"}
        run_id = digest(identity)
        identity_path = output / "run-identity.json"
        if identity_path.exists() and load_json(identity_path)["runId"] != run_id: raise ValueError("Regional code/input/profile changed; use a new --run-name")
        if not identity_path.exists(): save_json(identity_path, {"runId": run_id, **identity})
        before = time.perf_counter()
        if args.extract_cache:
            osm, preparation = cached_extract(Path(args.extract_cache), identity["regionArtifact"], profile["bbox"], args.image_id)
        else:
            osm = extract(directory, output, build, profile, args.image_id)
            info = json.loads(subprocess.check_output(["osmium", "fileinfo", "-e", "-j", str(output / "region.osm.pbf")], text=True))
            preparation = {"source": identity["regionArtifact"], "bbox": profile["bbox"], "xmlBytes": osm.stat().st_size, "xmlSha256": file_hash(osm),
                           "pbfBytes": (output / "region.osm.pbf").stat().st_size, "pbfSha256": file_hash(output / "region.osm.pbf"), "fileinfo": info}
        preparation = {**preparation, "runId": run_id, "cacheReused": bool(args.extract_cache), "currentPreflightMs": (time.perf_counter() - before) * 1000}
        save_json(output / "preparation.json", preparation)
        if args.stage == "extract": print(json.dumps(preparation, indent=2)); return
        osm = supported_xml(osm, output, args.image_id)
        print(f"Supported-highway XML: {osm.stat().st_size} bytes", flush=True)
        summary = qualify(output, osm, profile, identity["regionArtifact"], Path(args.model_reference), run_id)
        summary.update({"workerMaxRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        "workerWallMs": (time.perf_counter() - started) * 1000, "memoryLimit": "4g"})
        save_json(output / "summary.json", summary)
        names = ["graph.json", "graph.csr", "graph.csr.gz", "summary.json", "import-audit.json", "source-samples.osm", "car-roads.osm", "car-filter.json"] + summary["oracleArtifacts"]
        save_json(output / "manifest.json", {"runId": run_id, **identity, "graphIdentity": summary["graphIdentity"], "inputXmlSha256": preparation["xmlSha256"],
                  "artifacts": {name: {"bytes": (output / name).stat().st_size, "sha256": file_hash(output / name)} for name in names}})
        snapshots = output / "recipe"
        snapshots.mkdir(exist_ok=True)
        for name in scripts: atomic_write(snapshots / name, (recipe / name).read_bytes())
        print(json.dumps({key: summary[key] for key in ("baseRoads", "states", "transitions", "importMs", "workerWallMs", "workerMaxRssKiB", "failedOrigins", "publicApiCalls")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="/data")
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--expected-graph", required=True)
    parser.add_argument("--stage", choices=("extract", "build"), default="build")
    parser.add_argument("--model-reference", required=True)
    parser.add_argument("--extract-cache")
    run(parser.parse_args())
