# Protected 25 m geometry: preserved source semantics, failed inline size

October 25, 2026, checkout `648c731`. **The fixed 25 m source-geometry preservation checks pass; the complete inline storage forecast fails 70 MB.** V9 stays active. New helper/producer/validator/tests and this evidence are local/uncommitted. No routing candidate, new accuracy result or deployment.

## Frozen scope and method

[Execution plan](plan.json), SHA `fb1f8cad561e791c55db31751e5b0897e3ba7de1ceca4c11bcb978226f2d2420`, implements the [previously frozen design](../coarse-backbone-preflight-2026-10-25/next-design.json). It was recorded before this source run. All 49 cached Census partitions, exact geometry/class duplicate policy, source identity and assumed 105/85 speeds remain fixed. No city/region/query exception, endpoint snapping, inferred crossing, parameter sweep or source acquisition.

The [producer](../../../scripts/preflight-coarse-backbone-geometry.py) reproduces every original 501,493 source-parent length and ceil-decisecond cost before subdivision. Exact source endpoint/junction positions stay intact. New grid crossings and boundary-touch occurrences become separate degree 2 nodes; unrelated visits do not merge because of cell/coordinate coincidence. Intersections use canonical float gridlines at integer/40 degrees and exact rational parameters; only identical parameters at a true corner deduplicate.

The [helper](../../../scripts/coarse_backbone_geometry.py) uses deterministic iterative Douglas-Peucker at 23 m between protected positions, leaving 2 m of the fixed 25 m bound for interior storage quantization. Protected endpoints use exact float64 node positions. Interior coordinates quantize to 1e-5 degrees inside the original half-open owning cell. A deterministic original interior witness prevents a simplified chord from collapsing onto a different cell boundary. Exact consecutive duplicate positions can be omitted from geometric work while raw IDs/counts/cost denominators remain retained.

The metric is coordinate Euclidean distance multiplied by 111,320 meters/degree. This isotropic bound dominates distances in the existing spherical haversine model; vertex-to-corresponding-segment checks bound intervening linear source segments as well. This is a documented model metric, not a claim about datum/road/traffic accuracy. The 25 m allowance is source-line approximation, **not display-grid or contour accuracy**; the grid remains 0.025°.

Original full-source cumulative lengths determine interior access positions. Original parent kilometers/minutes are distributed proportionally over source subdivisions; simplified chord lengths never price travel. Float64 subdivision weights retain positive costs and every parent sum instead of adding new per-crossing rounding charges. No land mask, access eligibility, local-transfer flag or runtime field is changed.

## Measured preservation result

[Producer result](report.json), [independent full-source audit](independent-audit.json), [per-parent relative arithmetic](relative-audit.json):

| Measurement | Result |
| --- | ---: |
| Raw parts / exact duplicates / unique parts | 261,862 /38,470 /223,392 |
| Raw source vertices covered | 24,450,400 |
| Original parent arcs reproduced | 501,493 |
| Original junction nodes / added crossing occurrences | 245,842 /732,730 |
| Result nodes / arcs | 978,572 /1,234,223 |
| Retained interior geometry vertices | 1,415,730 |
| Indexed cells | 326,538 |
| Source components | 3,100, unchanged |
| Largest component road-length share | 98.5437%, unchanged |
| Maximum measured deviation after quantization | **23.552100 m** |
| Source-cell sequence mismatches | **0** |
| Maximum parent relative length error | **4.34e-16** |
| Maximum parent minute-sum error | **<6e-14 min** |
| Maximum chord undercharge | **0 m** |

The complete 83-case/166-endpoint ledger remains bound unchanged to the prior source inventory; no probe selection/replacement or route query occurred. Its vertex proximity remains proximity rather than legal access/reachability proof. All source components, including smaller ones, stay present. Shared 2D source incidence still does not establish grade, permitted turns or legal drivable access.

[Independent validator](../../../scripts/verify-coarse-backbone-geometry.py) separately reconstructs clipping/protected positions from every cached source part, checks every retained source span and original cost/cumulative distance, decodes every geometry span, checks every sparse cell/junction/crossing index membership and uses compact adjacency/BFS instead of the producer's union-find. All preservation checks pass. It does not run a simplifier, producer or route search. The [additional relative audit](audit-relative.py) checks the stricter per-parent relative limit directly from saved arrays/ranges; it passes for all 501,493 parents.

The producer's `independentQualificationPending:true` is its original pre-audit snapshot and is preserved. The separate audit records above complete geometry/source/index verification; they do not turn a failed size gate into an accepted routing model.

## Complete storage gate: failed

All 17 runtime arrays are measured: exact node positions, arc endpoints/full-source distances/minutes/speeds, geometry bytes and byte/interior/cumulative-distance indexes, per-part ranges, junction CSR, degree 2 crossing adjacency and sparse cell-to-arc lookup. No required index is omitted. Runtime gzip fields total **55,399,138 bytes**; the current base64 JSON fields plus metadata occupy **73,866,961 bytes**.

| Frozen forecast component | Bytes |
| --- | ---: |
| Kept-v9 JSON after replacing old Census layer/visits | 7,047,468 |
| New inline arrays/indexes/metadata | 73,866,961 |
| Existing framework function overhead | 3,822,197 |
| Unchanged integration reserve | 4,194,304 |
| **Projected function** | **88,930,930** |
| Frozen target | **70,000,000** |

All source/geometry/physical/cell/component/denominator gates pass; `projectedFunction:false` /`geometryAndSizePassed:false` remain frozen. This is a storage forecast, **not an actual Vercel package**. No tolerance/codec/budget retuning, alternate geometry run, activation or routing qualification followed the failure. Previous 117.56 MB/93.94 MB failures remain untouched.

Producer **166.996 s /320,110,592-byte maxRSS**, independent audit **115.828 s /413,597,696-byte maxRSS** on this Mac. These are offline producer/auditor scopes, not server/cloud load, request latency, retained decoded storage or peak-memory qualification. Three later packaging/load runs and a complete first-estimate check remain future work.

## Software and preservation checks

Fourteen new geometry fixtures cover negative/positive half-open boundaries, exact/near corners, endpoint cuts, duplicate positions, large/small bends, quantization budget, boundary witnesses, tangent touches, boundary-following roads, positive split weights/cost conservation, separate crossing occurrences, cumulative source lengths, encoded interiors and constant segments. **71 total Python fixtures, 175-file Biome and ordinary build pass.** No redundant full server/DB/Vercel/browser/memory suite was run for an unchanged app. [Checks and source/asset bindings](checks.json), [record manifest](sha256.json).

V9 runtime, UI, source dependencies and all nine prior sealed runs are unchanged. No provider/key/env/DB access, source download, schema/dependency/runtime change, commit/push or deployment. All 48/6/29 provider budgets are consumed. No new driving-time or spatial accuracy claim follows this preflight.

## Next: isolated binary packaging/load probe

[Next packaging plan](next-packaging-plan.json), SHA `b9d68164e0133f3e8c9dd371c6fa9b737e25cf7b0b3e60c0f1aa2df36d7d981d`, is a **proposal only**. Preserve these exact 17 gzip arrays and all kept-v9 values, and measure an emitted/traced server-binary mechanism in an isolated env-free copy of the existing app. Include descriptors, indexes, data and code; prove actual function bytes plus the original 4 MiB reserve fit 70 MB, three fresh local load/decode/validation runs<=3 s and retained decoded storage<=162,238,546 bytes. No public/CDN/cloud-DB/network data fallback or fabricated contours.

Inspection of the installed Nitro version found its production `serverAssets` loader routes binary assets through `raw:`, which embeds base64. That default path alone will retain overhead. [Read-only installed-source excerpt](nitro-server-assets.txt) and exact package/module hashes are bound in the proposal. Inspect supported emitted/traced-file behavior and freeze the exact build recipe before a probe build. **No binary packer, isolated probe, routing engine/candidate or first-query/accuracy result has run.** After packaging passes, the exact routing recipe/evaluation and all prior 83-case/35-sensitivity physical/accuracy/retention/latency/package gates still apply.

## Recovery

Ignored `data/coarse-quality/census-backbone-geometry-v1/` holds the 17 runtime gzip arrays, source-parent/source-part proofs and plan/report. Exact source/tool prerequisites and older inventory/codec/connector assets remain at their recorded paths. New runners refuse overwrite; preserve all failures and sealed producers.

Quick tests/bindings:

```sh
python3 -B -m unittest discover -s scripts -p 'coarse_backbone_geometry_test.py'
python3 -B docs/evidence/coarse-backbone-geometry-2026-10-25/verify.py > /tmp/backbone-geometry-bindings.json
```

Do not rerun the completed source producer or full cached-source auditor for readiness/documentation. The auditor command is documented in [local development](../../local-development.md#protected-backbone-geometry-preflight) for an intentional revalidation only. [Current next steps](../../next-steps.md) replace the completed geometry task with the packaging probe. No new service/process was started and no producer remains running at handoff.
