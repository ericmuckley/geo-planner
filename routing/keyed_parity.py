"""Exact frozen-graph parity for the numeric road-key lifetime importer."""

import argparse
import fcntl
import gzip
import json
from pathlib import Path
import time

from anchors import atomic_write, digest, load_json
from barriers import source_examples
from paged_io import advice_report, artifact, file_hash
from buffer_resources import Monitor
from compact_storage import save_json, write_csr
from crossing_audit import barrier_examples, source_uncertainties
from import_capacity import graph_data
from keyed_import import import_barriers, import_maneuvers
from paged_import import checked_manifest


CASES = {
    "downtown-v2": ("compact-pilot/compact-v1-downtown-v2", "reference-pilot/downtown-static-v1/roads.osm"),
    "corridor-v3": ("compact-pilot/compact-v1-corridor-v3", "regional-pilot/san-diego-tijuana-corridor-v2/car-roads.osm"),
    "wide-v3": ("compact-pilot/compact-v1-wide-v3", "regional-pilot/san-diego-tijuana-v2/car-roads.osm"),
    "hour-v3": ("compact-pilot/hour-v3", "coverage-pilot/hour-candidate-v1/car-roads.osm"),
}


def run(args):
    started = time.perf_counter()
    inputs, output, recipe = Path("/inputs"), Path(args.output), Path(__file__).parent
    with (output / ".lock").open("w") as lock, Monitor(output) as monitor:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "run-identity.json").exists(): raise ValueError("Preserve existing attempts; use a fresh series")
        previous = inputs / CASES[args.case][0]
        old = checked_manifest(previous)
        if old["imageId"] != args.image_id: raise ValueError("Tools image differs")
        source = inputs / CASES[args.case][1]
        if artifact(source) != old["sourceArtifact"]: raise ValueError("Frozen source changed")
        names = (*old["scripts"], "input_storage.py", "input_import.py", "input_capacity.py", "input-storage.mjs", "offline-no-swap.mjs", "settings.mjs", "paged_import.py", "paged-import.mjs", "paged_io.py", "buffer_resources.py", "keyed_import.py", "road_keys.py", "keyed_parity.py", "keyed-parity.mjs")
        scripts = {name: file_hash(recipe / name) for name in names}
        parity = {}
        if args.case == "hour-v3":
            for case in CASES:
                if case == "hour-v3": continue
                directory = inputs / "keyed-pilot" / f"{args.series}-{case}"
                proof = checked_manifest(directory)
                # Require the same importer code on the smaller frozen cases first.
                if any(proof["scripts"].get(name) != scripts[name] for name in ("keyed_import.py", "road_keys.py", "keyed_parity.py", "keyed-parity.mjs")):
                    raise ValueError("Smaller parity cases used different code")
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
        if args.case in {"wide-v3", "hour-v3"}:
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
        if args.case in {"wide-v3", "hour-v3"}: names.append("uncertain-crossings-source.osm")
        artifacts = {name: artifact(output / name) for name in names}
        if graph.identity != old["graphIdentity"]: raise ValueError("Graph identity differs")
        for name, actual in artifacts.items():
            if actual != old["artifacts"][name]: raise ValueError(f"Compact-input parity differs: {name}")
        reused = {"manifestSha256": identity["previousManifestSha256"], "graphIdentity": graph.identity,
                  "artifacts": {name: value for name, value in old["artifacts"].items() if name == "summary.json" or name.startswith("oracles/")},
                  "scope": "Checksum-verified existing qualification on the identical graph; no new route/search measurements"}
        if args.case == "hour-v3":
            native = load_json(previous / "native-verification.json")
            if native["sourceManifestSha256"] != identity["previousManifestSha256"]: raise ValueError("Native evidence manifest differs")
            if native["graphIdentity"] != graph.identity or native["compilation"]["sourceSha256"] != file_hash(recipe / "native_search.cpp") or native["compilation"]["binarySha256"] != file_hash(previous / "native_search"):
                raise ValueError("Native graph/source/binary differs")
            qualified = load_json(previous / "qualification-report.json")
            if qualified["graphIdentity"] != graph.identity or qualified["costComparisons"] != len(graph.states) * 5 or qualified["boundedCostComparisons"] != len(graph.states) * 40 or qualified["interiorDestinationComparisons"] != 2:
                raise ValueError("Independent qualification differs")
            if native["costComparisons"] != len(graph.states) * 45 or native["membershipComparisons"] != len(graph.states) * 40 or native["interiorDestinationComparisons"] != 2:
                raise ValueError("Native comparison counts differ")
            reused["qualificationReport"] = artifact(previous / "qualification-report.json")
            reused["nativeVerification"] = artifact(previous / "native-verification.json")
        observe("complete")
        report = {"runId": run_id, "case": args.case, "graphIdentity": graph.identity, "roads": len(graph.base.roads), "states": len(graph.states),
                  "transitions": len(graph.adjacency.targets), "viaWayRestrictions": len(graph.patterns), "importMs": import_ms,
                  "importStages": measurements, "workerWallMs": (time.perf_counter() - started) * 1000, "resourceCheckpoints": checkpoints,
                  "artifacts": artifacts, "identicalArtifactSha256": {name: value["sha256"] for name, value in artifacts.items()},
                  "reusedQualification": reused, "publicApiCalls": 0, "coverageVerified": False,
                  "sampling": monitor.summary(), "cacheAdvice": advice_report(),
                  "scope": "Exact frozen graph/audit/source/packed parity after replacing retained road-ID strings with three existing numeric arrays. Same base/history/access rules; old full/bounded/partial/native qualification reused on identical outputs. No new route searches, timings or coverage."}
        save_json(output / "report.json", report)
        save_json(output / "manifest.json", {"runId": run_id, **identity, "graphIdentity": graph.identity,
                                            "artifacts": {**artifacts, "report.json": artifact(output / "report.json")}})
        print(json.dumps({key: report[key] for key in ("case", "states", "transitions", "importMs", "workerWallMs")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--series", default="keys-v1")
    parser.add_argument("--output", default="/output")
    parser.add_argument("--image-id", required=True)
    run(parser.parse_args())
