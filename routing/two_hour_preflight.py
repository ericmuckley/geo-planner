"""Calibrate paged-ID preparation, then census the cached two-hour envelope."""

import argparse
import fcntl
import importlib.metadata
import json
from pathlib import Path
import time

from anchors import atomic_write, load_json
from buffer_resources import Monitor
from compact_storage import save_json
from coverage_census import census
from hour_admission import peak
from two_hour_admission import evaluate
from two_hour_frontier import plan
from import_roads import DEFAULT_SPEEDS, speed_kph
from increment import check_artifacts, check_scripts, snapshot
from paged_io import advice_report, artifact, file_hash
from regional_support import check_bounds
from two_hour_prepare import fixtures, prepare


SOURCE = "compact-pilot/hour-v3"
PREPARED = "coverage-pilot/hour-candidate-v1"


def run(args):
    output, inputs, recipe = Path(args.output), Path("/inputs"), Path(__file__).parent
    if (output / "identity.json").exists(): raise ValueError("Preserve attempts; use a fresh run name")
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started = time.perf_counter()
        profile_path = recipe / "profiles/coverage-two-hour-v1.json"
        profile = load_json(profile_path)
        current = load_json(inputs / SOURCE / "manifest.json")
        sparse = load_json(inputs / PREPARED / "report.json")
        qualified = load_json(inputs / SOURCE / "qualification-report.json")
        native = load_json(inputs / SOURCE / "native-verification.json")
        if current["imageId"] != args.base_image_id or sparse["imageId"] != args.image_id:
            raise ValueError("Pinned base/reader image differs")
        if qualified["graphIdentity"] != current["graphIdentity"] or native["sourceManifestSha256"] != file_hash(inputs / SOURCE / "manifest.json"):
            raise ValueError("Qualified graph/native evidence differs")
        if native["compilation"]["sourceSha256"] != file_hash(recipe / "native_search.cpp") or native["compilation"]["binarySha256"] != file_hash(inputs / SOURCE / "native_search"):
            raise ValueError("Native kernel/binary changed")
        qualified_peak, pressure = peak(qualified)
        if pressure or round(qualified_peak * 1.25) >= 4 * 1024 ** 3: raise ValueError("Qualification lacks 25% headroom")
        check_scripts(inputs / PREPARED, sparse["scripts"])
        check_artifacts(inputs / PREPARED, sparse["artifacts"])
        check_scripts(inputs / SOURCE, current["scripts"])
        check_artifacts(inputs / SOURCE, current["artifacts"])
        source_build = load_json(Path("/data/build-complete.json"))
        check_bounds(profile["bbox"], source_build["manifest"]["bbox"])
        if profile["model"] != current["profile"]["model"]["id"]: raise ValueError("Model differs")
        if profile["admissionHeadroomFactor"] != 1.25: raise ValueError("Keep the recorded margin")
        cut_directory = inputs / profile["cutInventory"]
        cuts = load_json(cut_directory / "report.json")
        if cuts["sourceManifestSha256"] != file_hash(inputs / SOURCE / "manifest.json") or cuts["nodesWithoutBoundaryLinks"]:
            raise ValueError("Cut evidence differs")
        check_artifacts(cut_directory, cuts["artifacts"])
        if max(DEFAULT_SPEEDS.values()) > 160 or speed_kph("160", 100) != 160: raise ValueError("Model speed bound changed")
        frontier = plan(load_json(cut_directory / "cut-nodes.json"), current["profile"]["bbox"], source_build["manifest"]["bbox"])
        if frontier["candidateBounds"] != profile["bbox"]: raise ValueError("Profile differs from all-frontier plan")
        parent = Path("/data/region.osm.pbf")
        if artifact(parent) != sparse["regionArtifact"]: raise ValueError("Parent PBF differs")
        bbox = current["profile"]["bbox"] if args.case == "calibration" else profile["bbox"]
        names = set(sparse["scripts"]) | set(current["scripts"]) | {"two_hour_preflight.py", "two-hour-preflight.mjs", "two_hour_admission.py", "two_hour_frontier.py", "two_hour_prepare.py", "paged_select.py", "paged_ids.py", "offline-sparse.mjs"}
        scripts = {name: file_hash(recipe / name) for name in sorted(names)}
        identity = {"case": args.case, "profile": profile, "profileSha256": file_hash(profile_path), "bbox": bbox,
                    "sourceManifestSha256": file_hash(inputs / SOURCE / "manifest.json"), "sourcePreparationReportSha256": file_hash(inputs / PREPARED / "report.json"),
                    "qualificationReportSha256": file_hash(inputs / SOURCE / "qualification-report.json"), "cutReportSha256": file_hash(cut_directory / "report.json"),
                    "regionArtifact": sparse["regionArtifact"], "frontier": frontier, "nativeReportSha256": file_hash(inputs / SOURCE / "native-verification.json"), "scripts": scripts, "imageId": args.image_id, "baseImageId": args.base_image_id,
                    "readerVersion": importlib.metadata.version("osmium"), "wheelLockSha256": file_hash(recipe / "tools/pyosmium-v1.json"),
                    "memoryLimit": "4g", "memorySwapLimit": "4g", "cpus": 2, "network": "none"}
        proof = None
        if args.case == "candidate":
            directory = inputs / "coverage-pilot" / args.calibration_run
            proof = load_json(directory / "report.json")
            if proof["scripts"] != scripts or proof["profile"] != profile or proof["imageId"] != args.image_id or not proof["xmlByteIdentical"]:
                raise ValueError("Complete same-code/profile/image calibration first")
            check_scripts(directory, proof["scripts"])
            check_artifacts(directory, proof["artifacts"])
            identity["calibrationReportSha256"] = file_hash(directory / "report.json")
        run_id = snapshot(output, identity, "identity.json")
        atomic_write(output / "recipe/coverage-two-hour-v1.json", profile_path.read_bytes())
        atomic_write(output / "recipe/pyosmium-v1.json", (recipe / "tools/pyosmium-v1.json").read_bytes())
        fixture_source = inputs / "coverage-pilot/staged-calibration-v2-r4"
        fixture_proof = load_json(fixture_source / "report.json")
        check_artifacts(fixture_source, fixture_proof["artifacts"])
        monitor.checkpoint("validated")
        fixture_rows = fixtures(inputs, output) if proof is None else proof["fixtures"]
        monitor.checkpoint("fixtures")
        xml, selection, commands = prepare(parent, bbox, output, monitor)
        xml_artifact = artifact(xml)
        counts = census(xml, bbox, output / "candidate.sqlite")
        identical = args.case == "calibration"
        if identical and (xml_artifact != current["sourceArtifact"] or counts != sparse["candidate"]):
            raise ValueError("Current-region XML/census differs")
        artifacts = {str(path.relative_to(output)): artifact(path) for path in output.rglob("*") if path.is_file()
                     and path.name not in {"identity.json", "progress.json", ".lock"} and "recipe" not in path.parts}
        monitor.checkpoint("verified")
        admission = None
        build_directory, rebuild_directory = inputs / SOURCE, inputs / "compact-pilot/hour-v3-rebuild"
        built, rebuilt = load_json(build_directory / "build-report.json"), load_json(rebuild_directory / "build-report.json")
        for directory in (build_directory, rebuild_directory):
            record = load_json(directory / "build-manifest.json")
            check_scripts(directory, record["scripts"])
            check_artifacts(directory, record["artifacts"])
        monitor.checkpoint("proofsVerified")
        if proof is not None:
            admission = evaluate(proof, {"resourceCheckpoints": monitor.checkpoints}, counts, built, rebuilt, qualified, native, cuts, frontier)
        report = {"runId": run_id, **identity, "fixtures": fixture_rows, "xmlByteIdentical": identical, "candidate": counts,
                  "selection": selection, "commands": commands, "artifacts": artifacts, "admission": admission,
                  "buildReportSha256": file_hash(build_directory / "build-report.json"), "rebuildReportSha256": file_hash(rebuild_directory / "build-report.json"),
                  "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(), "cacheAdvice": advice_report(),
                  "workerWallMs": (time.perf_counter() - started) * 1000, "publicApiCalls": 0, "fullGraphBuilt": False, "coverageVerified": False,
                  "scope": "Exact current-region XML/census and six native fixture proofs before the bounded cached two-hour census. Includes paged-ID preparation/import-export/qualification/inventory resource estimates with 25% margin. No new graph, route, contour or complete-coverage claim."}
        save_json(output / "report.json", report)
        print(json.dumps({key: report[key] for key in ("case", "xmlByteIdentical", "candidate", "admission", "workerWallMs")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("calibration", "candidate"), required=True)
    parser.add_argument("--calibration-run", default="two-hour-calibration-v1")
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--base-image-id", required=True)
    parser.add_argument("--output", default="/output")
    run(parser.parse_args())
