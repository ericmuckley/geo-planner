"""Build the two-hour candidate with the frozen outgoing importer and resource gate."""

import argparse
import fcntl
import gzip
import json
from pathlib import Path
import time

from anchors import atomic_write, load_json
from xml_evidence import source_examples, source_uncertainties
from buffer_resources import Monitor
from compact_storage import save_json, write_csr
from crossing_audit import barrier_examples
from region_admission import build_admission
from import_capacity import graph_data
from increment import ARTIFACTS, check_artifacts, check_counts, check_scripts, snapshot
from outgoing_import import import_barriers
from paged_import import checked_manifest
from range_hash import advice_report, artifact, file_hash
from cache_lifetime import release_output, release_read, save_json as save_export
from regional_support import check_bounds


PREPARATION = "coverage-pilot/two-hour-region-v2"
CURRENT = "compact-pilot/experiment-region-v1"


def candidate_profile(previous, prepared):
    check_bounds(previous["bbox"], prepared["bbox"])
    return {**previous, "id": "san-diego-two-hour-static-v3", "bbox": prepared["bbox"]}


def admission(inputs, image_id):
    directory = inputs / PREPARATION
    prepared = load_json(directory / "report.json")
    check_scripts(directory, prepared["scripts"])
    check_artifacts(directory, prepared["artifacts"])
    current = checked_manifest(inputs / CURRENT)
    build_dir = inputs / CURRENT
    built = load_json(build_dir / "build-report.json")
    rebuild = load_json(inputs / (CURRENT + "-rebuild") / "build-report.json")
    built = {"resourceCheckpoints": {**built["resourceCheckpoints"], **{"rebuild-" + key: value for key, value in rebuild["resourceCheckpoints"].items()}}}
    if prepared["baseImageId"] != image_id or current["imageId"] != image_id:
        raise ValueError("Pinned tools image differs")
    if prepared["buildReportSha256"] != file_hash(build_dir / "build-report.json") or prepared["qualificationReportSha256"] != file_hash(inputs / CURRENT / "qualification-report.json"):
        raise ValueError("Prepared resource evidence changed")
    if prepared["referenceReportSha256"]["rebuild"] != file_hash(inputs / (CURRENT + "-rebuild") / "build-report.json"):
        raise ValueError("Reference rebuild resource evidence changed")
    source = directory / "car-roads.osm"
    if artifact(source) != prepared["artifacts"]["car-roads.osm"]:
        raise ValueError("Prepared source differs")
    admitted = build_admission(prepared, built)
    if not admitted["eligible"]: raise ValueError("Build-only phase exceeds the unchanged resource gate")
    return admitted, prepared, current, source


def build(args, output, inputs, monitor):
    started = time.perf_counter()
    admitted, prepared, imported, source = admission(inputs, args.image_id)
    old = imported
    profile = candidate_profile(old["profile"], prepared)
    names = set(imported["scripts"]) | set(prepared["scripts"]) | {
        "two_hour_region.py", "two-hour-region.mjs", "regional_checks.py", "regional_qualification.py", "virtual_sink.py",
        "region_admission.py", "lean_qualification.py", "compact_load.py", "compact_native.py", "cut_inventory.py"}
    scripts = {name: file_hash(Path(__file__).parent / name) for name in sorted(names)}
    identity = {"stage": args.stage, "profile": profile, "sourceArtifact": artifact(source), "sourcePreparation": PREPARATION,
                "preparationReportSha256": file_hash(inputs / PREPARATION / "report.json"), "phaseAdmission": admitted,
                "previousManifestSha256": file_hash(inputs / CURRENT / "manifest.json"),
                "coverageRecipeSha256": prepared["scripts"]["two_hour_region_prepare_v2.py"],
                "candidateCounts": prepared["candidate"], "scripts": scripts, "imageId": args.image_id,
                "memoryLimit": "4g", "memorySwapLimit": "4g", "cpus": 2, "network": "none"}
    original = None
    if args.stage == "rebuild":
        directory = inputs / "compact-pilot" / args.source_run
        original = load_json(directory / "build-manifest.json")
        check_scripts(directory, original["scripts"])
        check_artifacts(directory, original["artifacts"])
        if original["sourceArtifact"] != identity["sourceArtifact"] or original["profile"] != profile:
            raise ValueError("Rebuild source/profile differs")
        identity["rebuildManifestSha256"] = file_hash(directory / "build-manifest.json")
    run_id = snapshot(output, identity, "run-identity.json")
    monitor.checkpoint("validated")
    measurements = {}
    before = time.perf_counter()
    graph, audit = import_barriers(source, output / "barrier-roads.osm", profile["bbox"], profile["model"], measurements, monitor.checkpoint)
    import_ms = (time.perf_counter() - before) * 1000
    check_counts(len(graph.base.roads), len(graph.states), prepared["candidate"])
    examples, incoming, outgoing = source_examples(source, output / "barrier-source-samples.osm", graph, audit)
    uncertain = source_uncertainties(source, output / "uncertain-crossings-source.osm")
    by_way = {row["id"]: [] for row in uncertain}
    for road in graph.base.roads:
        if road["way"] in by_way: by_way[road["way"]].append(road["id"])
    for row in uncertain: row["retainedDirectedRoadIds"] = by_way[row["id"]]
    audit["sourceCrossingUncertainties"] = uncertain
    extra = barrier_examples(graph, audit, {1228835396, 8181606580, 9357332258})
    private = next(row for row in extra if row["id"] == 1228835396)
    if not private["blockedByModel"] or not any(not row["uTurn"] for row in private["transitions"]):
        raise ValueError("Private through-gate fixture lost")
    if any(row["blockedByModel"] for row in extra if row["id"] != 1228835396): raise ValueError("Qualified crossing control closed")
    monitor.checkpoint("sourceEvidence")
    release_read(source, "source-evidence")
    save_export(output / "graph.json", graph_data(graph, profile["model"]))
    save_export(output / "import-audit.json", audit)
    write_csr(output / "graph.csr", graph.adjacency, graph.identity)
    release_output(output / "graph.csr", "csr-output")
    atomic_write(output / "graph.csr.gz", gzip.compress((output / "graph.csr").read_bytes(), mtime=0))
    release_read(output / "graph.csr", "gzip-input")
    release_output(output / "graph.csr.gz", "gzip-output")
    monitor.checkpoint("exported")
    artifacts = {name: artifact(output / name) for name in ARTIFACTS}
    if original is not None:
        if graph.identity != original["graphIdentity"]: raise ValueError("Rebuild graph identity differs")
        for name, actual in artifacts.items():
            if actual != original["artifacts"][name]: raise ValueError(f"Rebuild bytes differ: {name}")
    monitor.checkpoint("verified")
    report = {"runId": run_id, "graphIdentity": graph.identity, "roads": len(graph.base.roads), "states": len(graph.states),
              "transitions": len(graph.adjacency.targets), "viaWayRestrictions": len(graph.patterns), "importMs": import_ms,
              "importStages": measurements, "barrierExamples": examples + extra, "portIncoming": incoming, "portOutgoing": outgoing,
              "artifacts": artifacts, "identicalRebuildArtifacts": list(ARTIFACTS) if original else [],
              "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(), "cacheAdvice": advice_report(),
              "workerWallMs": (time.perf_counter() - started) * 1000, "publicApiCalls": 0, "coverageVerified": False,
              "scope": "Build-only resource admission; release still requires independent qualification, exact rebuild, native and all-cut checks. Source imported/exported under the unchanged cap. No new routes, contour, real eligibility or complete-coverage claim. Final checkpoint follows all artifact verification reads; small metadata writes excluded."}
    save_json(output / "build-report.json", report)
    save_json(output / "build-manifest.json", {"runId": run_id, **identity, "graphIdentity": graph.identity,
              "artifacts": {**artifacts, "build-report.json": artifact(output / "build-report.json")}})
    print(json.dumps({key: report[key] for key in ("graphIdentity", "roads", "states", "transitions", "importMs", "workerWallMs")}, indent=2))

def run(args):
    output, inputs = Path(args.output), Path("/inputs")
    if (output / "run-identity.json").exists(): raise ValueError("Preserve attempts; use a fresh run name")
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        build(args, output, inputs, monitor)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("build", "rebuild"), default="build")
    parser.add_argument("--source-run", default="two-hour-region-v1")
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--output", default="/output")
    arguments = parser.parse_args()
    if not arguments.source_run or any(not (c.isascii() and (c.isalnum() or c in "_-")) for c in arguments.source_run): parser.error("Invalid source run")
    run(arguments)
