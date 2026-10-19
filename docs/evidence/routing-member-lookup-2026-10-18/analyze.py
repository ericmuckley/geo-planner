"""Audit saved member-lookup parity, recipe bindings and complete-container use."""

import ast
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = ("downtown-v2", "corridor-v3", "wide-v3", "hour-v3")
CAP = 4 * 1024**3


def read(name):
    return json.loads((HERE / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def resources(report):
    rows = list(report["resourceCheckpoints"].values())
    assert all(row["memory.max"] == str(CAP) and row["memory.swap.max"] == "0" for row in rows)
    assert all(row["memory.swap.current"] == row["memory.swap.peak"] == "0" for row in rows)
    events = {key: max(int(row["memory.events"][key]) for row in rows) for key in ("max", "oom", "oom_kill", "oom_group_kill")}
    peak = max(int(row["memory.peak"]) for row in rows)
    return {"cgroupPeakBytes": peak, "workerPeakRssKiB": max(row["workerMaxRssKiB"] for row in rows),
            "events": events, "wallMs": report["workerWallMs"], "importMs": report["importMs"],
            "peakWith25PercentMarginBytes": math.ceil(peak * 1.25),
            "phaseHeadroomPass": not any(events.values()) and math.ceil(peak * 1.25) < CAP}


def check_code():
    def function(file, name):
        return next(node for node in ast.parse((ROOT / "routing" / file).read_text()).body if isinstance(node, ast.FunctionDef) and node.name == name)
    assert ast.dump(function("cache_import.py", "import_barriers")) == ast.dump(function("member_import.py", "import_barriers"))
    old, new = function("input_import.py", "resolve"), function("member_lookup.py", "resolve")
    old.args = new.args
    guards = [node for node in ast.walk(old) if isinstance(node, ast.If) and any(isinstance(child, ast.Constant) and child.value == "Duplicate directed road geometry" for child in ast.walk(node))]
    assert len(guards) == 1
    guards[0].test = ast.Name(id="duplicate_geometry", ctx=ast.Load())
    assert ast.dump(old) == ast.dump(new)
    for name, expected in read("new-recipe-sha256.json").items():
        assert sha(ROOT / "routing" / name) == expected
    for name, expected in read("preserved-sha256.json").items():
        assert sha(ROOT / name) == expected, name


def analyze():
    check_code()
    results = {}
    for case in CASES:
        report, manifest = read(f"members-{case}-report.json"), read(f"members-{case}-manifest.json")
        identity = read(f"members-{case}-run-identity.json")
        old, original = read(f"bounded-{case}-manifest.json"), read(f"qualified-{case}-manifest.json")
        baseline = read(f"bounded-{case}-report.json")
        assert report["runId"] == manifest["runId"] == identity["runId"]
        unsigned = {key: value for key, value in identity.items() if key != "runId"}
        assert identity["runId"] == hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        assert manifest["imageId"] == old["imageId"] and manifest["network"] == "none" and manifest["cpus"] == 2
        assert manifest["memoryLimit"] == manifest["memorySwapLimit"] == "4g" and manifest["swapPolicy"] == "disabled"
        assert report["publicApiCalls"] == 0 and not report["coverageVerified"]
        assert report["graphIdentity"] == old["graphIdentity"] == original["graphIdentity"]
        assert manifest["sourceArtifact"] == old["sourceArtifact"] == original["sourceArtifact"]
        assert manifest["profile"] == old["profile"] == original["profile"]
        assert manifest["previousManifestSha256"] == sha(HERE / f"bounded-{case}-manifest.json")
        assert manifest["previousReportSha256"] == sha(HERE / f"bounded-{case}-report.json")
        assert manifest["qualificationManifestSha256"] == sha(HERE / f"qualified-{case}-manifest.json")
        assert manifest["artifacts"]["report.json"] == artifact(HERE / f"members-{case}-report.json")
        for script, expected in manifest["scripts"].items(): assert sha(ROOT / "routing" / script) == expected, script
        assert len(report["artifacts"]) == {"downtown-v2": 4, "corridor-v3": 6, "wide-v3": 7, "hour-v3": 7}[case]
        assert all(value == old["artifacts"][name] == original["artifacts"][name] for name, value in report["artifacts"].items())
        assert all(report["identicalArtifactSha256"][name] == value["sha256"] for name, value in report["artifacts"].items())
        reused = report["reusedQualification"]
        assert reused == baseline["reusedQualification"]
        assert reused["manifestSha256"] == manifest["qualificationManifestSha256"]
        assert reused["artifacts"] == {name: value for name, value in original["artifacts"].items() if name == "summary.json" or name.startswith("oracles/")}
        fixture = read(f"members-{case}-fixture-parity.json")
        assert report["fixtureParity"] == manifest["artifacts"]["fixture-parity.json"] == artifact(HERE / f"members-{case}-fixture-parity.json")
        assert fixture["caseCount"] == len(fixture["cases"]) == 17
        assert fixture["fullCostComparisons"] == sum(row["states"] ** 2 for row in fixture["cases"])
        assert fixture["boundedCostComparisons"] == 3 * fixture["fullCostComparisons"]
        reasons = {row["name"]: row["fallbackReasons"] for row in fixture["cases"]}
        assert reasons["unselected-duplicate"] == [{"id": 99, "reason": "Duplicate directed road geometry"}]
        assert reasons["ambiguous-before-duplicate"] == [{"id": 99, "reason": "ambiguous/disconnected member join"}]
        assert reasons["selected-duplicate"] == [{"id": 99, "reason": "missing, closed or repeated-node member way"}]
        lookup = report["importStages"]["memberRoadLookups"]
        assert len(lookup) == report["importStages"]["sharedRoadLookupBuilds"]
        assert all(row["retainedKeys"] <= row["memberRoadsScanned"] <= row["totalRoads"] for row in lookup)
        assert all(row["duplicateRoads"] == 0 and row["scanMs"] > 0 for row in lookup)
        assert all(row["retainedKeys"] < row["totalRoads"] for row in lookup)
        assert report["ioLifetime"]["windowBytes"] == 16 * 1024**2
        for row in report["cacheAdvice"]["requests"]:
            assert row["windowBytes"] == 16 * 1024**2 and row["ranges"] == math.ceil(row["bytes"] / row["windowBytes"])
        measured = resources(report)
        assert measured["phaseHeadroomPass"] and not any(measured["events"].values())
        results[case] = {"before": resources(baseline), "after": measured,
                         "graphIdentity": report["graphIdentity"], "states": report["states"], "arcs": report["transitions"],
                         "identicalArtifacts": len(report["artifacts"]), "fixtureCases": fixture["caseCount"],
                         "maxRetainedKeys": max(row["retainedKeys"] for row in lookup),
                         "maxScannedRoads": max(row["totalRoads"] for row in lookup),
                         "maxWayKeys": max(row["maxWayKeys"] for row in lookup),
                         "lookupScanMs": sum(row["scanMs"] for row in lookup)}
    current = read("members-hour-v3-report.json")
    native, qualified = read("frozen-native-verification.json"), read("frozen-qualification-report.json")
    assert native["graphIdentity"] == qualified["graphIdentity"] == current["graphIdentity"]
    assert native["sourceManifestSha256"] == sha(HERE / "qualified-hour-v3-manifest.json")
    assert native["compilation"]["sourceSha256"] == sha(ROOT / "routing/native_search.cpp")
    assert native["costComparisons"] == current["states"] * 45 and native["membershipComparisons"] == current["states"] * 40
    assert qualified["costComparisons"] == current["states"] * 5 and qualified["boundedCostComparisons"] == current["states"] * 40
    assert native["interiorDestinationComparisons"] == qualified["interiorDestinationComparisons"] == 2
    assert current["reusedQualification"]["nativeVerification"] == artifact(HERE / "frozen-native-verification.json")
    assert current["reusedQualification"]["qualificationReport"] == artifact(HERE / "frozen-qualification-report.json")
    for case in CASES[:-1]:
        assert read("members-hour-v3-manifest.json")["parityReports"][case] == sha(HERE / f"members-{case}-report.json")
    return {"cases": results, "newLargerGraphBuilt": False, "coverageVerified": False,
            "scope": "Exact frozen graph/source/audit/CSR/gzip parity; fresh small-fixture checks and reused regional independent/native evidence. Complete capped observations include verification reads; no fresh regional searches, HTTP, contour, browser or Vercel timing. Cache/host/VM conditions uncontrolled; current phase headroom is not larger-graph admission."}


if __name__ == "__main__": print(json.dumps(analyze(), indent=2, sort_keys=True))
