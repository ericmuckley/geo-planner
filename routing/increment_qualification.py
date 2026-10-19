"""Calibrate queue Bellman-Ford on five frozen fields before the coverage increment."""

import argparse
import fcntl
import json
from pathlib import Path
import struct
import time

from anchors import load_json
from buffer_resources import Monitor
from compact_load import load_graph
from compact_storage import save_json, write_csr
from increment import check_artifacts, check_scripts, snapshot
from native_support import UINT64_MAX
from paged_io import advice_report, artifact, file_hash
from queue_oracle import bellman_ford
from queue_qualification import qualify
from wide import diagnose_routes


def calibrate(image_id, monitor):
    directory = Path("/inputs/compact-pilot/compact-v1-buffer-v3")
    manifest = load_json(directory / "manifest.json")
    if manifest["imageId"] != image_id: raise ValueError("Calibration image differs")
    check_scripts(directory, manifest["scripts"])
    check_artifacts(directory, manifest["artifacts"])
    graph, _ = load_graph(directory / "graph.json")
    rows = []
    for origin in load_json(directory / "summary.json")["origins"]:
        before = time.perf_counter()
        labels = bellman_ford(graph.adjacency, origin["seeds"])
        elapsed = (time.perf_counter() - before) * 1000
        payload = struct.pack(f"<{len(labels)}Q", *(UINT64_MAX if value == float("inf") else value for value in labels))
        expected = (directory / "oracles" / f"{origin['origin']}.u64le").read_bytes()
        if payload != expected: raise ValueError("Queue oracle differs from frozen full field")
        rows.append({"origin": origin["origin"], "statesCompared": len(labels), "oracleMs": elapsed})
        print(f"Queue oracle calibrated: {origin['origin']} in {elapsed / 1000:.2f} s", flush=True)
        del labels, payload, expected
    monitor.checkpoint("oracleCalibrated")
    return {"sourceManifestSha256": file_hash(directory / "manifest.json"), "graphIdentity": graph.identity,
            "cases": rows, "stateComparisons": sum(row["statesCompared"] for row in rows)}


def qualification(args, output, monitor, calibration, started):
    manifest = load_json(output / "build-manifest.json")
    if manifest["imageId"] != args.image_id: raise ValueError("Image differs")
    check_scripts(output, manifest["scripts"])
    check_artifacts(output, manifest["artifacts"])
    fixture_directory = Path("/inputs/model-pilot/downtown-maneuvers-v2")
    fixture_manifest = load_json(fixture_directory / "manifest.json")
    fixture_artifact = artifact(fixture_directory / "summary.json")
    if fixture_artifact != fixture_manifest["artifacts"]["summary.json"]: raise ValueError("Maneuver fixture summary changed")
    identity = {**{key: manifest[key] for key in ("profile", "sourceArtifact", "imageId", "memoryLimit", "memorySwapLimit", "cpus", "network")},
                "stage": "qualify-queue-oracle", "oracleCalibration": calibration, "buildManifestSha256": file_hash(output / "build-manifest.json"),
                "scripts": {**manifest["scripts"], **{name: file_hash(Path(__file__).parent / name) for name in ("queue_oracle.py", "queue_qualification.py", "increment_qualification.py", "increment-qualify.mjs")}},
                "fixtureSummaryArtifact": fixture_artifact, "fixtureManifestSha256": file_hash(fixture_directory / "manifest.json")}
    run_id = snapshot(output, identity, "qualification-identity.json")
    if (output / "manifest.json").exists(): raise ValueError("Preserve completed qualification")
    monitor.checkpoint("validated")
    graph, model = load_graph(output / "graph.json")
    if graph.identity != manifest["graphIdentity"] or model != manifest["profile"]["model"]: raise ValueError("Reload differs")
    write_csr(output / "reloaded.csr", graph.adjacency, graph.identity)
    if artifact(output / "reloaded.csr") != manifest["artifacts"]["graph.csr"]: raise ValueError("Reloaded CSR differs")
    monitor.checkpoint("reloaded")
    audit, built = load_json(output / "import-audit.json"), load_json(output / "build-report.json")
    fixture = load_json(fixture_directory / "summary.json")
    fixture["alternativeRoadIds"] = {str(row["restriction"]["id"]): row["alternativeRoadId"] for row in fixture["sourceSamples"]}
    summary = qualify(output, graph, audit, manifest["profile"], fixture, built["barrierExamples"], built["portIncoming"], built["portOutgoing"])
    monitor.checkpoint("fullBoundedQualified")
    if len(summary["sampledRoutes"]) != 12 or any(row["costMs"] is None for row in summary["sampledRoutes"]):
        raise ValueError("A sampled city direction is disconnected")
    diagnose_routes(output, graph, audit, summary)
    if len(summary["interiorDestinations"]) != 2: raise ValueError("Partial destination qualification missing")
    summary["runId"] = run_id
    save_json(output / "summary.json", summary)
    names = ["summary.json", "reloaded.csr", *summary["oracleArtifacts"]]
    artifacts = {**manifest["artifacts"], **{name: artifact(output / name) for name in names}}
    monitor.checkpoint("verified")
    report = {"runId": run_id, "graphIdentity": graph.identity, "resourceCheckpoints": monitor.checkpoints,
              "sampling": monitor.summary(), "cacheAdvice": advice_report(), "workerWallMs": (time.perf_counter() - started) * 1000,
              "costComparisons": summary["costComparisons"], "boundedCostComparisons": summary["boundedCostComparisons"],
              "interiorDestinationComparisons": summary["interiorDestinationComparisons"], "sampledCityDirections": 12,
              "publicApiCalls": 0, "coverageVerified": False,
              "scope": "Fresh compact reload/CSR equality, independent Python full/bounded/partial oracles and legal-in-model route witnesses. No real eligibility, contour or complete-coverage claim."}
    save_json(output / "qualification-report.json", report)
    save_json(output / "manifest.json", {"runId": run_id, **identity, "graphIdentity": graph.identity,
              "artifacts": {**artifacts, "build-manifest.json": artifact(output / "build-manifest.json"),
                            "qualification-report.json": artifact(output / "qualification-report.json")}})
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--output", default="/output")
    args = parser.parse_args()
    output = Path(args.output)
    if any((output / name).exists() for name in ("qualification-identity.json", "oracle-calibration-identity.json")):
        raise ValueError("Preserve qualification attempts")
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started = time.perf_counter()
        built = load_json(output / "build-manifest.json")
        snapshot(output, {"stage": "oracle-calibration", "buildManifestSha256": file_hash(output / "build-manifest.json"),
                 "imageId": args.image_id, "memoryLimit": "4g", "memorySwapLimit": "4g", "cpus": 2, "network": "none",
                 "scripts": {**built["scripts"], **{name: file_hash(Path(__file__).parent / name) for name in
                             ("queue_oracle.py", "queue_qualification.py", "increment_qualification.py", "increment-qualify.mjs")}}},
                 "oracle-calibration-identity.json")
        calibration = calibrate(args.image_id, monitor)
        qualification(args, output, monitor, calibration, started)
