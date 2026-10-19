"""Inventory every audited potential cut using frozen full-cost oracle fields."""

import argparse
import fcntl
import json
import mmap
from pathlib import Path
import struct
import time

from anchors import atomic_write, digest, file_hash, load_json
from buffer_resources import Monitor
from compact_load import load_graph
from compact_storage import save_json
from coverage_census import directions
from import_roads import access_allowed, inside
from input_storage import read_osm
from native_support import UINT64_MAX


def artifact(path): return {"bytes": path.stat().st_size, "sha256": file_hash(path)}


def outside_sides(point, bounds):
    return [side for side, outside in (("west", point[0] < bounds[0]), ("south", point[1] < bounds[1]),
                                      ("east", point[0] > bounds[2]), ("north", point[1] > bounds[3])) if outside]


def outward_allowed(properties, forward):
    if not directions(properties): return False
    oneway = properties.get("oneway:motorcar", properties.get("oneway:motor_vehicle", properties.get("oneway")))
    if oneway is None: oneway = "yes" if properties.get("junction") in {"roundabout", "circular"} or properties.get("highway") == "motorway" else "no"
    return (oneway != "-1" if forward else oneway in {"no", "0", "false", "-1"}) and access_allowed(properties, "forward" if forward else "backward")


def boundary_links(source, bounds, wanted, excluded):
    nodes, ways, _ = read_osm(source)
    result = {node: {"point": nodes[node]["point"], "links": []} for node in wanted}
    for way_id, way in ways.items():
        refs, properties = way["nodes"], way["tags"]
        for segment, (tail, head) in enumerate(zip(refs, refs[1:])):
            for node, other, forward in ((tail, head, True), (head, tail, False)):
                if node not in wanted: continue
                point = nodes[other]["point"]
                if inside(point, bounds): continue
                result[node]["links"].append({"way": way_id, "segment": segment, "direction": "f" if forward else "r",
                    "outsideNode": other, "outsidePoint": point, "outsideSides": outside_sides(point, bounds), "sourceTags": properties,
                    "wayOnlyOutwardAllowed": outward_allowed(properties, forward), "wayExcludedByModel": way_id in excluded})
    return result


def cut_states(graph, nodes):
    road_nodes = {road: head for road, head in enumerate(graph.base.roads.heads) if head in nodes}
    states = {node: [] for node in nodes}
    for index, state in enumerate(graph.states):
        node = road_nodes.get(state["road"])
        if node is not None: states[node].append(index)
    return states


def minimum_witness(labels, states):
    best = min(((struct.unpack_from("<Q", labels, state * 8)[0], state) for state in states), default=(UINT64_MAX, None))
    return {"costMs": best[0], "state": best[1]} if best[0] != UINT64_MAX else {"costMs": None, "state": None}


def run(args):
    started = time.perf_counter()
    output, source, inputs, recipe = Path(args.output), Path("/inputs/compact-pilot/compact-v1-buffer-v3"), Path("/inputs"), Path(__file__).parent
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "run-identity.json").exists(): raise ValueError("Preserve attempts; use a fresh run name")
        manifest, summary = load_json(source / "manifest.json"), load_json(source / "summary.json")
        if manifest["imageId"] != args.image_id: raise ValueError("Image differs")
        scripts = {name: file_hash(recipe / name) for name in ("cut_inventory.py", "cut-inventory.mjs", "buffer_resources.py", "offline-no-swap.mjs", "compact_load.py", "compact_storage.py", "input_storage.py", "coverage_census.py", "import_roads.py", "import_maneuvers.py", "maneuver_graph.py", "state_graph.py", "anchors.py", "native_support.py", "import_capacity.py")}
        identity = {"sourceManifestSha256": file_hash(source / "manifest.json"), "graphIdentity": manifest["graphIdentity"],
                    "sourceArtifact": manifest["sourceArtifact"], "profile": manifest["profile"], "scripts": scripts, "imageId": args.image_id,
                    "memoryLimit": "4g", "memorySwapLimit": "4g", "cpus": 2, "network": "none"}
        run_id = digest(identity)
        save_json(output / "run-identity.json", {"runId": run_id, **identity})
        (output / "recipe").mkdir()
        for name in scripts: atomic_write(output / "recipe" / name, (recipe / name).read_bytes())
        for name, expected in manifest["artifacts"].items():
            if artifact(source / name) != expected: raise ValueError(f"Frozen artifact changed: {name}")
        xml = inputs / "coverage-pilot/san-diego-tijuana-buffer-preflight-r2/car-roads.osm"
        if artifact(xml) != identity["sourceArtifact"]: raise ValueError("Source XML differs")
        monitor.checkpoint("validated")
        graph, model = load_graph(source / "graph.json")
        audit = load_json(source / "import-audit.json")
        if graph.identity != manifest["graphIdentity"]: raise ValueError("Graph differs")
        cuts = set(audit["cutExitNodes"])
        states = cut_states(graph, cuts)
        blocked = set(audit["blockedNodes"])
        records = {node: {"node": node, "blockedByModel": node in blocked, "stateCount": len(indices), "origins": {}} for node, indices in states.items()}
        for origin in summary["origins"]:
            path = source / "oracles" / f"{origin['origin']}.u64le"
            if path.stat().st_size != len(graph.states) * 8: raise ValueError("Oracle size differs")
            with path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as labels:
                for node, indices in states.items():
                    witness = minimum_witness(labels, indices)
                    witness["road"] = graph.base.roads[graph.states[witness["state"]]["road"]] if witness["state"] is not None else None
                    records[node]["origins"][origin["origin"]] = witness
            first = min((row["origins"][origin["origin"]]["costMs"] for row in records.values() if row["origins"][origin["origin"]]["costMs"] is not None), default=None)
            if first != origin["firstCutExitMs"]: raise ValueError("First cut differs from frozen qualification")
        monitor.checkpoint("oracleInventory")
        del graph
        links = boundary_links(xml, manifest["profile"]["bbox"], cuts, {row["id"] for row in audit["excludedWays"]})
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
            "properties": {"node": row["node"], "outsideSides": row["outsideSides"], "blockedByModel": row["blockedByModel"], "wayOnlyPlausibleOutward": row["wayOnlyPlausibleOutward"],
                           "costMsByOrigin": {key: value["costMs"] for key, value in row["origins"].items()}}} for row in records.values()]})
        monitor.checkpoint("complete")
        report = {"runId": run_id, **identity, "model": model, "auditedCutNodes": len(cuts), "cutStates": sum(map(len, states.values())),
                  "nodesWithoutBoundaryLinks": sum(not row["links"] for row in records.values()), "origins": origins,
                  "artifacts": {name: artifact(output / name) for name in ("cut-nodes.json", "cut-nodes.geojson")},
                  "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(), "workerWallMs": (time.perf_counter() - started) * 1000,
                  "publicApiCalls": 0, "coverageVerified": False, "routeEligibilityVerified": False,
                  "scope": "All audited cut endpoints and frozen full-field costs, including history states. Way-only departures do not verify node/turn/history legality beyond the extract. Side counts can overlap. No new route searches or complete contour claim."}
        save_json(output / "report.json", report)
        print(json.dumps({key: report[key] for key in ("auditedCutNodes", "cutStates", "nodesWithoutBoundaryLinks", "origins")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--output", default="/output")
    run(parser.parse_args())
