"""Check and measure the larger regional graph with the unchanged native kernel."""

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
from cell_experiment import checked_artifact, percentiles
from maneuver_graph import ManeuverGraph, interior_destination
from native_support import UINT64_MAX, NativeClient, compile_kernel, decode_labels, membership_bytes, pack_graph
from state_graph import StateGraph


def run(args):
    started = time.perf_counter()
    probe = subprocess.run([sys.executable, "-c", "import socket\ntry:\n s=socket.socket(); s.connect(('127.0.0.1',9))\nexcept PermissionError:\n print('denied')"], capture_output=True, text=True)
    if probe.returncode != 0 or probe.stdout.strip() != "denied": raise RuntimeError("A network-denying sandbox is required")
    directory = Path(__file__).resolve().parent.parent / "data/regional-pilot" / args.run_name
    with (directory / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = load_json(directory / "manifest.json")
        for name in manifest["artifacts"]: checked_artifact(directory, manifest, name)
        data, summary = load_json(directory / "graph.json"), load_json(directory / "summary.json")
        base_id = digest({"roads": data["roads"], "transitions": data["baseTransitions"]})
        graph_id = digest({"model": data["model"]["id"], "baseIdentity": base_id, "patterns": data["patterns"],
                           "states": data["states"], "transitions": data["transitions"]})
        if graph_id != manifest["graphIdentity"] or graph_id != data["graphIdentity"] or base_id != data["baseIdentity"]:
            raise ValueError("Regional graph identity mismatch")
        if pack_graph(data["transitions"], graph_id) != (directory / "graph.csr").read_bytes(): raise ValueError("CSR differs from JSON")
        binary = directory / "native_search"
        compilation = compile_kernel(binary)
        graph = ManeuverGraph(StateGraph(data["roads"], data["baseTransitions"], [], [], base_id), data["states"],
                              data["initialStates"], data["transitions"], data["patterns"], [], graph_id)
        roads = {road["id"]: i for i, road in enumerate(graph.base.roads)}
        client = NativeClient(binary, directory / "graph.csr", graph_id)
        cases, full_checks = [], []
        costs_checked = memberships_checked = destinations_checked = 0
        try:
            startup = {"processStartupAndHelloMs": client.startup_ms, **client.hello}
            for origin in summary["origins"]:
                oracle = (directory / "oracles" / f"{origin['origin']}.u64le").read_bytes()
                exact = decode_labels(oracle, len(graph.states))
                meta, data_bytes, roundtrip = client.request(origin["seeds"], None)
                if data_bytes != oracle: raise ValueError("Native full costs disagree with Bellman-Ford")
                costs_checked += len(exact)
                full_checks.append({"origin": origin["origin"], "native": meta, "childRoundTripMs": roundtrip})
                for destination in summary["interiorDestinations"]:
                    if destination["origin"] != origin["origin"]: continue
                    actual = interior_destination(graph, exact, roads[destination["roadId"]], destination["fraction"], origin["starts"])
                    if actual != (math.inf if destination["costMs"] is None else destination["costMs"]): raise ValueError("Native interior cost differs")
                    destinations_checked += 1
                for budget in summary["profile"]["budgetsMs"]:
                    case = next(case for case in origin["budgets"] if case["budgetMs"] == budget)
                    expected = {"labels": struct.pack(f"<{len(exact)}Q", *(value if value <= budget else UINT64_MAX for value in exact)),
                                "membership": membership_bytes(exact, budget)}
                    formats = {}
                    for mode in ("labels", "membership"):
                        samples = []
                        for repetition in range(summary["profile"]["nativeRepetitions"]):
                            meta, payload, roundtrip = client.request(origin["seeds"], budget, mode)
                            if meta["settledStates"] != case["reachableStates"] or meta["scannedArcs"] != case["scannedArcs"]:
                                raise ValueError("Native/Python traversal counts differ")
                            before = time.perf_counter()
                            decoded = decode_labels(payload, len(exact)) if mode == "labels" else memoryview(payload)
                            if mode == "membership" and len(exact) % 8 and payload[-1] >> (len(exact) % 8): raise ValueError("Invalid bitmap padding")
                            decode_ms = (time.perf_counter() - before) * 1000
                            if payload != expected[mode]: raise ValueError("Native bounded result differs from oracle")
                            if repetition == 0:
                                if mode == "labels": costs_checked += len(exact)
                                else: memberships_checked += len(exact)
                            samples.append({**meta, "childRoundTripMs": roundtrip, "pythonDecodeMs": decode_ms,
                                            "roundTripAndDecodeMs": roundtrip + decode_ms, "setupAndSearchMs": meta["sourceSetupMs"] + meta["searchMs"]})
                        formats[mode] = {"payloadBytes": len(payload), "payloadSha256": hashlib.sha256(payload).hexdigest(), "samples": samples,
                                         "timings": {metric: percentiles([sample[metric] for sample in samples]) for metric in
                                                     ("sourceSetupMs", "searchMs", "setupAndSearchMs", "encodeMs", "childRoundTripMs", "pythonDecodeMs", "roundTripAndDecodeMs")}}
                    case = next(case for case in origin["budgets"] if case["budgetMs"] == budget)
                    if formats["membership"]["payloadSha256"] != case["membershipSha256"]: raise ValueError("Python/native bitmap identity differs")
                    cases.append({"origin": origin["origin"], "budgetMs": budget, "boundaryReachedWithinBudget": case["boundaryReachedWithinBudget"],
                                  "reachableStates": case["reachableStates"], "formats": formats})
                print(f"Native regional costs qualified: {origin['origin']}", flush=True)
        finally:
            client.close()
        fresh = []
        source = summary["origins"][0]
        for _ in range(3):
            client = NativeClient(binary, directory / "graph.csr", graph_id)
            try:
                meta, mask, elapsed = client.request(source["seeds"], summary["profile"]["budgetsMs"][-1], "membership")
                expected = membership_bytes(decode_labels((directory / "oracles" / f"{source['origin']}.u64le").read_bytes(), len(graph.states)), summary["profile"]["budgetsMs"][-1])
                if mask != expected: raise ValueError("Fresh native process differs")
                fresh.append({"startupAndHelloMs": client.startup_ms, "hello": client.hello, "query": meta, "childRoundTripMs": elapsed})
            finally: client.close()
        report = {"sourceRunId": manifest["runId"], "sourceManifestSha256": file_hash(directory / "manifest.json"), "graphIdentity": graph_id,
                  "compilation": compilation, "nativeStartup": startup, "fullChecks": full_checks, "cases": cases, "freshProcesses": fresh,
                  "platform": platform.platform(), "python": sys.version, "workerSha256": file_hash(Path(__file__)),
                  "networkPolicySha256": file_hash(Path(__file__).with_name("native-network.sb")), "networkProbe": "loopback socket denied",
                  "costComparisons": costs_checked, "membershipComparisons": memberships_checked, "interiorDestinationComparisons": destinations_checked,
                  "workerWallMs": (time.perf_counter() - started) * 1000,
                  "pythonWorkerMaxRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // (1024 if sys.platform == "darwin" else 1),
                  "publicApiCalls": 0, "coverageVerified": False,
                  "limits": ["Five sequential samples per case/mode; p95 is the largest sample, not a stable tail estimate.",
                             "Search loop, allocation/seeding, encoding and local pipe round trips are separately timed; no HTTP measurement.",
                             "Bitmap decode creates a checked view; correctness comparisons are outside decode timing.",
                             "Native runs on host macOS; Python reference runs in Docker. Do not attribute a cross-environment ratio solely to implementation.",
                             "Fresh processes do not flush OS caches. No WASM/Vercel/concurrency/geographic-completeness claim."]}
        save_json(directory / "native-verification.json", report)
        atomic_write(directory / "recipe/regional_native.py", Path(__file__).read_bytes())
        print(json.dumps({key: report[key] for key in ("costComparisons", "membershipComparisons", "interiorDestinationComparisons", "publicApiCalls")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", default="san-diego-tijuana-corridor-v2")
    args = parser.parse_args()
    if not args.run_name or any(not (c.isascii() and (c.isalnum() or c in "_-")) for c in args.run_name): parser.error("Invalid run name")
    run(args)
