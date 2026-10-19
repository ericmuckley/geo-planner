"""Rebuild the v3 graph/audit from the unchanged v2 source, without rerunning oracles."""

import argparse
import fcntl
import gzip
import hashlib
from pathlib import Path
import resource
import tempfile
import time

from anchors import atomic_write, digest, file_hash, load_json, save_json
from barrier_policy import import_barriers
from barriers import source_examples
from cell_experiment import checked_artifact
from native_support import pack_graph


def run(args):
    started = time.perf_counter()
    output, previous, recipe = Path(args.output), Path(args.previous), Path(__file__).parent
    with (output / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = load_json(output / "manifest.json")
        if manifest["imageId"] != args.image_id: raise ValueError("Rebuild tools image changed")
        if manifest["previousManifestSha256"] != file_hash(previous / "manifest.json"): raise ValueError("Previous manifest changed")
        for name, expected in manifest["scripts"].items():
            if file_hash(recipe / name) != expected: raise ValueError("Rebuild source code changed")
        for name in manifest["artifacts"]: checked_artifact(output, manifest, name)
        old = load_json(previous / "manifest.json")
        checked_artifact(previous, old, "car-roads.osm")
        with tempfile.TemporaryDirectory(dir=output) as temporary:
            temporary = Path(temporary)
            before = time.perf_counter()
            graph, audit = import_barriers(previous / "car-roads.osm", temporary / "barrier-roads.osm", manifest["profile"]["bbox"], manifest["profile"]["model"])
            import_ms = (time.perf_counter() - before) * 1000
            source_examples(previous / "car-roads.osm", temporary / "barrier-source-samples.osm", graph, audit)
            data = {"graphIdentity": graph.identity, "baseIdentity": graph.base.identity, "model": manifest["profile"]["model"],
                    "roads": graph.base.roads, "baseTransitions": graph.base.adjacency, "states": graph.states,
                    "initialStates": graph.initial_states, "patterns": graph.patterns, "transitions": graph.adjacency}
            packed = pack_graph(graph.adjacency, graph.identity)
            actual = {"graph.json": digest(data), "import-audit.json": digest(audit), "graph.csr": hashlib.sha256(packed).hexdigest(),
                      "graph.csr.gz": hashlib.sha256(gzip.compress(packed, mtime=0)).hexdigest(),
                      "barrier-roads.osm": file_hash(temporary / "barrier-roads.osm"),
                      "barrier-source-samples.osm": file_hash(temporary / "barrier-source-samples.osm")}
        for name, value in actual.items():
            if value != manifest["artifacts"][name]["sha256"]: raise ValueError(f"Barrier rebuild differs: {name}")
        report = {"sourceRunId": manifest["runId"], "sourceManifestSha256": file_hash(output / "manifest.json"), "graphIdentity": graph.identity,
                  "identicalArtifactSha256": actual, "importMs": import_ms, "workerWallMs": (time.perf_counter() - started) * 1000,
                  "workerMaxRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "memoryLimit": "4g", "network": "none",
                  "workerSha256": file_hash(Path(__file__)), "publicApiCalls": 0,
                  "scope": "Reimport/repack and source transformation reproduced. Original oracle vectors/reports checked, not recomputed."}
        save_json(output / "rebuild-verification.json", report)
        atomic_write(output / "recipe/barriers_rebuild.py", Path(__file__).read_bytes())
        print(report, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/output")
    parser.add_argument("--previous", default="/previous")
    parser.add_argument("--image-id", required=True)
    run(parser.parse_args())
