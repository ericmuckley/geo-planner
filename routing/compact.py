"""Prove frozen graph byte parity, then qualify the prepared larger buffer under 4 GiB."""

import argparse
import fcntl
import gzip
import json
from pathlib import Path
import time

from anchors import atomic_write, digest, file_hash, load_json
from barriers import qualify, source_examples
from compact_import import import_barriers, import_maneuvers
from compact_storage import save_json, write_csr
from crossing_audit import barrier_examples, source_uncertainties
from import_capacity import graph_data, resources
from wide import diagnose_routes


CASES = {
    "downtown-v2": ("model-pilot/downtown-maneuvers-v2", "reference-pilot/downtown-static-v1/roads.osm"),
    "corridor-v2": ("regional-pilot/san-diego-tijuana-corridor-v2", "regional-pilot/san-diego-tijuana-corridor-v2/car-roads.osm"),
    "corridor-v3": ("barrier-pilot/san-diego-tijuana-barriers-v3", "regional-pilot/san-diego-tijuana-corridor-v2/car-roads.osm"),
    "wide-v3": ("barrier-pilot/san-diego-tijuana-wide-v3", "regional-pilot/san-diego-tijuana-v2/car-roads.osm"),
    "buffer-v3": ("coverage-pilot/san-diego-tijuana-buffer-preflight-r2", "coverage-pilot/san-diego-tijuana-buffer-preflight-r2/car-roads.osm"),
}


def artifact(path): return {"bytes": path.stat().st_size, "sha256": file_hash(path)}


def run(args):
    started = time.perf_counter()
    inputs, output, recipe = Path("/inputs"), Path(args.output), Path(__file__).parent
    with (output / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "run-identity.json").exists(): raise ValueError("Preserve existing attempts; use a fresh run name")
        buffer = args.case == "buffer-v3"
        previous, source = (inputs / item for item in CASES[args.case])
        previous_name = "report.json" if buffer else "manifest.json"
        old = load_json(previous / previous_name)
        image = load_json(previous / "run-identity.json")["imageId"] if buffer else old["imageId"]
        if image != args.image_id: raise ValueError("Tools image differs")
        # Check complete frozen evidence before using it as an equality oracle.
        for name, expected in old["artifacts"].items():
            if artifact(previous / name) != expected: raise ValueError(f"Prior artifact changed: {name}")
        if not buffer:
            expected = old.get("sourceXmlSha256", old.get("sourceArtifact", old["artifacts"].get("car-roads.osm")))
            if isinstance(expected, dict): expected = expected["sha256"]
            if file_hash(source) != expected: raise ValueError("Frozen source changed")
        else:
            if artifact(source) != old["artifacts"]["car-roads.osm"]: raise ValueError("Prepared buffer changed")
        scripts = {name: file_hash(recipe / name) for name in ("compact.py", "compact_import.py", "compact_storage.py", "stream_import.py", "import_roads.py",
                   "import_maneuvers.py", "state_graph.py", "maneuver_graph.py", "anchors.py", "barrier_policy.py", "barriers.py", "wide.py", "crossing_audit.py",
                   "import_capacity.py", "native_support.py", "regional_support.py", "reference.py", "cell_experiment.py", "cell_index.py")}
        parity = {}
        if buffer:
            for case in CASES:
                if case == "buffer-v3": continue
                directory = inputs / "compact-pilot" / f"compact-v1-{case}"
                proof = load_json(directory / "report.json")
                identity = load_json(directory / "run-identity.json")
                if identity["scripts"] != scripts or not proof["identicalArtifactSha256"]: raise ValueError("Complete same-code parity cases first")
                for name, expected in proof["artifacts"].items():
                    if artifact(directory / name) != expected: raise ValueError("Parity artifact changed")
                parity[case] = file_hash(directory / "report.json")
            reference = load_json(inputs / "barrier-pilot/san-diego-tijuana-wide-v3/manifest.json")
            profile = {**reference["profile"], "id": "san-diego-tijuana-buffer-v3", "bbox": old["profile"]["bbox"]}
        else:
            profile = {**old["profile"], "bbox": old["profile"].get("bbox", old.get("bbox"))}
        identity = {"case": args.case, "profile": profile, "sourceArtifact": artifact(source), "previousManifestSha256": file_hash(previous / previous_name),
                    "imageId": args.image_id, "scripts": scripts, "parityReports": parity, "memoryLimit": "4g", "cpus": 2, "network": "none"}
        run_id = digest(identity)
        save_json(output / "run-identity.json", {"runId": run_id, **identity})
        (output / "recipe").mkdir()
        for name in scripts: atomic_write(output / "recipe" / name, (recipe / name).read_bytes())
        checkpoints = {}

        def observe(stage):
            checkpoints[stage] = {**resources(), "elapsedMs": (time.perf_counter() - started) * 1000}
            save_json(output / "progress.json", checkpoints)
            print(f"{stage}: RSS {checkpoints[stage]['workerMaxRssKiB']} KiB; container peak {checkpoints[stage].get('memory.peak')} bytes", flush=True)

        observe("preflight")
        measurements = {}
        before = time.perf_counter()
        v3 = args.case.endswith("v3")
        if v3: graph, audit = import_barriers(source, output / "barrier-roads.osm", profile["bbox"], profile["model"], measurements, observe)
        else: graph, audit = import_maneuvers(source, profile["bbox"], profile["model"], measurements, observe)
        import_ms = (time.perf_counter() - before) * 1000
        examples, incoming, outgoing = [], [], []
        if v3: examples, incoming, outgoing = source_examples(source, output / "barrier-source-samples.osm", graph, audit)
        if args.case in {"wide-v3", "buffer-v3"}:
            uncertain = source_uncertainties(source, output / "uncertain-crossings-source.osm")
            by_way = {row["id"]: [] for row in uncertain}
            for road in graph.base.roads:
                if road["way"] in by_way: by_way[road["way"]].append(road["id"])
            for row in uncertain: row["retainedDirectedRoadIds"] = by_way[row["id"]]
            audit["sourceCrossingUncertainties"] = uncertain
            examples += barrier_examples(graph, audit, {1228835396, 8181606580, 9357332258})
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
        identical = {}
        if not buffer:
            if graph.identity != old["graphIdentity"]: raise ValueError("Graph identity differs")
            for name, expected in old["artifacts"].items():
                if name in artifacts:
                    if artifacts[name] != expected: raise ValueError(f"Compact parity differs: {name}")
                    identical[name] = expected["sha256"]
        else:
            # Independent frozen qualification runs directly on the compact views.
            fixture = load_json(inputs / "model-pilot/downtown-maneuvers-v2/summary.json")
            fixture["alternativeRoadIds"] = {str(row["restriction"]["id"]): row["alternativeRoadId"] for row in fixture["sourceSamples"]}
            summary = qualify(output, graph, audit, profile, fixture, examples, incoming, outgoing)
            diagnose_routes(output, graph, audit, summary)
            summary.update({"runId": run_id, "importMs": import_ms, "importStages": measurements,
                            "resourceCheckpoints": checkpoints, "workerWallMs": (time.perf_counter() - started) * 1000})
            save_json(output / "summary.json", summary)
            names += ["summary.json"] + summary["oracleArtifacts"]
            artifacts = {name: artifact(output / name) for name in names}
        observe("complete")
        report = {"runId": run_id, "case": args.case, "graphIdentity": graph.identity, "roads": len(graph.base.roads), "states": len(graph.states),
                  "transitions": len(graph.adjacency.targets), "viaWayRestrictions": len(graph.patterns), "importMs": import_ms, "importStages": measurements,
                  "resourceCheckpoints": checkpoints, "workerWallMs": (time.perf_counter() - started) * 1000, "artifacts": artifacts,
                  "identicalArtifactSha256": identical, "publicApiCalls": 0, "coverageVerified": False,
                  "scope": "Exact frozen graph/audit/packed-byte equality" if not buffer else "Larger compact graph with independent full/bounded/partial oracles; no real-world eligibility or complete-coverage claim"}
        save_json(output / "report.json", report)
        save_json(output / "manifest.json", {"runId": run_id, **identity, "graphIdentity": graph.identity, "artifacts": {**artifacts, "report.json": artifact(output / "report.json")}})
        print(json.dumps({key: report[key] for key in ("case", "roads", "states", "transitions", "importMs", "workerWallMs", "identicalArtifactSha256")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    run(parser.parse_args())
