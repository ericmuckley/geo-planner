"""Verify the exact storage calibration and recompute the partial-source screen."""

import argparse
import hashlib
import json
from pathlib import Path

from hour_admission import peak
from region_release import check_resources
from six_hour_preflight import admission


ROOT = Path(__file__).resolve().parent.parent
PAYLOADS = {"graph.json", "import-audit.json", "graph.csr", "graph.csr.gz", "barrier-roads.osm",
            "barrier-source-samples.osm", "uncertain-crossings-source.osm", "scoped-fixtures.json"}


def load(path): return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def artifact(path): return {"bytes": path.stat().st_size, "sha256": sha(path)}


def check_recipe(directory, scripts):
    for name, expected in scripts.items():
        if sha(directory / "recipe" / name) != expected or sha(ROOT / "routing" / name) != expected:
            raise ValueError(f"Recipe differs: {name}")


def run(output):
    if output.exists(): raise ValueError("Preserve the completed result")
    reference_dir = ROOT / "data/compact-pilot/two-hour-region-v2"
    reference = load(reference_dir / "manifest.json")
    check_recipe(reference_dir, reference["scripts"])
    reference_sha = sha(reference_dir / "manifest.json")
    reports, manifests, fixtures = {}, {}, {}
    for stage, name in (("build", "source-outgoing-v1"), ("rebuild", "source-outgoing-v1-rebuild")):
        directory = ROOT / "data/compact-pilot" / name
        manifest = load(directory / "build-manifest.json")
        report = load(directory / "build-report.json")
        check_recipe(directory, manifest["scripts"])
        if (manifest["previousManifestSha256"] != reference_sha or manifest["profile"] != reference["profile"] or
                manifest["imageId"] != reference["imageId"] or manifest["graphIdentity"] != reference["graphIdentity"] or
                artifact(directory / "build-report.json") != manifest["artifacts"]["build-report.json"] or
                set(report["identicalQualifiedArtifacts"]) != PAYLOADS):
            raise ValueError(f"Calibration provenance differs: {stage}")
        for name in PAYLOADS:
            expected = reference["artifacts"][name]
            if manifest["artifacts"][name] != expected or artifact(directory / name) != expected:
                raise ValueError(f"Qualified bytes differ: {stage}/{name}")
        fixture = load(directory / "storage-fixtures.json")
        if (fixture["caseCount"] != 17 or fixture["fullCostComparisons"] != 416 or
                fixture["boundedCostComparisons"] != 1248 or fixture["partialComparisons"] != 320 or
                not all(row["sourceSortedBuilds"] > 0 for row in fixture["cases"])):
            raise ValueError("Missing fresh scoped storage fixtures")
        fixtures[stage] = artifact(directory / "storage-fixtures.json")
        reports[stage], manifests[stage] = report, manifest
    build_dir = ROOT / "data/compact-pilot/source-outgoing-v1"
    if (manifests["build"]["scripts"] != manifests["rebuild"]["scripts"] or
            manifests["rebuild"]["rebuildManifestSha256"] != sha(build_dir / "build-manifest.json") or
            set(reports["rebuild"]["identicalRebuildArtifacts"]) != PAYLOADS):
        raise ValueError("Repeat does not reproduce the same producer/input binding")

    qualified = load(reference_dir / "qualification-report.json")
    native = load(reference_dir / "native-verification.json")
    cuts_dir = ROOT / "data/compact-pilot/two-hour-region-v2-cuts"
    cuts = load(cuts_dir / "report.json")
    summary = load(reference_dir / "summary.json")
    states = summary["states"]
    for name in ("build-report.json", "qualification-report.json", "summary.json"):
        if artifact(reference_dir / name) != reference["artifacts"][name]: raise ValueError(name)
    release = load(reference_dir / "release.json")
    if (release["sourceManifestSha256"] != reference_sha or
            release["nativeReportSha256"] != sha(reference_dir / "native-verification.json") or
            release["cutReportSha256"] != sha(cuts_dir / "report.json")):
        raise ValueError("Reused release bindings differ")
    for proof in (native, cuts):
        if proof["sourceManifestSha256"] != reference_sha or proof["graphIdentity"] != reference["graphIdentity"]:
            raise ValueError("Reused proof belongs to different bytes")
    if (native["compilation"]["binarySha256"] != sha(reference_dir / "native_search") or
            native["compilation"]["sourceSha256"] != sha(ROOT / "routing/native_search.cpp") or
            native["costComparisons"] != states * 45 or native["membershipComparisons"] != states * 40 or
            native["interiorDestinationComparisons"] != 2 or qualified["costComparisons"] != states * 5 or
            qualified["boundedCostComparisons"] != states * 40 or qualified["interiorDestinationComparisons"] != 2 or
            cuts["nodesWithoutBoundaryLinks"] or cuts["auditedCutNodes"] != 805 or cuts["cutStates"] != 1173):
        raise ValueError("Incomplete reused regional qualification")
    for name, expected in cuts["artifacts"].items():
        if artifact(cuts_dir / name) != expected: raise ValueError(name)

    candidate_dir = ROOT / "data/coverage-pilot/six-hour-cached-v1"
    candidate = load(candidate_dir / "report.json")
    previous = load(ROOT / "data/coverage-pilot/two-hour-region-v2/report.json")
    original = load(reference_dir / "build-report.json")
    observed = {name: peak(report) for name, report in {**reports, "qualification": qualified,
                "cuts": cuts, "preparation": candidate}.items()}
    resources = {stage: check_resources(report) for stage, report in reports.items()}
    forecast = admission(candidate["candidate"], previous["candidate"], original, observed, False)
    result = {"producerSha256": sha(Path(__file__)), "graphIdentity": reference["graphIdentity"],
              "sourceManifestSha256": reference_sha, "identicalPayloads": sorted(PAYLOADS),
              "buildReportSha256": {stage: sha(ROOT / "data/compact-pilot" / name / "build-report.json")
                  for stage, name in (("build", "source-outgoing-v1"), ("rebuild", "source-outgoing-v1-rebuild"))},
              "resources": resources, "fixtureArtifacts": fixtures,
              "reusedProofs": {"qualification": artifact(reference_dir / "qualification-report.json"),
                  "native": artifact(reference_dir / "native-verification.json"), "cuts": artifact(cuts_dir / "report.json"),
                  "scope": "Existing independent/native/cut evidence remains valid on the exact graph bytes. These regional searches and their resources were not rerun; only construction storage changed."},
              "candidateReportSha256": sha(candidate_dir / "report.json"), "admission": forecast,
              "workerWallMs": {stage: report["workerWallMs"] for stage, report in reports.items()},
              "publicApiCalls": 0, "coverageVerified": False, "largerGraphBuilt": False,
              "scope": "One exact storage change, fresh full build/rebuild/fixture resources and unchanged regional proof reuse. The partial-source screen is a heuristic, not full six-hour admission or a memory lower bound. Serving graph/code remain unchanged. This host-side checksum analysis is not a new capped Linux construction measurement."}
    with output.open("x") as stream: json.dump(result, stream, indent=2, sort_keys=True); stream.write("\n")
    print(json.dumps({"resources": resources, "admission": forecast}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/resource-pilot/source-outgoing-validation-v1/result.json")
    run(parser.parse_args().output)
