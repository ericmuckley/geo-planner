"""Audit the saved lifetime experiments without routing APIs or large graph loads."""

import ast
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
CAP = 4 * 1024**3
ROOT = HERE.parents[2]


def read(name):
    return json.loads((HERE / name).read_text())


def resources(report):
    rows = list(report["resourceCheckpoints"].values())
    events = {key: max(int(row["memory.events"][key]) for row in rows)
              for key in ("max", "oom", "oom_kill", "oom_group_kill")}
    assert all(row["memory.max"] == str(CAP) and row["memory.swap.max"] == "0" for row in rows)
    assert all(row["memory.swap.current"] == row["memory.swap.peak"] == "0" for row in rows)
    peak = max(int(row["memory.peak"]) for row in rows)
    return {"cgroupPeakBytes": peak, "workerPeakRssKiB": max(row["workerMaxRssKiB"] for row in rows),
            "childPeakRssKiB": max(row["maxChildRssKiB"] for row in rows), "events": events,
            "wallMs": report["workerWallMs"], "peakWith25PercentMarginBytes": math.ceil(peak * 1.25),
            "phaseHeadroomPass": not any(events.values()) and math.ceil(peak * 1.25) < CAP}


def analyze():
    old_source = (ROOT / "routing/input_import.py").read_text()
    new_source = (ROOT / "routing/keyed_import.py").read_text()
    expected = old_source[old_source.index("def import_maneuvers("):]
    expected = expected.replace('before = {road["id"] for road in original.roads}',
                                'before = RoadKeys(original.roads)\n    if measurements is not None: measurements["originalRoadKeys"] = before.summary()')
    expected = expected.replace('restored = [road for road in base.roads if road["id"] not in before]',
                                'restored = before.restored(base.roads)\n    del before')
    expected = expected.replace('        lookup = road_lookup(base) if candidates else {}',
                                '        if observe: observe(f"baseReady{iterations}")\n        lookup = road_lookup(base) if candidates else {}\n        if observe: observe(f"lookupReady{iterations}")')
    actual = new_source[new_source.index("def import_maneuvers("):]
    assert ast.dump(ast.parse(expected)) == ast.dump(ast.parse(actual))
    preparation = {}
    for mode in ("isolated", "batched"):
        preparation[mode] = {}
        for case in ("calibration", "candidate"):
            name = f"{mode}-{case}"
            report = read(f"{name}-report.json")
            identity = read(f"{name}-identity.json")
            frozen = read(f"old-{case}-report.json")
            assert report["runId"] == identity["runId"]
            for script, sha in report["scripts"].items():
                assert hashlib.sha256((ROOT / "routing" / script).read_bytes()).hexdigest() == sha, script
            assert report["mode"] == mode and report["case"] == case
            assert report["xmlByteIdentical"] and not report["fullGraphBuilt"] and not report["coverageVerified"]
            assert report["candidate"] == frozen["candidate"]
            assert report["publicApiCalls"] == 0 and report["network"] == "none"
            assert len(report["fixtures"]) == 6 and all(row["graphAndAuditIdentical"] for row in report["fixtures"])
            for item in ("car-roads.osm", "selected-ids.txt"):
                assert report["artifacts"][item] == frozen["artifacts"][item]
            lifetime = report["selection"]["processLifetime"]
            assert lifetime["selectorExitedBeforeCompletion"] and lifetime["selectorPid"] != lifetime["parentPid"]
            if case == "candidate":
                proof = HERE / f"{mode}-calibration-report.json"
                assert report["calibrationReportSha256"] == hashlib.sha256(proof.read_bytes()).hexdigest()
                assert report["admission"]["decision"] == "hold"
            preparation[mode][case] = {**resources(report), "xml": report["artifacts"]["car-roads.osm"],
                                      "census": report["candidate"], "selectorLifetime": lifetime}
    imports = {}
    for case in ("downtown-v2", "corridor-v3", "wide-v3", "hour-v3"):
        report = read(f"keys-{case}-report.json")
        old = read(f"old-keys-{case}-manifest.json")
        manifest = read(f"keys-{case}-manifest.json")
        for script, sha in manifest["scripts"].items():
            assert hashlib.sha256((ROOT / "routing" / script).read_bytes()).hexdigest() == sha, script
        assert report["graphIdentity"] == old["graphIdentity"]
        assert report["publicApiCalls"] == 0 and not report["coverageVerified"]
        assert len(report["artifacts"]) == {"downtown-v2": 4, "corridor-v3": 6, "wide-v3": 7, "hour-v3": 7}[case]
        assert all(value == old["artifacts"][name] for name, value in report["artifacts"].items())
        assert all(value["sha256"] == report["identicalArtifactSha256"][name] for name, value in report["artifacts"].items())
        keys = report["importStages"]["originalRoadKeys"]
        assert keys["payloadBytes"] == keys["roads"] * 13
        imports[case] = {**resources(report), "graphIdentity": report["graphIdentity"], "states": report["states"],
                         "arcs": report["transitions"], "importMs": report["importMs"], "roadKeys": keys,
                         "identicalArtifacts": len(report["artifacts"])}
    current = read("keys-hour-v3-report.json")
    assert "qualificationReport" in current["reusedQualification"] and "nativeVerification" in current["reusedQualification"]
    native, qualified = read("frozen-native-verification.json"), read("frozen-qualification-report.json")
    assert native["graphIdentity"] == qualified["graphIdentity"] == current["graphIdentity"]
    assert native["sourceManifestSha256"] == hashlib.sha256((HERE / "old-keys-hour-v3-manifest.json").read_bytes()).hexdigest()
    assert native["costComparisons"] == current["states"] * 45 and native["membershipComparisons"] == current["states"] * 40
    assert qualified["costComparisons"] == current["states"] * 5 and qualified["boundedCostComparisons"] == current["states"] * 40
    assert native["interiorDestinationComparisons"] == qualified["interiorDestinationComparisons"] == 2
    for key, name in (("nativeVerification", "frozen-native-verification.json"), ("qualificationReport", "frozen-qualification-report.json")):
        path = HERE / name
        assert current["reusedQualification"][key] == {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    summary = {"preparation": preparation, "imports": imports,
               "oldPreparation": {case: resources(read(f"old-{case}-report.json")) for case in ("calibration", "candidate")},
               "oldCurrentBuild": resources(read("old-current-build-report.json")),
               "oldCurrentRebuild": resources(read("old-current-rebuild-report.json")),
               "newLargerGraphBuilt": False, "coverageVerified": False,
               "scope": "Measured complete cgroup peaks, separate worker/child RSS, exact frozen bytes. Resource observations have uncontrolled host/cache conditions; no causal timing claim. Existing graph/native qualification reused, no fresh route search or contour. Preparation headroom alone does not admit the larger graph."}
    return summary


if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2, sort_keys=True))
