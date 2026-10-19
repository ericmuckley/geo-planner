"""Measure streaming imports and prove frozen output equality before a wider retry."""

import argparse
import fcntl
import gzip
import hashlib
import json
import math
from pathlib import Path
import resource
import struct
import time

from anchors import atomic_write, digest, file_hash, load_json, save_json
from barriers import source_examples
from cell_experiment import checked_artifact
from maneuver_graph import replay
from native_support import UINT64_MAX, pack_graph
from regional_support import snap_attachments
from state_graph import bellman_ford, dijkstra
from stream_import import import_barriers, import_maneuvers


def resources():
    cgroup = Path("/sys/fs/cgroup")
    result = {"workerMaxRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    for name in ("memory.max", "memory.peak", "memory.current"):
        path = cgroup / name
        if path.exists(): result[name] = path.read_text().strip()
    events = cgroup / "memory.events"
    if events.exists(): result["memory.events"] = dict(line.split() for line in events.read_text().splitlines())
    return result


def graph_data(graph, model):
    return {"graphIdentity": graph.identity, "baseIdentity": graph.base.identity, "model": model,
            "roads": graph.base.roads, "baseTransitions": graph.base.adjacency, "states": graph.states,
            "initialStates": graph.initial_states, "patterns": graph.patterns, "transitions": graph.adjacency}


def qualify_wide(output, graph, audit, profile, fixture):
    by_id = {road["id"]: index for index, road in enumerate(graph.base.roads)}
    patterns = {rule["id"]: rule for rule in graph.patterns}
    for sample in load_json(fixture / "summary.json")["sourceSamples"]:
        original = sample["restriction"]
        rule = patterns[original["id"]]
        if rule["roadIds"] != original["roadIds"]: raise ValueError("Wider import changed a qualified maneuver")
        if replay(graph, rule["roads"])["allowed"] or not replay(graph, [by_id[sample["alternativeRoadId"]]] + rule["roads"][1:])["allowed"]:
            raise ValueError("Wider maneuver decision differs")
    cut_nodes = set(audit["cutExitNodes"])
    cut_states = [index for index, state in enumerate(graph.states) if graph.base.roads[state["road"]]["to"] in cut_nodes]
    cases = []
    (output / "oracles").mkdir(exist_ok=True)
    for origin in profile["origins"]:
        starts, seeds, snap = snap_attachments(graph, [origin["lon"], origin["lat"]], profile["sourceSnapMaxMeters"])
        before = time.perf_counter()
        result = dijkstra(graph.adjacency, seeds)
        search_ms = (time.perf_counter() - before) * 1000
        before = time.perf_counter()
        oracle = bellman_ford(graph.adjacency, seeds)
        oracle_ms = (time.perf_counter() - before) * 1000
        if result.labels != oracle: raise ValueError("Wide Dijkstra/Bellman-Ford differ")
        boundary = min((oracle[state] for state in cut_states), default=math.inf)
        budgets = []
        for budget in profile["budgetsMs"]:
            bounded = dijkstra(graph.adjacency, seeds, budget)
            if bounded.labels != [value if value <= budget else math.inf for value in oracle]: raise ValueError("Wide bounded costs differ")
            budgets.append({"budgetMs": budget, "reachableStates": bounded.settled_states, "scannedArcs": bounded.scanned_arcs,
                            "boundaryReachedWithinBudget": boundary <= budget})
        artifact = f"oracles/{origin['id']}.u64le"
        atomic_write(output / artifact, struct.pack(f"<{len(oracle)}Q", *(UINT64_MAX if value == math.inf else value for value in oracle)))
        cases.append({"origin": origin["id"], "starts": [[road, str(offset)] for road, offset in starts], "seeds": seeds, "snap": snap,
                      "fullReachableStates": result.settled_states, "firstCutExitMs": boundary if math.isfinite(boundary) else None,
                      "pythonFullSearchMs": search_ms, "bellmanFordMs": oracle_ms, "budgets": budgets, "oracleArtifact": artifact})
        print(f"Wide oracle qualified: {origin['id']}; first cut {boundary} ms", flush=True)
    return {"origins": cases, "costComparisons": len(graph.states) * len(cases),
            "boundedCostComparisons": len(graph.states) * len(cases) * len(profile["budgetsMs"]),
            "coverageVerified": False, "scope": "Same conservative v2 semantics; no barrier policy expansion, contour or real driving-time validation."}


def run(args):
    started = time.perf_counter()
    output, recipe = Path(args.output), Path(__file__).parent
    with (output / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source_dir = {"downtown-v2": Path("/downtown"), "corridor-v2": Path("/corridor"), "corridor-v3": Path("/barriers"), "wide-v2": Path("/wide")}[args.case]
        wide = args.case == "wide-v2"
        previous = load_json(source_dir / ("run-identity.json" if wide else "manifest.json"))
        if previous["imageId"] != args.image_id: raise ValueError("Tools image differs from source recipe")
        if wide:
            filtered = load_json(source_dir / "car-filter.json")
            source = source_dir / "car-roads.osm"
            if source.stat().st_size != filtered["bytes"] or file_hash(source) != filtered["sha256"]: raise ValueError("Wide cached XML differs")
        else:
            for name in previous["artifacts"]: checked_artifact(source_dir, previous, name)
            source = Path("/reference/roads.osm") if args.case == "downtown-v2" else Path("/corridor/car-roads.osm")
        profile = previous["profile"]
        bounds = profile.get("bbox", previous.get("bbox"))
        if bounds is None: raise ValueError("Missing source bounds")
        if args.case == "downtown-v2" and file_hash(source) != previous["sourceXmlSha256"]: raise ValueError("Downtown input differs")
        if args.case == "corridor-v3" and file_hash(source) != previous["sourceArtifact"]["sha256"]: raise ValueError("Barrier input differs")
        scripts = {path.name: file_hash(path) for path in recipe.glob("*.py") if path.name in {
            "import_capacity.py", "stream_import.py", "import_roads.py", "import_maneuvers.py", "barrier_policy.py", "barriers.py",
            "state_graph.py", "maneuver_graph.py", "native_support.py", "anchors.py", "regional_support.py", "reference.py", "cell_experiment.py", "cell_index.py"}}
        identity = {"case": args.case, "previousRunId": previous["runId"], "previousManifestSha256": file_hash(source_dir / ("run-identity.json" if wide else "manifest.json")),
                    "sourceXmlSha256": file_hash(source), "profile": profile, "bbox": bounds, "scripts": scripts,
                    "imageId": args.image_id, "memoryLimit": "4g", "cpus": 2, "network": "none"}
        run_id = digest(identity)
        identity_path = output / "run-identity.json"
        if identity_path.exists() and load_json(identity_path)["runId"] != run_id: raise ValueError("Code/input changed; use a new run name")
        if (output / "report.json").exists(): raise ValueError("Completed import exists; preserve it and use a new run name")
        save_json(identity_path, {"runId": run_id, **identity})
        checkpoints = {"preflight": resources()}
        measurements = {}
        before = time.perf_counter()
        if args.case == "corridor-v3":
            graph, audit = import_barriers(source, output / "barrier-roads.osm", bounds, profile["model"], measurements)
        else:
            graph, audit = import_maneuvers(source, bounds, profile["model"], measurements)
        import_ms = (time.perf_counter() - before) * 1000
        checkpoints["import"] = resources()
        print(f"Stream import: {len(graph.states)} states in {import_ms:.1f} ms; RSS {checkpoints['import']['workerMaxRssKiB']} KiB", flush=True)
        if args.case == "corridor-v3": source_examples(source, output / "barrier-source-samples.osm", graph, audit)
        data = graph_data(graph, profile["model"])
        packed = pack_graph(graph.adjacency, graph.identity)
        compressed = gzip.compress(packed, mtime=0)
        actual = {"graph.json": digest(data), "import-audit.json": digest(audit), "graph.csr": hashlib.sha256(packed).hexdigest()}
        if "graph.csr.gz" in previous.get("artifacts", {}): actual["graph.csr.gz"] = hashlib.sha256(compressed).hexdigest()
        if args.case == "corridor-v3":
            for name in ("barrier-roads.osm", "barrier-source-samples.osm"): actual[name] = file_hash(output / name)
        checkpoints["packAndHash"] = resources()
        if not wide:
            for name, value in actual.items():
                if previous["artifacts"][name]["sha256"] != value: raise ValueError(f"Streaming import differs: {name}")
            qualification = {"identicalArtifactSha256": actual, "graphIdentity": graph.identity,
                             "scope": "Graph/audit/packed bytes reproduced; prior oracle vectors verified, not recomputed."}
        else:
            save_json(output / "graph.json", data)
            save_json(output / "import-audit.json", audit)
            atomic_write(output / "graph.csr", packed)
            atomic_write(output / "graph.csr.gz", compressed)
            del data, packed, compressed
            qualification = qualify_wide(output, graph, audit, profile, Path("/downtown"))
            names = ["graph.json", "import-audit.json", "graph.csr", "graph.csr.gz"] + [row["oracleArtifact"] for row in qualification["origins"]]
            qualification["artifacts"] = {name: {"bytes": (output / name).stat().st_size, "sha256": file_hash(output / name)} for name in names}
        checkpoints["complete"] = resources()
        report = {"runId": run_id, **identity, "graphIdentity": graph.identity, "roads": len(graph.base.roads), "states": len(graph.states),
                  "transitions": sum(map(len, graph.adjacency)), "importMs": import_ms, "importStages": measurements,
                  "workerWallMs": (time.perf_counter() - started) * 1000, "resourceCheckpoints": checkpoints, **qualification,
                  "publicApiCalls": 0, "coverageVerified": False}
        save_json(output / "report.json", report)
        (output / "recipe").mkdir(exist_ok=True)
        for name in scripts: atomic_write(output / "recipe" / name, (recipe / name).read_bytes())
        print(json.dumps({key: report[key] for key in ("case", "states", "transitions", "importMs", "workerWallMs", "resourceCheckpoints", "publicApiCalls")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=("downtown-v2", "corridor-v2", "corridor-v3", "wide-v2"))
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--output", default="/output")
    run(parser.parse_args())
