"""Independent offline raw-reference, timing and model-comparison audit; stdout only."""

from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
from math import asin, ceil, cos, isclose, radians, sin, sqrt
from pathlib import Path
from statistics import mean, median


root = Path(__file__).resolve().parent
load = lambda p: json.loads(p.read_text())
digest = lambda p: sha256(p.read_bytes()).hexdigest()
bindings = load(root.parent / "coarse-benchmark-plan-2026-10-24/checks.json")
for group in ("producerFiles", "referenceFiles"):
    for name, expected in bindings[group].items():
        assert digest(Path(name)) == expected, name


def verify_capture(path):
    manifest = load(path / "sha256.json")
    assert sorted(p.name for p in path.iterdir()) == sorted([*manifest, "sha256.json"])
    for name, expected in manifest.items():
        assert digest(path / name) == expected, name


def snap_meters(a, b):
    dlat, dlon = radians(b[1] - a[1]), radians(b[0] - a[0])
    h = sin(dlat / 2) ** 2 + cos(radians(a[1])) * cos(radians(b[1])) * sin(dlon / 2) ** 2
    return 6371000 * 2 * asin(min(1, sqrt(h)))


def close(a, b):
    assert isclose(a, b, abs_tol=1e-8), (a, b)


capture = root / "reference"
control = root.parent / "coarse-control-reference-2026-10-24/reference"
frontier = root.parent / "coarse-frontier-reference-2026-10-23/reference"
for path in (capture, control, frontier):
    verify_capture(path)
plan = load(capture / "plan.json")
assert digest(capture / "plan.json") == bindings["planSha256"]
report = load(root / "comparison.json")
assert report["planSha256"] == bindings["planSha256"]
assert report["transport"] == "live"
calibration = load(root.parent / "coarse-class-calibration-2026-10-23/comparison.json")
models = {f"{r['set']}/{r['id']}": r for r in calibration["rows"]}
raw_by_id = {}
for path, prefix in ((frontier, "frontier/"), (control, ""), (capture, "")):
    queries = load(path / "plan.json")["queries"]
    ledger = load(path / "ledger.json")
    assert len(queries) == len(ledger["cases"])
    for i, (q, entry) in enumerate(zip(queries, ledger["cases"], strict=True)):
        assert q["id"] == entry["id"]
        key = prefix + q["id"]
        assert key not in raw_by_id
        record = load(path / f"{i:02}-result.json") if entry["outcome"] == "attempted" else None
        raw_by_id[key] = (path, i, q, record)
assert set(raw_by_id) == set(models) and len(raw_by_id) == 83
assert [r["id"] for r in report["cases"]] == list(models)
engines = set()
for row in report["cases"]:
    model = models[row["id"]]
    for name, original in (("v8Model", "baseline"), ("rejectedCandidateModel", "candidate")):
        for field in ("pointMinutes", "cellMinutes", "predictedReachable"):
            assert row[name][field] == model[original][field]
    path, i, q, record = raw_by_id[row["id"]]
    assert q["request"]["coordinates"] == [[model["origin"]["lon"], model["origin"]["lat"]], [model["destination"]["lon"], model["destination"]["lat"]]]
    if row["ors"] is None:
        assert row["v8"] is None and row["rejectedCandidate"] is None
        continue
    assert record and record["status"] == 200 and record["error"] is None
    assert set(record["headers"]) <= {"content-type", "retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"}
    body = load(path / f"{i:02}-response.txt")
    feature = body["features"][0]
    minutes = feature["properties"]["summary"]["duration"] / 60
    close(minutes, row["ors"]["minutes"])
    close(feature["properties"]["summary"]["distance"] / 1000, row["ors"]["distanceKm"])
    points = feature["geometry"]["coordinates"]
    for endpoint, expected, measured in zip((points[0], points[-1]), q["request"]["coordinates"], row["ors"]["snapMeters"], strict=True):
        close(snap_meters(endpoint, expected), measured)
    engine = body.get("metadata", {}).get("engine", {})
    engines.add(tuple(engine.get(k) for k in ("version", "build_date", "graph_date", "osm_date")))
    for name, original in (("v8", "baseline"), ("rejectedCandidate", "candidate")):
        signed = model[original]["pointMinutes"] - minutes
        close(signed, row[name]["signedMinutes"])
        close(abs(signed), row[name]["absoluteMinutes"])
        close(signed / minutes * 100, row[name]["signedPercent"])
    close(row["rejectedCandidate"]["absoluteMinutes"] - row["v8"]["absoluteMinutes"], row["absoluteErrorChangeMinutes"])


def summarize(rows):
    paired = [r for r in rows if r["ors"] is not None]
    result = {"planned": len(rows), "paired": len(paired), "models": {}}
    for name in ("v8", "rejectedCandidate"):
        values = [models[r["id"]]["baseline" if name == "v8" else "candidate"]["pointMinutes"] - r["ors"]["minutes"] for r in paired]
        absolute = sorted(abs(x) for x in values)
        result["models"][name] = {
            "meanSignedMinutes": mean(values) if values else None,
            "meanAbsoluteMinutes": mean(absolute) if absolute else None,
            "medianAbsoluteMinutes": median(absolute) if absolute else None,
            "p90AbsoluteMinutes": absolute[ceil(len(absolute) * .9) - 1] if absolute else None,
        }
    result["candidateChanges"] = {
        "improve": sum(r["absoluteErrorChangeMinutes"] < -1e-9 for r in paired),
        "regress": sum(r["absoluteErrorChangeMinutes"] > 1e-9 for r in paired),
        "unchanged": sum(abs(r["absoluteErrorChangeMinutes"]) <= 1e-9 for r in paired),
    }
    return result


cases = report["cases"]
expected_primary = all(r["ors"] is not None for r in cases) and len(engines) == 1 and all(next(iter(engines)))
assert (report["primary"] is not None) == bool(expected_primary)
assert report["completedLiveBenchmark"] == bool(expected_primary)
groups = {"overall": summarize(cases)}
groups.update({s: summarize([r for r in cases if r["set"] == s]) for s in ("original", "regional", "frontier")})
if report["primary"] is not None:
    assert len(engines) == 1 and all(next(iter(engines)))
    for key, result in groups.items():
        saved = report["primary"]["overall"] if key == "overall" else report["primary"]["bySet"][key]
        assert result["planned"] == saved["planned"] and result["paired"] == saved["pairedFinite"]
        for name, metrics in result["models"].items():
            for metric, value in metrics.items():
                close(value, saved["models"][name][metric])
        assert result["candidateChanges"] == saved["candidateChanges"]
ledger = load(capture / "ledger.json")
records = [load(capture / f"{i:02}-result.json") for i in range(ledger["attempted"])]
starts = [datetime.fromisoformat(r["startedAt"].replace("Z", "+00:00")) for r in records]
intervals = [(b - a).total_seconds() * 1000 for a, b in zip(starts, starts[1:])]
assert len(records) <= 29 and (not intervals or min(intervals) >= 6500)
remaining = [int(r["headers"]["x-ratelimit-remaining"]) for r in records if "x-ratelimit-remaining" in r["headers"]]
assert all(a - b == 1 for a, b in zip(remaining, remaining[1:]))
older = [r for r in cases if r["valhalla"] is not None and r["ors"] is not None]
gaps = [r["ors"]["minutes"] - r["valhalla"]["minutes"] for r in older]
for r, gap in zip(older, gaps, strict=True):
    close(gap, r["orsMinusValhalla"]["signedMinutes"])
print(json.dumps({
    "requests": len(records), "statuses": dict(Counter(r["status"] for r in records)),
    "stopReason": ledger["stopReason"], "minimumStartIntervalMs": min(intervals) if intervals else None,
    "firstStart": records[0]["startedAt"], "lastFinish": records[-1]["finishedAt"],
    "returnedQuotaRemaining": remaining, "maximumResponseBytes": max(r["bodyBytes"] for r in records),
    "httpAndBodyMsRange": [min(r["httpAndBodyMs"] for r in records), max(r["httpAndBodyMs"] for r in records)],
    "bodyRedactions": sum(r["bodyRedacted"] for r in records),
    "maximumSnapMetersAll83": max(m for r in cases if r["ors"] for m in r["ors"]["snapMeters"]),
    "engineBuildGraphOsmCohorts": sorted(engines, key=str),
    "groups": groups,
    "olderOrsMinusValhalla": {"planned": 35, "paired": len(gaps), "meanSignedMinutes": mean(gaps) if gaps else None, "medianSignedMinutes": median(gaps) if gaps else None, "positive": sum(g > 0 for g in gaps), "negative": sum(g < 0 for g in gaps)},
    "largestCandidateRegressions": [{"id": r["id"], "absoluteErrorChangeMinutes": r["absoluteErrorChangeMinutes"]} for r in sorted((r for r in cases if r["ors"]), key=lambda r: r["absoluteErrorChangeMinutes"], reverse=True)[:10]],
    "scope": "Independent raw-reference and frozen-model arithmetic/protocol audit, no new search, key/env read or provider call. Same-provider observed development cases do not establish traffic truth or national accuracy. Saved candidate remains historically rejected; HTTP-plus-body elapsed is not engine search time.",
}, indent=2))
