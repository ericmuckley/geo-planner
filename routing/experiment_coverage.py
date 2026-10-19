"""Prepare a bounded all-direction coverage increment for the visible local experiment."""

import argparse
import fcntl
import math
from pathlib import Path
import time

from anchors import load_json
from buffer_resources import Monitor
from compact_storage import save_json
from coverage_census import census
from hour_admission import peak
from increment import check_artifacts, check_scripts, snapshot
from lifetime_prepare import prepare
from paged_io import artifact, file_hash
from regional_support import check_bounds


BOUNDS = [-118.0, 31.6, -115.5, 34.0]


def run(args):
    output, inputs = Path(args.output), Path("/inputs")
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "identity.json").exists(): raise ValueError("Preserve attempts; choose a fresh run name")
        started = time.perf_counter()
        calibration_dir = inputs / "coverage-pilot/lifetime-batched-calibration-v1"
        calibration = load_json(calibration_dir / "report.json")
        if calibration["imageId"] != args.image_id or calibration["baseImageId"] != args.base_image_id: raise ValueError("Cached images differ")
        check_scripts(calibration_dir, calibration["scripts"])
        check_artifacts(calibration_dir, calibration["artifacts"])
        if not calibration["xmlByteIdentical"] or len(calibration["fixtures"]) != 6 or not all(row["graphAndAuditIdentical"] for row in calibration["fixtures"]): raise ValueError("Missing exact preparation calibration")
        parent = Path("/data/region.osm.pbf")
        if artifact(parent) != calibration["regionArtifact"]: raise ValueError("Cached source differs")
        check_bounds(BOUNDS, load_json(Path("/data/build-complete.json"))["manifest"]["bbox"])
        current_dir = inputs / "outgoing-pilot/outgoing-v1-hour-v3"
        built = load_json(current_dir / "report.json")
        check_scripts(current_dir, load_json(current_dir / "manifest.json")["scripts"])
        check_artifacts(current_dir, load_json(current_dir / "manifest.json")["artifacts"])
        qualified = load_json(inputs / "compact-pilot/hour-v3/qualification-report.json")
        scripts = {**calibration["scripts"], **{name: file_hash(Path(__file__).parent / name) for name in ("experiment_coverage.py", "experiment-coverage.mjs")}}
        identity = {"bbox": BOUNDS, "regionArtifact": calibration["regionArtifact"], "imageId": args.image_id, "baseImageId": args.base_image_id,
                    "scripts": scripts, "calibrationReportSha256": file_hash(calibration_dir / "report.json"),
                    "buildReportSha256": file_hash(current_dir / "report.json"), "qualificationReportSha256": file_hash(inputs / "compact-pilot/hour-v3/qualification-report.json"),
                    "memoryLimit": "4g", "memorySwapLimit": "4g", "cpus": 2, "network": "none", "referenceBatches": 4,
                    "purpose": "Increment toward two-hour coverage; all sides expand. This smaller envelope does not contain every conservative two-hour continuation envelope. Fresh cuts must determine remaining clipping."}
        run_id = snapshot(output, identity, "identity.json")
        monitor.checkpoint("validated")
        xml, selection, commands = prepare(parent, BOUNDS, output, monitor, batches=4)
        counts = census(xml, BOUNDS, output / "candidate.sqlite")
        xml_artifact = artifact(xml)
        monitor.checkpoint("counted")
        keys = ("sourceNodes", "sourceWays", "sourceRelations", "wayEligibleDirectedSegments", "historyPrefixCeiling", "candidateViaWayRules")
        ratios = {key: counts[key] / calibration["candidate"][key] for key in keys}
        ratios.update({"roadCeiling": counts["roadStatesUpperBound"] / built["roads"], "historyCeiling": counts["historyStatesUpperBound"] / built["states"]})
        scale = max(1, *ratios.values())
        preparation, pressure = peak({"resourceCheckpoints": monitor.checkpoints})
        build_peak, build_pressure = peak(built)
        qualification_peak, qualification_pressure = peak(qualified)
        phases = {"preparation": preparation, "build": math.ceil(build_peak * scale), "qualification": math.ceil(qualification_peak * scale)}
        estimate = math.ceil(max(phases.values()) * 1.25)
        eligible = not (pressure or build_pressure or qualification_pressure) and estimate < 4 * 1024**3
        report = {"runId": run_id, **identity, "candidate": counts, "selection": selection, "commands": commands,
                  "artifacts": {"car-roads.osm": xml_artifact, "selected-ids.txt": artifact(output / "selected-ids.txt")},
                  "admission": {"eligibleForSeparateBuild": eligible, "ratios": ratios, "scalingRatio": scale, "estimatedPhasePeaksBytes": phases, "wholeWorkflowWith25PercentMarginBytes": estimate, "capBytes": 4 * 1024**3},
                  "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(), "workerWallMs": (time.perf_counter() - started) * 1000,
                  "publicApiCalls": 0, "coverageVerified": False, "newGraphBuilt": False}
        save_json(output / "report.json", report)
        print({key: report[key] for key in ("candidate", "admission", "workerWallMs")}, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--base-image-id", required=True)
    run(parser.parse_args())
