"""Measure the cached, incomplete six-hour source before any bulk acquisition."""

import argparse
import fcntl
from pathlib import Path
import time

from anchors import load_json
from buffer_resources import Monitor
from compact_storage import save_json
from coverage_census import census
from hour_admission import peak
from increment import check_artifacts, check_scripts, snapshot
from lifetime_prepare import prepare
from paged_io import advice_report, artifact, file_hash
from six_hour_preflight import CURRENT, CUTS, PREPARATION, admission, frontier


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
        if (not calibration["xmlByteIdentical"] or len(calibration["fixtures"]) != 6 or
                not all(row["graphAndAuditIdentical"] for row in calibration["fixtures"])):
            raise ValueError("Missing exact preparation calibration")
        if artifact(Path("/data/region.osm.pbf")) != calibration["regionArtifact"]:
            raise ValueError("Original calibration parent differs")
        source_dir = inputs / "source-pilot" / args.source_run
        source = load_json(source_dir / "report.json")
        check_scripts(source_dir, source["scripts"])
        check_artifacts(source_dir, source["artifacts"])
        if source["imageId"] != args.base_image_id or source["sourceComplete"]:
            raise ValueError("Require the pinned partial cached-source screening input")
        current_dir = inputs / CURRENT
        current = load_json(current_dir / "manifest.json")
        cuts = load_json(inputs / CUTS / "report.json")
        check_scripts(current_dir, current["scripts"])
        check_artifacts(inputs / CUTS, cuts["artifacts"])
        plan_path = inputs / "coverage-pilot" / args.plan_run / "plan.json"
        plan = load_json(plan_path)
        expected_frontier = frontier(load_json(inputs / CUTS / "cut-nodes.json"), current["profile"]["bbox"])
        if (plan["manifestSha256"] != file_hash(current_dir / "manifest.json") or
                plan["cutReportSha256"] != file_hash(inputs / CUTS / "report.json") or
                plan["planningScriptSha256"] != file_hash(Path(__file__).with_name("six_hour_preflight.py")) or
                plan["frontierHelperSha256"] != file_hash(Path(__file__).with_name("two_hour_frontier.py")) or
                plan["frontier"] != expected_frontier or cuts["graphIdentity"] != current["graphIdentity"]):
            raise ValueError("Planning inputs changed")
        reference = load_json(inputs / PREPARATION / "report.json")
        build_manifest = load_json(current_dir / "build-manifest.json")
        if (file_hash(current_dir / "build-manifest.json") != current["buildManifestSha256"] or
                file_hash(inputs / PREPARATION / "report.json") != build_manifest["preparationReportSha256"]):
            raise ValueError("Reference census is not bound to the qualified build")
        report_paths = {"build": CURRENT + "/build-report.json", "rebuild": CURRENT + "-rebuild/build-report.json",
                        "qualification": CURRENT + "/qualification-report.json", "cuts": CUTS + "/report.json"}
        reports = {name: load_json(inputs / path) for name, path in report_paths.items()}
        for name in ("build", "qualification"):
            filename = Path(report_paths[name]).name
            if artifact(inputs / report_paths[name]) != current["artifacts"][filename]:
                raise ValueError(f"Qualified reference report differs: {name}")
        rebuild_dir = inputs / (CURRENT + "-rebuild")
        rebuild = load_json(rebuild_dir / "build-manifest.json")
        if (artifact(rebuild_dir / "build-report.json") != rebuild["artifacts"]["build-report.json"] or
                rebuild["graphIdentity"] != current["graphIdentity"]):
            raise ValueError("Rebuild reference differs")
        names = ("six_hour_prepare.py", "six-hour-prepare.mjs", "six_hour_preflight.py", "two_hour_frontier.py", "hour_admission.py")
        scripts = {**calibration["scripts"], **source["scripts"],
                   **{name: file_hash(Path(__file__).parent / name) for name in names}}
        bounds = expected_frontier["candidateBounds"]
        identity = {"bbox": bounds, "frontier": expected_frontier, "scripts": scripts,
                    "imageId": args.image_id, "baseImageId": args.base_image_id,
                    "sourceRun": args.source_run, "sourceReportSha256": file_hash(source_dir / "report.json"),
                    "regionArtifact": source["artifacts"]["region.osm.pbf"], "sourceComplete": False,
                    "planSha256": file_hash(plan_path), "calibrationReportSha256": file_hash(calibration_dir / "report.json"),
                    "referencePreparationSha256": file_hash(inputs / PREPARATION / "report.json"),
                    "referenceReportSha256": {name: file_hash(inputs / path) for name, path in report_paths.items()},
                    "referenceManifestSha256": file_hash(current_dir / "manifest.json"),
                    "memoryLimit": "4g", "memorySwapLimit": "4g", "cpus": 2, "network": "none", "referenceBatches": 4,
                    "purpose": "Partial-source early resource screening. Full cached SoCal/Mexico/Arizona intersected with the unclipped six-hour rectangle. Missing neighboring sources preclude full six-hour admission regardless of this result."}
        run_id = snapshot(output, identity, "identity.json")
        monitor.checkpoint("validated")
        try:
            xml, selection, commands = prepare(source_dir / "region.osm.pbf", bounds, output, monitor, batches=4)
            counts = census(xml, bounds, output / "candidate.sqlite")
            artifacts = {name: artifact(output / name) for name in ("car-roads.osm", "selected-ids.txt", "candidate.sqlite")}
            monitor.checkpoint("counted")
            observed = {name: peak(report) for name, report in reports.items()}
            observed["preparation"] = peak({"resourceCheckpoints": monitor.checkpoints})
            report = {"runId": run_id, **identity, "candidate": counts, "selection": selection,
                      "commands": commands, "artifacts": artifacts,
                      "admission": admission(counts, reference["candidate"], reports["build"], observed, False),
                      "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(),
                      "cacheAdvice": advice_report(), "workerWallMs": (time.perf_counter() - started) * 1000,
                      "publicApiCalls": 0, "coverageVerified": False, "newGraphBuilt": False}
            save_json(output / "report.json", report)
            print({key: report[key] for key in ("candidate", "admission", "workerWallMs")}, flush=True)
        except Exception as error:
            save_json(output / "failure.json", {"runId": run_id, "error": str(error),
                "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(),
                "workerWallMs": (time.perf_counter() - started) * 1000,
                "decision": "hold", "newGraphBuilt": False, "coverageVerified": False, "publicApiCalls": 0})
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--base-image-id", required=True)
    parser.add_argument("--source-run", default="six-hour-cached-v1")
    parser.add_argument("--plan-run", default="six-hour-plan-v1")
    run(parser.parse_args())
