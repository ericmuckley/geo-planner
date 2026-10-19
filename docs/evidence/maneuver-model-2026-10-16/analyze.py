"""Verify reproducibility, native results, source provenance and frozen prior assets."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


first = load(HERE / "first-manifest.json")
repeat = load(HERE / "repeat-manifest.json")
assert first["runId"] == repeat["runId"]
assert first["graphIdentity"] == repeat["graphIdentity"]
stable = [name for name in first["artifacts"] if name != "summary.json"]
assert all(first["artifacts"][name] == repeat["artifacts"][name] for name in stable)
for label, manifest in (("first", first), ("repeat", repeat)):
    assert sha(HERE / f"{label}-summary.json") == manifest["artifacts"]["summary.json"]["sha256"]
local = ROOT / "data/model-pilot/downtown-maneuvers-v2"
for name, artifact in repeat["artifacts"].items():
    path = local / name
    assert path.stat().st_size == artifact["bytes"] and sha(path) == artifact["sha256"]
assert sha(HERE / "first-import-audit.json") == repeat["artifacts"]["import-audit.json"]["sha256"]
assert sha(HERE / "first-source-samples.osm") == repeat["artifacts"]["source-samples.osm"]["sha256"]
for name, expected in repeat["scripts"].items():
    assert sha(ROOT / "routing" / name) == expected
reference = ROOT / "data/reference-pilot/downtown-static-v1"
reference_manifest = load(reference / "manifest.json")
assert repeat["sourceReferenceRunId"] == reference_manifest["runId"]
assert repeat["sourceGraphIdentity"] == reference_manifest["graphIdentity"]
assert sha(reference / "roads.osm") == repeat["sourceXmlSha256"]
for name, artifact in reference_manifest["artifacts"].items():
    path = reference / name
    assert path.stat().st_size == artifact["bytes"] and sha(path) == artifact["sha256"]
summary = load(HERE / "repeat-summary.json")
previous = load(HERE / "first-summary.json")
assert summary["interiorDestinations"] == previous["interiorDestinations"]
assert summary["replayChecks"] == previous["replayChecks"]
assert summary["sourceSamples"] == previous["sourceSamples"]
assert [{key: value for key, value in origin.items() if key != "fullSearchMs"} for origin in summary["origins"]] == [
    {key: value for key, value in origin.items() if key != "fullSearchMs"} for origin in previous["origins"]]
native = load(HERE / "repeat-native-verification.json")
assert native["sourceRunId"] == repeat["runId"] and native["sourceManifestSha256"] == sha(HERE / "repeat-manifest.json")
assert native["graphIdentity"] == repeat["graphIdentity"]
assert native["publicApiCalls"] == summary["publicApiCalls"] == previous["publicApiCalls"] == 0
assert native["compilation"]["binarySha256"] == sha(local / "native_search")
old_native = load(ROOT / "docs/evidence/native-routing-2026-10-16/repeat-summary.json")
assert native["compilation"]["binarySha256"] == old_native["compilation"]["binarySha256"]
patterns = {rule["id"]: rule for rule in load(HERE / "first-import-audit.json")["viaWayRestrictions"]}
assert all(not check["allowed"] and check["blockedStep"] == len(patterns[check["restrictionId"]]["roads"]) - 1
           for check in summary["replayChecks"])
assert all(origin["budgets"][-1]["boundaryReachedWithinBudget"] for origin in summary["origins"])
report = {"runId": repeat["runId"], "graphIdentity": repeat["graphIdentity"],
          "identicalArtifacts": stable, "v1ReferenceUnchanged": True, "nativeExecutableUnchanged": True,
          "replayAndDestinationResultsIdentical": True, "all40ReplaysBlockAtFinalEntry": True,
          "allLongBudgetCasesHitCut": True, "publicApiCalls": 0,
          "pythonFullCostComparisonsPerRun": summary["costComparisons"],
          "pythonBoundedCostComparisonsPerRun": summary["boundedCostComparisons"],
          "interiorCostComparisonsPerRun": summary["interiorDestinationComparisons"],
          "boundedInteriorMembershipComparisonsPerRun": summary["boundedDestinationMembershipComparisons"],
          "nativeCostComparisons": native["costComparisons"], "nativeMembershipComparisons": native["membershipComparisons"]}
(HERE / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
