"""Fresh independent verification for the Arizona-inclusive two-hour candidate."""

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
from lean_qualification import calibrate
from region_verification import load_checked
from range_hash import advice_report, artifact, file_hash
from region_admission import qualification_admission
from xml_stream import report as graph_stream_report

CURRENT = QUALIFIED = "compact-pilot/experiment-region-v1"
PREPARATION = "coverage-pilot/two-hour-region-v2"

def qualification(args, output, inputs, monitor):
    started = time.perf_counter()
    manifest = load_json(output / "build-manifest.json")
    if manifest["imageId"] != args.image_id: raise ValueError("Image differs")
    check_scripts(output, manifest["scripts"])
    check_artifacts(output, manifest["artifacts"])
    base = {key: manifest[key] for key in ("profile", "sourceArtifact", "scripts", "imageId", "memoryLimit", "memorySwapLimit", "cpus", "network")}
    base["scripts"] = {**base["scripts"], **{name: file_hash(Path(__file__).parent / name) for name in ("two_hour_region_verification.py", "two-hour-region-verify.mjs", "range_graph.py", "xml_stream.py", "region_verification.py")}}
    base["buildManifestSha256"] = file_hash(output / "build-manifest.json")
    calibration_dir = inputs / QUALIFIED
    resource_calibration = load_json(calibration_dir / "qualification-report.json")
    previous_manifest = load_json(calibration_dir / "manifest.json")
    check_scripts(calibration_dir, previous_manifest["scripts"])
    check_artifacts(calibration_dir, previous_manifest["artifacts"])
    if manifest["previousManifestSha256"] != file_hash(inputs / CURRENT / "manifest.json"):
        raise ValueError("Qualification calibration differs")
    prepared = load_json(inputs / PREPARATION / "report.json")
    admitted = qualification_admission(prepared, resource_calibration)
    if not admitted["eligible"]: raise ValueError("Qualification phase exceeds the unchanged resource gate")
    base["phaseAdmission"] = admitted
    base["resourceCalibrationReportSha256"] = file_hash(calibration_dir / "qualification-report.json")
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
        qualification(args, output, inputs, monitor)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    run(parser.parse_args())
