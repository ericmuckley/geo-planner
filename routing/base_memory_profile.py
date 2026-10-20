"""Bounded owner census of one frozen final base build, not a graph release."""

import argparse
from array import array
import fcntl
from pathlib import Path
import re
import sys
import time

from anchors import load_json
from buffer_resources import Monitor
from cache_input import read_osm
from compact_storage import save_json
from increment import check_scripts, snapshot
from outgoing_input import build_base
from range_hash import artifact, file_hash
from region_release import check_resources


CURRENT = "compact-pilot/two-hour-region-v2"


def allocation(value):
    result = {"type": type(value).__name__, "containerBytes": sys.getsizeof(value)}
    if isinstance(value, (array, bytearray)):
        result.update(records=len(value), payloadBytes=len(value) * (value.itemsize if isinstance(value, array) else 1))
    elif isinstance(value, dict):
        result.update(records=len(value), keyReferenceShallowBytes=sum(sys.getsizeof(key) for key in value),
                      valueReferenceShallowBytes=sum(sys.getsizeof(item) for item in value.values()),
                      nonSmallIntegerValueReferenceBytes=sum(sys.getsizeof(item) for item in value.values()
                          if type(item) is int and not -5 <= item <= 256))
    elif isinstance(value, list):
        result["records"] = len(value)
    elif hasattr(value, "__dict__"):
        result["fields"] = {key: allocation(item) for key, item in vars(value).items()
                            if isinstance(item, (array, bytearray, dict, list))}
    return result


def owners(frame):
    result = {}
    while frame is not None:
        if frame.f_globals.get("__name__") in {"outgoing_index", "outgoing_input"}:
            for name in ("nodes", "ways", "relations", "roads", "outgoing", "adjacency", "blocked_turns", "rules"):
                if name in frame.f_locals and name not in result:
                    result[name] = allocation(frame.f_locals[name])
        frame = frame.f_back
    return result


def run(args):
    output, directory = Path(args.output), Path("/inputs") / CURRENT
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started = time.perf_counter()
        manifest = load_json(directory / "manifest.json")
        if args.image_id != manifest["imageId"]: raise ValueError("Pinned image differs")
        check_scripts(directory, manifest["scripts"])
        for name in ("barrier-roads.osm", "import-audit.json", "graph.json"):
            if artifact(directory / name) != manifest["artifacts"][name]: raise ValueError(f"Reference differs: {name}")
        with (directory / "graph.json").open("rb") as stream:
            expected = re.match(rb'\{"baseIdentity":"([0-9a-f]{64})"', stream.read(100))[1].decode()
        audit = load_json(directory / "import-audit.json")
        omitted = {row["id"] for row in audit["viaWayRestrictions"]}
        scripts = {**manifest["scripts"], **{name: file_hash(Path(__file__).parent / name)
                   for name in ("base_memory_profile.py", "base-memory-profile.mjs")}}
        identity = {"scripts": scripts, "imageId": args.image_id, "sourceManifestSha256": file_hash(directory / "manifest.json"),
                    "sourceArtifact": manifest["artifacts"]["barrier-roads.osm"], "omittedRelations": sorted(omitted),
                    "expectedBaseIdentity": expected, "profile": manifest["profile"],
                    "memoryLimit": "4g", "memorySwapLimit": "4g", "cpus": 2, "network": "none",
                    "scope": "Diagnostic final base only, using the accepted via-way omission set. Does not include original road-key retention, six fallback builds, barrier preparation, maneuver graph, exports or qualification. Never substitute this peak for a complete-phase admission measurement."}
        run_id = snapshot(output, identity, "identity.json")
        monitor.checkpoint("validated")
        nodes, ways, relations = read_osm(directory / "barrier-roads.osm")
        monitor.checkpoint("parsed")
        records = {"parsed": {name: allocation(value) for name, value in (("nodes", nodes), ("ways", ways), ("relations", relations))}}
        timings = {}
        def observe(stage):
            monitor.checkpoint(stage)
            if stage in {"outgoingCounted", "rulesReady", "arcsBuilt", "indexesReleased"}:
                before = time.perf_counter()
                records[stage] = owners(sys._getframe().f_back)
                timings[stage] = (time.perf_counter() - before) * 1000
                save_json(output / "owners.json", records)
        graph, base_audit = build_base(nodes, ways, relations, manifest["profile"]["bbox"], manifest["profile"]["model"], omitted, observe=observe)
        if graph.identity != expected or len(graph.roads) != load_json(directory / "build-report.json")["roads"]:
            raise ValueError("Profiled final base differs from the qualified payload")
        monitor.checkpoint("verified")
        report = {"runId": run_id, **identity, "baseIdentity": graph.identity, "basePayloadIdentical": True,
                  "roads": len(graph.roads), "transitions": len(graph.adjacency.targets), "owners": records,
                  "ownerCensusWallMs": timings, "resources": check_resources({"resourceCheckpoints": monitor.checkpoints}),
                  "resourceCheckpoints": monitor.checkpoints, "sampling": monitor.summary(),
                  "workerWallMs": (time.perf_counter() - started) * 1000, "publicApiCalls": 0, "newGraphReleased": False,
                  "coverageVerified": False, "accountingScope": "Array/container allocated sizes are sys.getsizeof; dictionary key/value footprints count references and may count shared objects repeatedly. Lists count their reference storage only; referenced strings/ET trees are not deep-counted. This is an owner census, not exhaustive unique allocation tracking or RSS decomposition. Introspection time/memory is included in this diagnostic and not in earlier complete-phase measurements."}
        save_json(output / "report.json", report)
        print({key: report[key] for key in ("baseIdentity", "roads", "transitions", "resources", "workerWallMs")}, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    run(parser.parse_args())
