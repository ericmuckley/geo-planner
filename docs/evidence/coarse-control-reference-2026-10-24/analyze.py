"""Offline arithmetic/protocol audit; prints JSON, never reads keys or calls services."""

from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
from math import isclose
from pathlib import Path
from statistics import mean, median


root = Path(__file__).resolve().parent
capture = root / "reference"
load = lambda p: json.loads(p.read_text())
digest = lambda p: sha256(p.read_bytes()).hexdigest()
bindings = load(root.parent / "coarse-control-tool-2026-10-24/checks.json")
for group in ("producerFiles", "referenceFiles"):
    for name, expected in bindings[group].items():
        assert digest(Path(name)) == expected, name
manifest = load(capture / "sha256.json")
assert sorted(p.name for p in capture.iterdir()) == sorted([*manifest, "sha256.json"])
for name, expected in manifest.items():
    assert digest(capture / name) == expected, name
report = load(root / "comparison.json")
plan = load(capture / "plan.json")
assert digest(capture / "plan.json") == report["planSha256"] == bindings["planSha256"]
assert report["transport"] == "live" and report["attempted"] == 6
assert report["stopReason"] is None
assert len(report["cases"]) == len(plan["queries"]) == 6
calibration_path = root.parent / "coarse-class-calibration-2026-10-23/comparison.json"
calibration = load(calibration_path)
expected_calibration = load(calibration_path.parent / "sha256.json")["comparison.json"]
assert digest(calibration_path) == expected_calibration
cases, records, bodies = [], [], []
for i, (row, query) in enumerate(zip(report["cases"], plan["queries"], strict=True)):
    record = load(capture / f"{i:02}-result.json")
    body = load(capture / f"{i:02}-response.txt")
    assert record["status"] == row["status"] == 200 and record["error"] is None
    assert row["outcome"] == "paired" and row["id"] == query["id"] == record["id"]
    assert "authorization" not in {k.lower() for k in record["headers"]}
    assert set(record["headers"]) <= {
        "content-type", "retry-after", "x-ratelimit-limit",
        "x-ratelimit-remaining", "x-ratelimit-reset",
    }
    ors = body["features"][0]["properties"]["summary"]["duration"] / 60
    assert ors == row["ors"]["minutes"]
    gap = ors - query["existingValhallaMinutes"]
    assert gap == row["differenceMinutes"]
    assert abs(gap) == row["absoluteDifferenceMinutes"]
    assert gap / row["valhallaMinutes"] * 100 == row["differencePercent"]
    dataset, name = row["id"].split("/", 1)
    matched = [r for r in calibration["rows"] if r["set"] == dataset and r["id"] == name]
    assert len(matched) == 1
    old = matched[0]
    assert old["referenceMinutes"] == row["valhallaMinutes"]
    assert old["baseline"]["pointMinutes"] == row["v8Minutes"]
    candidate = old["candidate"]["pointMinutes"]
    cases.append({
        "id": row["id"], "v8Minutes": row["v8Minutes"],
        "rejectedCandidateMinutes": candidate, "orsMinutes": ors,
        "valhallaMinutes": row["valhallaMinutes"], "orsMinusValhallaMinutes": gap,
        "v8AbsoluteToOrsMinutes": abs(row["v8Minutes"] - ors),
        "candidateAbsoluteToOrsMinutes": abs(candidate - ors),
        "v8AbsoluteToValhallaMinutes": abs(row["v8Minutes"] - row["valhallaMinutes"]),
        "candidateAbsoluteToValhallaMinutes": abs(candidate - row["valhallaMinutes"]),
    })
    records.append(record)
    bodies.append(body)
gaps = [r["orsMinusValhallaMinutes"] for r in cases]
assert isclose(mean(gaps), report["overall"]["meanSignedMinutes"], abs_tol=1e-10)
assert isclose(median(gaps), report["overall"]["medianSignedMinutes"], abs_tol=1e-10)
assert sum(g >= 5 for g in gaps) >= 4 and median(gaps) >= 5
starts = [datetime.fromisoformat(r["startedAt"].replace("Z", "+00:00")) for r in records]
intervals = [(b - a).total_seconds() * 1000 for a, b in zip(starts, starts[1:])]
assert min(intervals) >= 6500
remaining = [int(r["headers"]["x-ratelimit-remaining"]) for r in records]
assert all(a - b == 1 for a, b in zip(remaining, remaining[1:]))
model_means = {field: mean(r[field] for r in cases) for field in (
    "v8AbsoluteToOrsMinutes", "candidateAbsoluteToOrsMinutes",
    "v8AbsoluteToValhallaMinutes", "candidateAbsoluteToValhallaMinutes",
)}
print(json.dumps({
    "requests": len(records), "statuses": dict(Counter(r["status"] for r in records)),
    "minimumStartIntervalMs": min(intervals), "firstStart": records[0]["startedAt"],
    "lastFinish": records[-1]["finishedAt"], "returnedQuotaRemaining": remaining,
    "maximumResponseBytes": max(r["bodyBytes"] for r in records),
    "httpAndBodyMs": [r["httpAndBodyMs"] for r in records],
    "bodyRedactions": sum(r["bodyRedacted"] for r in records),
    "maxSnapMeters": max(m for r in report["cases"] for m in r["ors"]["snapMeters"]),
    "orsEngineMetadata": [json.loads(x) for x in sorted({json.dumps(b["metadata"]["engine"], sort_keys=True) for b in bodies})],
    "orsMinusValhalla": {"meanMinutes": mean(gaps), "medianMinutes": median(gaps),
        "minimumMinutes": min(gaps), "maximumMinutes": max(gaps),
        "allSixPositive": all(g > 0 for g in gaps), "atLeastFiveMinutes": sum(g >= 5 for g in gaps),
        "materialPositiveDiscrepancy": True,
        "percentageRange": [min(r["differencePercent"] for r in report["cases"]), max(r["differencePercent"] for r in report["cases"])]},
    "postHocCandidateSensitivity": {"cases": 6, "means": model_means,
        "improveAgainstOrs": sum(r["candidateAbsoluteToOrsMinutes"] < r["v8AbsoluteToOrsMinutes"] for r in cases),
        "regressAgainstOrs": sum(r["candidateAbsoluteToOrsMinutes"] > r["v8AbsoluteToOrsMinutes"] for r in cases),
        "scope": "Post hoc reuse of saved candidate timings; not a predeclared gate, new search or model acceptance. Original rejection unchanged."},
    "cases": cases,
    "scope": "Six selected matched OD controls; ORS/Valhalla profile/data/route/date differences are not separable here. Neither engine is traffic truth. No national inference, model activation or new correction fitted. HTTP-plus-body elapsed is not graph-search time.",
}, indent=2))
