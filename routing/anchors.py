"""Quota-free coordinate-matrix pilot. Not an exact graph-state distance oracle."""

import argparse
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import struct
import subprocess
import time
import xml.etree.ElementTree as ET


MODEL = {
    "costing": "auto",
    "costing_options": {"auto": {"speed_types": ["freeflow", "constrained"]}},
    "units": "kilometers",
    "verbose": True,
}
UNKNOWN = 0xFFFFFFFF


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def atomic_write(path, content):
    temporary = path.with_suffix(path.suffix + ".part")
    with temporary.open("wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def save_json(path, value):
    atomic_write(path, encoded(value))


def load_json(path):
    return json.loads(path.read_text())


def verify_artifacts(directory, build):
    # Force archive reads later so unverified loose tiles cannot affect the run.
    for name in ("region.osm.pbf", "tiles.tar", "valhalla.json", "admin.sqlite"):
        path = directory / name
        expected = build["artifacts"][name]
        if path.stat().st_size != expected["bytes"] or file_hash(path) != expected["sha256"]:
            raise ValueError(f"Input checksum mismatch: {name}")


def read_candidates(directory, bounds):
    completed = subprocess.run(
        ["osmium", "tags-filter", "-R", str(directory / "region.osm.pbf"),
         "n/highway=motorway_junction", "-f", "osm"],
        check=True, capture_output=True,
    )
    candidates = []
    for node in ET.fromstring(completed.stdout).findall("node"):
        lat, lon = float(node.attrib["lat"]), float(node.attrib["lon"])
        if bounds and not (bounds[0] <= lon <= bounds[2] and bounds[1] <= lat <= bounds[3]):
            continue
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in node.findall("tag")}
        candidates.append({
            "osmNodeId": int(node.attrib["id"]), "lat": lat, "lon": lon,
            "ref": tags.get("ref"), "name": tags.get("name"),
        })
    return sorted(candidates, key=lambda point: point["osmNodeId"])


def select_anchors(candidates, count):
    if len(candidates) < count:
        raise ValueError(f"Only {len(candidates)} motorway-junction candidates; requested {count}")
    # Deterministic geographic spread only; driving-time coverage is not established.
    longitude_scale = math.cos(math.radians(sum(p["lat"] for p in candidates) / len(candidates)))
    distances = [math.inf] * len(candidates)
    selected = []
    index = 0
    for _ in range(count):
        anchor = candidates[index]
        selected.append(anchor)
        for i, point in enumerate(candidates):
            distance = (point["lat"] - anchor["lat"]) ** 2 + (
                (point["lon"] - anchor["lon"]) * longitude_scale
            ) ** 2
            distances[i] = min(distances[i], distance)
        distances[index] = -1
        index = max(range(len(candidates)), key=lambda i: distances[i])
    return selected


def validate_response(response, count):
    if response.get("units") != "kilometers" or not response.get("algorithm"):
        raise ValueError("Missing matrix units/algorithm")
    rows = response.get("sources_to_targets", [])
    if len(rows) != 1 or len(rows[0]) != count:
        raise ValueError("Incomplete matrix row")
    if len(response.get("sources", [])) != 1 or len(response.get("targets", [])) != count:
        raise ValueError("Missing correlated source/target locations")
    for index, pair in enumerate(rows[0]):
        if pair.get("from_index") != 0 or pair.get("to_index") != index:
            raise ValueError("Matrix indices out of order")
        for key in ("time", "distance", "cost"):
            if key not in pair:
                raise ValueError(f"Missing matrix {key}")
            value = pair.get(key)
            if value is not None and (
                not isinstance(value, (int, float)) or isinstance(value, bool)
                or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"Invalid matrix {key}")
        duration = pair.get("time")
        if duration is not None and (duration != int(duration) or duration >= UNKNOWN):
            raise ValueError("Cannot losslessly pack matrix seconds as uint32")
    return rows[0]


def save_row(path, data):
    save_json(path, {"sha256": digest(data), "data": data})


def read_row(path, dataset_id, index, count):
    envelope = load_json(path)
    data = envelope["data"]
    if envelope["sha256"] != digest(data):
        raise ValueError(f"Checkpoint checksum mismatch: {path.name}")
    if data["datasetId"] != dataset_id or data["rowIndex"] != index:
        raise ValueError(f"Checkpoint identity mismatch: {path.name}")
    validate_response(data["response"], count)
    return data


def prepare(directory, output, count, image_id, expected_graph, algorithm):
    build = load_json(directory / "build-complete.json")
    manifest = build["manifest"]
    if manifest["id"] != expected_graph:
        raise ValueError("Selected manifest differs from completed graph")
    verify_artifacts(directory, build)
    version = subprocess.check_output(["valhalla_service", "--version"], text=True).strip()
    if version != manifest["engineVersion"]:
        raise ValueError("Engine revision differs from completed graph")
    candidates = read_candidates(directory, manifest.get("bbox"))
    anchors = select_anchors(candidates, count)
    config = load_json(directory / "valhalla.json")
    config["mjolnir"]["tile_dir"] = "/nonexistent"
    config["mjolnir"]["tile_extract"] = str(directory / "tiles.tar")
    config["mjolnir"].pop("tile_url", None)
    config["thor"]["source_to_target_algorithm"] = algorithm
    # Pilot capacity only. No time horizon or completeness claim follows from this.
    config["service_limits"]["auto"]["max_matrix_distance"] = 2_000_000
    config["service_limits"]["auto"]["max_matrix_location_pairs"] = 1000
    identity = {
        "schemaVersion": 1, "graph": manifest, "artifacts": build["artifacts"],
        "engineVersion": version, "toolsImageId": image_id,
        "workerSha256": file_hash(Path(__file__)), "runtimeConfig": config,
        "requestModel": MODEL, "anchors": anchors,
        "selection": "OSM motorway_junction; lowest node ID then geographic farthest-point v1",
        "candidateCount": len(candidates),
        "semantics": "coordinate-to-coordinate preferred-route elapsed seconds; not exact composable state costs",
        "nullMeaning": "engine returned no connection; cause unknown (not certified unreachable)",
        "coverageVerified": False, "timeHorizonSeconds": None,
        "borderPolicy": "engine default access/crossing costs; Mexico permitted; no live queues",
        "network": "Docker network none; no remote provider, downloads, or fallback",
    }
    dataset_id = digest(identity)
    record = {"datasetId": dataset_id, **identity}
    path = output / "manifest.json"
    if path.exists() and load_json(path) != record:
        raise ValueError("Dataset identity changed. Preserve this run and use a new --run-name.")
    if not path.exists():
        atomic_write(output / "worker.py", Path(__file__).read_bytes())
        save_json(path, record)
        save_json(output / "anchors.geojson", {
            "type": "FeatureCollection", "features": [{
                "type": "Feature", "properties": {"index": i, **p},
                "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
            } for i, p in enumerate(anchors)],
        })
    return record, config


def run(args):
    started = time.perf_counter()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    # Prevent concurrent writers without leaving a stale lock after interruption.
    with (output / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        record, config = prepare(Path(args.data), output, args.count, args.image_id, args.expected_graph, args.algorithm)
        dataset_id = record["datasetId"]
        rows_dir = output / "rows"
        rows_dir.mkdir(exist_ok=True)
        existing = {}
        # Check every saved row before doing any new computation.
        for index in range(args.count):
            path = rows_dir / f"{index:05}.json"
            if path.exists():
                existing[index] = read_row(path, dataset_id, index, args.count)
        preflight_ms = (time.perf_counter() - started) * 1000
        print(f"Verified graph/engine/cache: {len(existing)}/{args.count} rows; public API calls: 0", flush=True)
        locations = [{"lat": p["lat"], "lon": p["lon"]} for p in record["anchors"]]
        actor = None
        new_rows = 0
        for index in range(args.count):
            if index in existing:
                continue
            if args.max_new_rows is not None and new_rows >= args.max_new_rows:
                break
            if actor is None:
                from valhalla import Actor
                actor = Actor(config)
                status = json.loads(actor.status("{}"))
                if status["version"] != record["engineVersion"]:
                    raise ValueError("Actor version mismatch")
            request = {**MODEL, "sources": [locations[index]], "targets": locations}
            before = time.perf_counter()
            raw = actor.matrix(json.dumps(request))
            actor_ms = (time.perf_counter() - before) * 1000
            before = time.perf_counter()
            response = json.loads(raw)
            validate_response(response, args.count)
            if response["algorithm"] != args.algorithm:
                raise ValueError("Engine did not use the selected matrix algorithm")
            data = {
                "datasetId": dataset_id, "rowIndex": index,
                "sourceOsmNodeId": record["anchors"][index]["osmNodeId"],
                "actorCallMs": actor_ms,
                "decodeValidateMs": (time.perf_counter() - before) * 1000,
                "responseBytes": len(raw.encode()), "response": response,
            }
            save_row(rows_dir / f"{index:05}.json", data)
            existing[index] = data
            new_rows += 1
            if new_rows % 16 == 0 or new_rows == 1:
                print(f"Checkpointed {len(existing)}/{args.count} rows", flush=True)
        complete = len(existing) == args.count
        row_files = [rows_dir / f"{index:05}.json" for index in existing]
        summary = {
            "datasetId": dataset_id, "anchorCount": args.count,
            "completedRows": len(existing), "newRows": new_rows,
            "reusedRows": len(existing) - new_rows, "complete": complete,
            "publicApiCalls": 0, "network": "none", "preflightMs": preflight_ms,
            "workerWallMs": (time.perf_counter() - started) * 1000,
            "rowJsonBytes": sum(path.stat().st_size for path in row_files),
            "timingDefinition": "actorCallMs includes snapping, search, matrix construction and JSON serialization; not isolated graph search",
        }
        if complete:
            pairs = [pair for i in range(args.count)
                     for pair in existing[i]["response"]["sources_to_targets"][0]]
            packed = b"".join(struct.pack("<I", UNKNOWN if p["time"] is None else p["time"]) for p in pairs)
            atomic_write(output / "times.u32le", packed)
            atomic_write(output / "times.u32le.gz", gzip.compress(packed, mtime=0))
            durations = [p["time"] for p in pairs if p["time"] is not None]
            calls = sorted(row["actorCallMs"] for row in existing.values())
            summary.update({
                "pairCount": len(pairs), "unknownPairs": len(pairs) - len(durations),
                "maxReturnedSeconds": max(durations, default=None),
                "warningRows": [i for i, r in existing.items() if r["response"].get("warnings")],
                "actorCallMs": {"firstRow": existing[0]["actorCallMs"],
                                "p50": calls[math.ceil(len(calls) * 0.5) - 1],
                                "p95": calls[math.ceil(len(calls) * 0.95) - 1], "sum": sum(calls)},
                "packedFormat": "row-major uint32 little-endian elapsed seconds; 4294967295 = unknown",
                "packedBytes": len(packed), "packedGzipBytes": (output / "times.u32le.gz").stat().st_size,
                "packedSha256": hashlib.sha256(packed).hexdigest(),
            })
        summary["workerMaxRssKiB"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        save_json(output / "summary.json", summary)
        print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="/data")
    parser.add_argument("--output", default="/output")
    parser.add_argument("--count", type=int, default=32)
    parser.add_argument("--algorithm", choices=("timedistancematrix", "costmatrix"), default="timedistancematrix")
    parser.add_argument("--max-new-rows", type=int)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--expected-graph", required=True)
    options = parser.parse_args()
    if not 2 <= options.count <= 1000 or (options.max_new_rows is not None and options.max_new_rows < 0):
        parser.error("count must be 2–1000; max-new-rows must be nonnegative")
    run(options)
