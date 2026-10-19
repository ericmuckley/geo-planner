"""Offline cell-summary/storage/refinement comparison on the frozen state reference."""

import argparse
from collections import Counter
import fcntl
import json
import math
from pathlib import Path
import resource
import statistics
import struct
import time

from anchors import atomic_write, digest, file_hash, load_json, save_json
from cell_index import CellReader, build_cells, classify_cells, materialize, refine_targets, verify_cells
from state_graph import StateGraph, bellman_ford, classify, dijkstra, unpack_index


def checked_artifact(directory, manifest, name):
    expected = manifest["artifacts"][name]
    path = directory / name
    if path.stat().st_size != expected["bytes"] or file_hash(path) != expected["sha256"]:
        raise ValueError(f"Reference artifact checksum mismatch: {name}")
    return path


def percentiles(values):
    values = sorted(values)
    return {"p50": statistics.median(values), "p95": values[math.ceil(len(values) * .95) - 1]}


def validate_certificates(result, order, labels, budget):
    checks = 0
    for start, end, status, lower, upper in result["groups"]:
        for position in range(start, end):
            actual = labels[order[position]]
            if not lower <= actual <= upper or (status == "reachable" and actual > budget) or (status == "unreachable" and actual <= budget):
                raise ValueError("Unsafe group certificate")
            checks += 1
    for state, (status, lower, upper) in result["states"].items():
        actual = labels[state]
        if not lower <= actual <= upper or (status == "reachable" and actual > budget) or (status == "unreachable" and actual <= budget):
            raise ValueError("Unsafe detail certificate")
        checks += 1
    if checks != len(labels):
        raise ValueError("Certificate coverage mismatch")
    return checks


def run(args):
    started = time.perf_counter()
    reference, output, recipe = Path(args.reference), Path(args.output), Path(__file__).parent
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        profile = load_json(recipe / "profiles/cell-downtown-v1.json")
        source = load_json(reference / "manifest.json")
        if not source["completeLandmarkFields"]:
            raise ValueError("Reference fields must be complete")
        for name in ("graph.json", "landmarks.u32le", "summary.json", "import-audit.json"):
            checked_artifact(reference, source, name)
        graph_data = load_json(reference / "graph.json")
        identity = digest({"roads": graph_data["roads"], "transitions": graph_data["transitions"]})
        if identity != source["graphIdentity"] or graph_data["graphIdentity"] != identity:
            raise ValueError("Reference graph identity mismatch")
        graph = StateGraph(graph_data["roads"], graph_data["transitions"], [], [], identity)
        reference_summary = load_json(reference / "summary.json")
        index = unpack_index(graph, reference_summary["landmarkStates"], (reference / "landmarks.u32le").read_bytes(), identity, True)
        scripts = {name: file_hash(recipe / name) for name in ("cell_experiment.py", "cell_index.py", "state_graph.py", "anchors.py")}
        run_identity = {"profile": profile, "referenceRunId": source["runId"], "graphIdentity": identity,
                        "referenceArtifacts": source["artifacts"], "scripts": scripts, "toolsImageId": args.image_id}
        run_id = digest(run_identity)
        identity_path = output / "run-identity.json"
        if identity_path.exists() and load_json(identity_path)["runId"] != run_id:
            raise ValueError("Cell experiment inputs/code changed; preserve this run and use a new --run-name")
        if not identity_path.exists():
            save_json(identity_path, {"runId": run_id, **run_identity})
        preflight_ms = (time.perf_counter() - started) * 1000
        candidates = []
        for leaf_size in profile["leafSizes"]:
            directory = output / f"leaf-{leaf_size}"
            before = time.perf_counter()
            if (directory / "manifest.json").exists():
                metadata = verify_cells(directory, identity)
                if metadata["leafSize"] != leaf_size or metadata["landmarkStates"] != index.states:
                    raise ValueError("Mixed candidate index")
                count = metadata["stateCount"]
                order = list(struct.unpack(f"<{count}I", (directory / "states.u32le").read_bytes()))
                built = False
            else:
                metadata, order = build_cells(graph, index, leaf_size, directory)
                verify_cells(directory, identity)
                built = True
            candidates.append({"directory": directory, "metadata": metadata, "order": order,
                               "built": built, "prepareMs": (time.perf_counter() - before) * 1000})
        oracle_labels = {}
        oracle_checks = []
        for origin in reference_summary["oracleChecks"]:
            labels = bellman_ford(graph.adjacency, origin["seeds"])
            if dijkstra(graph.adjacency, origin["seeds"]).labels != labels:
                raise ValueError("Reference search disagreement")
            oracle_labels[origin["origin"]] = labels
            oracle_checks.append({"origin": origin["origin"], "labelsCompared": len(labels)})
        all_rows, certificate_checks = [], 0
        cut_nodes = set(load_json(reference / "import-audit.json")["cutExitNodes"])
        cut_states = [s for s, road in enumerate(graph.roads) if road["to"] in cut_nodes]
        for origin in reference_summary["oracleChecks"]:
            name, seeds = origin["origin"], origin["seeds"]
            labels = oracle_labels[name]
            for budget in profile["budgetsMs"]:
                baseline_times, full_times = [], []
                for _ in range(profile["repetitions"]):
                    before = time.perf_counter()
                    baseline = dijkstra(graph.adjacency, seeds, budget)
                    baseline_times.append((time.perf_counter() - before) * 1000)
                    before = time.perf_counter()
                    full_decisions = classify(graph, index, seeds, budget)
                    full_times.append((time.perf_counter() - before) * 1000)
                full_counts = dict(Counter(status for status, _, _ in full_decisions))
                for candidate in candidates:
                    samples = []
                    for repetition in range(profile["repetitions"]):
                        before = time.perf_counter()
                        reader = CellReader(candidate["directory"], candidate["metadata"])
                        try:
                            result = classify_cells(reader, seeds, budget)
                            classify_ms = (time.perf_counter() - before) * 1000
                            before = time.perf_counter()
                            reached, refinement = refine_targets(graph.adjacency, seeds, budget, result["unresolved"])
                            refine_ms = (time.perf_counter() - before) * 1000
                            samples.append({"classifyMs": classify_ms, "summaryMs": result["summaryMs"],
                                            "detailMs": result["detailMs"], "refineMs": refine_ms,
                                            "classifyAndRefineMs": classify_ms + refine_ms,
                                            "logicalIndexBytesRead": reader.bytes, "indexRangeReads": reader.reads,
                                            "cellsRead": reader.nodes_read, "detailStatesRead": reader.detail_states,
                                            **refinement})
                        finally:
                            reader.close()
                        if repetition == 0:
                            certificate_checks += validate_certificates(result, candidate["order"], labels, budget)
                            before = time.perf_counter()
                            membership = materialize(result, candidate["order"], reached)
                            materialize_ms = (time.perf_counter() - before) * 1000
                            if membership != [value <= budget for value in labels]:
                                raise ValueError("Refined membership differs from independent oracle")
                    if len({(s["logicalIndexBytesRead"], s["cellsRead"], s["detailStatesRead"]) for s in samples}) != 1:
                        raise ValueError("Nondeterministic index access pattern")
                    row = {"origin": name, "budgetMs": budget, "leafSize": candidate["metadata"]["leafSize"],
                           "summaryCertifiedStates": result["summaryCertified"],
                           "unresolvedStatesBeforeSearch": len(result["unresolved"]), "fullClassification": full_counts,
                           "baselineSettledStates": baseline.settled_states, "baselineScannedArcs": baseline.scanned_arcs,
                           "baselineGraphMs": percentiles(baseline_times), "fullClassificationMs": percentiles(full_times),
                           "candidateMs": {metric: percentiles([s[metric] for s in samples]) for metric in ("classifyMs", "refineMs", "classifyAndRefineMs")},
                           "samples": samples, "materializeForVerificationMs": materialize_ms,
                           "boundaryReachedWithinBudget": any(labels[state] <= budget for state in cut_states),
                           "membershipMismatches": 0, "unsafeCertificates": 0}
                    all_rows.append(row)
            print(f"Qualified grouped/refined queries for {name}", flush=True)
        summary = {"runId": run_id, "graphIdentity": identity, "profile": profile, "stateCount": len(graph.roads),
                   "oracleChecks": oracle_checks, "certificateStateBudgetChecks": certificate_checks,
                   "refinedMembershipChecks": certificate_checks, "preflightMs": preflight_ms,
                   "indexes": [{"leafSize": c["metadata"]["leafSize"], "nodeCount": c["metadata"]["nodeCount"],
                                "built": c["built"], "prepareMs": c["prepareMs"], "artifacts": c["metadata"]["artifacts"]} for c in candidates],
                   "queries": all_rows, "publicApiCalls": 0, "network": "none", "coverageVerified": False,
                   "workerMaxRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   "workerWallMs": (time.perf_counter() - started) * 1000,
                   "measurementLimits": ["Fresh file handles and application state per query; OS page cache was not flushed.",
                                         "logicalIndexBytesRead counts pread payload, not physical disk or network traffic; preflight hashes full files separately.",
                                         "Graph is fully resident during exact refinement; graph bytes are not included in index-range counters.",
                                         "Compact results use cell ranges; full membership expansion and verification are timed separately.",
                                         "Cell certification does not allow pruning transit paths; target refinement retains all required graph paths.",
                                         "Model exclusions and downtown cuts persist; no 12-hour, national, cloud or browser coverage proof."]}
        save_json(output / "summary.json", summary)
        artifact = {"bytes": (output / "summary.json").stat().st_size, "sha256": file_hash(output / "summary.json")}
        save_json(output / "manifest.json", {"runId": run_id, **run_identity, "summary": artifact})
        snapshots = output / "recipe"
        snapshots.mkdir(exist_ok=True)
        for name in scripts:
            atomic_write(snapshots / name, (recipe / name).read_bytes())
        print(json.dumps({"queries": len(all_rows), "certificateStateBudgetChecks": certificate_checks,
                          "mismatches": 0, "publicApiCalls": 0, "workerWallMs": summary["workerWallMs"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", default="/reference")
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    run(parser.parse_args())
