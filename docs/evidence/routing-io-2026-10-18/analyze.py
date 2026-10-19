"""Audit the saved I/O lifetime parity and complete-container observations."""

import ast
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CAP = 4 * 1024**3
CASES = ("downtown-v2", "corridor-v3", "wide-v3", "hour-v3")


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


def audit_mode(prefix, baseline_prefix):
    results = {}
    for case in CASES:
        report, manifest = read(f"{prefix}-{case}-report.json"), read(f"{prefix}-{case}-manifest.json")
        identity = read(f"{prefix}-{case}-run-identity.json")
        old, original = read(f"{baseline_prefix}-{case}-manifest.json"), read(f"qualified-{case}-manifest.json")
        baseline = read(f"{baseline_prefix}-{case}-report.json")
        assert report["runId"] == manifest["runId"] == identity["runId"]
        unsigned = {key: value for key, value in identity.items() if key != "runId"}
        assert identity["runId"] == hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        assert manifest["imageId"] == old["imageId"]
        assert manifest["network"] == "none" and manifest["cpus"] == 2
        assert report["publicApiCalls"] == 0 and not report["coverageVerified"]
        assert report["graphIdentity"] == old["graphIdentity"] == original["graphIdentity"]
        assert manifest["sourceArtifact"] == old["sourceArtifact"] == original["sourceArtifact"]
        assert manifest["profile"] == old["profile"] == original["profile"]
        assert manifest["previousManifestSha256"] == sha(HERE / f"{baseline_prefix}-{case}-manifest.json")
        assert manifest["previousReportSha256"] == sha(HERE / f"{baseline_prefix}-{case}-report.json")
        assert manifest["qualificationManifestSha256"] == sha(HERE / f"qualified-{case}-manifest.json")
        for script, expected in manifest["scripts"].items():
            assert sha(ROOT / "routing" / script) == expected, script
        assert len(report["artifacts"]) == {"downtown-v2": 4, "corridor-v3": 6, "wide-v3": 7, "hour-v3": 7}[case]
        assert all(value == old["artifacts"][name] == original["artifacts"][name] for name, value in report["artifacts"].items())
        assert all(report["identicalArtifactSha256"][name] == value["sha256"] for name, value in report["artifacts"].items())
        reused = report["reusedQualification"]
        assert reused["manifestSha256"] == manifest["qualificationManifestSha256"]
        assert reused["artifacts"] == {name: value for name, value in original["artifacts"].items() if name == "summary.json" or name.startswith("oracles/")}
        policy = report["ioLifetime"]
        assert policy["windowBytes"] == 16 * 1024**2 and policy["readThresholdBytes"] == 8 * 1024**2
        streamed = {Path(row["path"]).name: row for row in policy["requests"] if row["kind"] == "streamed-output"}
        assert set(streamed) == {"graph.json", "import-audit.json"}
        for name, row in streamed.items():
            assert row["bytes"] == report["artifacts"][name]["bytes"]
            assert row["syncs"] == math.ceil(row["bytes"] / policy["windowBytes"])
        for row in policy["requests"]:
            if row["kind"] in ("streamed-output", "completed-output"):
                assert row["path"].startswith("/output/")
            if row["kind"] == "completed-read":
                assert not row["synced"] and row["bytes"] >= policy["readThresholdBytes"]
        if prefix == "bounded":
            assert report["cacheAdvice"]["requests"]
            for row in report["cacheAdvice"]["requests"]:
                assert row["windowBytes"] == 16 * 1024**2
                assert row["ranges"] == math.ceil(row["bytes"] / row["windowBytes"])
        measured = resources(report)
        assert measured["phaseHeadroomPass"] and not any(measured["events"].values())
        results[case] = {"before": resources(baseline), "after": measured,
                         "graphIdentity": report["graphIdentity"], "states": report["states"], "arcs": report["transitions"],
                         "identicalArtifacts": len(report["artifacts"]), "ioRequests": len(policy["requests"])}
    current = read(f"{prefix}-hour-v3-report.json")
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
        assert read(f"{prefix}-hour-v3-manifest.json")["parityReports"][case] == sha(HERE / f"{prefix}-{case}-report.json")
    return results


def analyze():
    before = ast.parse((ROOT / "routing/keyed_import.py").read_text())
    after = ast.parse((ROOT / "routing/cache_import.py").read_text())
    for name in ("import_maneuvers", "import_barriers"):
        original = next(n for n in before.body if isinstance(n, ast.FunctionDef) and n.name == name)
        current = next(n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == name)
        assert ast.dump(original) == ast.dump(current), name
    old_checker = ast.parse((ROOT / "routing/paged_import.py").read_text())
    new_checker = ast.parse((ROOT / "routing/range_manifest.py").read_text())
    original = next(n for n in old_checker.body if isinstance(n, ast.FunctionDef) and n.name == "checked_manifest")
    current = next(n for n in new_checker.body if isinstance(n, ast.FunctionDef) and n.name == "checked_manifest")
    assert ast.dump(original) == ast.dump(current)
    return {"io": audit_mode("io", "old"), "bounded": audit_mode("bounded", "io"),
            "newLargerGraphBuilt": False, "coverageVerified": False,
            "scope": "Exact frozen graph/source/audit/CSR/gzip parity and reused independent/native evidence. Complete capped I/O observations include verification reads; no fresh search, HTTP, contour, browser or Vercel measurement. Host/cache/VM conditions uncontrolled; phase headroom is not larger-graph admission."}


if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2, sort_keys=True))
