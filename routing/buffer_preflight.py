"""Qualify staged extraction, then count a cut-guided cached coverage increment."""

import argparse
import fcntl
import json
from pathlib import Path
import shutil
import time

from anchors import atomic_write, digest, file_hash, load_json
from buffer_resources import Monitor
from compact_storage import encoded_blocks, save_json
from coverage_census import census
from import_capacity import graph_data
from input_import import import_barriers
from maneuver_graph_test import MODEL, osm
from reference import extract
from regional_support import check_bounds, supported_xml
from staged_prepare import command, prepare


def artifact(path): return {"bytes": path.stat().st_size, "sha256": file_hash(path)}


def fixture_checks(output, image):
    sources = [osm(), osm("only_straight_on"), osm(extra='<tag k="restriction:conditional" v="no_left_turn @ (Mo-Fr)"/>'),
               osm(extra='<tag k="except" v="motorcar"/>'), osm().replace('type" v="restriction"', 'type" v="restriction:bicycle"')]
    # Outer nodes and a wholly outside member must survive completion.
    sources.append('<osm><node id="1" lon="-2" lat="0"/><node id="2" lon="-.5" lat="0"/><node id="3" lon="0" lat="0"/>'
        '<node id="4" lon=".5" lat="0"/><node id="5" lon="2" lat="0"/><node id="6" lon="3" lat="0"/>'
        + ''.join(f'<way id="{identifier}">' + ''.join(f'<nd ref="{node}"/>' for node in refs) + '<tag k="highway" v="residential"/></way>' for identifier, refs in ((10,(1,2)), (20,(2,3,4)), (30,(4,5,6)), (40,(6,1)), (50,(2,4))))
        + '<relation id="100"><member type="way" ref="10" role="from"/><member type="way" ref="20" role="via"/><member type="way" ref="30" role="to"/><tag k="type" v="restriction"/><tag k="restriction" v="no_straight_on"/></relation>'
        + '<relation id="101"><member type="way" ref="40" role="from"/><member type="node" ref="1" role="via"/><member type="way" ref="10" role="to"/><tag k="type" v="restriction"/><tag k="restriction" v="no_right_turn"/></relation></osm>')
    rows = []
    for index, text in enumerate(sources):
        directory = output / "fixtures" / str(index)
        directory.mkdir(parents=True)
        raw = directory / "source.osm"
        raw.write_text(text.replace('<osm>', '<osm version="0.6">', 1))
        command(["osmium", "cat", str(raw), "-o", str(directory / "region.osm.pbf")], directory, "toPbf", None)
        build = {"artifacts": {"region.osm.pbf": artifact(directory / "region.osm.pbf")}}
        old = directory / "old"; old.mkdir()
        bounds = [-1, -1, 1, 1]
        old_xml = supported_xml(extract(directory, old, build, {"bbox": bounds}, image), old, image)
        new_xml, _ = prepare(directory / "region.osm.pbf", bounds, directory / "new")
        model = {**MODEL, "id": "exploratory-static-car-v3"}
        old_graph, old_audit = import_barriers(old_xml, old / "barrier.osm", bounds, model)
        new_graph, new_audit = import_barriers(new_xml, directory / "new/barrier.osm", bounds, model)
        if b"".join(encoded_blocks(graph_data(old_graph, model))) != b"".join(encoded_blocks(graph_data(new_graph, model))) or old_audit != new_audit:
            raise ValueError(f"Staged preparation fixture differs: {index}")
        rows.append({"fixture": index, "graphIdentity": new_graph.identity, "auditSha256": digest(new_audit), "graphAndAuditIdentical": True,
                     "sourceArtifact": artifact(raw), "oldXml": artifact(old_xml), "newXml": artifact(new_xml)})
    return rows


def assess(candidate, calibration, measured, factor=1.25, cap=4 * 1024 ** 3):
    ratios = {key: candidate[key] / calibration[key] for key in ("sourceNodes", "sourceWays", "wayEligibleDirectedSegments", "historyStatesUpperBound")}
    ratio = max(ratios.values())
    worker = measured["resourceCheckpoints"]["historyBuilt"]["workerMaxRssKiB"] * 1024
    estimate = round(worker * ratio * factor)
    return {"ratios": ratios, "scalingRatio": ratio, "calibrationWorkerPeakBytes": worker, "workerEstimateWithHeadroomBytes": estimate,
            "headroomFactor": factor, "capBytes": cap, "workerEstimateFits": estimate < cap,
            "decision": "hold-for-import-export-accounting" if estimate < cap else "hold-for-worker-capacity", "fullGraphAdmitted": False,
            "scope": "Input/state-ratio worker heuristic, not a bound. Prior complete-container export peak was near cap; measured preparation and worker estimates alone do not admit a full build."}


def run(args):
    started = time.perf_counter()
    output, recipe, inputs = Path(args.output), Path(__file__).parent, Path("/inputs")
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "run-identity.json").exists(): raise ValueError("Preserve attempts; use a fresh run name")
        profile = load_json(recipe / "profiles" / f"coverage-{args.case}-v2.json")
        source = Path("/data")
        build = load_json(source / "build-complete.json")
        known_path = inputs / "compact-pilot/compact-v1-buffer-v3/manifest.json"
        known = load_json(known_path)
        check_bounds(profile["bbox"], build["manifest"]["bbox"])
        scripts = {name: file_hash(recipe / name) for name in ("buffer_preflight.py", "buffer-preflight.mjs", "staged_prepare.py", "buffer_resources.py", "offline-no-swap.mjs", "coverage_census.py", "input_import.py", "input_storage.py", "compact_import.py", "compact_storage.py", "barrier_policy.py", "import_roads.py", "import_maneuvers.py", "maneuver_graph.py", "maneuver_graph_test.py", "state_graph.py", "anchors.py", "reference.py", "regional_support.py", "import_capacity.py", "stream_import.py", "barriers.py", "native_support.py", "cell_experiment.py", "cell_index.py")}
        identity = {"case": args.case, "profile": profile, "sourceBuildSha256": file_hash(source / "build-complete.json"),
                    "sourceManifest": build["manifest"], "regionArtifact": build["artifacts"]["region.osm.pbf"], "imageId": args.image_id,
                    "frozenBufferManifestSha256": file_hash(known_path),
                    "scripts": scripts, "memoryLimit": "4g", "memorySwapLimit": "4g", "cpus": 2, "network": "none"}
        if args.case == "candidate":
            calibration = inputs / "coverage-pilot" / args.calibration_run
            proof = load_json(calibration / "report.json")
            if not proof["matchesFrozenXml"] or proof["scripts"] != scripts: raise ValueError("Qualify the same-code staged calibration first")
            if proof["imageId"] != args.image_id or proof["regionArtifact"] != identity["regionArtifact"]: raise ValueError("Calibration source/image differs")
            for name, expected in proof["artifacts"].items():
                if artifact(calibration / name) != expected: raise ValueError("Calibration artifact changed")
            cuts = inputs / "coverage-pilot/buffer-cut-inventory-v1"
            cut_report = load_json(cuts / "report.json")
            for name, expected in cut_report["artifacts"].items():
                if artifact(cuts / name) != expected: raise ValueError("Cut inventory changed")
            identity.update({"calibrationReportSha256": file_hash(calibration / "report.json"), "cutReportSha256": file_hash(cuts / "report.json")})
            measured_path = inputs / "input-pilot/input-v1-buffer-v3/report.json"
            measured = load_json(measured_path)
            measured_manifest = load_json(measured_path.with_name("manifest.json"))
            if artifact(measured_path) != measured_manifest["artifacts"]["report.json"] or measured["graphIdentity"] != known["graphIdentity"]:
                raise ValueError("Measured import calibration changed")
            identity["measuredImportReportSha256"] = file_hash(measured_path)
        run_id = digest(identity)
        save_json(output / "run-identity.json", {"runId": run_id, **identity})
        (output / "recipe").mkdir()
        for name in scripts: atomic_write(output / "recipe" / name, (recipe / name).read_bytes())
        atomic_write(output / "recipe/profile.json", (recipe / "profiles" / f"coverage-{args.case}-v2.json").read_bytes())
        if artifact(source / "region.osm.pbf") != identity["regionArtifact"]: raise ValueError("Parent changed")
        if args.image_id != known["imageId"]: raise ValueError("Image differs")
        monitor.checkpoint("validated")
        fixtures = fixture_checks(output, args.image_id) if args.case == "calibration" else proof["fixtures"]
        monitor.checkpoint("fixtures")
        xml, commands = prepare(source / "region.osm.pbf", profile["bbox"], output, monitor)
        matches = artifact(xml) == known["sourceArtifact"] if args.case == "calibration" else None
        counts = census(xml, profile["bbox"], output / "candidate.sqlite")
        monitor.checkpoint("census")
        capacity = None
        if args.case == "candidate":
            capacity = assess(counts, proof["candidate"], measured, profile["admissionHeadroomFactor"], profile["memoryLimitBytes"])
        artifacts = {str(path.relative_to(output)): artifact(path) for path in output.rglob("*") if path.is_file() and path.name not in {".lock", "progress.json", "run-identity.json"} and "recipe" not in path.parts}
        monitor.checkpoint("complete")
        disk = shutil.disk_usage(output)
        report = {"runId": run_id, **identity, "fixtures": fixtures, "commands": commands, "matchesFrozenXml": matches, "candidate": counts,
                  "capacity": capacity, "artifacts": artifacts, "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(),
                  "workerWallMs": (time.perf_counter() - started) * 1000, "diskFreeBytes": disk.free,
                  "publicApiCalls": 0, "fullGraphBuilt": False, "coverageVerified": False, "routeEligibilityVerified": False,
                  "limitations": ["Prepared reference-complete objects and count bounds do not establish legal new routes or complete contours.",
                    "Parent California/Mexico source has missing AZ/NV roads and no Canada; parent clipping remains.",
                    "Static v3 access uncertainty, border queues/current eligibility and long-range coverage limitations remain.",
                    "Source selection is a versioned recipe; calibration equality gates candidate use."]}
        save_json(output / "report.json", report)
        print(json.dumps({key: report[key] for key in ("matchesFrozenXml", "candidate", "capacity", "workerWallMs")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("calibration", "candidate"), required=True)
    parser.add_argument("--calibration-run", default="staged-calibration-v2-r4")
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--output", default="/output")
    run(parser.parse_args())
