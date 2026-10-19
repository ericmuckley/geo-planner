"""Build and qualify the prepared all-direction local-experiment region.

Build and inventory bodies follow the frozen increment recipe. This distinct version
binds the new admission/source and uses the qualified virtual-terminal checks.
"""

import argparse
import fcntl
import gzip
import json
import mmap
from pathlib import Path
import time

from anchors import atomic_write, load_json
from xml_evidence import source_examples, source_uncertainties
from buffer_resources import Monitor
from compact_storage import save_json, write_csr
from crossing_audit import barrier_examples
from cut_inventory import boundary_links, cut_states, minimum_witness
from region_admission import build_admission, qualification_admission
from import_capacity import graph_data
from increment import ARTIFACTS, check_artifacts, check_counts, check_scripts, snapshot
from outgoing_import import import_barriers
from regional_checks import diagnose_routes, qualify
from lean_qualification import calibrate, load_checked
from paged_import import checked_manifest
from range_hash import advice_report, artifact, file_hash
from cache_lifetime import release_output, release_read, save_json as save_export
from regional_support import check_bounds


PREPARATION = "coverage-pilot/experiment-increment-v1"
CURRENT = "compact-pilot/hour-v3"
QUALIFIED = "qualification-pilot/experiment-lean-v1"


def candidate_profile(previous, prepared):
    check_bounds(previous["bbox"], prepared["bbox"])
    return {**previous, "id": "southern-california-baja-experiment-v3", "bbox": prepared["bbox"]}


def admission(inputs, image_id):
    directory = inputs / PREPARATION
    prepared = load_json(directory / "report.json")
    check_scripts(directory, prepared["scripts"])
    check_artifacts(directory, prepared["artifacts"])
    current = checked_manifest(inputs / CURRENT)
    build_dir = inputs / "outgoing-pilot/outgoing-v1-hour-v3"
    build_manifest = checked_manifest(build_dir)
    built = load_json(build_dir / "report.json")
    if prepared["baseImageId"] != image_id or current["imageId"] != image_id or build_manifest["imageId"] != image_id:
        raise ValueError("Pinned tools image differs")
    if build_manifest["graphIdentity"] != current["graphIdentity"]:
        raise ValueError("Importer calibration graph differs")
    if prepared["buildReportSha256"] != file_hash(build_dir / "report.json") or prepared["qualificationReportSha256"] != file_hash(inputs / CURRENT / "qualification-report.json"):
        raise ValueError("Prepared resource evidence changed")
    source = directory / "car-roads.osm"
    if artifact(source) != prepared["artifacts"]["car-roads.osm"]:
        raise ValueError("Prepared source differs")
    admitted = build_admission(prepared, built)
    if not admitted["eligible"]: raise ValueError("Build-only phase exceeds the unchanged resource gate")
    return admitted, prepared, {**current, "scripts": {**current["scripts"], **build_manifest["scripts"]}}, source


def build(args, output, inputs, monitor):
    started = time.perf_counter()
    admitted, prepared, imported, source = admission(inputs, args.image_id)
    old = imported
    profile = candidate_profile(old["profile"], prepared)
    names = set(imported["scripts"]) | set(prepared["scripts"]) | {
        "region_increment.py", "region-increment.mjs", "regional_checks.py", "regional_qualification.py", "virtual_sink.py",
        "region_admission.py", "lean_qualification.py", "compact_load.py", "compact_native.py", "cut_inventory.py"}
    scripts = {name: file_hash(Path(__file__).parent / name) for name in sorted(names)}
    identity = {"stage": args.stage, "profile": profile, "sourceArtifact": artifact(source), "sourcePreparation": PREPARATION,
                "preparationReportSha256": file_hash(inputs / PREPARATION / "report.json"), "phaseAdmission": admitted,
                "previousManifestSha256": file_hash(inputs / CURRENT / "manifest.json"),
                "coverageRecipeSha256": prepared["scripts"]["experiment_coverage.py"],
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

def qualification(args, output, inputs, monitor):
    started = time.perf_counter()
    manifest = load_json(output / "build-manifest.json")
    if manifest["imageId"] != args.image_id: raise ValueError("Image differs")
    check_scripts(output, manifest["scripts"])
    check_artifacts(output, manifest["artifacts"])
    base = {key: manifest[key] for key in ("profile", "sourceArtifact", "scripts", "imageId", "memoryLimit", "memorySwapLimit", "cpus", "network")}
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
              "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(), "cacheAdvice": advice_report(),
              "workerWallMs": (time.perf_counter() - started) * 1000, "costComparisons": summary["costComparisons"],
              "boundedCostComparisons": summary["boundedCostComparisons"], "interiorDestinationComparisons": summary["interiorDestinationComparisons"],
              "sampledCityDirections": 12, "publicApiCalls": 0, "coverageVerified": False,
              "scope": "Fresh independent full/bounded/virtual-terminal checks on the new graph after frozen flat-sink calibration. Final checkpoint follows verification reads; small metadata writes excluded. No contour or real eligibility claim."}
    save_json(output / "qualification-report.json", report)
    save_json(output / "manifest.json", {"runId": run_id, **identity, "graphIdentity": graph.identity,
              "artifacts": {**artifacts, "build-manifest.json": artifact(output / "build-manifest.json"),
                            "qualification-report.json": artifact(output / "qualification-report.json")}})
    print(json.dumps({key: report[key] for key in ("graphIdentity", "costComparisons", "boundedCostComparisons", "interiorDestinationComparisons", "workerWallMs")}, indent=2))


def inventory(args, output, inputs, monitor):
    started = time.perf_counter()
    source = inputs / "compact-pilot" / args.source_run
    manifest = load_json(source / "manifest.json")
    if manifest["imageId"] != args.image_id: raise ValueError("Image differs")
    check_scripts(source, manifest["scripts"])
    check_artifacts(source, manifest["artifacts"])
    xml = inputs / PREPARATION / "car-roads.osm"
    if artifact(xml) != manifest["sourceArtifact"]: raise ValueError("Source XML differs")
    identity = {**{key: manifest[key] for key in ("profile", "sourceArtifact", "scripts", "imageId", "memoryLimit", "memorySwapLimit", "cpus", "network")},
                "stage": "cuts", "sourceManifestSha256": file_hash(source / "manifest.json")}
    run_id = snapshot(output, identity, "run-identity.json")
    monitor.checkpoint("validated")
    graph = load_checked(source, manifest)
    audit, summary = load_json(source / "import-audit.json"), load_json(source / "summary.json")
    states = cut_states(graph, set(audit["cutExitNodes"]))
    blocked = set(audit["blockedNodes"])
    records = {node: {"node": node, "blockedByModel": node in blocked, "stateCount": len(indices), "origins": {}} for node, indices in states.items()}
    for origin in summary["origins"]:
        with (source / "oracles" / f"{origin['origin']}.u64le").open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as labels:
            if len(labels) != len(graph.states) * 8: raise ValueError("Oracle size differs")
            for node, indices in states.items():
                witness = minimum_witness(labels, indices)
                witness["road"] = graph.base.roads[graph.states[witness["state"]]["road"]] if witness["state"] is not None else None
                records[node]["origins"][origin["origin"]] = witness
        first = min((row["origins"][origin["origin"]]["costMs"] for row in records.values() if row["origins"][origin["origin"]]["costMs"] is not None), default=None)
        if first != origin["firstCutExitMs"]: raise ValueError("First cut differs")
    del graph
    monitor.checkpoint("oracleInventory")
    links = boundary_links(xml, manifest["profile"]["bbox"], set(states), {row["id"] for row in audit["excludedWays"]})
    for node, row in records.items():
        row.update(links[node])
        row["outsideSides"] = sorted({side for link in row["links"] for side in link["outsideSides"]})
        row["wayOnlyPlausibleOutward"] = not row["blockedByModel"] and any(link["wayOnlyOutwardAllowed"] and not link["wayExcludedByModel"] for link in row["links"])
    origins = []
    for origin in summary["origins"]:
        budgets = []
        for budget in summary["profile"]["budgetsMs"]:
            reached = [row for row in records.values() if row["origins"][origin["origin"]]["costMs"] is not None and row["origins"][origin["origin"]]["costMs"] <= budget]
            budgets.append({"budgetMs": budget, "reachableCutNodes": len(reached), "wayOnlyPlausibleOutwardNodes": sum(row["wayOnlyPlausibleOutward"] for row in reached),
                            "bySide": {side: sum(side in row["outsideSides"] for row in reached) for side in ("north", "east", "south", "west")}})
        origins.append({"origin": origin["origin"], "firstCutExitMs": origin["firstCutExitMs"], "budgets": budgets})
    save_json(output / "cut-nodes.json", [records[node] for node in sorted(records)])
    save_json(output / "cut-nodes.geojson", {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": row["point"]},
              "properties": {"node": row["node"], "outsideSides": row["outsideSides"], "blockedByModel": row["blockedByModel"],
                             "wayOnlyPlausibleOutward": row["wayOnlyPlausibleOutward"], "costMsByOrigin": {key: value["costMs"] for key, value in row["origins"].items()}}} for row in records.values()]})
    artifacts = {name: artifact(output / name) for name in ("cut-nodes.json", "cut-nodes.geojson")}
    monitor.checkpoint("verified")
    report = {"runId": run_id, **identity, "graphIdentity": manifest["graphIdentity"], "auditedCutNodes": len(states), "cutStates": sum(map(len, states.values())),
              "nodesWithoutBoundaryLinks": sum(not row["links"] for row in records.values()), "origins": origins, "artifacts": artifacts,
              "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(), "cacheAdvice": advice_report(),
              "workerWallMs": (time.perf_counter() - started) * 1000, "publicApiCalls": 0, "coverageVerified": False, "routeEligibilityVerified": False,
              "scope": "Every audited cut/history state with source links and new qualified oracle costs. Way-only outward permissions do not prove node/turn/history continuation beyond the extract."}
    save_json(output / "report.json", report)
    print(json.dumps({key: report[key] for key in ("auditedCutNodes", "cutStates", "nodesWithoutBoundaryLinks", "origins")}, indent=2))

def run(args):
    output, inputs = Path(args.output), Path("/inputs")
    identity_name = "qualification-identity.json" if args.stage == "qualify" else "run-identity.json"
    if (output / identity_name).exists() or (args.stage == "qualify" and (output / "oracle-calibration-identity.json").exists()): raise ValueError("Preserve attempts; use a fresh run name")
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.stage in {"build", "rebuild"}: build(args, output, inputs, monitor)
        elif args.stage == "qualify": qualification(args, output, inputs, monitor)
        else: inventory(args, output, inputs, monitor)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("build", "rebuild", "qualify", "cuts"), default="build")
    parser.add_argument("--source-run", default="experiment-region-v1")
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--output", default="/output")
    arguments = parser.parse_args()
    if not arguments.source_run or any(not (c.isascii() and (c.isalnum() or c in "_-")) for c in arguments.source_run): parser.error("Invalid source run")
    run(arguments)
