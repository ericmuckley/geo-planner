"""Verify the changed real history-state graph with the unchanged C++ kernel."""

import argparse
import fcntl
import json
import math
from pathlib import Path
import platform
import struct
import subprocess
import sys

from anchors import atomic_write, digest, file_hash, load_json, save_json
from cell_experiment import checked_artifact
from maneuver_graph import ManeuverGraph, interior_destination
from native_support import UINT64_MAX, NativeClient, compile_kernel, decode_labels, membership_bytes, pack_graph
from state_graph import StateGraph


def run(args):
    probe = subprocess.run([sys.executable, "-c", "import socket\ntry:\n s=socket.socket(); s.connect(('127.0.0.1',9))\nexcept PermissionError:\n print('denied')"], capture_output=True, text=True)
    if probe.returncode != 0 or probe.stdout.strip() != "denied":
        raise RuntimeError("Native model verification requires a working network-denying sandbox")
    directory = Path(__file__).resolve().parent.parent / "data/model-pilot" / args.run_name
    with (directory / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = load_json(directory / "manifest.json")
        for name in manifest["artifacts"]: checked_artifact(directory, manifest, name)
        data, summary = load_json(directory / "graph.json"), load_json(directory / "summary.json")
        base_id = digest({"roads": data["roads"], "transitions": data["baseTransitions"]})
        graph_id = digest({"model": data["model"]["id"], "baseIdentity": base_id, "patterns": data["patterns"],
                           "states": data["states"], "transitions": data["transitions"]})
        if base_id != data["baseIdentity"] or graph_id != data["graphIdentity"] or graph_id != manifest["graphIdentity"]:
            raise ValueError("History graph identity mismatch")
        if (directory / "graph.csr").read_bytes() != pack_graph(data["transitions"], graph_id):
            raise ValueError("Packed history graph differs from JSON transitions")
        binary = directory / "native_search"
        compilation = compile_kernel(binary)
        base = StateGraph(data["roads"], data["baseTransitions"], [], [], base_id)
        graph = ManeuverGraph(base, data["states"], data["initialStates"], data["transitions"], data["patterns"], [], graph_id)
        roads = {road["id"]: index for index, road in enumerate(base.roads)}
        client = NativeClient(binary, directory / "graph.csr", graph_id)
        cases, costs_compared, memberships_compared, destinations_compared = [], 0, 0, 0
        try:
            startup = {"processStartupAndHelloMs": client.startup_ms, **client.hello}
            for origin in summary["origins"]:
                expected_bytes = (directory / "oracles" / f"{origin['origin']}.u64le").read_bytes()
                expected = decode_labels(expected_bytes, len(graph.states))
                metadata, payload, roundtrip = client.request(origin["seeds"], None)
                if payload != expected_bytes: raise ValueError("Native history-state costs differ from Bellman-Ford")
                costs_compared += len(expected)
                labels = decode_labels(payload, len(graph.states))
                attachments = origin["starts"]
                for destination in summary["interiorDestinations"]:
                    if destination["origin"] != origin["origin"]: continue
                    actual = interior_destination(graph, labels, roads[destination["roadId"]], destination["fraction"], attachments)
                    if actual != (math.inf if destination["costMs"] is None else destination["costMs"]):
                        raise ValueError("Native-cost interior destination disagrees with sink oracle")
                    destinations_compared += 1
                budgets = []
                for budget in summary["profile"]["budgetsMs"]:
                    filtered = struct.pack(f"<{len(expected)}Q", *(value if value <= budget else UINT64_MAX for value in expected))
                    cost_meta, costs, cost_roundtrip = client.request(origin["seeds"], budget)
                    mask_meta, mask, mask_roundtrip = client.request(origin["seeds"], budget, "membership")
                    if costs != filtered or mask != membership_bytes(expected, budget):
                        raise ValueError("Native bounded history costs/membership disagree")
                    costs_compared += len(expected)
                    memberships_compared += len(expected)
                    budgets.append({"budgetMs": budget, "labels": cost_meta, "membership": mask_meta,
                                    "labelsChildRoundTripMs": cost_roundtrip, "membershipChildRoundTripMs": mask_roundtrip})
                cases.append({"origin": origin["origin"], "full": metadata, "fullChildRoundTripMs": roundtrip, "budgets": budgets})
        finally:
            client.close()
        report = {"sourceRunId": manifest["runId"], "sourceManifestSha256": file_hash(directory / "manifest.json"),
                  "graphIdentity": graph_id, "compilation": compilation, "nativeStartup": startup,
                  "platform": platform.platform(), "python": sys.version,
                  "workerSha256": file_hash(Path(__file__)), "networkPolicySha256": file_hash(Path(__file__).with_name("native-network.sb")),
                  "networkProbe": "loopback socket denied; no external service contacted", "publicApiCalls": 0,
                  "costComparisons": costs_compared, "membershipComparisons": memberships_compared,
                  "interiorDestinationComparisons": destinations_compared, "cases": cases, "coverageVerified": False,
                  "timingLimits": "One qualification observation per case, not a performance distribution. Internal search, setup, encoding and local pipe round trips are distinct; no HTTP/WASM/Vercel claim."}
        save_json(directory / "native-verification.json", report)
        atomic_write(directory / "recipe/model_native.py", Path(__file__).read_bytes())
        print(json.dumps({key: report[key] for key in ("costComparisons", "membershipComparisons", "interiorDestinationComparisons", "publicApiCalls")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", default="downtown-maneuvers-v2")
    args = parser.parse_args()
    if not args.run_name or any(not (character.isascii() and (character.isalnum() or character in "_-")) for character in args.run_name):
        parser.error("Run names accept letters, numbers, underscores and hyphens")
    run(args)
