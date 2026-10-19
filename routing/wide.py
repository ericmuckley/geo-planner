"""Qualify the saved wider region using streaming v3 access, without network."""

import argparse
import fcntl
from fractions import Fraction
import gzip
import json
import math
from pathlib import Path
import tempfile
import time

from anchors import atomic_write, digest, file_hash, load_json, save_json
from barrier_policy import MODEL_ID
from barriers import qualify, source_examples
from cell_experiment import checked_artifact
from crossing_audit import barrier_examples, route_evidence, source_uncertainties
from import_capacity import graph_data, resources
from maneuver_graph import destination_oracle, interior_destination
from native_support import decode_labels, pack_graph
from regional_support import route_to_interior
from stream_import import import_barriers


ARTIFACTS = ("graph.json", "graph.csr", "graph.csr.gz", "import-audit.json", "barrier-roads.osm", "barrier-source-samples.osm", "uncertain-crossings-source.osm")


def materialize(source, output, profile):
    measurements = {}
    before = time.perf_counter()
    graph, audit = import_barriers(source, output / "barrier-roads.osm", profile["bbox"], profile["model"], measurements)
    import_ms = (time.perf_counter() - before) * 1000
    checkpoints = {"import": resources()}
    print(f"Imported wider v3: {len(graph.states)} states in {import_ms:.1f} ms", flush=True)
    examples, incoming, outgoing = source_examples(source, output / "barrier-source-samples.osm", graph, audit)
    uncertain = source_uncertainties(source, output / "uncertain-crossings-source.osm")
    by_way = {row["id"]: [] for row in uncertain}
    for road in graph.base.roads:
        if road["way"] in by_way: by_way[road["way"]].append(road["id"])
    for row in uncertain: row["retainedDirectedRoadIds"] = by_way[row["id"]]
    audit["sourceCrossingUncertainties"] = uncertain
    extra = barrier_examples(graph, audit, {1228835396, 8181606580, 9357332258})
    private = next(row for row in extra if row["id"] == 1228835396)
    if not private["blockedByModel"] or not any(not row["uTurn"] for row in private["transitions"]):
        raise ValueError("Source-backed private through-gate closure is missing")
    if any(row["blockedByModel"] for row in extra if row["id"] != 1228835396): raise ValueError("Qualified crossing control closed")
    packed = pack_graph(graph.adjacency, graph.identity)
    save_json(output / "graph.json", graph_data(graph, profile["model"]))
    save_json(output / "import-audit.json", audit)
    atomic_write(output / "graph.csr", packed)
    atomic_write(output / "graph.csr.gz", gzip.compress(packed, mtime=0))
    checkpoints["materialized"] = resources()
    return graph, audit, examples + extra, incoming, outgoing, import_ms, measurements, checkpoints


def diagnose_routes(output, graph, audit, summary):
    uncertainties = audit["sourceCrossingUncertainties"]
    origins = {row["origin"]: row for row in summary["origins"]}
    opened = {row["id"] for row in audit["barrierPolicy"]["decisions"] if row["open"] and not row["blockedByModel"]}
    for route in summary["sampledRoutes"]:
        route["accessEvidence"] = route_evidence(graph, origins[route["origin"]], route, uncertainties, opened)
    # Explicitly exercise the uncertain branch even when the fastest city route avoids it.
    origin = origins["tijuana"]
    road = next(index for index, road in enumerate(graph.base.roads) if road["id"] == "114198251:0:f")
    labels = decode_labels((output / "oracles/tijuana.u64le").read_bytes(), len(graph.states))
    actual = interior_destination(graph, labels, road, Fraction(1, 2), origin["starts"])
    expected = destination_oracle(graph, origin["seeds"], road, Fraction(1, 2), origin["starts"])
    if actual != expected or not math.isfinite(actual): raise ValueError("Uncertain crossing branch disagrees with sink oracle")
    route = {"origin": "tijuana", "destination": "uncertain-otay-way-interior",
             **route_to_interior(graph, labels, origin["seeds"], origin["starts"], road, Fraction(1, 2)),
             "targetRoadId": graph.base.roads[road]["id"], "targetFraction": "1/2"}
    route["accessEvidence"] = route_evidence(graph, origin, route, uncertainties, opened)
    if 114198251 not in route["accessEvidence"]["sourceUncertaintyWayIds"]: raise ValueError("Uncertain route warning lost")
    summary["uncertainBranchRoutes"] = [route]
    summary["sourceCrossingUncertainties"] = uncertainties
    summary["interiorDestinations"].append({"origin": "tijuana", "roadId": graph.base.roads[road]["id"], "fraction": "1/2", "costMs": actual})
    summary["interiorDestinationComparisons"] += 1
    summary["routeEligibilityVerified"] = False


def run(args):
    started = time.perf_counter()
    output, recipe = Path(args.output), Path(__file__).parent
    with (output / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous_dir, source_dir, fixture_dir = Path("/wide-v2"), Path("/source"), Path("/fixture")
        previous = load_json(previous_dir / "report.json")
        if previous["case"] != "wide-v2" or previous["imageId"] != args.image_id: raise ValueError("Wrong wider reference/image")
        for name, artifact in previous["artifacts"].items():
            if (previous_dir / name).stat().st_size != artifact["bytes"] or file_hash(previous_dir / name) != artifact["sha256"]: raise ValueError("Wider reference changed")
        source = source_dir / "car-roads.osm"
        if file_hash(source) != previous["sourceXmlSha256"]: raise ValueError("Wider OSM input changed")
        fixture_manifest = load_json(fixture_dir / "manifest.json")
        for name in fixture_manifest["artifacts"]: checked_artifact(fixture_dir, fixture_manifest, name)
        failed_identity = load_json(source_dir / "run-identity.json")
        if failed_identity["regionArtifact"] != fixture_manifest["regionArtifact"]: raise ValueError("Fixture/source snapshot differs")
        profile = {**previous["profile"], "id": "san-diego-tijuana-wide-v3", "model": {**previous["profile"]["model"], "id": MODEL_ID}, "nativeRepetitions": 5,
                   "borderPolicy": "Qualified static permissions only. Explicit source uncertainty is reported without changing v3 access. No queues, delays, documents or real crossing-eligibility claim."}
        scripts = {name: file_hash(recipe / name) for name in ("wide.py", "crossing_audit.py", "stream_import.py", "import_capacity.py", "barriers.py", "barrier_policy.py",
                   "import_roads.py", "import_maneuvers.py", "maneuver_graph.py", "state_graph.py", "anchors.py", "native_support.py", "regional_support.py",
                   "reference.py", "cell_experiment.py", "cell_index.py")}
        identity = {"previousRunId": previous["runId"], "previousReportSha256": file_hash(previous_dir / "report.json"), "profile": profile,
                    "sourceXmlSha256": previous["sourceXmlSha256"], "fixtureManifestSha256": file_hash(fixture_dir / "manifest.json"),
                    "scripts": scripts, "imageId": args.image_id, "memoryLimit": "4g", "cpus": 2, "network": "none"}
        run_id = digest(identity)
        identity_path = output / "run-identity.json"
        if identity_path.exists() and load_json(identity_path)["runId"] != run_id: raise ValueError("Code/input changed; use a fresh run name")
        preflight = resources()
        if args.stage == "rebuild":
            manifest = load_json(output / "manifest.json")
            if manifest["runId"] != run_id: raise ValueError("Rebuild identity differs")
            for name in manifest["artifacts"]: checked_artifact(output, manifest, name)
            with tempfile.TemporaryDirectory(dir=output) as temporary:
                temporary = Path(temporary)
                graph, audit, examples, incoming, outgoing, import_ms, measurements, checkpoints = materialize(source, temporary, profile)
                hashes = {name: file_hash(temporary / name) for name in ARTIFACTS}
                for name, value in hashes.items():
                    if value != manifest["artifacts"][name]["sha256"]: raise ValueError(f"Wider v3 rebuild differs: {name}")
            report = {"sourceRunId": run_id, "sourceManifestSha256": file_hash(output / "manifest.json"), "graphIdentity": graph.identity,
                      "identicalArtifactSha256": hashes, "importMs": import_ms, "workerWallMs": (time.perf_counter() - started) * 1000,
                      "resourceCheckpoints": {"preflight": preflight, **checkpoints, "complete": resources()}, "workerSha256": file_hash(Path(__file__)),
                      "publicApiCalls": 0, "scope": "Reimport/materialize equality; original oracle vectors checked, not recomputed."}
            save_json(output / "rebuild-verification.json", report)
            print(json.dumps(report, indent=2)); return
        if (output / "manifest.json").exists(): raise ValueError("Completed graph exists; use a fresh run name")
        save_json(identity_path, {"runId": run_id, **identity})
        graph, audit, examples, incoming, outgoing, import_ms, measurements, checkpoints = materialize(source, output, profile)
        fixture = load_json(fixture_dir / "summary.json")
        fixture["alternativeRoadIds"] = {str(row["restriction"]["id"]): row["alternativeRoadId"] for row in fixture["sourceSamples"]}
        summary = qualify(output, graph, audit, profile, fixture, examples, incoming, outgoing)
        diagnose_routes(output, graph, audit, summary)
        summary.update({"runId": run_id, "importMs": import_ms, "importStages": measurements, "workerWallMs": (time.perf_counter() - started) * 1000,
                        "resourceCheckpoints": {"preflight": preflight, **checkpoints, "complete": resources()}, "publicApiCalls": 0, "coverageVerified": False})
        save_json(output / "summary.json", summary)
        names = list(ARTIFACTS) + ["summary.json"] + summary["oracleArtifacts"]
        save_json(output / "manifest.json", {"runId": run_id, **identity, "graphIdentity": graph.identity,
                  "artifacts": {name: {"bytes": (output / name).stat().st_size, "sha256": file_hash(output / name)} for name in names}})
        (output / "recipe").mkdir(exist_ok=True)
        for name in scripts: atomic_write(output / "recipe" / name, (recipe / name).read_bytes())
        print(json.dumps({key: summary[key] for key in ("runId", "states", "transitions", "importMs", "workerWallMs", "resourceCheckpoints", "publicApiCalls")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--output", default="/output")
    parser.add_argument("--stage", choices=("build", "rebuild"), default="build")
    run(parser.parse_args())
