"""Verify sparse-source equality, unchanged graph bytes and resource admission."""

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT / "routing"))
from resource_admission import evaluate


def read(path): return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream: return hashlib.file_digest(stream, "sha256").hexdigest()


def check(path, expected):
    assert path.stat().st_size == expected["bytes"], path
    assert sha(path) == expected["sha256"], path


RUNS = {"profile": ("resource-pilot/frozen-import-profile-v1", "identity.json"),
        "import": ("resource-pilot/paged-import-v1", "run-identity.json"),
        "calibration": ("sparse-pilot/sparse-calibration-v1", "identity.json"),
        "candidate": ("sparse-pilot/sparse-candidate-v1", "identity.json"),
        "candidate-paged": ("sparse-pilot/sparse-paged-candidate-v1", "identity.json")}


def run():
    reports = {}
    for key, (relative, identity_name) in RUNS.items():
        directory = ROOT / "data" / relative
        report, identity = read(directory / "report.json"), read(directory / identity_name)
        assert report == read(HERE / f"{key}-report.json")
        payload = {name: value for name, value in identity.items() if name != "runId"}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        assert hashlib.sha256(encoded).hexdigest() == identity["runId"] == report["runId"]
        report = {**identity, **report}
        for name, expected in report["scripts"].items():
            assert sha(ROOT / "routing" / name) == sha(directory / "recipe" / name) == expected
        for name, expected in report.get("artifacts", {}).items(): check(directory / name, expected)
        for resource in report["resourceCheckpoints"].values():
            assert int(resource["memory.max"]) == 4294967296
            assert resource["memory.swap.max"] == resource["memory.swap.current"] == resource["memory.swap.peak"] == "0"
            for event in ("oom", "oom_kill", "oom_group_kill", "max"): assert int(resource["memory.events"][event]) == 0
        assert report["publicApiCalls"] == 0 and report["network"] == "none" and not report["coverageVerified"]
        assert report["sampling"]["samples"] > 1
        reports[key] = report
    frozen = ROOT / "data/compact-pilot/compact-v1-buffer-v3"
    manifest = read(frozen / "manifest.json")
    for name, expected in manifest["artifacts"].items(): check(frozen / name, expected)
    profiled = ROOT / "data/resource-pilot/frozen-import-profile-v1"
    profile = reports["profile"]
    assert profile["childReportSha256"] == sha(profiled / "import/report.json")
    assert profile["childManifestSha256"] == sha(profiled / "import/manifest.json")
    child = read(profiled / "import/report.json")
    for name, expected in child["artifacts"].items(): check(profiled / "import" / name, expected)
    for report in (child, reports["import"]):
        assert report["graphIdentity"] == manifest["graphIdentity"]
        assert len(report["identicalArtifactSha256"]) == 7
        for name, expected in report["artifacts"].items(): assert expected == manifest["artifacts"][name]
    imported = reports["import"]
    assert len(imported["parityReports"]) == 4
    for case, expected in imported["parityReports"].items():
        assert sha(ROOT / "data/input-pilot" / f"input-v1-{case}" / "report.json") == expected
    assert imported["cacheAdvice"]["requests"]
    native = {key: read(ROOT / "data/coverage-pilot" / relative / "report.json") for key, relative in
              (("calibration", "staged-calibration-v2-r4"), ("candidate", "staged-candidate-v2"))}
    for key in ("calibration", "candidate", "candidate-paged"):
        report = reports[key]
        prior_key = "calibration" if key == "calibration" else "candidate"
        previous_dir = ROOT / "data/coverage-pilot" / ("staged-calibration-v2-r4" if prior_key == "calibration" else "staged-candidate-v2")
        assert report["priorReportSha256"] == sha(previous_dir / "report.json")
        assert report["artifacts"]["car-roads.osm"] == native[prior_key]["artifacts"]["car-roads.osm"]
        assert report["candidate"] == native[prior_key]["candidate"]
        assert report["xmlByteIdentical"] and not report["fullGraphBuilt"]
        assert len(report["fixtures"]) == 6 and all(row["graphAndAuditIdentical"] for row in report["fixtures"])
        assert report["baseImageId"] == native[prior_key]["imageId"] and report["readerVersion"] == "4.3.1"
        assert report["selection"]["nodesScanned"] == 89776916 and report["selection"]["waysScanned"] == 10435256
        assert report["selection"]["relationsScanned"] == 113780
        check(ROOT / "data/valhalla-v2/region.osm.pbf", report["sourceArtifact"])
    assert reports["candidate-paged"]["cacheAdvice"]["requests"]
    for key in ("candidate", "candidate-paged"):
        assert reports[key]["calibrationReportSha256"] == sha(ROOT / "data/sparse-pilot/sparse-calibration-v1/report.json")
    lock = read(ROOT / "routing/tools/pyosmium-v1.json")
    image = read(ROOT / "data/tools/sparse-image-v1.json")
    assert sha(ROOT / "routing/tools/pyosmium-v1.json") == image["wheelsLockSha256"]
    assert sha(ROOT / "routing/sparse.Dockerfile") == image["dockerfileSha256"]
    for wheel in lock["wheels"]: check(ROOT / "data/tools/pyosmium-v1" / wheel["filename"], wheel)
    for key in ("calibration", "candidate", "candidate-paged"):
        assert reports[key]["imageId"] == image["imageId"] and reports[key]["wheelLockSha256"] == image["wheelsLockSha256"]
    unadvised = evaluate(reports["candidate"], imported, reports["calibration"]["candidate"], reports["candidate"]["candidate"])
    admission = evaluate(reports["candidate-paged"], imported, reports["calibration"]["candidate"], reports["candidate-paged"]["candidate"])
    bindings = {key: sha(ROOT / "data" / relative / "report.json") for key, (relative, _) in RUNS.items()}
    admission.update({"sourceReportSha256": bindings, "admissionRuleSha256": sha(ROOT / "routing/resource_admission.py"),
                      "sourceXmlArtifact": reports["candidate-paged"]["artifacts"]["car-roads.osm"], "profile": reports["candidate-paged"]["profile"]})
    (HERE / "admission.json").write_text(json.dumps(admission, indent=2) + "\n")
    rows = {}
    for key, report in reports.items():
        final = max(report["resourceCheckpoints"].values(), key=lambda item: item["elapsedMs"])
        rows[key] = {"cgroupPeakBytes": int(final["memory.peak"]), "workerMaxRssKiB": final["workerMaxRssKiB"],
                     "maxChildRssKiB": final["maxChildRssKiB"], "sampling": report["sampling"], "workerWallMs": report.get("workerWallMs")}
    comparison = {"resources": rows, "unadvisedSparseAdmission": unadvised, "admission": admission, "allGraphAndSourceArtifactsIdentical": True,
                  "publicRoutingApiCalls": 0, "toolWheelDownloadBytes": sum(wheel["bytes"] for wheel in lock["wheels"]),
                  "newRoadDownloads": 0, "newGraphBuilt": False, "coverageVerified": False}
    (HERE / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    print(json.dumps(admission, indent=2))


if __name__ == "__main__": run()
