"""Check compact parity, saved qualification and memory evidence without graph decoding."""

import hashlib
import json
from pathlib import Path
import statistics
import struct


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
CASES = ("downtown-v2", "corridor-v2", "corridor-v3", "wide-v3", "buffer-v3")
PREVIOUS = {"downtown-v2": "model-pilot/downtown-maneuvers-v2", "corridor-v2": "regional-pilot/san-diego-tijuana-corridor-v2",
            "corridor-v3": "barrier-pilot/san-diego-tijuana-barriers-v3", "wide-v3": "barrier-pilot/san-diego-tijuana-wide-v3"}
SOURCES = {"downtown-v2": "reference-pilot/downtown-static-v1/roads.osm", "corridor-v2": "regional-pilot/san-diego-tijuana-corridor-v2/car-roads.osm",
           "corridor-v3": "regional-pilot/san-diego-tijuana-corridor-v2/car-roads.osm", "wide-v3": "regional-pilot/san-diego-tijuana-v2/car-roads.osm",
           "buffer-v3": "coverage-pilot/san-diego-tijuana-buffer-preflight-r2/car-roads.osm"}


def read(path): return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream: return hashlib.file_digest(stream, "sha256").hexdigest()


def check(path, expected):
    assert path.stat().st_size == expected["bytes"], path
    assert sha(path) == expected["sha256"], path


def run():
    rows = []
    for case in CASES:
        directory = ROOT / "data/compact-pilot" / f"compact-v1-{case}"
        manifest, report = read(directory / "manifest.json"), read(directory / "report.json")
        identity = read(directory / "run-identity.json")
        assert report == read(HERE / f"{case}-report.json")
        assert manifest == read(HERE / f"{case}-manifest.json")
        encoded = json.dumps({key: value for key, value in identity.items() if key != "runId"}, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        assert hashlib.sha256(encoded).hexdigest() == identity["runId"] == report["runId"] == manifest["runId"]
        check(ROOT / "data" / SOURCES[case], identity["sourceArtifact"])
        for name, expected in manifest["artifacts"].items(): check(directory / name, expected)
        for name, expected in manifest["scripts"].items():
            assert sha(ROOT / "routing" / name) == sha(directory / "recipe" / name) == expected
        for resource in report["resourceCheckpoints"].values():
            assert int(resource["memory.max"]) == 4 * 1024 ** 3
            for event in ("oom", "oom_kill", "oom_group_kill"): assert int(resource["memory.events"][event]) == 0
        assert report["publicApiCalls"] == 0 and manifest["network"] == "none" and not report["coverageVerified"]
        with (directory / "graph.csr").open("rb") as stream: magic, count, arcs, graph_id = struct.unpack("<8sII32s", stream.read(48))
        assert magic == b"GPCSR001" and count == report["states"] and arcs == report["transitions"] and graph_id.hex() == report["graphIdentity"]
        assert manifest["artifacts"]["graph.csr"]["bytes"] == 48 + 4 * (count + 1 + 2 * arcs)
        if case in PREVIOUS:
            previous = ROOT / "data" / PREVIOUS[case]
            old = read(previous / "manifest.json")
            for name, expected in old["artifacts"].items(): check(previous / name, expected)
            for name, expected in report["identicalArtifactSha256"].items(): assert old["artifacts"][name]["sha256"] == expected
            assert old["graphIdentity"] == report["graphIdentity"]
        resource = report["resourceCheckpoints"]["complete"]
        rows.append({"case": case, "runId": report["runId"], "states": count, "arcs": arcs,
                     "workerRssKiB": resource["workerMaxRssKiB"], "cgroupPeakBytes": int(resource["memory.peak"]),
                     "limitEvents": int(resource["memory.events"]["max"]), "importMs": report["importMs"], "workerWallMs": report["workerWallMs"]})
    directory = ROOT / "data/compact-pilot/compact-v1-buffer-v3"
    manifest, summary, native = (read(directory / name) for name in ("manifest.json", "summary.json", "native-verification.json"))
    swap_observations = [read(HERE / name) for name in ("swap-observation-early.json", "swap-observation-port.json", "swap-observation-late.json")]
    for observation in swap_observations:
        assert observation["sourceRunId"] == manifest["runId"]
        assert observation["memory.swap.current"] == observation["memory.swap.peak"] == "0"
        assert int(observation["memory.swap.max"]) == 4 * 1024 ** 3
    reload_dir = ROOT / "data/compact-pilot/compact-v1-buffer-reload"
    reload = read(reload_dir / "report.json")
    assert reload == read(HERE / "reload-report.json") and reload["graphIdentity"] == manifest["graphIdentity"]
    assert int(reload["resources"]["memory.max"]) == 1024 ** 3
    for event in ("oom", "oom_kill", "oom_group_kill", "max"): assert int(reload["resources"]["memory.events"][event]) == 0
    for name, expected in reload["scripts"].items(): assert sha(ROOT / "routing" / name) == sha(reload_dir / "recipe" / name) == expected
    for name, expected in reload["sourceArtifacts"].items(): assert expected == manifest["artifacts"][name]
    check(reload_dir / "graph.csr", manifest["artifacts"]["graph.csr"])
    assert summary == read(HERE / "buffer-v3-summary.json") and native == read(HERE / "native-verification.json")
    assert native["sourceManifestSha256"] == sha(directory / "manifest.json")
    for key, name in (("workerSha256", "compact_native.py"), ("loaderSha256", "compact_load.py"), ("storageSha256", "compact_storage.py")):
        assert sha(ROOT / "routing" / name) == native[key]
    assert sha(ROOT / "routing/native_search.cpp") == native["compilation"]["sourceSha256"]
    assert sha(directory / "native_search") == native["compilation"]["binarySha256"]
    prior = ROOT / "data/barrier-pilot/san-diego-tijuana-wide-v3"
    prior_native = read(prior / "native-verification.json")
    assert prior_native["compilation"]["sourceSha256"] == native["compilation"]["sourceSha256"]
    assert sha(prior / "native_search") == prior_native["compilation"]["binarySha256"]
    expected = read(ROOT / "data/coverage-pilot/san-diego-tijuana-buffer-preflight-r2/report.json")["candidate"]
    assert expected["roadStatesLowerBound"] <= summary["baseRoads"] <= expected["roadStatesUpperBound"]
    assert summary["states"] <= expected["historyStatesUpperBound"]
    assert summary["costComparisons"] == summary["states"] * len(summary["origins"])
    assert summary["boundedCostComparisons"] == summary["states"] * len(summary["origins"]) * len(summary["profile"]["budgetsMs"])
    assert native["costComparisons"] + native["membershipComparisons"] == summary["costComparisons"] + 2 * summary["boundedCostComparisons"]
    assert native["interiorDestinationComparisons"] == summary["interiorDestinationComparisons"] == 2
    assert len(summary["sampledRoutes"]) == 12 and all(route["costMs"] is not None for route in summary["sampledRoutes"])
    old_summary = read(prior / "summary.json")
    old_costs = {(route["origin"], route["destination"]): route["costMs"] for route in old_summary["sampledRoutes"]}
    assert all(old_costs[route["origin"], route["destination"]] == route["costMs"] for route in summary["sampledRoutes"])
    assert all(not route["accessEvidence"]["carEligibilityVerified"] for route in summary["sampledRoutes"])
    private = next(row for row in summary["barrierExamples"] if row["id"] == 1228835396)
    assert private["blockedByModel"] and any(not row["uTurn"] for row in private["transitions"])
    assert all(not row["allowed"] for row in private["transitions"])
    for node in (8181606580, 9357332258):
        control = next(row for row in summary["barrierExamples"] if row["id"] == node)
        assert not control["blockedByModel"] and any(row["allowed"] for row in control["transitions"])
    assert 114198251 in summary["uncertainBranchRoutes"][0]["accessEvidence"]["sourceUncertaintyWayIds"]
    aggregates = []
    for budget in summary["profile"]["budgetsMs"]:
        cases = [case for case in native["cases"] if case["budgetMs"] == budget]
        aggregates.append({"budgetMs": budget, "medianOriginSearchP50Ms": statistics.median(case["modes"]["membership"]["timings"]["searchMs"]["p50"] for case in cases),
                           "medianOriginPipeP50Ms": statistics.median(case["modes"]["membership"]["timings"]["childRoundTripMs"]["p50"] for case in cases),
                           "cutOrigins": sum(case["boundaryReachedWithinBudget"] for case in cases)})
    features = [{"type": "Feature", "properties": {"origin": cut["origin"], "costMs": cut["costMs"], "roadId": cut["road"]["id"], "name": cut["road"]["name"],
                 "scope": "Reachable inside endpoint of a cut way; outside continuation is unqualified", "coverageVerified": False},
                 "geometry": {"type": "Point", "coordinates": cut["road"]["toPoint"]}} for cut in native["cutWitnesses"] if cut["road"]]
    (HERE / "cut-witnesses.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}, indent=2) + "\n")
    comparison = {"cases": rows, "frozenGraphsUnchanged": True, "zeroOomAllRuns": True, "sampledCityCostsUnchanged": True,
                  "nativeBinaryIdenticalToWideV3": native["compilation"]["binarySha256"] == prior_native["compilation"]["binarySha256"], "swapObservations": swap_observations,
                  "reloadResources": reload["resources"], "nativeAggregates": aggregates,
                  "cutWitnesses": native["cutWitnesses"], "coverageVerified": False,
                  "scope": "Exact frozen parity and qualified costs on a clipped static model; no real-world car eligibility, complete contour or cloud performance claim."}
    (HERE / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__": run()
