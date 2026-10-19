"""Verify the east/south hour candidate, independent oracles, rebuild and all cuts."""

from fractions import Fraction
import ast
import hashlib
import json
import mmap
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT / "routing"))
from anchors import digest
from compact_load import load_graph
from crossing_audit import route_evidence
from cut_inventory import cut_states, minimum_witness


def read(path): return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream: return hashlib.file_digest(stream, "sha256").hexdigest()


def check(path, expected):
    assert path.stat().st_size == expected["bytes"], path
    assert sha(path) == expected["sha256"], path


def identity(directory, filename):
    record = read(directory / filename)
    assert record["runId"] == digest({key: value for key, value in record.items() if key != "runId"})
    for name, expected in record["scripts"].items():
        assert sha(ROOT / "routing" / name) == sha(directory / "recipe" / name) == expected
    assert record["memoryLimit"] == record["memorySwapLimit"] == "4g"
    assert record["cpus"] == 2 and record["network"] == "none"
    return record


def resource(report):
    rows = list(report["resourceCheckpoints"].values())
    for row in rows:
        assert row["memory.max"] == "4294967296"
        assert row["memory.swap.max"] == row["memory.swap.current"] == row["memory.swap.peak"] == "0"
        assert all(int(row["memory.events"][key]) == 0 for key in ("oom", "oom_kill", "oom_group_kill"))
    last = max(rows, key=lambda row: row["elapsedMs"])
    return {"workerWallMs": report["workerWallMs"], "workerMaxRssKiB": last["workerMaxRssKiB"],
            "cgroupPeakBytes": max(int(row["memory.peak"]) for row in rows), "limitHits": int(last["memory.events"]["max"]),
            "sampling": report["sampling"], "importMs": report.get("importMs")}


def interpolate(road, fraction):
    return [a + (b - a) * float(fraction) for a, b in zip(road["fromPoint"], road["toPoint"], strict=True)]


def run():
    local = ROOT / "data/compact-pilot/hour-v3"
    rebuild = ROOT / "data/compact-pilot/hour-v3-rebuild"
    cut_directory = ROOT / "data/compact-pilot/hour-v3-cuts"
    manifest = read(local / "manifest.json")
    built_manifest = read(local / "build-manifest.json")
    rebuilt_manifest = read(rebuild / "build-manifest.json")
    for directory, filename in ((local, "run-identity.json"), (local, "qualification-identity.json"),
                                (local, "oracle-calibration-identity.json"),
                                (rebuild, "run-identity.json"), (cut_directory, "run-identity.json")):
        identity(directory, filename)
    for directory, local_name, copied_name in ((local, "run-identity.json", "run-identity.json"),
            (local, "qualification-identity.json", "qualification-identity.json"),
            (local, "oracle-calibration-identity.json", "oracle-calibration-identity.json"),
            (rebuild, "run-identity.json", "rebuild-identity.json"),
            (cut_directory, "run-identity.json", "cuts-identity.json")):
        assert read(directory / local_name) == read(HERE / copied_name)
    calibration = manifest["oracleCalibration"]
    old_directory = ROOT / "data/compact-pilot/compact-v1-buffer-v3"
    assert calibration["sourceManifestSha256"] == sha(old_directory / "manifest.json")
    assert len(calibration["partialDestinations"]) == 2
    frozen = read(old_directory / "summary.json")["interiorDestinations"]
    for row in calibration["partialDestinations"]:
        assert {key: value for key, value in row.items() if key != "oracleMs"} in frozen
    # This version changes the independent oracle import, not the qualification body.
    bodies = []
    for name in ("lean_checks.py", "queue_qualification.py"):
        parsed = ast.parse((ROOT / "routing" / name).read_text())
        bodies.append(ast.dump(next(node for node in parsed.body if isinstance(node, ast.FunctionDef) and node.name == "qualify")))
    assert bodies[0] == bodies[1]
    for directory, record in ((local, manifest), (rebuild, rebuilt_manifest)):
        for name, expected in record["artifacts"].items(): check(directory / name, expected)
    prepared = ROOT / "data/coverage-pilot/hour-candidate-v1"
    check(prepared / "car-roads.osm", manifest["sourceArtifact"])
    assert sha(prepared / "report.json") == built_manifest["preparationReportSha256"]
    assert sha(ROOT / "docs/evidence/hour-preflight-2026-10-17/admission.json") == built_manifest["admissionSha256"]
    admitted = read(ROOT / "docs/evidence/hour-preflight-2026-10-17/admission.json")
    assert admitted["cappedExperimentEligible"]
    assert built_manifest["sourceArtifact"] == admitted["candidateSourceArtifact"]
    assert built_manifest["profile"]["bbox"] == admitted["profile"]["bbox"]
    assert built_manifest["profileSha256"] == sha(ROOT / "routing/profiles/coverage-hour-v1.json") == sha(local / "recipe/coverage-hour-v1.json")
    assert manifest["buildManifestSha256"] == sha(local / "build-manifest.json")
    assert rebuilt_manifest["rebuildManifestSha256"] == sha(local / "build-manifest.json")
    assert manifest["graphIdentity"] == rebuilt_manifest["graphIdentity"]
    built = read(local / "build-report.json")
    rebuilt = read(rebuild / "build-report.json")
    qualification = read(local / "qualification-report.json")
    summary = read(local / "summary.json")
    audit = read(local / "import-audit.json")
    native = read(local / "native-verification.json")
    cuts = read(cut_directory / "report.json")
    records = read(cut_directory / "cut-nodes.json")
    for report in (built, rebuilt, qualification, cuts):
        assert report["publicApiCalls"] == 0 and not report["coverageVerified"]
    for name in rebuilt["identicalRebuildArtifacts"]: assert built["artifacts"][name] == rebuilt["artifacts"][name]
    assert len(rebuilt["identicalRebuildArtifacts"]) == 7
    assert cuts["sourceManifestSha256"] == native["sourceManifestSha256"] == sha(local / "manifest.json")
    assert native["workerSha256"] == sha(ROOT / "routing/compact_native.py")
    assert native["compilation"]["sourceSha256"] == sha(ROOT / "routing/native_search.cpp")
    assert native["compilation"]["binarySha256"] == sha(local / "native_search")
    assert native["networkProbe"] == "loopback socket denied" and native["publicApiCalls"] == 0
    assert native["costComparisons"] == summary["states"] * 45
    assert native["membershipComparisons"] == summary["states"] * 40
    assert native["interiorDestinationComparisons"] == 2
    assert summary["costComparisons"] == summary["states"] * 5
    assert summary["boundedCostComparisons"] == summary["states"] * 40
    assert summary["interiorDestinationComparisons"] == 2
    assert len(summary["sampledRoutes"]) == 12 and all(route["costMs"] is not None for route in summary["sampledRoutes"])
    for name, expected in cuts["artifacts"].items(): check(cut_directory / name, expected)
    assert cuts["nodesWithoutBoundaryLinks"] == 0
    graph, model = load_graph(local / "graph.json")
    assert graph.identity == manifest["graphIdentity"] and model == manifest["profile"]["model"]
    states = cut_states(graph, set(audit["cutExitNodes"]))
    assert len(records) == cuts["auditedCutNodes"] == len(states)
    assert cuts["cutStates"] == sum(map(len, states.values()))
    by_node = {row["node"]: row for row in records}
    for origin in summary["origins"]:
        with (local / "oracles" / f"{origin['origin']}.u64le").open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as labels:
            for node, indices in states.items():
                expected = minimum_witness(labels, indices)
                actual = by_node[node]["origins"][origin["origin"]]
                assert all(actual[key] == value for key, value in expected.items())
        cut_origin = next(row for row in cuts["origins"] if row["origin"] == origin["origin"])
        assert cut_origin["firstCutExitMs"] == origin["firstCutExitMs"]
        for budget in cut_origin["budgets"]:
            reached = [row for row in records if row["origins"][origin["origin"]]["costMs"] is not None and row["origins"][origin["origin"]]["costMs"] <= budget["budgetMs"]]
            assert len(reached) == budget["reachableCutNodes"]
            for side, count in budget["bySide"].items(): assert count == sum(side in row["outsideSides"] for row in reached)
    origins = {row["origin"]: row for row in summary["origins"]}
    opened = {row["id"] for row in audit["barrierPolicy"]["decisions"] if row["open"] and not row["blockedByModel"]}
    features = []
    for route in summary["sampledRoutes"] + summary["uncertainBranchRoutes"]:
        origin = origins[route["origin"]]
        assert route_evidence(graph, origin, route, summary["sourceCrossingUncertainties"], opened) == route["accessEvidence"]
        roads = [graph.base.roads[graph.states[state]["road"]] for state in route["states"]]
        first_index = graph.states[route["states"][0]]["road"]
        offset = next(Fraction(fraction) for road, fraction in origin["starts"] if road == first_index)
        coordinates = [interpolate(roads[0], offset)] + [road["toPoint"] for road in roads[:-1]] + [interpolate(roads[-1], Fraction(route["targetFraction"]))]
        if origin["snap"]: assert all(abs(a - b) < 1e-9 for a, b in zip(coordinates[0], origin["snap"]["snapped"], strict=True))
        features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coordinates},
                         "properties": {key: route[key] for key in ("origin", "destination", "costMs", "accessEvidence")}})
    for witness in native["cutWitnesses"]:
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": witness["road"]["toPoint"]},
                         "properties": {"origin": witness["origin"], "costMs": witness["costMs"], "kind": "first-potential-cut", "roadId": witness["road"]["id"]}})
    (HERE / "route-and-cut-evidence.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")) + "\n")
    old_summary = read(ROOT / "data/compact-pilot/increment-v3/summary.json")
    old_audit = read(ROOT / "data/compact-pilot/increment-v3/import-audit.json")
    assert {key: value for key, value in manifest["profile"].items() if key not in {"id", "bbox"}} == {key: value for key, value in old_summary["profile"].items() if key not in {"id", "bbox"}}
    decisions = {row["id"]: row for row in audit["barrierPolicy"]["decisions"]}
    for row in old_audit["barrierPolicy"]["decisions"]:
        assert all(decisions[row["id"]][key] == row[key] for key in ("open", "blockedByModel"))
    assert {row["id"] for row in audit["sourceCrossingUncertainties"]} == {114198251, 185333061, 577149752}
    snaps = [{"origin": row["origin"], "distanceMeters": row["snap"]["distanceMeters"],
              "samePhysicalSegment": row["snap"]["physicalSegment"] == old["snap"]["physicalSegment"],
              "sameSnappedCoordinates": row["snap"]["snapped"] == old["snap"]["snapped"]}
             for row in summary["origins"] for old in old_summary["origins"] if row["origin"] == old["origin"] and row["snap"]]
    assert all(row["distanceMeters"] <= summary["profile"]["sourceSnapMaxMeters"] for row in snaps)
    old_cuts = read(ROOT / "data/compact-pilot/increment-v3-cuts/report.json")
    route_changes = [{"origin": row["origin"], "destination": row["destination"], "oldCostMs": old["costMs"], "newCostMs": row["costMs"],
                      "roadIdsIdentical": old["roadIds"] == row["roadIds"]} for row in summary["sampledRoutes"]
                     for old in old_summary["sampledRoutes"] if (old["origin"], old["destination"]) == (row["origin"], row["destination"])]
    comparison = {"graphIdentity": graph.identity, "roads": built["roads"], "states": built["states"], "transitions": built["transitions"],
                  "viaWayRestrictions": built["viaWayRestrictions"], "rebuildArtifactsIdentical": 7, "cityRouteComparison": route_changes,
                  "sourceSnapping": snaps, "priorBarrierDecisionsUnchanged": True,
                  "barrierDecisionCounts": audit["barrierPolicy"]["decisionCounts"],
                  "oldCuts": old_cuts["origins"], "newCuts": cuts["origins"], "nativeCostComparisons": native["costComparisons"],
                  "nativeMembershipComparisons": native["membershipComparisons"], "nativePartialComparisons": 2,
                  "nativeDefaultSixtyMinuteLabels": next(row for row in native["cases"] if row["origin"] == "san-diego" and row["budgetMs"] == 3600000)["modes"]["labels"],
                  "nativeVerification": {key: native[key] for key in ("workerWallMs", "compactReloadMs", "pythonWorkerMaxRssKiB", "nativeStartup", "timingLimits")},
                  "resources": {key: resource(report) for key, report in (("build", built), ("rebuild", rebuilt), ("qualification", qualification), ("cuts", cuts))},
                  "frozenSinkCalibration": calibration,
                  "admissionEstimateWithMarginBytes": admitted["wholeWorkloadEstimateWithHeadroomBytes"],
                  "observedLargestLinuxPhasePeakBytes": max(resource(r)["cgroupPeakBytes"] for r in (built, rebuilt, qualification, cuts)),
                  "sameCountsHave25PercentHeadroom": max(resource(r)["cgroupPeakBytes"] for r in (built, rebuilt, qualification, cuts)) * 1.25 < 4 * 1024 ** 3
                      and all(resource(r)["limitHits"] == 0 for r in (built, rebuilt, qualification, cuts)),
                  "selectedOriginsWithoutSixtyMinutePotentialCuts": [row["origin"] for row in cuts["origins"]
                      if next(b for b in row["budgets"] if b["budgetMs"] == 3600000)["reachableCutNodes"] == 0],
                  "allSelectedOriginsWithoutSixtyMinutePotentialCuts": all(next(b for b in row["budgets"] if b["budgetMs"] == 3600000)["reachableCutNodes"] == 0 for row in cuts["origins"]),
                  "completeGeographicCoverageVerified": False,
                  "publicRoutingApiCalls": 0, "newRoadDownloads": 0, "coverageVerified": False, "routeEligibilityVerified": False}
    for name, path in {"build-report.json": local / "build-report.json", "build-manifest.json": local / "build-manifest.json",
                       "qualification-report.json": local / "qualification-report.json", "manifest.json": local / "manifest.json",
                       "summary.json": local / "summary.json", "native-verification.json": local / "native-verification.json",
                       "rebuild-report.json": rebuild / "build-report.json", "rebuild-manifest.json": rebuild / "build-manifest.json",
                       "cuts-report.json": cut_directory / "report.json"}.items():
        assert read(HERE / name) == read(path), name
    (HERE / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    print(json.dumps({key: comparison[key] for key in ("graphIdentity", "states", "transitions", "nativeCostComparisons", "nativeMembershipComparisons", "coverageVerified", "allSelectedOriginsWithoutSixtyMinutePotentialCuts")}, indent=2))


if __name__ == "__main__": run()
