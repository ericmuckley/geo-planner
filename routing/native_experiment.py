"""Quota-free local C++/CSR baseline on the frozen static state graph."""

import argparse
import fcntl
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time

from anchors import atomic_write, digest, file_hash, load_json, save_json
from cell_experiment import checked_artifact, percentiles
from native_support import NativeClient, compile_kernel, compiler_config, decode_labels, membership_bytes, pack_graph, verify_packed
from state_graph import bellman_ford, dijkstra


def run(args):
    started = time.perf_counter()
    reference, output, recipe = Path(args.reference), Path(args.output), Path(__file__).parent
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Check the actual inherited policy without contacting any external service.
        probe = subprocess.run([sys.executable, "-c", "import socket\ntry:\n s=socket.socket(); s.connect(('127.0.0.1',9))\nexcept PermissionError:\n print('denied')"], capture_output=True, text=True)
        if probe.returncode != 0 or probe.stdout.strip() != "denied":
            raise RuntimeError("Native benchmark requires a working network-denying sandbox")
        profile = load_json(recipe / "profiles/native-downtown-v1.json")
        source = load_json(reference / "manifest.json")
        for name in ("graph.json", "summary.json", "import-audit.json"):
            checked_artifact(reference, source, name)
        graph = load_json(reference / "graph.json")
        graph_id = digest({"roads": graph["roads"], "transitions": graph["transitions"]})
        if graph_id != source["graphIdentity"] or graph["graphIdentity"] != graph_id:
            raise ValueError("Reference graph identity mismatch")
        config = compiler_config()
        scripts = {name: file_hash(recipe / name) for name in ("native_experiment.py", "native_support.py", "native_search.cpp", "native-network.sb",
                                                              "anchors.py", "state_graph.py", "cell_experiment.py", "cell_index.py")}
        run_identity = {"profile": profile, "referenceRunId": source["runId"], "referenceArtifacts": source["artifacts"],
                        "graphIdentity": graph_id, "scripts": scripts, "compiler": config,
                        "platform": platform.platform(), "architecture": platform.machine(), "python": sys.version,
                        "networkPolicy": "macOS sandbox-exec: deny network*; no provider/fallback"}
        run_id = digest(run_identity)
        identity_path = output / "run-identity.json"
        if identity_path.exists() and load_json(identity_path)["runId"] != run_id:
            raise ValueError("Native experiment inputs/code/compiler changed; preserve this run and use a new --run-name")
        if not identity_path.exists(): save_json(identity_path, {"runId": run_id, **run_identity})
        before = time.perf_counter()
        packed = pack_graph(graph["transitions"], graph_id)
        artifact = {"bytes": len(packed), "sha256": hashlib.sha256(packed).hexdigest()}
        packed_path = output / "graph.csr"
        if packed_path.exists(): verify_packed(packed_path, artifact)
        else: atomic_write(packed_path, packed)
        atomic_write(output / "graph.csr.gz", gzip.compress(packed, mtime=0))
        packing_ms = (time.perf_counter() - before) * 1000
        binary = output / "native_search"
        compilation = compile_kernel(binary, config)
        reference_summary = load_json(reference / "summary.json")
        audit = load_json(reference / "import-audit.json")
        cut_nodes = set(audit["cutExitNodes"])
        cut_states = [state for state, road in enumerate(graph["roads"]) if road["to"] in cut_nodes]
        preflight_pack_compile_ms = (time.perf_counter() - started) * 1000
        labels_checked = memberships_checked = 0
        full_checks, cases = [], []
        client = NativeClient(binary, packed_path, graph_id)
        try:
            native_startup = {"processStartupAndHelloMs": client.startup_ms, **client.hello}
            for origin in reference_summary["oracleChecks"]:
                name, seeds = origin["origin"], origin["seeds"]
                exact = bellman_ford(graph["transitions"], seeds)
                if dijkstra(graph["transitions"], seeds).labels != exact:
                    raise ValueError("Python reference search disagreement")
                metadata, payload, roundtrip = client.request(seeds, None, "labels")
                if decode_labels(payload, len(exact)) != exact:
                    raise ValueError("Native full-state cost disagreement")
                labels_checked += len(exact)
                full_checks.append({"origin": name, "labelsCompared": len(exact), "native": metadata, "childRoundTripMs": roundtrip})
                boundary_time = min((exact[state] for state in cut_states), default=math.inf)
                for budget in profile["budgetsMs"]:
                    python_samples = []
                    for _ in range(profile["repetitions"]):
                        before = time.perf_counter()
                        baseline = dijkstra(graph["transitions"], seeds, budget)
                        python_samples.append((time.perf_counter() - before) * 1000)
                    expected_costs = [cost if cost <= budget else math.inf for cost in exact]
                    expected_mask = membership_bytes(exact, budget)
                    formats = {}
                    for mode in profile["outputModes"]:
                        samples, payload_digest = [], None
                        for repetition in range(profile["repetitions"]):
                            meta, data, roundtrip = client.request(seeds, budget, mode)
                            before = time.perf_counter()
                            if mode == "labels":
                                decoded = decode_labels(data, len(exact))
                            else:
                                decoded = memoryview(data)
                                if len(exact) % 8 and data[-1] >> (len(exact) % 8):
                                    raise ValueError("Nonzero membership padding bits")
                            decode_ms = (time.perf_counter() - before) * 1000
                            if meta["settledStates"] != baseline.settled_states or meta["scannedArcs"] != baseline.scanned_arcs:
                                raise ValueError("Native/Python traversal counts differ")
                            if repetition == 0:
                                if mode == "labels":
                                    if decoded != expected_costs: raise ValueError("Native bounded costs disagree")
                                    labels_checked += len(exact)
                                else:
                                    if data != expected_mask: raise ValueError("Native membership bitmap disagrees")
                                    memberships_checked += len(exact)
                                payload_digest = hashlib.sha256(data).hexdigest()
                            elif hashlib.sha256(data).hexdigest() != payload_digest:
                                raise ValueError("Nondeterministic native result bytes")
                            samples.append({**meta, "childRoundTripMs": roundtrip, "pythonDecodeMs": decode_ms,
                                            "roundTripAndDecodeMs": roundtrip + decode_ms})
                        formats[mode] = {"payloadBytes": len(data), "payloadSha256": payload_digest, "samples": samples,
                                         "timings": {metric: percentiles([sample[metric] for sample in samples]) for metric in
                                                     ("sourceSetupMs", "searchMs", "encodeMs", "childRoundTripMs", "pythonDecodeMs", "roundTripAndDecodeMs")}}
                    cases.append({"origin": name, "seeds": seeds, "budgetMs": budget,
                                  "pythonGraphSamplesMs": python_samples, "pythonGraphMs": percentiles(python_samples),
                                  "reachableStates": baseline.settled_states, "scannedArcs": baseline.scanned_arcs,
                                  "firstCutExitMs": boundary_time if math.isfinite(boundary_time) else None,
                                  "boundaryReachedWithinBudget": boundary_time <= budget, "formats": formats})
                print(f"Qualified native costs/bitmaps for {name}", flush=True)
        finally:
            client.close()
        fresh_processes = []
        sample_origin = reference_summary["oracleChecks"][0]
        expected = membership_bytes(bellman_ford(graph["transitions"], sample_origin["seeds"]), profile["budgetsMs"][-1])
        for _ in range(profile["freshProcesses"]):
            before = time.perf_counter()
            fresh = NativeClient(binary, packed_path, graph_id)
            try:
                meta, data, roundtrip = fresh.request(sample_origin["seeds"], profile["budgetsMs"][-1], "membership")
                if data != expected: raise ValueError("Fresh-process result mismatch")
                fresh_processes.append({"startupAndHelloMs": fresh.startup_ms, "hello": fresh.hello, "firstQuery": meta,
                                        "childRoundTripMs": roundtrip, "startupThroughFirstReplyMs": (time.perf_counter() - before) * 1000})
            finally:
                fresh.close()
        summary = {"runId": run_id, "graphIdentity": graph_id, "profile": profile, "graphStates": len(graph["roads"]),
                   "graphArcs": sum(map(len, graph["transitions"])), "packedGraph": artifact,
                   "packedGraphGzipBytes": (output / "graph.csr.gz").stat().st_size, "packingMs": packing_ms,
                   "compilation": compilation, "preflightPackCompileMs": preflight_pack_compile_ms,
                   "nativeStartup": native_startup, "fullChecks": full_checks, "cases": cases, "freshProcesses": fresh_processes,
                   "nativeCostComparisons": labels_checked, "nativeMembershipComparisons": memberships_checked,
                   "publicApiCalls": 0, "coverageVerified": False, "networkPolicy": run_identity["networkPolicy"],
                   "networkDenialProbe": "loopback socket operation denied; no external service contacted",
                   "pythonWorkerMaxRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // (1024 if sys.platform == "darwin" else 1),
                   "workerWallMs": (time.perf_counter() - started) * 1000,
                   "measurementLimits": ["Same local Mac/Python baseline; earlier Docker/Python timings are not the comparison baseline.",
                                         "Native searchMs times the heap/adjacency loop only; allocation/seeding, result encoding and child IPC are separate.",
                                         "Child round trip includes command write, scheduling, setup/search/encoding and complete reply read; it is not HTTP or pure graph search.",
                                         "Bitmap decode timing creates a checked memory view; all-state correctness verification is excluded from timing.",
                                         "Fresh processes do not flush OS caches; no cold disk/device, concurrency, WAN, WASM or Vercel measurement.",
                                         "Long budgets test numeric/search semantics on a clipped downtown graph; they do not establish complete 2/6/10/12-hour coverage.",
                                         "CSR excludes geometry, snapping indexes, OSM IDs and attribution metadata, which remain in the reference assets."]}
        save_json(output / "summary.json", summary)
        save_json(output / "manifest.json", {"runId": run_id, **run_identity, "packedGraph": artifact, "compilation": compilation,
                                             "summarySha256": file_hash(output / "summary.json")})
        snapshots = output / "recipe"
        snapshots.mkdir(exist_ok=True)
        for name in scripts: atomic_write(snapshots / name, (recipe / name).read_bytes())
        print(json.dumps({"cases": len(cases), "nativeCostComparisons": labels_checked, "nativeMembershipComparisons": memberships_checked,
                          "packedGraphBytes": len(packed), "publicApiCalls": 0, "workerWallMs": summary["workerWallMs"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output", required=True)
    run(parser.parse_args())
