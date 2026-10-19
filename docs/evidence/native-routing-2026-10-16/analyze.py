"""Reproduce the report aggregates and verify the retained/local artifacts."""

import hashlib
import json
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name):
    return json.loads((HERE / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_cases(summary):
    return [{key: case[key] for key in ("origin", "seeds", "budgetMs", "reachableStates", "scannedArcs",
                                      "firstCutExitMs", "boundaryReachedWithinBudget")} |
            {"payloads": {mode: {key: value[key] for key in ("payloadBytes", "payloadSha256")}
                          for mode, value in case["formats"].items()}} for case in summary["cases"]]


def aggregate(summary):
    rows = []
    for budget in summary["profile"]["budgetsMs"]:
        cases = [case for case in summary["cases"] if case["budgetMs"] == budget]
        row = {"budgetMs": budget, "pythonGraphMs": statistics.median(case["pythonGraphMs"]["p50"] for case in cases),
               "boundaryFlags": sum(case["boundaryReachedWithinBudget"] for case in cases)}
        for mode in ("labels", "membership"):
            values = [case["formats"][mode] for case in cases]
            row[mode] = {metric: statistics.median(value["timings"][metric]["p50"] for value in values)
                         for metric in ("sourceSetupMs", "searchMs", "encodeMs", "roundTripAndDecodeMs")}
            row[mode]["setupAndSearchMs"] = statistics.median(
                statistics.median(sample["sourceSetupMs"] + sample["searchMs"] for sample in value["samples"])
                for value in values)
        rows.append(row)
    return rows


first, repeat = load("first-summary.json"), load("repeat-summary.json")
assert first["runId"] == repeat["runId"]
assert stable_cases(first) == stable_cases(repeat)
assert first["compilation"]["binarySha256"] == repeat["compilation"]["binarySha256"]
assert first["packedGraph"] == repeat["packedGraph"]
for full in repeat["fullChecks"]:
    long_cases = [case for case in repeat["cases"] if case["origin"] == full["origin"] and case["budgetMs"] >= 7_200_000]
    assert all(case["reachableStates"] == full["native"]["settledStates"] for case in long_cases)
    assert len({case["formats"]["membership"]["payloadSha256"] for case in long_cases}) == 1
manifest = load("repeat-manifest.json")
assert manifest["summarySha256"] == sha(HERE / "repeat-summary.json")
assert load("first-manifest.json")["summarySha256"] == sha(HERE / "first-summary.json")
for name, artifact in manifest["referenceArtifacts"].items():
    path = ROOT / "data/reference-pilot/downtown-static-v1" / name
    assert path.stat().st_size == artifact["bytes"] and sha(path) == artifact["sha256"]
for name, expected in manifest["scripts"].items():
    assert sha(ROOT / "routing" / name) == expected
local = ROOT / "data/native-pilot/downtown-native-v1"
assert sha(local / "graph.csr") == repeat["packedGraph"]["sha256"]
assert sha(local / "native_search") == repeat["compilation"]["binarySha256"]

report = {"runId": first["runId"], "identicalCases": len(first["cases"]), "referenceArtifactsUnchanged": True,
          "binaryIdentical": True, "packedGraphIdentical": True, "resultsAndTraversalCountsIdentical": True,
          "importedComponentsSaturateBy2Hours": True,
          "aggregation": "Median of nine per-origin p50 values; ten sequential samples per case/mode. Setup+search sums paired samples before aggregating.",
          "first": aggregate(first), "repeat": aggregate(repeat),
          "retainedFiles": {name: {"bytes": (HERE / name).stat().st_size, "sha256": sha(HERE / name)}
                            for name in ("first-summary.json", "repeat-summary.json", "first-manifest.json", "repeat-manifest.json", "first-run-identity.json")}}
(HERE / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({key: value for key, value in report.items() if key != "retainedFiles"}, indent=2))
