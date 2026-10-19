"""Check complete cut inventory and staged preparation without routing API calls."""

import hashlib
import json
import mmap
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
DATA = ROOT / "data"
RUNS = {"cuts": "buffer-cut-inventory-v1", "calibration": "staged-calibration-v2-r4", "candidate": "staged-candidate-v2"}


def read(path): return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream: return hashlib.file_digest(stream, "sha256").hexdigest()


def check(path, expected):
    assert path.stat().st_size == expected["bytes"], path
    assert sha(path) == expected["sha256"], path


def run():
    reports = {}
    for key, name in RUNS.items():
        directory = DATA / "coverage-pilot" / name
        report, identity = read(directory / "report.json"), read(directory / "run-identity.json")
        assert report == read(HERE / f"{key}-report.json")
        encoded = json.dumps({field: value for field, value in identity.items() if field != "runId"}, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        assert hashlib.sha256(encoded).hexdigest() == identity["runId"] == report["runId"]
        for file, expected in report["artifacts"].items(): check(directory / file, expected)
        for file, expected in report["scripts"].items():
            assert sha(directory / "recipe" / file) == sha(ROOT / "routing" / file) == expected
        if key != "cuts": assert read(directory / "recipe/profile.json") == report["profile"]
        assert report["memoryLimit"] == report["memorySwapLimit"] == "4g" and report["network"] == "none"
        assert report["publicApiCalls"] == 0 and not report["coverageVerified"] and not report["routeEligibilityVerified"]
        for sample in report["resourceCheckpoints"].values():
            assert int(sample["memory.max"]) == 4294967296
            assert sample["memory.swap.max"] == sample["memory.swap.current"] == sample["memory.swap.peak"] == "0"
            for event in ("oom", "oom_kill", "oom_group_kill"): assert int(sample["memory.events"][event]) == 0
        assert report["sampling"]["samples"] > 1 and report["sampling"]["intervalSeconds"] == .2
        reports[key] = report
    source = DATA / "compact-pilot/compact-v1-buffer-v3"
    manifest, summary, audit = (read(source / file) for file in ("manifest.json", "summary.json", "import-audit.json"))
    cuts = reports["cuts"]
    assert cuts["sourceManifestSha256"] == sha(source / "manifest.json")
    for file, expected in manifest["artifacts"].items(): check(source / file, expected)
    nodes = read(DATA / "coverage-pilot" / RUNS["cuts"] / "cut-nodes.json")
    assert {row["node"] for row in nodes} == set(audit["cutExitNodes"])
    assert len(nodes) == cuts["auditedCutNodes"] == 337
    assert sum(row["stateCount"] for row in nodes) == cuts["cutStates"] == 407
    assert all(row["links"] for row in nodes) and cuts["nodesWithoutBoundaryLinks"] == 0
    for origin in cuts["origins"]:
        oracle = source / "oracles" / f"{origin['origin']}.u64le"
        with oracle.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as labels:
            for row in nodes:
                witness = row["origins"][origin["origin"]]
                if witness["state"] is not None:
                    assert struct.unpack_from("<Q", labels, witness["state"] * 8)[0] == witness["costMs"]
                    assert witness["road"]["to"] == row["node"] and witness["road"]["toPoint"] == row["point"]
        first = min(row["origins"][origin["origin"]]["costMs"] for row in nodes if row["origins"][origin["origin"]]["costMs"] is not None)
        assert first == origin["firstCutExitMs"] == next(item for item in summary["origins"] if item["origin"] == origin["origin"])["firstCutExitMs"]
        for budget in origin["budgets"]:
            reached = [row for row in nodes if row["origins"][origin["origin"]]["costMs"] is not None and row["origins"][origin["origin"]]["costMs"] <= budget["budgetMs"]]
            assert len(reached) == budget["reachableCutNodes"]
            assert budget["bySide"] == {side: sum(side in row["outsideSides"] for row in reached) for side in ("north", "east", "south", "west")}
    calibration, candidate = reports["calibration"], reports["candidate"]
    assert calibration["matchesFrozenXml"] is True and len(calibration["fixtures"]) == 6
    assert all(row["graphAndAuditIdentical"] for row in calibration["fixtures"])
    assert calibration["artifacts"]["car-roads.osm"] == manifest["sourceArtifact"]
    assert calibration["candidate"] == read(DATA / "coverage-pilot/san-diego-tijuana-buffer-preflight-r2/report.json")["candidate"]
    assert candidate["scripts"] == calibration["scripts"]
    assert candidate["calibrationReportSha256"] == sha(DATA / "coverage-pilot" / RUNS["calibration"] / "report.json")
    assert candidate["cutReportSha256"] == sha(DATA / "coverage-pilot" / RUNS["cuts"] / "report.json")
    assert candidate["measuredImportReportSha256"] == sha(DATA / "input-pilot/input-v1-buffer-v3/report.json")
    assert candidate["frozenBufferManifestSha256"] == calibration["frozenBufferManifestSha256"] == sha(source / "manifest.json")
    for report in (calibration, candidate):
        check(DATA / "valhalla-v2/region.osm.pbf", report["regionArtifact"])
        assert report["sourceBuildSha256"] == sha(DATA / "valhalla-v2/build-complete.json")
        assert not report["fullGraphBuilt"]
    assert candidate["candidate"]["sourceNodes"] > calibration["candidate"]["sourceNodes"]
    assert candidate["candidate"]["roadStatesLowerBound"] <= candidate["candidate"]["roadStatesUpperBound"] <= candidate["candidate"]["historyStatesUpperBound"]
    assert not candidate["capacity"]["fullGraphAdmitted"]
    rejected = read(HERE / "rejected-simple-comparison.json")
    assert not rejected["graphIdentical"] and rejected["outputs"][0]["graphIdentity"] != rejected["outputs"][1]["graphIdentity"]
    assert sha(ROOT / "routing/input_import.py") == rejected["importerSha256"]
    assert sha(HERE / "rejected-simple-source.osm") == rejected["sourceFixtureSha256"]
    for row in rejected["outputs"]:
        assert sha(HERE / f"rejected-simple-{row['kind']}-car-roads.osm") == row["xmlSha256"]
    attempts = []
    for name in ("staged-calibration-v2", "staged-calibration-v2-r2", "staged-calibration-v2-r3"):
        directory = DATA / "coverage-pilot" / name
        identity = read(directory / "run-identity.json")
        for file, expected in identity["scripts"].items(): assert sha(directory / "recipe" / file) == expected
        attempts.append({"name": name, "identitySha256": sha(directory / "run-identity.json"), "completedReport": (directory / "report.json").exists()})
    comparison = {"cutNodes": len(nodes), "cutStates": 407, "origins": cuts["origins"], "boundaryNodesBySide": {side: sum(side in row["outsideSides"] for row in nodes) for side in ("north", "east", "south", "west")},
                  "calibrationXmlByteIdentical": True, "candidateBounds": candidate["profile"]["bbox"], "candidateCounts": candidate["candidate"],
                  "capacity": candidate["capacity"], "resources": {key: {"checkpoints": report["resourceCheckpoints"], "sampling": report["sampling"], "workerWallMs": report["workerWallMs"]} for key, report in reports.items()},
                  "preservedAttempts": attempts, "publicRoutingApiCalls": 0, "newGraphBuilt": False, "coverageVerified": False}
    (HERE / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    print(json.dumps({key: comparison[key] for key in ("cutNodes", "boundaryNodesBySide", "candidateBounds", "candidateCounts", "capacity")}, indent=2))


if __name__ == "__main__": run()
