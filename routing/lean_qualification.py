"""Requalify frozen fields and partial costs with a virtual sink under the same cap."""

import argparse
import fcntl
import json
from pathlib import Path
import time

from anchors import digest, load_json
from buffer_resources import Monitor
from compact_load import load_graph
from compact_storage import save_json, write_csr
from increment import check_artifacts, check_scripts, snapshot
from lean_checks import diagnose_routes, qualify
from paged_io import advice_report, artifact, file_hash
from virtual_sink import destination_oracle


SOURCE = "compact-pilot/increment-v3"
CALIBRATION = "compact-pilot/compact-v1-buffer-v3"


def functional_summary(summary):
    result = json.loads(json.dumps(summary))
    result.pop("runId", None)
    result["origins"] = [{key: value for key, value in row.items() if key not in {"fullSearchMs", "bellmanFordMs"}} for row in result["origins"]]
    return result


def load_checked(directory, manifest):
    graph, model = load_graph(directory / "graph.json")
    if graph.identity != manifest["graphIdentity"] or model != manifest["profile"]["model"]:
        raise ValueError("Reloaded graph/model differs")
    # Identity has been recomputed; finish this read scope with a checksum/advice pass.
    if artifact(directory / "graph.json") != manifest["artifacts"]["graph.json"]:
        raise ValueError("Graph changed during reload")
    return graph


def calibrate(inputs, output, monitor):
    directory = inputs / CALIBRATION
    manifest = load_json(directory / "manifest.json")
    check_scripts(directory, manifest["scripts"])
    check_artifacts(directory, manifest["artifacts"])
    graph = load_checked(directory, manifest)
    summary = load_json(directory / "summary.json")
    wanted = {row["roadId"] for row in summary["interiorDestinations"]}
    roads = {road["id"]: index for index, road in enumerate(graph.base.roads) if road["id"] in wanted}
    origins = {row["origin"]: row for row in summary["origins"]}
    results = []
    for previous in summary["interiorDestinations"]:
        origin = origins[previous["origin"]]
        before = time.perf_counter()
        actual = destination_oracle(graph, origin["seeds"], roads[previous["roadId"]], previous["fraction"], origin["starts"])
        if actual != previous["costMs"]: raise ValueError("Virtual sink differs from frozen flat oracle")
        results.append({**previous, "oracleMs": (time.perf_counter() - before) * 1000})
        print(f"Frozen sink calibrated: {previous['origin']} / {previous['roadId']}: {actual} ms", flush=True)
    monitor.checkpoint("sinksCalibrated")
    return {"sourceManifestSha256": file_hash(directory / "manifest.json"), "graphIdentity": graph.identity, "partialDestinations": results}


def run(args):
    output, inputs, recipe = Path(args.output), Path("/inputs"), Path(__file__).parent
    if (output / "identity.json").exists(): raise ValueError("Preserve attempts; use a fresh run name")
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started = time.perf_counter()
        directory = inputs / SOURCE
        manifest = load_json(directory / "manifest.json")
        if manifest["imageId"] != args.image_id: raise ValueError("Tools image differs")
        check_scripts(directory, manifest["scripts"])
        scripts = {**manifest["scripts"], **{name: file_hash(recipe / name) for name in
                   ("virtual_sink.py", "lean_checks.py", "lean_qualification.py", "lean-qualification.mjs")}}
        fixture_directory = inputs / "model-pilot/downtown-maneuvers-v2"
        fixture_manifest = load_json(fixture_directory / "manifest.json")
        fixture = load_json(fixture_directory / "summary.json")
        if artifact(fixture_directory / "summary.json") != fixture_manifest["artifacts"]["summary.json"]: raise ValueError("Maneuver fixture differs")
        identity = {"sourceManifestSha256": file_hash(directory / "manifest.json"), "sourceGraphIdentity": manifest["graphIdentity"],
                    "sourceDirectory": SOURCE, "calibrationManifestSha256": file_hash(inputs / CALIBRATION / "manifest.json"),
                    "profile": manifest["profile"], "scripts": scripts, "fixtureArtifact": artifact(fixture_directory / "summary.json"),
                    "imageId": args.image_id, "memoryLimit": "4g", "memorySwapLimit": "4g", "cpus": 2, "network": "none"}
        run_id = snapshot(output, identity, "identity.json")
        check_artifacts(directory, manifest["artifacts"])
        native = load_json(directory / "native-verification.json")
        if native["sourceManifestSha256"] != identity["sourceManifestSha256"] or native["graphIdentity"] != manifest["graphIdentity"]:
            raise ValueError("Native evidence differs")
        if native["compilation"]["sourceSha256"] != file_hash(recipe / "native_search.cpp"):
            raise ValueError("Frozen native kernel differs")
        if native["compilation"]["binarySha256"] != file_hash(directory / "native_search"):
            raise ValueError("Frozen native binary differs")
        monitor.checkpoint("validated")
        calibration = calibrate(inputs, output, monitor)
        graph = load_checked(directory, manifest)
        write_csr(output / "graph.csr", graph.adjacency, graph.identity)
        if artifact(output / "graph.csr") != manifest["artifacts"]["graph.csr"]: raise ValueError("Reloaded CSR differs")
        monitor.checkpoint("reloaded")
        audit, built = load_json(directory / "import-audit.json"), load_json(directory / "build-report.json")
        fixture["alternativeRoadIds"] = {str(row["restriction"]["id"]): row["alternativeRoadId"] for row in fixture["sourceSamples"]}
        summary = qualify(output, graph, audit, manifest["profile"], fixture, built["barrierExamples"], built["portIncoming"], built["portOutgoing"])
        monitor.checkpoint("fullBoundedQualified")
        diagnose_routes(output, graph, audit, summary)
        previous = load_json(directory / "summary.json")
        if functional_summary(summary) != functional_summary(previous): raise ValueError("Functional qualification differs")
        summary["runId"] = run_id
        save_json(output / "summary.json", summary)
        names = ["graph.csr", "summary.json", *summary["oracleArtifacts"]]
        artifacts = {name: artifact(output / name) for name in names}
        identical = {name: artifacts[name]["sha256"] for name in ["graph.csr", *summary["oracleArtifacts"]]}
        for name in identical:
            if artifacts[name] != manifest["artifacts"][name]: raise ValueError("Frozen packed/oracle bytes differ")
        monitor.checkpoint("verified")
        peak = max(int(row["memory.peak"]) for row in monitor.checkpoints.values())
        pressure = any(int(row["memory.events"]["max"]) for row in monitor.checkpoints.values())
        estimate = round(peak * 1.25)
        report = {"runId": run_id, **identity, "graphIdentity": graph.identity, "calibration": calibration, "artifacts": artifacts,
                  "functionalSummaryIdentical": True, "identicalArtifactSha256": identical,
                  "costComparisons": summary["costComparisons"], "boundedCostComparisons": summary["boundedCostComparisons"],
                  "interiorDestinationComparisons": summary["interiorDestinationComparisons"],
                  "reusedNativeEvidence": {"reportSha256": file_hash(directory / "native-verification.json"),
                    "sourceManifestSha256": native["sourceManifestSha256"], "graphIdentity": native["graphIdentity"],
                    "costComparisons": native["costComparisons"], "membershipComparisons": native["membershipComparisons"],
                    "scope": "Existing native verification reused only on byte-identical graph/CSR/full fields and unchanged partial costs; no new native run."},
                  "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(), "cacheAdvice": advice_report(),
                  "qualificationPeakWith25PercentMarginBytes": estimate, "qualificationHeadroomRestored": not pressure and estimate < 4 * 1024 ** 3,
                  "workerWallMs": (time.perf_counter() - started) * 1000, "publicApiCalls": 0, "fullGraphBuilt": False, "coverageVerified": False,
                  "scope": "Virtual terminal/queue oracle and post-reload per-file checksum advice. Exact frozen fields, partial costs, routes, snaps and cuts; no graph/model/coverage changes. Final checkpoint follows verification reads; small report writes excluded."}
        save_json(output / "report.json", report)
        print(json.dumps({key: report[key] for key in ("functionalSummaryIdentical", "qualificationHeadroomRestored", "qualificationPeakWith25PercentMarginBytes", "workerWallMs")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--output", default="/output")
    run(parser.parse_args())
