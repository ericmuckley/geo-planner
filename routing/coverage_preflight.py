"""Prepare a broader cached extract and assess capacity before a full graph build."""

import argparse
import fcntl
import json
from pathlib import Path
import resource
import shutil
import time

from anchors import atomic_write, digest, file_hash, load_json, save_json
from coverage_census import census
from import_capacity import resources
from reference import extract
from regional_support import check_bounds, supported_xml


def artifact(path):
    return {"bytes": path.stat().st_size, "sha256": file_hash(path)}


def assessment(candidate, calibration, summary, rebuild, profile):
    ratios = {key: candidate[key] / calibration[key] for key in ("sourceNodes", "sourceWays", "wayEligibleDirectedSegments")}
    ratio = max(ratios.values())
    rss = max(summary["resourceCheckpoints"]["complete"]["workerMaxRssKiB"], rebuild["resourceCheckpoints"]["complete"]["workerMaxRssKiB"]) * 1024
    peak = max(int(summary["resourceCheckpoints"]["complete"]["memory.peak"]), int(rebuild["resourceCheckpoints"]["complete"]["memory.peak"]))
    forecast = peak * ratio * profile["admissionHeadroomFactor"]
    return {"ratiosToCalibration": ratios, "scalingRatio": ratio, "calibrationWorkerRssBytes": rss,
            "calibrationObservedContainerPeakBytes": peak, "scaledWorkerRssBytes": round(rss * ratio),
            "scaledContainerPeakBytes": round(peak * ratio), "headroomFactor": profile["admissionHeadroomFactor"],
            "admissionEstimateBytes": round(forecast), "capBytes": profile["memoryLimitBytes"],
            "decision": "hold-for-compact-storage" if forecast >= profile["memoryLimitBytes"] else "eligible-for-separate-capped-build",
            "scope": "Heuristic linear scaling by the largest measured input/road ratio, calibrated to the larger observed build/rebuild peak. Not a memory bound or national forecast; relation complexity, topology, geometry and file cache can change scaling."}


def run(args):
    started = time.perf_counter()
    output, recipe, source = Path(args.output), Path(__file__).parent, Path(args.data)
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "run-identity.json").exists(): raise ValueError("Run exists; preserve completed or failed attempts and use a new --run-name")
        profile = load_json(recipe / "profiles/coverage-buffer-v1.json")
        build = load_json(source / "build-complete.json")
        check_bounds(profile["bbox"], build["manifest"]["bbox"])
        calibration = Path("/calibration")
        manifest = load_json(calibration / "manifest.json")
        summary = load_json(calibration / "summary.json")
        rebuild = load_json(calibration / "rebuild-verification.json")
        old_source = Path("/calibration-source/car-roads.osm")
        if file_hash(old_source) != manifest["sourceXmlSha256"]: raise ValueError("Calibration source changed")
        for name in ("summary.json", "graph.csr", "graph.json"):
            if artifact(calibration / name) != manifest["artifacts"][name]: raise ValueError(f"Calibration changed: {name}")
        if manifest["imageId"] != args.image_id or rebuild["sourceManifestSha256"] != file_hash(calibration / "manifest.json"):
            raise ValueError("Calibration image/rebuild differs")
        if summary["profile"]["model"]["id"] != profile["model"]: raise ValueError("Calibration model differs")
        scripts = {name: file_hash(recipe / name) for name in (
            "coverage_preflight.py", "coverage_census.py", "anchors.py", "reference.py", "regional_support.py", "import_roads.py", "import_maneuvers.py",
            "state_graph.py", "maneuver_graph.py", "import_capacity.py", "stream_import.py", "barrier_policy.py", "barriers.py", "native_support.py", "cell_experiment.py", "cell_index.py")}
        identity = {"profile": profile, "sourceManifest": build["manifest"], "regionArtifact": build["artifacts"]["region.osm.pbf"],
                    "sourceBuildSha256": file_hash(source / "build-complete.json"), "calibrationManifestSha256": file_hash(calibration / "manifest.json"),
                    "calibrationRebuildSha256": file_hash(calibration / "rebuild-verification.json"), "imageId": args.image_id,
                    "scripts": scripts, "cpus": 2, "network": "none", "memoryLimit": "4g"}
        run_id = digest(identity)
        save_json(output / "run-identity.json", {"runId": run_id, **identity})
        checkpoints, timings = {}, {}

        def checkpoint(stage, before):
            checkpoints[stage] = {**resources(), "maxChildRssKiB": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}
            timings[stage] = (time.perf_counter() - before) * 1000
            save_json(output / "progress.json", {"completedStage": stage, "resources": checkpoints, "stageWallMs": timings})
            print(f"Completed {stage}: {timings[stage] / 1000:.2f} s; cgroup peak {checkpoints[stage].get('memory.peak')} bytes", flush=True)

        before = time.perf_counter()
        old = census(old_source, summary["profile"]["bbox"], output / "calibration.sqlite")
        if not old["roadStatesLowerBound"] <= summary["baseRoads"] <= old["roadStatesUpperBound"] or summary["states"] > old["historyStatesUpperBound"]:
            raise ValueError("Census bounds do not contain the qualified graph")
        checkpoint("calibrationCensus", before)
        before = time.perf_counter()
        raw = extract(source, output, build, profile, args.image_id)
        checkpoint("extractAndRoadXml", before)
        before = time.perf_counter()
        filtered = supported_xml(raw, output, args.image_id)
        checkpoint("supportedRoadFilter", before)
        before = time.perf_counter()
        current = census(filtered, profile["bbox"], output / "candidate.sqlite")
        checkpoint("candidateCensus", before)
        assessment_result = assessment(current, old, summary, rebuild, profile)
        preparation = checkpoints["supportedRoadFilter"]
        pressure = int(preparation.get("memory.events", {}).get("max", 0)) > 0
        names = ("region.osm.pbf", "roads.osm", "car-roads.osm", "calibration.sqlite", "candidate.sqlite", "extract.json", "car-filter.json", "extract-resources.txt", "car-filter-resources.txt")
        artifacts = {name: artifact(output / name) for name in names}
        disk = shutil.disk_usage(output)
        graph_scale = max(current["roadStatesUpperBound"] / summary["baseRoads"], current["historyStatesUpperBound"] / summary["states"])
        report = {"runId": run_id, "profile": profile, "calibration": old, "candidate": current,
                  "calibrationGraph": {"roads": summary["baseRoads"], "states": summary["states"], "graphIdentity": manifest["graphIdentity"]},
                  "capacity": assessment_result, "resourceCheckpoints": checkpoints, "stageWallMs": timings,
                  "preparationLimitPressure": pressure,
                  "artifacts": artifacts, "disk": {"preparedArtifactBytes": sum(item["bytes"] for item in artifacts.values()),
                      "availableBytesObserved": disk.free, "scaledGraphJsonBytes": round(manifest["artifacts"]["graph.json"]["bytes"] * graph_scale),
                      "scaledCsrBytes": round(manifest["artifacts"]["graph.csr"]["bytes"] * graph_scale),
                      "scope": "Prepared artifact bytes measured; graph/CSR bytes estimated from state/road ratio, not built. Future geometry, oracles, snapshots and scratch require extra space."},
                  "workerWallMs": (time.perf_counter() - started) * 1000, "publicApiCalls": 0, "network": "none", "fullGraphBuilt": False,
                  "coverageVerified": False, "routeEligibilityVerified": False,
                  "limitations": ["Buffer reduces known cuts but does not establish complete 60-minute or 10–12-hour reachability.",
                      "Parent bbox is California/northern Baja; AZ/NV roads are missing and parent cuts remain. No Canadian buffer.",
                      "Smart completion can include roads outside the candidate bbox; only segments with both endpoints inside count toward states.",
                      "Road/state intervals are capacity bounds, not exact built graph counts, paths, contours or validated access.",
                      "V3 source crossing uncertainties, border queues, documents, speeds and static-cost limitations remain unchanged."]}
        snapshots = output / "recipe"
        snapshots.mkdir()
        for name in scripts: atomic_write(snapshots / name, (recipe / name).read_bytes())
        atomic_write(snapshots / "coverage-buffer-v1.json", (recipe / "profiles/coverage-buffer-v1.json").read_bytes())
        save_json(output / "report.json", report)
        print(json.dumps({"runId": run_id, "candidate": current, "capacity": assessment_result, "disk": report["disk"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="/data")
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    run(parser.parse_args())
