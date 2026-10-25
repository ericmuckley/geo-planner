"""Read saved v8 paths/proofs and both timing outcomes; no new search or fitting."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

root = Path.cwd()
load = lambda p: json.loads(p.read_text())
benchmark_path = root / "docs/evidence/coarse-benchmark-reference-2026-10-24/comparison.json"
benchmark = load(benchmark_path)
expected = load(benchmark_path.parent / "sha256.json")["comparison.json"]
assert hashlib.sha256(benchmark_path.read_bytes()).hexdigest() == expected
regional = load(root / "docs/evidence/coarse-finer-2026-10-23/paths.json")
frontier = json.loads(gzip.decompress((root / "docs/evidence/coarse-frontier-reference-2026-10-23/paths.json.gz").read_bytes()))
proofs = []
for folder, binding in [("resolution-0025-base-v1", "base-build.json"), ("resolution-0025-road-v1", "road-build.json")]:
    raw = (root / "data/coarse-quality" / folder / "links.json.gz").read_bytes()
    frozen = load(root / "docs/evidence/coarse-finer-2026-10-23" / binding)
    assert hashlib.sha256(raw).hexdigest() == frozen["linkProof"]["sha256"]
    proofs.append({r["key"]: r for r in json.loads(gzip.decompress(raw))})
width, size = 2360, 2360 * 1040
rows = []
for case in benchmark["cases"]:
    group, id_ = case["id"].split("/", 1)
    path = next(r["path"] for r in (frontier if group == "frontier" else regional[group]) if r["id"] == id_)
    classes = Counter()
    for edge in path:
        if edge["kind"] != "road":
            classes[edge["kind"]] += edge["minutes"]
            continue
        a, b = (edge["from"], edge["to"]) if group == "frontier" else (edge["cell"], edge["target"])
        layer = a >= size
        assert layer == (b >= size)
        a, b = sorted([a % size, b % size])
        key = a * 4 + {1: 0, width + 1: 1, width: 2, width - 1: 3}[b - a]
        proof = proofs[int(layer)][key]
        assert abs(proof["deciseconds"] / 600 - edge["minutes"]) < 1e-8
        source_kind = "census-layer" if layer else proof["kind"]
        classes[f"{source_kind}/{proof['speedKph']}"] += edge["minutes"]
    rows.append({"id": case["id"], "v8SignedMinutes": case["v8"]["signedMinutes"],
        "prototypeSignedMinutes": case["rejectedCandidate"]["signedMinutes"],
        "prototypeAbsoluteErrorChangeMinutes": case["absoluteErrorChangeMinutes"],
        "v8RoadCostMinutesBySourceClass": dict(classes)})
regressions = [r for r in rows if r["prototypeAbsoluteErrorChangeMinutes"] > 1e-9]
slow = [r for r in regressions if r["v8SignedMinutes"] > 0]
overshoot = [r for r in regressions if r["v8SignedMinutes"] <= 0 < r["prototypeSignedMinutes"]]
print(json.dumps({"cases": len(rows), "regressions": len(regressions),
    "regressionsAlreadySlowerThanOrs": len(slow), "regressionsOvershootFromFasterToSlower": len(overshoot),
    "largestRegressions": sorted(regressions, key=lambda r: r["prototypeAbsoluteErrorChangeMinutes"], reverse=True)[:10],
    "rows": rows,
    "scope": "Descriptive saved-v8-path/source-cost exposure and observed old prototype errors, not causal ETA decomposition or a new candidate/forecast. All83 observed development cases retained; no locations enter a routing rule, no new search/provider/key/env/DB read."}, indent=2))
