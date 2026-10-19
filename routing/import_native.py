"""Qualify the larger streaming-import graph with the unchanged native kernel."""

import argparse
import fcntl
import json
from pathlib import Path
import resource
import struct
import subprocess
import sys

from anchors import atomic_write, digest, file_hash, load_json, save_json
from native_support import UINT64_MAX, NativeClient, compile_kernel, decode_labels, membership_bytes, pack_graph


def run(name):
    probe = subprocess.run([sys.executable, "-c", "import socket\ntry:\n s=socket.socket(); s.connect(('127.0.0.1',9))\nexcept PermissionError:\n print('denied')"], capture_output=True, text=True)
    if probe.returncode or probe.stdout.strip() != "denied": raise RuntimeError("A network-denying sandbox is required")
    directory = Path(__file__).resolve().parent.parent / "data/import-pilot" / name
    with (directory / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source = load_json(directory / "report.json")
        if source["case"] != "wide-v2": raise ValueError("Expected the qualified wider v2 import")
        for artifact, expected in source["artifacts"].items():
            path = directory / artifact
            if path.stat().st_size != expected["bytes"] or file_hash(path) != expected["sha256"]: raise ValueError("Wide artifact changed")
        data = load_json(directory / "graph.json")
        base_id = digest({"roads": data["roads"], "transitions": data["baseTransitions"]})
        graph_id = digest({"model": data["model"]["id"], "baseIdentity": base_id, "patterns": data["patterns"],
                           "states": data["states"], "transitions": data["transitions"]})
        if base_id != data["baseIdentity"] or graph_id != data["graphIdentity"] or graph_id != source["graphIdentity"]:
            raise ValueError("Wide graph identity mismatch")
        if pack_graph(data["transitions"], graph_id) != (directory / "graph.csr").read_bytes(): raise ValueError("Wide CSR differs from JSON")
        count = len(data["states"])
        del data
        compilation = compile_kernel(directory / "native_search")
        client = NativeClient(directory / "native_search", directory / "graph.csr", graph_id)
        costs = memberships = 0
        cases = []
        try:
            startup = {"processStartupAndHelloMs": client.startup_ms, **client.hello}
            for origin in source["origins"]:
                oracle = (directory / origin["oracleArtifact"]).read_bytes()
                exact = decode_labels(oracle, count)
                full, payload, full_roundtrip = client.request(origin["seeds"], None)
                if payload != oracle: raise ValueError("Wide native full costs differ from Bellman-Ford")
                costs += count
                budgets = []
                for case in origin["budgets"]:
                    budget = case["budgetMs"]
                    expected = {"labels": struct.pack(f"<{count}Q", *(value if value <= budget else UINT64_MAX for value in exact)),
                                "membership": membership_bytes(exact, budget)}
                    modes = {}
                    for mode, correct in expected.items():
                        meta, payload, elapsed = client.request(origin["seeds"], budget, mode)
                        if payload != correct or meta["settledStates"] != case["reachableStates"] or meta["scannedArcs"] != case["scannedArcs"]:
                            raise ValueError("Wide native bounded costs/membership/counts differ")
                        if mode == "labels": costs += count
                        else: memberships += count
                        modes[mode] = {**meta, "childRoundTripMs": elapsed}
                    budgets.append({**case, "modes": modes})
                cases.append({"origin": origin["origin"], "full": full, "fullChildRoundTripMs": full_roundtrip, "budgets": budgets})
                print(f"Native wider graph qualified: {origin['origin']}", flush=True)
        finally: client.close()
        report = {"sourceRunId": source["runId"], "sourceReportSha256": file_hash(directory / "report.json"), "graphIdentity": graph_id,
                  "compilation": compilation, "nativeStartup": startup, "cases": cases, "costComparisons": costs, "membershipComparisons": memberships,
                  "workerSha256": file_hash(Path(__file__)), "networkPolicySha256": file_hash(Path(__file__).with_name("native-network.sb")),
                  "pythonWorkerMaxRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // (1024 if sys.platform == "darwin" else 1),
                  "publicApiCalls": 0, "coverageVerified": False, "networkProbe": "loopback socket denied",
                  "timingLimits": "One observation per origin/budget/mode, for qualification. Setup, search-loop wall time, encoding and local pipe time are distinct. No distribution, HTTP, contour, CPU-only or cloud claim."}
        save_json(directory / "native-verification.json", report)
        atomic_write(directory / "recipe/import_native.py", Path(__file__).read_bytes())
        print(json.dumps({key: report[key] for key in ("costComparisons", "membershipComparisons", "publicApiCalls")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", default="stream-v1-wide-v2")
    args = parser.parse_args()
    if not args.run_name or any(not (c.isascii() and (c.isalnum() or c in "_-")) for c in args.run_name): parser.error("Invalid run name")
    run(args.run_name)
