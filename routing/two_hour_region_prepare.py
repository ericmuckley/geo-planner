"""Prepare the next region from the qualified expanded graph's two-hour frontier."""

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
from two_hour_frontier import plan


CURRENT = "compact-pilot/experiment-region-v1"
CUTS = CURRENT + "-cuts"
PREVIOUS_PREPARATION = "coverage-pilot/experiment-increment-v1"


def scaling(candidate, reference, built):
    keys = ("sourceNodes", "sourceWays", "sourceRelations", "wayEligibleDirectedSegments",
            "historyPrefixCeiling", "candidateViaWayRules")
    ratios = {key: candidate[key] / reference[key] for key in keys}
    ratios.update(roadCeiling=candidate["roadStatesUpperBound"] / built["roads"],
                  historyCeiling=candidate["historyStatesUpperBound"] / built["states"])
    return ratios, max(1, *ratios.values())


def run(args):
    output, inputs = Path(args.output), Path("/inputs")
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started = time.perf_counter()
        calibration_dir = inputs / "coverage-pilot/lifetime-batched-calibration-v1"
        calibration = load_json(calibration_dir / "report.json")
        if calibration["imageId"] != args.image_id or calibration["baseImageId"] != args.base_image_id:
            raise ValueError("Cached images differ")
        check_scripts(calibration_dir, calibration["scripts"])
        check_artifacts(calibration_dir, calibration["artifacts"])
        if not calibration["xmlByteIdentical"] or len(calibration["fixtures"]) != 6 or not all(row["graphAndAuditIdentical"] for row in calibration["fixtures"]):
            raise ValueError("Missing exact preparation calibration")
        parent = Path("/data/region.osm.pbf")
        if artifact(parent) != calibration["regionArtifact"]:
            raise ValueError("Cached parent source differs")
        current = load_json(inputs / CURRENT / "manifest.json")
        cuts = load_json(inputs / CUTS / "report.json")
        check_scripts(inputs / CURRENT, current["scripts"])
        check_artifacts(inputs / CURRENT, current["artifacts"])
        check_artifacts(inputs / CUTS, cuts["artifacts"])
        if cuts["graphIdentity"] != current["graphIdentity"] or cuts["sourceManifestSha256"] != file_hash(inputs / CURRENT / "manifest.json"):
            raise ValueError("Cut inventory belongs to a different graph")
        parent_bounds = load_json(Path("/data/build-complete.json"))["manifest"]["bbox"]
        frontier = plan(load_json(inputs / CUTS / "cut-nodes.json"), current["profile"]["bbox"], parent_bounds)
        if frontier["clippedSides"]:
            raise ValueError("This candidate needs source coverage beyond the cached parent")
        bounds = frontier["candidateBounds"]
        check_bounds(current["profile"]["bbox"], bounds)
        reference = load_json(inputs / PREVIOUS_PREPARATION / "report.json")
        reports = {"build": load_json(inputs / CURRENT / "build-report.json"),
                   "rebuild": load_json(inputs / (CURRENT + "-rebuild") / "build-report.json"),
                   "qualification": load_json(inputs / CURRENT / "qualification-report.json"), "cuts": cuts}
        scripts = {**calibration["scripts"], **current["scripts"], **{name: file_hash(Path(__file__).parent / name)
                   for name in ("two_hour_region_prepare.py", "two-hour-region-prepare.mjs", "two_hour_frontier.py", "hour_admission.py")}}
        identity = {"bbox": bounds, "frontier": frontier, "regionArtifact": calibration["regionArtifact"],
                    "imageId": args.image_id, "baseImageId": args.base_image_id, "scripts": scripts,
                    "calibrationReportSha256": file_hash(calibration_dir / "report.json"),
                    "previousManifestSha256": file_hash(inputs / CURRENT / "manifest.json"),
                    "previousPreparationReportSha256": file_hash(inputs / PREVIOUS_PREPARATION / "report.json"),
                    "cutReportSha256": file_hash(inputs / CUTS / "report.json"),
                    "buildReportSha256": file_hash(inputs / CURRENT / "build-report.json"),
                    "qualificationReportSha256": file_hash(inputs / CURRENT / "qualification-report.json"),
                    "memoryLimit": "4g", "memorySwapLimit": "4g", "cpus": 2, "network": "none", "referenceBatches": 4,
                    "purpose": "Contains all conservative 120-minute continuation envelopes from the expanded qualified graph. Rectangle/source footprints and restored topology remain separate limitations; fresh qualification and cuts are required."}
        run_id = snapshot(output, identity, "identity.json")
        monitor.checkpoint("validated")
        xml, selection, commands = prepare(parent, bounds, output, monitor, batches=4)
        counts = census(xml, bounds, output / "candidate.sqlite")
        xml_artifact = artifact(xml)
        monitor.checkpoint("counted")
        ratios, scale = scaling(counts, reference["candidate"], reports["build"])
        observed = {name: peak(report) for name, report in reports.items()}
        observed["preparation"] = peak({"resourceCheckpoints": monitor.checkpoints})
        phases = {name: math.ceil(value[0] * (1 if name == "preparation" else scale)) for name, value in observed.items()}
        estimate = math.ceil(max(phases.values()) * 1.25)
        report = {"runId": run_id, **identity, "candidate": counts, "selection": selection, "commands": commands,
                  "artifacts": {"car-roads.osm": xml_artifact, "selected-ids.txt": artifact(output / "selected-ids.txt")},
                  "referenceReportSha256": {name: file_hash(inputs / path) for name, path in {
                      "build": CURRENT + "/build-report.json", "rebuild": CURRENT + "-rebuild/build-report.json",
                      "qualification": CURRENT + "/qualification-report.json", "cuts": CUTS + "/report.json"}.items()},
                  "admission": {"eligibleForSeparateBuild": not any(v[1] for v in observed.values()) and estimate < 4 * 1024**3,
                      "ratios": ratios, "scalingRatio": scale, "estimatedPhasePeaksBytes": phases,
                      "observedReferencePeaksBytes": {name: value[0] for name, value in observed.items()},
                      "wholeWorkflowWith25PercentMarginBytes": estimate, "capBytes": 4 * 1024**3},
                  "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(),
                  "workerWallMs": (time.perf_counter() - started) * 1000, "publicApiCalls": 0,
                  "coverageVerified": False, "newGraphBuilt": False}
        save_json(output / "report.json", report)
        print({key: report[key] for key in ("bbox", "candidate", "admission", "workerWallMs")}, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--base-image-id", required=True)
    run(parser.parse_args())
