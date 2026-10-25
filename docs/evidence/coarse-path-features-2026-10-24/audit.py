"""Independently check saved comparisons, path sums and frozen gates; stdout only."""
import gzip
import hashlib
import json
from math import ceil, isclose
from pathlib import Path
from statistics import mean

root = Path(__file__).resolve().parent
load = lambda p: json.loads(p.read_text())
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
plan = load(root / "candidate-plan.json")
assert digest(root / "candidate-plan.json") == "5a990ab557251ef75fb98b17381c307a32679ddbd3ccf270f775e8d80baf6a81"
for name, expected in plan["inputs"].items():
    assert digest(Path(name)) == expected, name
benchmark = load(Path("docs/evidence/coarse-benchmark-reference-2026-10-24/comparison.json"))
report = load(root / "comparison.json")
assert report["planSha256"] == digest(root / "candidate-plan.json")
assert len(report["rows"]) == 83
assert digest(Path(report["artifact"])) == report["artifactSha256"]
raw = (root / "paths.json.gz").read_bytes()
assert hashlib.sha256(raw).hexdigest() == report["pathSha256"]
paths = json.loads(gzip.decompress(raw))
assert len(paths) == 166
assert len({(p["id"], p["model"]) for p in paths}) == 166
for row in report["rows"]:
    id_ = f"{row['set']}/{row['id']}"
    saved = next(r for r in benchmark["cases"] if r["id"] == id_)
    assert row["referenceMinutes"] == saved["ors"]["minutes"]
    assert isclose(row["baseline"]["pointMinutes"], saved["v8Model"]["pointMinutes"], abs_tol=1e-8)
    assert isclose(row["baseline"]["cellMinutes"], saved["v8Model"]["cellMinutes"], abs_tol=1e-8)
    assert row["baseline"]["predictedReachable"] == saved["v8Model"]["predictedReachable"]
    for model in ("baseline", "candidate"):
        m = row[model]
        assert m["pointMinutes"] is not None and m["pathComponents"] is not None
        assert isclose(sum(m["pathComponents"].values()), m["pointMinutes"], abs_tol=1e-8)
        predicted = m["predictedReachable"]
        expected = "ambiguous" if abs(row["referenceMinutes"] - row["budgetMinutes"]) <= 5 else "correct" if predicted == (row["referenceMinutes"] < row["budgetMinutes"]) else "falseReachable" if predicted else "missedReachable"
        assert m["classification"] == expected
    before = abs(row["baseline"]["pointMinutes"] - row["referenceMinutes"])
    after = abs(row["candidate"]["pointMinutes"] - row["referenceMinutes"])
    assert isclose(after - before, row["absoluteErrorChangeMinutes"], abs_tol=1e-8)
    for model, name in (("baseline", "v8"), ("candidate", "candidate")):
        path = next(p for p in paths if p["id"] == id_ and p["model"] == name)
        assert path["nodes"][0] == [row["origin"]["lon"], row["origin"]["lat"]]
        assert path["nodes"][-1] == [row["destination"]["lon"], row["destination"]["lat"]]

rows = report["rows"]
frontier = [r for r in rows if r["set"] == "frontier"]
older = [r for r in rows if r["set"] != "frontier"]
errors = lambda items: sorted(abs(r["candidate"]["pointMinutes"] - r["referenceMinutes"]) for r in items)
mae = lambda items: mean(errors(items))
p90 = lambda items: errors(items)[ceil(len(items) * .9) - 1]
horizon = lambda h: [r for r in frontier if r["budgetMinutes"] == int(h)]
missed = lambda items: sum(r["candidate"]["classification"] == "missedReachable" for r in items)
maximum = lambda items: max(r["absoluteErrorChangeMinutes"] for r in items)
a = plan["admission"]
gates = {
    "overallMean": mae(rows) <= a["overallMeanAbsoluteMaximum"],
    "frontierMean": mae(frontier) <= a["frontierMeanAbsoluteMaximum"],
    "originalMean": mae([r for r in rows if r["set"] == "original"]) <= a["setMeansMaximum"]["original"],
    "regionalMean": mae([r for r in rows if r["set"] == "regional"]) <= a["setMeansMaximum"]["regional"],
    "frontierP90": p90(frontier) <= a["frontierP90Maximum"],
    "horizonMeans": all(mae(horizon(h)) <= maximum for h, maximum in a["horizonMeansMaximum"].items()),
    "horizonP90": all(p90(horizon(h)) <= maximum for h, maximum in a["horizonP90Maximum"].items()),
    "frontierWorstRegression": maximum(frontier) <= a["maximumFrontierAbsoluteErrorIncreaseMinutes"],
    "olderWorstRegression": maximum(older) <= a["maximumOlderAbsoluteErrorIncreaseMinutes"],
    "frontierDefiniteClassificationErrors": sum(r["candidate"]["classification"] in ("falseReachable", "missedReachable") for r in frontier) <= a["maximumFrontierDefiniteClassificationErrors"],
    "frontierMissed": missed(frontier) <= a["maximumFrontierMissedReachable"],
    "twelveHourMissed": missed(horizon(720)) <= a["maximum12hMissedReachable"],
    "all83Paired": len(rows) == 83 and all(r["candidate"]["pointMinutes"] is not None for r in rows),
    "all166PathSums": len(paths) == 166,
    "all35StillShaded": len(older) == 35 and all(r["candidate"]["predictedReachable"] for r in older),
}
assert gates == report["gates"]
assert all(gates.values()) == report["accuracyGatesPassed"]
assert isclose(mae(rows), report["overall"]["candidate"]["meanAbsoluteMinutes"], abs_tol=1e-8)
by_origin = []
for key in sorted({json.dumps(r["origin"], sort_keys=True) for r in rows}):
    selected = [r for r in rows if json.dumps(r["origin"], sort_keys=True) == key]
    by_origin.append({"origin":json.loads(key), "planned":len(selected),
        "baselineMae":mean(abs(r["baseline"]["pointMinutes"]-r["referenceMinutes"]) for r in selected),
        "candidateMae":mae(selected),
        "improve":sum(r["absoluteErrorChangeMinutes"] < -1e-8 for r in selected),
        "regress":sum(r["absoluteErrorChangeMinutes"] > 1e-8 for r in selected)})
print(json.dumps({"cases":83, "pathSums":166, "allFrozenBaselineCostsAndShading":True,
    "candidateMae":mae(rows), "worstFrontierRegression":maximum(frontier), "worstOlderRegression":maximum(older),
    "frontierMissed":missed(frontier), "twelveHourMissed":missed(horizon(720)),
    "gates":gates, "accepted":all(gates.values()), "byOrigin":by_origin,
    "scope":"Independent offline saved-output arithmetic and path-sum/gate audit; no graph producer/search, provider/key/env/DB read or activation. Original failed evidence/gates unchanged; Full physical/runtime qualification is recorded separately."},indent=2))
