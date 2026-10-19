"""Validate retained preflight products without loading any road graph into RAM."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check(path, expected):
    assert path.stat().st_size == expected["bytes"], path
    assert sha(path) == expected["sha256"], path


def run():
    reports = []
    for label, name in (("first", "san-diego-tijuana-buffer-preflight-v1"), ("repeat", "san-diego-tijuana-buffer-preflight-r2")):
        directory = ROOT / "data/coverage-pilot" / name
        report, identity = read(directory / "report.json"), read(directory / "run-identity.json")
        assert report == read(HERE / f"{label}-report.json")
        assert identity == read(HERE / f"{label}-identity.json")
        encoded = json.dumps({key: value for key, value in identity.items() if key != "runId"}, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        assert hashlib.sha256(encoded).hexdigest() == report["runId"] == identity["runId"]
        for name, expected in report["artifacts"].items(): check(directory / name, expected)
        for name, expected in identity["scripts"].items():
            assert sha(directory / "recipe" / name) == expected
            if label == "repeat": assert sha(ROOT / "routing" / name) == expected
        assert read(directory / "recipe/coverage-buffer-v1.json") == report["profile"]
        for checkpoint in report["resourceCheckpoints"].values():
            assert int(checkpoint["memory.max"]) == 4 * 1024 ** 3
            for event in ("oom", "oom_kill", "oom_group_kill"):
                assert int(checkpoint["memory.events"][event]) == 0
        complete = report["resourceCheckpoints"]["candidateCensus"]
        assert int(complete["memory.peak"]) == 4 * 1024 ** 3
        assert int(complete["memory.events"]["max"]) > 0
        assert not report["coverageVerified"] and not report["fullGraphBuilt"]
        assert report["publicApiCalls"] == 0 and report["network"] == "none"
        bounds, old = report["calibration"], report["calibrationGraph"]
        assert bounds["roadStatesLowerBound"] <= old["roads"] <= bounds["roadStatesUpperBound"]
        assert old["states"] <= bounds["historyStatesUpperBound"]
        assert report["capacity"]["decision"] == "hold-for-compact-storage"
        assert report["capacity"]["admissionEstimateBytes"] > report["capacity"]["capBytes"]
        reports.append(report)
    assert reports[0]["candidate"] == reports[1]["candidate"]
    assert reports[0]["calibration"] == reports[1]["calibration"]
    stable = ("region.osm.pbf", "roads.osm", "car-roads.osm", "candidate.sqlite", "calibration.sqlite")
    for name in stable: assert reports[0]["artifacts"][name] == reports[1]["artifacts"][name]
    identity = read(HERE / "repeat-identity.json")
    check(ROOT / "data/valhalla-v2/region.osm.pbf", identity["regionArtifact"])
    calibration = ROOT / "data/barrier-pilot/san-diego-tijuana-wide-v3"
    assert sha(calibration / "manifest.json") == identity["calibrationManifestSha256"]
    assert sha(calibration / "rebuild-verification.json") == identity["calibrationRebuildSha256"]
    manifest = read(calibration / "manifest.json")
    for name, expected in manifest["artifacts"].items(): check(calibration / name, expected)
    for name, expected in manifest["scripts"].items(): assert sha(ROOT / "routing" / name) == expected
    comparison = {"candidateCountsIdentical": True, "calibrationCountsIdentical": True,
                  "identicalProducts": {name: reports[1]["artifacts"][name] for name in stable},
                  "parentAndPriorWideArtifactsUnchanged": True, "sameCapBothRuns": 4 * 1024 ** 3,
                  "zeroOomBothRuns": True, "preparationHitLimitBothRuns": True,
                  "capacityDecision": reports[1]["capacity"]["decision"], "fullGraphBuilt": False,
                  "scope": "Checksums/count intervals/resources only. No routing, contour, real-world eligibility or complete-coverage validation."}
    (HERE / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    run()
