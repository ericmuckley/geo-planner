"""Versioned frozen-graph parity with per-file checksum cache advice and profiling."""

import argparse
import fcntl
import gzip
import json
from pathlib import Path
import time

from anchors import atomic_write, digest, load_json
from barriers import source_examples
from compact import CASES
from paged_io import advice_report, artifact, file_hash
from buffer_resources import Monitor
from compact_storage import save_json, write_csr
from crossing_audit import barrier_examples, source_uncertainties
from import_capacity import graph_data
from input_import import import_barriers, import_maneuvers


def checked_manifest(directory):
    manifest = load_json(directory / "manifest.json")
    for name, expected in manifest["artifacts"].items():
        if artifact(directory / name) != expected: raise ValueError(f"Frozen artifact changed: {directory / name}")
    for name, expected in manifest["scripts"].items():
        if file_hash(directory / "recipe" / name) != expected or file_hash(Path(__file__).parent / name) != expected:
            raise ValueError(f"Frozen recipe changed: {name}")
    return manifest


def run(args):
    started = time.perf_counter()
    inputs, output, recipe = Path("/inputs"), Path(args.output), Path(__file__).parent
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "run-identity.json").exists(): raise ValueError("Preserve existing attempts; use a fresh series")
        previous = inputs / "compact-pilot" / f"compact-v1-{args.case}"
        old = checked_manifest(previous)
        if old["imageId"] != args.image_id: raise ValueError("Tools image differs")
        source = inputs / CASES[args.case][1]
        if artifact(source) != old["sourceArtifact"]: raise ValueError("Frozen source changed")
        names = (*old["scripts"], "input_storage.py", "input_import.py", "input_capacity.py", "input-storage.mjs", "offline-no-swap.mjs", "settings.mjs", "paged_import.py", "paged-import.mjs", "paged_io.py", "buffer_resources.py")
        scripts = {name: file_hash(recipe / name) for name in names}
        parity = {}
        if args.case == "buffer-v3":
            for case in CASES:
                if case == "buffer-v3": continue
                directory = inputs / "input-pilot" / f"{args.series}-{case}"
                proof = checked_manifest(directory)
                # checked_manifest verifies the unchanged semantic source/proofs; this version changes checksum I/O only.
                report = load_json(directory / "report.json")
                if not report["identicalArtifactSha256"]: raise ValueError("Missing parity proof")
                parity[case] = file_hash(directory / "report.json")
        identity = {"case": args.case, "series": args.series, "profile": old["profile"], "sourceArtifact": artifact(source),
                    "previousManifestSha256": file_hash(previous / "manifest.json"), "imageId": args.image_id, "scripts": scripts,
                    "parityReports": parity, "memoryLimit": "4g", "memorySwapLimit": "4g", "swapPolicy": "disabled",
                    "cpus": 2, "network": "none"}
        run_id = digest(identity)
        save_json(output / "run-identity.json", {"runId": run_id, **identity})
        (output / "recipe").mkdir()
        for name in scripts: atomic_write(output / "recipe" / name, (recipe / name).read_bytes())
        checkpoints = {}

        def observe(stage):
            monitor.checkpoint(stage)
            checkpoints[stage] = monitor.checkpoints[stage]

        observe("preflight")
        measurements = {}
        profile = old["profile"]
        before = time.perf_counter()
        v3 = args.case.endswith("v3")
        if v3: graph, audit = import_barriers(source, output / "barrier-roads.osm", profile["bbox"], profile["model"], measurements, observe)
        else: graph, audit = import_maneuvers(source, profile["bbox"], profile["model"], measurements, observe)
        import_ms = (time.perf_counter() - before) * 1000
        if v3: source_examples(source, output / "barrier-source-samples.osm", graph, audit)
        if args.case in {"wide-v3", "buffer-v3"}:
            uncertain = source_uncertainties(source, output / "uncertain-crossings-source.osm")
            by_way = {row["id"]: [] for row in uncertain}
            for road in graph.base.roads:
                if road["way"] in by_way: by_way[road["way"]].append(road["id"])
            for row in uncertain: row["retainedDirectedRoadIds"] = by_way[row["id"]]
            audit["sourceCrossingUncertainties"] = uncertain
            # The frozen runner also computes these examples; its audit is unchanged.
            barrier_examples(graph, audit, {1228835396, 8181606580, 9357332258})
        observe("sourceEvidence")
        save_json(output / "graph.json", graph_data(graph, profile["model"]))
        save_json(output / "import-audit.json", audit)
        write_csr(output / "graph.csr", graph.adjacency, graph.identity)
        atomic_write(output / "graph.csr.gz", gzip.compress((output / "graph.csr").read_bytes(), mtime=0))
        observe("exported")
        names = ["graph.json", "import-audit.json", "graph.csr", "graph.csr.gz"]
        if v3: names += ["barrier-roads.osm", "barrier-source-samples.osm"]
        if args.case in {"wide-v3", "buffer-v3"}: names.append("uncertain-crossings-source.osm")
        artifacts = {name: artifact(output / name) for name in names}
        if graph.identity != old["graphIdentity"]: raise ValueError("Graph identity differs")
        for name, actual in artifacts.items():
            if actual != old["artifacts"][name]: raise ValueError(f"Compact-input parity differs: {name}")
        reused = {"manifestSha256": identity["previousManifestSha256"], "graphIdentity": graph.identity,
                  "artifacts": {name: value for name, value in old["artifacts"].items() if name == "summary.json" or name.startswith("oracles/")},
                  "scope": "Checksum-verified existing qualification on the identical graph; no new route/search measurements"}
        if args.case == "buffer-v3":
            native = load_json(previous / "native-verification.json")
            if native["sourceManifestSha256"] != identity["previousManifestSha256"]: raise ValueError("Native evidence manifest differs")
            reused["nativeVerification"] = artifact(previous / "native-verification.json")
        observe("complete")
        report = {"runId": run_id, "case": args.case, "graphIdentity": graph.identity, "roads": len(graph.base.roads), "states": len(graph.states),
                  "transitions": len(graph.adjacency.targets), "viaWayRestrictions": len(graph.patterns), "importMs": import_ms,
                  "importStages": measurements, "workerWallMs": (time.perf_counter() - started) * 1000, "resourceCheckpoints": checkpoints,
                  "artifacts": artifacts, "identicalArtifactSha256": {name: value["sha256"] for name, value in artifacts.items()},
                  "reusedQualification": reused, "publicApiCalls": 0, "coverageVerified": False,
                  "sampling": monitor.summary(), "cacheAdvice": advice_report(),
                  "scope": "Exact frozen graph/audit/source/packed parity with per-file checksum cache advice; unchanged import/cost/access/storage semantics. No new route searches or coverage."}
        save_json(output / "report.json", report)
        save_json(output / "manifest.json", {"runId": run_id, **identity, "graphIdentity": graph.identity,
                                            "artifacts": {**artifacts, "report.json": artifact(output / "report.json")}})
        print(json.dumps({key: report[key] for key in ("case", "states", "transitions", "importMs", "workerWallMs")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--series", default="input-v1")
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    run(parser.parse_args())
