"""Build and qualify a bounded real-road state graph, entirely offline."""

import argparse
from collections import Counter
import fcntl
from fractions import Fraction
import gzip
import json
import math
from pathlib import Path
import resource
import subprocess
import time

from anchors import atomic_write, digest, file_hash, load_json, save_json, select_anchors
from import_roads import DEFAULT_SPEEDS, distance_m, import_roads
from state_graph import bellman_ford, classify, dijkstra, landmark_index, pack_index, partial_source, unpack_index


def snap_source(graph, point, max_distance=100):
    scale = math.cos(math.radians(point[1]))
    best = None
    for state, road in enumerate(graph.roads):
        a, b = road["fromPoint"], road["toPoint"]
        dx, dy = (b[0] - a[0]) * scale, b[1] - a[1]
        denom = dx * dx + dy * dy
        fraction = max(0, min(1, (((point[0] - a[0]) * scale * dx + (point[1] - a[1]) * dy) / denom))) if denom else 0
        snapped = [a[0] + fraction * (b[0] - a[0]), a[1] + fraction * (b[1] - a[1])]
        distance = distance_m(point, snapped)
        candidate = (distance, road["id"], state, fraction, snapped)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    if best[0] > max_distance:
        raise ValueError("No supported road within source snap cutoff")
    _, _, chosen, fraction, snapped = best
    physical_id = graph.roads[chosen]["id"].rsplit(":", 1)[0]
    seeds = []
    for state, road in enumerate(graph.roads):
        if road["id"].rsplit(":", 1)[0] == physical_id:
            offset = fraction if state == chosen else 1 - fraction
            seeds.extend(partial_source(graph, state, Fraction(str(round(offset, 12)))))
    return seeds, {"input": point, "snapped": snapped, "distanceMeters": best[0], "physicalSegment": physical_id, "seeds": seeds}


def choose_states(graph, count, excluded_nodes=()):
    candidates, seen = [], set(excluded_nodes)
    for state, road in enumerate(graph.roads):
        if road["to"] in seen:
            continue
        seen.add(road["to"])
        candidates.append({"osmNodeId": state, "lon": road["toPoint"][0], "lat": road["toPoint"][1]})
    return [point["osmNodeId"] for point in select_anchors(candidates, count)]


def extract(directory, output, build, profile, image_id):
    source = directory / "region.osm.pbf"
    expected = build["artifacts"]["region.osm.pbf"]
    if source.stat().st_size != expected["bytes"] or file_hash(source) != expected["sha256"]:
        raise ValueError("Regional OSM input checksum mismatch")
    extraction = {"source": expected, "bbox": profile["bbox"], "imageId": image_id,
                  "strategy": "smart; types=restriction,restriction:motorcar,restriction:motor_vehicle,restriction:vehicle"}
    cache = output / "extract.json"
    osm = output / "roads.osm"
    if cache.exists():
        recorded = load_json(cache)
        if recorded["identity"] != extraction or file_hash(osm) != recorded["osmSha256"]:
            raise ValueError("Extract identity/checksum changed; use a new run name")
        return osm
    bounds = ",".join(map(str, profile["bbox"]))
    subprocess.run(["/usr/bin/time", "-v", "-o", str(output / "extract-resources.txt"), "osmium", "extract",
                    f"--bbox={bounds}", "--strategy=smart", "-S", extraction["strategy"].split("; ")[1],
                    str(source), "-o", str(output / "region.osm.pbf"), "--overwrite"], check=True)
    subprocess.run(["osmium", "tags-filter", str(output / "region.osm.pbf"), "w/highway", "r/type=restriction*",
                    "-f", "osm", "-o", str(osm), "--overwrite"], check=True)
    save_json(cache, {"identity": extraction, "osmSha256": file_hash(osm)})
    return osm


def run(args):
    started = time.perf_counter()
    directory, output, recipe = Path(args.data), Path(args.output), Path(__file__).parent
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        build = load_json(directory / "build-complete.json")
        if build["manifest"]["id"] != args.expected_graph:
            raise ValueError("Selected graph differs from source manifest")
        profile = load_json(recipe / "profiles/reference-downtown-v1.json")
        scripts = {name: file_hash(recipe / name) for name in ("reference.py", "state_graph.py", "import_roads.py", "anchors.py")}
        identity = {"sourceManifest": build["manifest"], "regionArtifact": build["artifacts"]["region.osm.pbf"],
                    "profile": profile, "defaultSpeedsKph": DEFAULT_SPEEDS, "scripts": scripts, "toolsImageId": args.image_id}
        run_id = digest(identity)
        manifest_path = output / "manifest.json"
        if manifest_path.exists() and load_json(manifest_path)["runId"] != run_id:
            raise ValueError("Reference model/code/source changed; preserve this run and use a new --run-name")
        osm = extract(directory, output, build, profile, args.image_id)
        preflight_ms = (time.perf_counter() - started) * 1000
        before = time.perf_counter()
        graph, audit = import_roads(osm, profile["bbox"], profile["model"])
        import_ms = (time.perf_counter() - before) * 1000
        save_json(output / "import-audit.json", audit)
        graph_data = {"graphIdentity": graph.identity, "roads": graph.roads, "transitions": graph.adjacency}
        save_json(output / "graph.json", graph_data)
        landmarks = choose_states(graph, profile["landmarkCount"])
        holdouts = choose_states(graph, profile["holdoutCount"], [graph.roads[s]["to"] for s in landmarks])
        before = time.perf_counter()
        index = landmark_index(graph, landmarks)
        index_ms = (time.perf_counter() - before) * 1000
        before = time.perf_counter()
        packed = pack_index(graph, index)
        atomic_write(output / "landmarks.u32le", packed)
        atomic_write(output / "landmarks.u32le.gz", gzip.compress(packed, mtime=0))
        pack_ms = (time.perf_counter() - before) * 1000
        before = time.perf_counter()
        saved = (output / "landmarks.u32le").read_bytes()
        if saved != packed or gzip.decompress((output / "landmarks.u32le.gz").read_bytes()) != saved:
            raise ValueError("Landmark export roundtrip mismatch")
        index = unpack_index(graph, landmarks, saved, graph.identity, complete=True)
        read_decode_ms = (time.perf_counter() - before) * 1000
        seeds, snap = snap_source(graph, [profile["origin"]["lon"], profile["origin"]["lat"]])
        origins = [("san-diego", seeds)] + [(f"holdout-{i}", partial_source(graph, state, Fraction(1, 3))) for i, state in enumerate(holdouts)]
        cut_nodes = set(audit["cutExitNodes"])
        cut_states = {i for i, road in enumerate(graph.roads) if road["to"] in cut_nodes}
        results, oracle_checks = [], []
        for name, source in origins:
            before = time.perf_counter()
            exact = dijkstra(graph.adjacency, source)
            dijkstra_ms = (time.perf_counter() - before) * 1000
            before = time.perf_counter()
            independent = bellman_ford(graph.adjacency, source)
            oracle_ms = (time.perf_counter() - before) * 1000
            if exact.labels != independent:
                raise ValueError(f"Dijkstra/Bellman-Ford disagreement: {name}")
            oracle_checks.append({"origin": name, "seeds": source, "labelsCompared": len(exact.labels),
                                  "dijkstraGraphMs": dijkstra_ms, "bellmanFordGraphMs": oracle_ms})
            for budget in profile["budgetsMs"]:
                before = time.perf_counter()
                bounded = dijkstra(graph.adjacency, source, budget)
                bounded_ms = (time.perf_counter() - before) * 1000
                before = time.perf_counter()
                decisions = classify(graph, index, source, budget)
                classify_ms = (time.perf_counter() - before) * 1000
                counts = Counter(decision for decision, _, _ in decisions)
                for target, (decision, low, high) in enumerate(decisions):
                    actual = independent[target]
                    if not low <= actual <= high or (decision == "reachable" and actual > budget) or (decision == "unreachable" and actual <= budget):
                        raise ValueError(f"Unsafe landmark certificate: {name}, state {target}")
                    if (bounded.labels[target] <= budget) != (actual <= budget):
                        raise ValueError("Bounded search membership mismatch")
                boundary_time = min((exact.labels[s] for s in cut_states), default=math.inf)
                results.append({"origin": name, "budgetMs": budget, "classification": dict(counts),
                                "reachableStates": bounded.settled_states, "scannedArcs": bounded.scanned_arcs,
                                "boundedDijkstraGraphMs": bounded_ms, "classificationMs": classify_ms,
                                "boundaryReachedWithinBudget": boundary_time <= budget,
                                "firstCutExitMs": boundary_time if math.isfinite(boundary_time) else None,
                                "falsePositiveStates": 0, "falseNegativeStates": 0})
            print(f"Qualified {name}: {len(exact.labels)} labels and {len(profile['budgetsMs'])} budgets", flush=True)
        summary = {"runId": run_id, "graphIdentity": graph.identity, "profile": profile,
                   "states": len(graph.roads), "transitions": sum(map(len, graph.adjacency)),
                   "landmarkStates": landmarks, "holdoutStates": holdouts,
                   "blockedTurnTransitions": len(graph.blocked_turns), "appliedRestrictionCount": len(audit["appliedRestrictions"]),
                   "unsupportedRestrictionCount": len(audit["unsupportedRestrictions"]), "excludedWayCounts": audit["excludedWayCounts"],
                   "snap": snap, "preflightAndExtractionMs": preflight_ms, "importMs": import_ms, "landmarkBuildGraphMs": index_ms,
                   "sourceRestrictionSamples": [{**turn, "fromRoad": graph.roads[turn["fromState"]], "toRoad": graph.roads[turn["toState"]]}
                                                for turn in graph.blocked_turns[:5]],
                   "fourthAvenueDirectedSegments": audit["onewayFourthAvenue"],
                   "fourthAvenueSourceTags": audit["onewayFourthAvenueSourceTags"],
                   "landmarkBytes": len(packed), "landmarkGzipBytes": (output / "landmarks.u32le.gz").stat().st_size,
                   "landmarkPackWriteMs": pack_ms, "landmarkReadDecodeMs": read_decode_ms, "queriesUseReloadedFields": True,
                   "oracleChecks": oracle_checks, "queries": results, "publicApiCalls": 0, "network": "none",
                   "coverageVerified": False, "workerMaxRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   "workerWallMs": (time.perf_counter() - started) * 1000,
                   "limitations": ["Exact only on the imported simplified integer-ms graph, not real-world driving or Valhalla's model.",
                                   "Unsupported restrictions remove all member ways; conditional/access exclusions reduce coverage.",
                                   "Source/target road endpoints, not filled geographic contours; interior destinations remain unimplemented.",
                                   "Classification scans every road state and reads complete landmark fields; no proven query speedup or demand loading.",
                                   "Cut exits flag uncertainty; absence of a flag is not an independent coverage guarantee."]}
        save_json(output / "summary.json", summary)
        artifact_names = ("graph.json", "import-audit.json", "landmarks.u32le", "landmarks.u32le.gz", "summary.json")
        save_json(manifest_path, {"runId": run_id, **identity, "graphIdentity": graph.identity,
                                 "fieldFormat": "first all forward then all reverse landmark rows, uint32 little-endian milliseconds; 4294967295 = unreachable in complete imported graph",
                                 "completeLandmarkFields": True,
                                 "artifacts": {name: {"bytes": (output / name).stat().st_size, "sha256": file_hash(output / name)} for name in artifact_names}})
        snapshots = output / "recipe"
        snapshots.mkdir(exist_ok=True)
        for name in scripts:
            atomic_write(snapshots / name, (recipe / name).read_bytes())
        print(json.dumps({k: summary[k] for k in ("states", "transitions", "landmarkBytes", "landmarkGzipBytes", "appliedRestrictionCount", "unsupportedRestrictionCount", "workerWallMs", "publicApiCalls")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="/data")
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--expected-graph", required=True)
    run(parser.parse_args())
