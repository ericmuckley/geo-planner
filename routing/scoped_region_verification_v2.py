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
from scoped_range_graph import load_checked
from range_hash import advice_report, artifact, file_hash
from region_admission import qualification_admission
from scoped_member_lookup import POLICY_ID
from region_release import check_resources
from xml_stream import report as graph_stream_report

CURRENT = QUALIFIED = "compact-pilot/experiment-region-v1"
PREPARATION = "coverage-pilot/two-hour-region-v2"

def qualification(args, output, inputs, monitor):
    started = time.perf_counter()
    manifest = load_json(output / "build-manifest.json")
    if manifest["imageId"] != args.image_id: raise ValueError("Image differs")
    if manifest["profile"]["model"].get("restrictionGeometryPolicy") != POLICY_ID: raise ValueError("Require the scoped restriction policy")
    check_scripts(output, manifest["scripts"])
    check_artifacts(output, manifest["artifacts"])
    base = {key: manifest[key] for key in ("profile", "sourceArtifact", "scripts", "imageId", "memoryLimit", "memorySwapLimit", "cpus", "network")}
    base["scripts"] = {**base["scripts"], **{name: file_hash(Path(__file__).parent / name) for name in ("scoped_region_verification_v2.py", "scoped-region-verify-v2.mjs", "range_graph.py", "xml_stream.py", "scoped_load.py", "scoped_range_graph.py")}}
    base["buildManifestSha256"] = file_hash(output / "build-manifest.json")
    calibration_dir = inputs / QUALIFIED
    resource_calibration = load_json(calibration_dir / "qualification-report.json")
    previous_manifest = load_json(calibration_dir / "manifest.json")
    check_scripts(calibration_dir, previous_manifest["scripts"])
    check_artifacts(calibration_dir, previous_manifest["artifacts"])
    if manifest["previousManifestSha256"] != file_hash(inputs / CURRENT / "manifest.json"):
        raise ValueError("Qualification calibration differs")
    policy_dir = inputs / "compact-pilot/scoped-current-v1"
    policy = load_json(policy_dir / "calibration-report.json")
    policy_manifest = load_json(policy_dir / "build-manifest.json")
    check_scripts(policy_dir, policy_manifest["scripts"])
    check_artifacts(policy_dir, policy_manifest["artifacts"])
    check_resources(policy)
    if not policy["routingPayloadUnchanged"] or policy["sourceManifestSha256"] != file_hash(inputs / CURRENT / "manifest.json") or policy["normalizedGraphSha256"] != previous_manifest["artifacts"]["graph.json"]["sha256"]:
        raise ValueError("Current-graph scoped policy calibration failed")
    base["policyCalibrationReportSha256"] = file_hash(policy_dir / "calibration-report.json")
    prepared = load_json(inputs / PREPARATION / "report.json")
    admitted = qualification_admission(prepared, resource_calibration)
    if not admitted["eligible"]: raise ValueError("Qualification phase exceeds the unchanged resource gate")
    base["phaseAdmission"] = admitted
    base["resourceCalibrationReportSha256"] = file_hash(calibration_dir / "qualification-report.json")
    # Seal this phase before calibration so failed attempts cannot be overwritten.
    snapshot(output, {**base, "stage": "reuse-frozen-sinks-and-scoped-loader-v2"}, "oracle-v2-calibration-identity.json")
    previous_attempt = load_json(output / "qualification-identity.json")
    check_scripts(output, previous_attempt["scripts"])
    if previous_attempt["buildManifestSha256"] != base["buildManifestSha256"]:
        raise ValueError("Previous sink calibration belongs to another build")
    calibration = previous_attempt["oracleCalibration"]
    frozen = inputs / "compact-pilot/compact-v1-buffer-v3"
    if calibration["sourceManifestSha256"] != file_hash(frozen / "manifest.json"):
        raise ValueError("Preserved virtual-sink source differs")
    expected_sinks = load_json(frozen / "summary.json")["interiorDestinations"]
    if [{key: row[key] for key in expected_sinks[0]} for row in calibration["partialDestinations"]] != expected_sinks:
        raise ValueError("Preserved virtual-sink costs differ")
    base["reusedSinkCalibrationIdentitySha256"] = file_hash(output / "qualification-identity.json")
    monitor.checkpoint("sinksReused")
    fixture_directory = inputs / "model-pilot/downtown-maneuvers-v2"
    fixture_manifest = load_json(fixture_directory / "manifest.json")
    fixture_artifact = artifact(fixture_directory / "summary.json")
    if fixture_artifact != fixture_manifest["artifacts"]["summary.json"]: raise ValueError("Maneuver fixture changed")
    identity = {**base, "stage": "qualify-virtual-sink", "oracleCalibration": calibration,
                "fixtureSummaryArtifact": fixture_artifact, "fixtureManifestSha256": file_hash(fixture_directory / "manifest.json")}
    run_id = snapshot(output, identity, "qualification-v2-identity.json")
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
    report = {"runId": run_id, "graphIdentity": graph.identity, "oracleCalibration": calibration, "sinkCalibrationReused": True,
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
        for filename in ("manifest.json", "summary.json", "qualification-report.json", "reloaded.csr", "oracle-v2-calibration-identity.json"):
            if (output / filename).exists(): raise ValueError("Preserve attempts; completed output already exists: " + filename)
        qualification(args, output, inputs, monitor)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    run(parser.parse_args())
