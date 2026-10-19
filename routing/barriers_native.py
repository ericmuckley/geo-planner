"""Independently execute the v3 graph using the unchanged native search kernel."""

import argparse
import fcntl
import hashlib
import json
import math
from pathlib import Path
import platform
import resource
import struct
import subprocess
import sys
import time

from anchors import atomic_write, digest, file_hash, load_json, save_json
from barrier_policy import MODEL_ID
from cell_experiment import checked_artifact, percentiles
from maneuver_graph import ManeuverGraph, interior_destination
from native_support import UINT64_MAX, NativeClient, compile_kernel, decode_labels, membership_bytes, pack_graph
from state_graph import StateGraph


def run(name):
    started = time.perf_counter()
    probe = subprocess.run([sys.executable, "-c", "import socket\ntry:\n s=socket.socket(); s.connect(('127.0.0.1',9))\nexcept PermissionError:\n print('denied')"], capture_output=True, text=True)
    if probe.returncode or probe.stdout.strip() != "denied": raise RuntimeError("A network-denying sandbox is required")
    directory = Path(__file__).resolve().parent.parent / "data/barrier-pilot" / name
    with (directory / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = load_json(directory / "manifest.json")
        for artifact in manifest["artifacts"]: checked_artifact(directory, manifest, artifact)
        data, summary = load_json(directory / "graph.json"), load_json(directory / "summary.json")
        base_id = digest({"roads": data["roads"], "transitions": data["baseTransitions"]})
        graph_id = digest({"model": data["model"]["id"], "baseIdentity": base_id, "patterns": data["patterns"],
                           "states": data["states"], "transitions": data["transitions"]})
        if data["model"]["id"] != MODEL_ID or base_id != data["baseIdentity"] or graph_id != data["graphIdentity"] or graph_id != manifest["graphIdentity"]:
            raise ValueError("Barrier graph identity mismatch")
        if pack_graph(data["transitions"], graph_id) != (directory / "graph.csr").read_bytes(): raise ValueError("CSR differs from JSON")
        graph = ManeuverGraph(StateGraph(data["roads"], data["baseTransitions"], [], [], base_id), data["states"],
                              data["initialStates"], data["transitions"], data["patterns"], [], graph_id)
        roads = {road["id"]: index for index, road in enumerate(graph.base.roads)}
        compilation = compile_kernel(directory / "native_search")
        client = NativeClient(directory / "native_search", directory / "graph.csr", graph_id)
        cases, destinations = [], []
        costs_checked = memberships_checked = 0
        try:
            startup = {"processStartupAndHelloMs": client.startup_ms, **client.hello}
            for origin in summary["origins"]:
                oracle = (directory / "oracles" / f"{origin['origin']}.u64le").read_bytes()
                exact = decode_labels(oracle, len(graph.states))
                meta, payload, elapsed = client.request(origin["seeds"], None)
                if payload != oracle: raise ValueError("Native v3 full costs disagree with Bellman-Ford")
                costs_checked += len(exact)
                for destination in summary["interiorDestinations"]:
                    if destination["origin"] != origin["origin"]: continue
                    actual = interior_destination(graph, exact, roads[destination["roadId"]], destination["fraction"], origin["starts"])
                    if actual != (math.inf if destination["costMs"] is None else destination["costMs"]): raise ValueError("Native partial destination disagrees")
                    destinations.append({**destination, "nativeCostMs": actual})
                for budget in summary["profile"]["budgetsMs"]:
                    case = next(row for row in origin["budgets"] if row["budgetMs"] == budget)
                    expected = {"labels": struct.pack(f"<{len(exact)}Q", *(value if value <= budget else UINT64_MAX for value in exact)),
                                "membership": membership_bytes(exact, budget)}
                    modes = {}
                    for mode in expected:
                        samples = []
                        for _ in range(summary["profile"]["nativeRepetitions"]):
                            meta, payload, elapsed = client.request(origin["seeds"], budget, mode)
                            if payload != expected[mode] or meta["settledStates"] != case["reachableStates"] or meta["scannedArcs"] != case["scannedArcs"]:
                                raise ValueError("Native bounded v3 costs/membership/traversal differ")
                            samples.append({**meta, "childRoundTripMs": elapsed})
                        if mode == "labels": costs_checked += len(exact)
                        else: memberships_checked += len(exact)
                        modes[mode] = {"payloadBytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "samples": samples,
                                       "timings": {metric: percentiles([row[metric] for row in samples]) for metric in
                                                   ("sourceSetupMs", "searchMs", "encodeMs", "childRoundTripMs")}}
                    cases.append({"origin": origin["origin"], "budgetMs": budget, "boundaryReachedWithinBudget": case["boundaryReachedWithinBudget"], "modes": modes})
                print(f"Native v3 qualified: {origin['origin']}", flush=True)
        finally: client.close()
        report = {"sourceRunId": manifest["runId"], "sourceManifestSha256": file_hash(directory / "manifest.json"), "graphIdentity": graph_id,
                  "compilation": compilation, "nativeStartup": startup, "cases": cases, "interiorDestinations": destinations,
                  "costComparisons": costs_checked, "membershipComparisons": memberships_checked, "interiorDestinationComparisons": len(destinations),
                  "workerSha256": file_hash(Path(__file__)), "networkPolicySha256": file_hash(Path(__file__).with_name("native-network.sb")),
                  "networkProbe": "loopback socket denied", "publicApiCalls": 0, "coverageVerified": False,
                  "platform": platform.platform(), "workerWallMs": (time.perf_counter() - started) * 1000,
                  "pythonWorkerMaxRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // (1024 if sys.platform == "darwin" else 1),
                  "timingLimits": "Five sequential observations per case/mode; p95 is the largest sample. Search is steady-clock loop wall time. Setup, encoding and local pipe round trips are separate; no HTTP, CPU-only, geographic-completeness, WASM or Vercel claim."}
        save_json(directory / "native-verification.json", report)
        atomic_write(directory / "recipe/barriers_native.py", Path(__file__).read_bytes())
        print(json.dumps({key: report[key] for key in ("costComparisons", "membershipComparisons", "interiorDestinationComparisons", "publicApiCalls")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", default="san-diego-tijuana-barriers-v3")
    args = parser.parse_args()
    if not args.run_name or any(not (c.isascii() and (c.isalnum() or c in "_-")) for c in args.run_name): parser.error("Invalid run name")
    run(args.run_name)
