"""Candidate-specific verification with unchanged algorithms and range-advised graph reads.

The first calibration attempt is preserved. This version verifies exact old functional
summaries and full-field bytes before its measured peak can admit the expanded graph.
"""

import argparse
import fcntl
import json
from pathlib import Path
import time

from anchors import load_json
from buffer_resources import Monitor
from compact_storage import save_json, write_csr
from increment import check_artifacts, check_scripts, snapshot
from regional_checks import diagnose_routes, qualify
from regional_qualification import functional_summary
from lean_qualification import calibrate
from range_graph import load_graph
from range_hash import advice_report, artifact, file_hash
from region_admission import qualification_admission
from xml_stream import report as graph_stream_report

SOURCE = CURRENT = "compact-pilot/hour-v3"
PREPARATION = "coverage-pilot/experiment-increment-v1"
CALIBRATION = "compact-pilot/compact-v1-buffer-v3"
QUALIFIED = "qualification-pilot/experiment-ranged-v1"


def load_checked(directory, manifest):
    graph, model = load_graph(directory / "graph.json")
    if graph.identity != manifest["graphIdentity"] or model != manifest["profile"]["model"]:
        raise ValueError("Reloaded graph/model differs")
    if artifact(directory / "graph.json") != manifest["artifacts"]["graph.json"]:
        raise ValueError("Graph changed during reload")
    reads = [row for row in graph_stream_report()["requests"] if row["path"] == str(directory / "graph.json")]
    if len(reads) != 1 or any(not row["closed"] or not row["eofObserved"] or row["readBytes"] != row["fileBytes"] or row["successfulAdviceBytes"] != row["readBytes"] or row["adviceErrors"] for row in reads):
        raise ValueError("Range-advised graph read incomplete")
    return graph


def parity(args, output, inputs, monitor):
    recipe = Path(__file__).parent
    if (output / "identity.json").exists(): raise ValueError("Preserve attempts; use a fresh run name")
    started = time.perf_counter()
    directory = inputs / SOURCE
    manifest = load_json(directory / "manifest.json")
    if manifest["imageId"] != args.image_id: raise ValueError("Tools image differs")
    check_scripts(directory, manifest["scripts"])
    scripts = {**manifest["scripts"], **{name: file_hash(recipe / name) for name in
               ("virtual_sink.py", "regional_checks.py", "region_verification.py", "region-verify.mjs", "range_graph.py", "xml_stream.py")}}
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
              "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(), "cacheAdvice": advice_report(), "graphStreams": graph_stream_report(),
              "qualificationPeakWith25PercentMarginBytes": estimate, "qualificationHeadroomRestored": not pressure and estimate < 4 * 1024 ** 3,
              "workerWallMs": (time.perf_counter() - started) * 1000, "publicApiCalls": 0, "fullGraphBuilt": False, "coverageVerified": False,
              "scope": "Candidate-specific qualification with targeted road IDs, streamed fields and bounded label lifetimes; unchanged independent algorithms. Exact frozen fields, partial costs, routes, snaps and cuts; no graph/model/coverage changes. Final checkpoint follows verification reads; small report writes excluded."}
    save_json(output / "report.json", report)
    print(json.dumps({key: report[key] for key in ("functionalSummaryIdentical", "qualificationHeadroomRestored", "qualificationPeakWith25PercentMarginBytes", "workerWallMs")}, indent=2))

def qualification(args, output, inputs, monitor):
    started = time.perf_counter()
    manifest = load_json(output / "build-manifest.json")
    if manifest["imageId"] != args.image_id: raise ValueError("Image differs")
    check_scripts(output, manifest["scripts"])
    check_artifacts(output, manifest["artifacts"])
    base = {key: manifest[key] for key in ("profile", "sourceArtifact", "scripts", "imageId", "memoryLimit", "memorySwapLimit", "cpus", "network")}
    base["scripts"] = {**base["scripts"], **{name: file_hash(Path(__file__).parent / name) for name in ("region_verification.py", "region-verify.mjs", "range_graph.py", "xml_stream.py")}}
    base["buildManifestSha256"] = file_hash(output / "build-manifest.json")
    calibration_dir = inputs / QUALIFIED
    resource_calibration = load_json(calibration_dir / "report.json")
    check_scripts(calibration_dir, resource_calibration["scripts"])
    check_artifacts(calibration_dir, resource_calibration["artifacts"])
    if resource_calibration["sourceManifestSha256"] != file_hash(inputs / CURRENT / "manifest.json") or not resource_calibration["functionalSummaryIdentical"]:
        raise ValueError("Qualification calibration differs")
    prepared = load_json(inputs / PREPARATION / "report.json")
    admitted = qualification_admission(prepared, resource_calibration)
    if not admitted["eligible"]: raise ValueError("Qualification phase exceeds the unchanged resource gate")
    base["phaseAdmission"] = admitted
    base["resourceCalibrationReportSha256"] = file_hash(calibration_dir / "report.json")
    # Seal this phase before calibration so failed attempts cannot be overwritten.
    snapshot(output, {**base, "stage": "frozen-sink-calibration"}, "oracle-calibration-identity.json")
    calibration = calibrate(inputs, output, monitor)
    fixture_directory = inputs / "model-pilot/downtown-maneuvers-v2"
    fixture_manifest = load_json(fixture_directory / "manifest.json")
    fixture_artifact = artifact(fixture_directory / "summary.json")
    if fixture_artifact != fixture_manifest["artifacts"]["summary.json"]: raise ValueError("Maneuver fixture changed")
    identity = {**base, "stage": "qualify-virtual-sink", "oracleCalibration": calibration,
                "fixtureSummaryArtifact": fixture_artifact, "fixtureManifestSha256": file_hash(fixture_directory / "manifest.json")}
    run_id = snapshot(output, identity, "qualification-identity.json")
    monitor.checkpoint("validated")
    graph = load_checked(output, manifest)
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
    report = {"runId": run_id, "graphIdentity": graph.identity, "oracleCalibration": calibration,
              "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(), "cacheAdvice": advice_report(), "graphStreams": graph_stream_report(),
              "workerWallMs": (time.perf_counter() - started) * 1000, "costComparisons": summary["costComparisons"],
              "boundedCostComparisons": summary["boundedCostComparisons"], "interiorDestinationComparisons": summary["interiorDestinationComparisons"],
              "sampledCityDirections": 12, "publicApiCalls": 0, "coverageVerified": False,
              "scope": "Fresh independent full/bounded/virtual-terminal checks on the new graph after frozen flat-sink calibration. Final checkpoint follows verification reads; small metadata writes excluded. No contour or real eligibility claim."}
    save_json(output / "qualification-report.json", report)
    save_json(output / "manifest.json", {"runId": run_id, **identity, "graphIdentity": graph.identity,
              "artifacts": {**artifacts, "build-manifest.json": artifact(output / "build-manifest.json"),
                            "qualification-report.json": artifact(output / "qualification-report.json")}})
    print(json.dumps({key: report[key] for key in ("graphIdentity", "costComparisons", "boundedCostComparisons", "interiorDestinationComparisons", "workerWallMs")}, indent=2))


def run(args):
    output, inputs = Path(args.output), Path("/inputs")
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.stage == "calibrate": parity(args, output, inputs, monitor)
        else: qualification(args, output, inputs, monitor)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("calibrate", "qualify"), default="calibrate")
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--output", default="/output")
    run(parser.parse_args())
