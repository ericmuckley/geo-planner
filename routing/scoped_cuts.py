"""Inventory qualified regional cuts without decoding unrelated source objects."""

import argparse
import fcntl
import json
import mmap
from pathlib import Path
import time

from anchors import load_json
from buffer_resources import Monitor
from compact_storage import save_json
from cut_inventory import cut_states, minimum_witness, outward_allowed, outside_sides
from import_roads import inside, tags
from increment import check_artifacts, check_scripts, snapshot
from range_hash import advice_report, artifact, file_hash
from region_admission import admission
from scoped_range_graph import load_checked
from regional_cuts import boundary_links
from hour_admission import peak
from xml_stream import parse_xml, report as stream_report


def run(args):
    started = time.perf_counter()
    output, inputs = Path(args.output), Path("/inputs")
    source = inputs / "compact-pilot" / args.graph_run
    preparation = inputs / "coverage-pilot" / args.preparation_run
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = load_json(source / "manifest.json")
        if manifest["imageId"] != args.image_id: raise ValueError("Image differs")
        check_scripts(source, manifest["scripts"])
        check_artifacts(source, manifest["artifacts"])
        xml = preparation / "car-roads.osm"
        if artifact(xml) != manifest["sourceArtifact"]: raise ValueError("Source XML differs")
        scripts = {**manifest["scripts"], **{name: file_hash(Path(__file__).parent / name) for name in
                   ("scoped_cuts.py", "scoped-region-cuts-v2.mjs", "regional_cuts.py", "scoped_load.py", "scoped_range_graph.py", "range_graph.py", "xml_stream.py")}}
        identity = {**{key: manifest[key] for key in ("profile", "sourceArtifact", "imageId", "memoryLimit", "memorySwapLimit", "cpus", "network")},
                    "stage": "cuts", "scripts": scripts, "sourceManifestSha256": file_hash(source / "manifest.json"),
                    "graphIdentity": manifest["graphIdentity"]}
        original = None
        if args.compare_run:
            original_dir = inputs / "compact-pilot" / args.compare_run
            original = load_json(original_dir / "report.json")
            if original["graphIdentity"] != manifest["graphIdentity"]: raise ValueError("Calibration graph differs")
            check_artifacts(original_dir, original["artifacts"])
            identity["previousCutReportSha256"] = file_hash(original_dir / "report.json")
        else:
            calibrated_dir = inputs / "compact-pilot/experiment-region-v1-cuts-streamed"
            calibrated = load_json(calibrated_dir / "report.json")
            check_scripts(calibrated_dir, calibrated["scripts"])
            check_artifacts(calibrated_dir, calibrated["artifacts"])
            if not calibrated["identicalCutArtifacts"]: raise ValueError("Missing boundary-reader calibration")
            measured, pressure = peak(calibrated)
            admitted = admission("all-cut-inventory", measured, load_json(preparation / "report.json")["admission"]["scalingRatio"], pressure)
            if not admitted["eligible"]: raise ValueError("Cut inventory exceeds the unchanged resource gate")
            identity.update(phaseAdmission=admitted, calibrationReportSha256=file_hash(calibrated_dir / "report.json"))
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
        if original and artifacts != original["artifacts"]: raise ValueError("Frozen boundary artifacts differ")
        monitor.checkpoint("verified")
        report = {"runId": run_id, **identity, "auditedCutNodes": len(states), "cutStates": sum(map(len, states.values())),
                  "nodesWithoutBoundaryLinks": sum(not row["links"] for row in records.values()), "origins": origins, "artifacts": artifacts,
                  "identicalCutArtifacts": bool(original), "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(),
                  "cacheAdvice": advice_report(), "streams": stream_report(), "workerWallMs": (time.perf_counter() - started) * 1000,
                  "publicApiCalls": 0, "coverageVerified": False, "routeEligibilityVerified": False,
                  "scope": "Every audited cut/history state and exact oracle witness. Only incident source ways and neighboring nodes retained. Potential outward links do not prove real access or complete sources."}
        save_json(output / "report.json", report)
        print(json.dumps({key: report[key] for key in ("auditedCutNodes", "cutStates", "nodesWithoutBoundaryLinks", "identicalCutArtifacts", "workerWallMs")}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("graph-run", "preparation-run"): parser.add_argument("--" + name, required=True)
    parser.add_argument("--compare-run")
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    args = parser.parse_args()
    for value in (args.graph_run, args.preparation_run, args.compare_run):
        if value is not None and (not value or any(not (c.isascii() and (c.isalnum() or c in "_-")) for c in value)): parser.error("Invalid run name")
    run(args)
