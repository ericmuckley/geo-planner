"""Check lean qualification equality and the measured next-region admission rule."""

import ast
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT / "routing"))
from anchors import digest
from hour_admission import evaluate, peak
from lean_qualification import functional_summary


def read(path): return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream: return hashlib.file_digest(stream, "sha256").hexdigest()


def check(path, expected):
    assert path.stat().st_size == expected["bytes"], path
    assert sha(path) == expected["sha256"], path


def run():
    runs = {"lean": "qualification-pilot/virtual-sink-v1", "calibration": "coverage-pilot/hour-calibration-v1",
            "candidate": "coverage-pilot/hour-candidate-v1"}
    reports = {}
    for key, relative in runs.items():
        directory = ROOT / "data" / relative
        identity, report = read(directory / "identity.json"), read(directory / "report.json")
        assert identity["runId"] == digest({name: value for name, value in identity.items() if name != "runId"})
        assert report["runId"] == identity["runId"]
        assert read(HERE / f"{key}-identity.json") == identity
        assert read(HERE / f"{key}-report.json") == report
        for name, expected in identity["scripts"].items():
            assert sha(ROOT / "routing" / name) == sha(directory / "recipe" / name) == expected
        for name, expected in report["artifacts"].items(): check(directory / name, expected)
        measured, pressure = peak(report)
        assert not pressure and measured < 4 * 1024 ** 3
        assert identity["cpus"] == 2 and identity["network"] == "none"
        assert report["publicApiCalls"] == 0 and not report["fullGraphBuilt"] and not report["coverageVerified"]
        reports[key] = report
    lean, calibration, candidate = (reports[key] for key in ("lean", "calibration", "candidate"))
    for old, name in (("queue_qualification.py", "qualify"), ("wide.py", "diagnose_routes")):
        def body(path):
            return ast.dump(next(node for node in ast.parse(path.read_text()).body if isinstance(node, ast.FunctionDef) and node.name == name))
        assert body(ROOT / "routing" / old) == body(ROOT / "routing/lean_checks.py")
    source = ROOT / "data/compact-pilot/increment-v3"
    manifest = read(source / "manifest.json")
    for name, expected in manifest["artifacts"].items(): check(source / name, expected)
    assert lean["sourceManifestSha256"] == sha(source / "manifest.json")
    assert lean["functionalSummaryIdentical"] and lean["qualificationHeadroomRestored"]
    assert functional_summary(read(ROOT / "data/qualification-pilot/virtual-sink-v1/summary.json")) == functional_summary(read(source / "summary.json"))
    for name in lean["identicalArtifactSha256"]:
        assert lean["artifacts"][name] == manifest["artifacts"][name]
    assert len(lean["identicalArtifactSha256"]) == 6
    assert lean["reusedNativeEvidence"]["reportSha256"] == sha(source / "native-verification.json")
    frozen = ROOT / "data/compact-pilot/compact-v1-buffer-v3"
    assert lean["calibration"]["sourceManifestSha256"] == sha(frozen / "manifest.json")
    previous_destinations = read(frozen / "summary.json")["interiorDestinations"]
    assert len(lean["calibration"]["partialDestinations"]) == 2
    for row in lean["calibration"]["partialDestinations"]:
        assert {key: value for key, value in row.items() if key != "oracleMs"} in previous_destinations
    assert lean["costComparisons"] == 2938992 * 5 and lean["boundedCostComparisons"] == 2938992 * 40
    assert lean["interiorDestinationComparisons"] == 2
    prepared = ROOT / "data/sparse-pilot/sparse-paged-candidate-v1"
    assert calibration["candidate"] == read(prepared / "report.json")["candidate"]
    assert calibration["xmlByteIdentical"] and calibration["artifacts"]["car-roads.osm"] == manifest["sourceArtifact"]
    assert len(calibration["fixtures"]) == 6 and all(row["graphAndAuditIdentical"] for row in calibration["fixtures"])
    assert candidate["calibrationReportSha256"] == sha(ROOT / "data/coverage-pilot/hour-calibration-v1/report.json")
    assert not candidate["xmlByteIdentical"]
    tools = read(ROOT / "data/tools/sparse-image-v1.json")
    for key in ("calibration", "candidate"):
        report, directory = reports[key], ROOT / "data" / runs[key]
        assert report["imageId"] == tools["imageId"] and report["baseImageId"] == tools["baseImageId"]
        assert report["profileSha256"] == sha(ROOT / "routing/profiles/coverage-hour-v1.json") == sha(directory / "recipe/coverage-hour-v1.json")
        assert report["wheelLockSha256"] == tools["wheelsLockSha256"] == sha(directory / "recipe/pyosmium-v1.json")
        assert report["qualificationReportSha256"] == sha(ROOT / "data/qualification-pilot/virtual-sink-v1/report.json")
        assert report["sourceManifestSha256"] == sha(source / "manifest.json")
    check(ROOT / "data/valhalla-v2/region.osm.pbf", candidate["regionArtifact"])
    built, rebuilt = read(source / "build-report.json"), read(ROOT / "data/compact-pilot/increment-v3-rebuild/build-report.json")
    assert candidate["buildReportSha256"] == sha(source / "build-report.json")
    assert candidate["rebuildReportSha256"] == sha(ROOT / "data/compact-pilot/increment-v3-rebuild/build-report.json")
    admission = evaluate(calibration, candidate, candidate["candidate"], built, rebuilt, lean)
    assert admission == candidate["admission"]
    admission.update({"candidateSourceArtifact": candidate["artifacts"]["car-roads.osm"], "profile": candidate["profile"],
                      "sourceReportSha256": {key: sha(ROOT / "data" / relative / "report.json") for key, relative in runs.items()},
                      "admissionRuleSha256": sha(ROOT / "routing/hour_admission.py")})
    (HERE / "admission.json").write_text(json.dumps(admission, indent=2) + "\n")
    resources = {}
    for key, report in {**reports, "previousQualification": read(source / "qualification-report.json")}.items():
        last = max(report["resourceCheckpoints"].values(), key=lambda row: row["elapsedMs"])
        resources[key] = {"cgroupPeakBytes": int(last["memory.peak"]), "workerMaxRssKiB": last["workerMaxRssKiB"],
                          "maxChildRssKiB": last["maxChildRssKiB"], "workerWallMs": report["workerWallMs"], "sampling": report["sampling"]}
    comparison = {"resources": resources, "candidateCounts": candidate["candidate"], "admission": admission,
                  "functionalSummaryIdentical": True, "fullOracleFilesIdentical": 5, "packedCsrIdentical": True,
                  "partialDestinationsIdentical": 2, "oldBufferSinkCalibrationComparisons": 2,
                  "nativeEvidenceReusedByExactIdentity": True, "newNativeRuns": 0, "newGraphBuilt": False,
                  "publicRoutingApiCalls": 0, "newDownloads": 0, "coverageVerified": False}
    (HERE / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    print(json.dumps({"qualificationHeadroomRestored": True, "admission": admission}, indent=2))


if __name__ == "__main__": run()
