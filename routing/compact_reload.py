"""Independently reload the completed graph exports under a smaller memory cap."""

import argparse
import fcntl
from pathlib import Path
import struct
import time

from anchors import atomic_write, file_hash
from compact_load import load_graph
from compact_storage import save_json, write_csr
from import_capacity import resources


def run(args):
    started = time.perf_counter()
    output, source, recipe = Path(args.output), Path("/source"), Path(__file__).parent
    with (output / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "identity.json").exists(): raise ValueError("Preserve attempts and use a fresh run name")
        identity = {"sourceArtifacts": {name: {"bytes": (source / name).stat().st_size, "sha256": file_hash(source / name)} for name in ("graph.json", "graph.csr")},
                    "scripts": {name: file_hash(recipe / name) for name in ("compact_reload.py", "compact_load.py", "compact_storage.py")},
                    "imageId": args.image_id, "memoryLimit": "1g", "cpus": 2, "network": "none"}
        save_json(output / "identity.json", identity)
        graph, model = load_graph(source / "graph.json")
        reload_ms = (time.perf_counter() - started) * 1000
        write_csr(output / "graph.csr", graph.adjacency, graph.identity)
        if file_hash(output / "graph.csr") != identity["sourceArtifacts"]["graph.csr"]["sha256"]: raise ValueError("Reloaded CSR differs")
        with (source / "graph.csr").open("rb") as stream:
            magic, states, arcs, graph_id = struct.unpack("<8sII32s", stream.read(48))
        if magic != b"GPCSR001" or states != len(graph.states) or arcs != len(graph.adjacency.targets) or graph_id.hex() != graph.identity:
            raise ValueError("Reloaded graph/header differs")
        report = {**identity, "graphIdentity": graph.identity, "model": model, "roads": len(graph.base.roads), "states": states, "transitions": arcs,
                  "reloadAndIdentityMs": reload_ms, "workerWallMs": (time.perf_counter() - started) * 1000, "resources": resources(), "publicApiCalls": 0,
                  "scope": "Full canonical JSON reloaded into compact views and rehashed; CSR bytes reproduced. No routing, cold-cache, cloud or complete-coverage claim."}
        save_json(output / "report.json", report)
        (output / "recipe").mkdir()
        for name in identity["scripts"]: atomic_write(output / "recipe" / name, (recipe / name).read_bytes())
        print(report, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--output", default="/output")
    run(parser.parse_args())
