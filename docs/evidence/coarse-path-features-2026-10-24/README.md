# Geometry diagnosis and qualified v9 connector timing

Started October 24, completed October 25, 2026 on checkout `37ff14b`. **Decision: qualify the one planned candidate and activate it locally as v9. Uncommitted; no deployment.** The separately authored floating-map UI is preserved byte for byte. All older failed candidates, thresholds, sealed producers and measured records remain unchanged.

## What changed and why

The [read-only protocol](protocol.json) was frozen before extracting source curvature, NE/Census connection exposure and bidirectional model/reference corridor proximity at 1/3 km on **all 83 saved cases**. [Features](features.json) retain every denominator and both directions; seven synthetic geometry fixtures check weighted length, segment interiors, index boundaries/high latitudes and unmatched cases. A replay is byte-identical. Source/ORS paths differ, repeated origins are correlated, and these are descriptive features rather than causal ETA decompositions.

NE connector km per 100 source-road km correlates with signed v8-minus-ORS error −0.522 on frontier 48, −0.226 overall 83 and +0.075 in the major-dominated 30 subset. Only two major-dominated cases are slower than ORS. The heterogeneous association supports testing a geometry-dependent charge; it is not a reliable universal predictor. Curvature/proximity are also weak aggregate signals. All contrary observations remain in the features ledger.

The separately [frozen candidate plan](candidate-plan.json), SHA `5a990ab557251ef75fb98b17381c307a32679ddbd3ccf270f775e8d80baf6a81`, predates production/full-search results. It defines one generic rule:

- Source-road speeds: major 105, secondary 85 (formerly 80), beltway/bypass 90, other 55 km/h.
- Artificial Natural Earth source-to-canonical connections pay their physical length at **55 km/h**,  the existing minimum retained road class, instead of at each source class speed.
- Census connections, general local travel and layer transfers remain **25 km/h**.
- Geometry, topology, masks, ownership, visits, eligibility and 0.025° resolution stay fixed. All source alternatives are repriced; no aggregate edge scaling, city/coordinate/region/query exception or parameter sweep.

Artificial connections retain existing eligibility. Charging them does **not** establish that a drivable road exists. The 55 value is a prospective engineering assumption, not a fitted optimum or measured real-world connector speed. Both original 95/85 and subsequent 100/82 rejections remain immutable; this is a separately versioned policy and plan.

## Accuracy outcome and limitations

Primary reference policy was fixed before this candidate: all 83 matched ORS 9.10 engine/build/graph/OSM cases, including saved 48 frontier +6 controls +29 completed benchmark requests. **Zero new provider calls**. All 48/6/29 budgets are consumed. These are observed development data, not traffic truth, nationwide/area accuracy or a fresh holdout. Older Valhalla results remain a separate sensitivity.

| Set | Cases | V8 mean absolute difference, min | Candidate, min |
| --- | ---: | ---: | ---: |
| Original | 11 | 11.213 | 7.223 |
| Broader regional | 24 | 10.016 | 8.613 |
| Frontier | 48 | 52.273 | 44.629 |
| Overall | 83 | 34.612 | 29.257 |
| Frontier 6h | 16 | 33.985 | 30.200 |
| Frontier 10h | 16 | 44.060 | 36.899 |
| Frontier 12h | 16 | 78.775 | 66.789 |

**All 15 prospective gates pass**,  including >=10% overall/frontier mean improvement, no per-set/horizon mean or gated p90 worsening, individual-loss limits, finite/path/shading checks and missed caps tightened to the v8 counts 5 overall/2 at 12h. No threshold or parameter changed after results. [Full comparison/all83 gains and regressions/35 sensitivities](comparison.json), [all166 paths](paths.json.gz), [independent arithmetic/gate/per-origin audit](audit.json), [audit source](audit.py).

**59 improve and 24 regress.** Worst absolute-error increase is 22.182 min frontier and 4.983 min older. Frontier p90 improves 116.332→97.813 min, but **frontier median worsens 37.254→40.561 min** (not a predeclared gate). Overall median improves 21.295→15.985 min. Frontier classifications change 23→32 correct,17→11 false reachable,5→2 missed reachable,3 ambiguous; 12h missed 2→1. This remains a substantial error rate. Per-origin deterioration is visible in the independent audit; an overall improvement does not imply every origin improves.

**Valhalla sensitivity worsens:** original 11 mean 10.288→14.896 min and broader 24 mean 12.011→13.389 min. The new prospective plan explicitly uses matched ORS as primary and retains this sensitivity; it does not reinterpret either old failure. Even the largest improvement still differs by 107.940 min from ORS. The largest frontier loss is a different selected path than ORS, and the largest older loss has almost identical candidate/v8 geometry. Do not treat connector exposure as proof of the error's cause.

## Independent qualification

[Producer report](producer-console.json) reproduces every original v8 source base/layer cost and speed tag before repricing the pinned NE and 49 Census partitions. Candidate 61,225,528 bytes, SHA `2904d0b72e4f15537abd69f5bb9cbc05358c1dacb18d041360e7df10c131b39b`. [Independent source repeat](repeat-check.json) reproduces the grid and both component-proof gzip hashes exactly. Producer 121.408 s/maxRSS 1,427,537,920 bytes on this Mac is an offline source pass, **not runtime/Vercel memory**.

[Independent physical checks](physical.json) validate all 378,515 base +346,821 layer links,317,586 Census states,36,325 shore links,123,116 NE owner visits,317,586 supplemental visits,10,185 systematic input attachments and 42 arbitrary-origin 6/10/12h estimates. Source-arc/chord and connector-distance/cost/positive-rounding bounds, max 105 physical limits, full visit validation, continuous generalized land on Census/shore/transfers and unchanged NE eligibility pass. These prove model consistency, not road access or real-world accuracy.

[Memory](memory.json): retained decoded heap+buffers **158,046,458 bytes**,  within v8+4 MiB. Three complete anchor-input sweeps total 952,758, with post-GC growth<=101,008heap bytes/zero buffers, below unchanged retention guards. Parsed encoded input is retained separately. This is not peak memory, cloud capacity or concurrent load qualification.

[Isolated candidate package](package-handler.json):65,051,308bytes/28files, first local computation after config3,693.2ms; no copied env files. [Final v9 package](active-package-handler.json):** 65,047,708bytes/28files**, first local computation after config **3,442.8ms**, then389.6/295.8ms and30min26.5ms. Both pass frozen<=70MB/<=5s gates. Outbound fetch is rejected; no routing fetch occurs, server data stays out of client assets, raw sources/env/embedded secrets are absent, research stays disabled and missing-DB history falls back. Final output scanner reads existing env values only locally to detect embedded secrets; no value is printed and env files are unchanged. Local handler timings exclude preceding module/config load and are not Vercel cold-start, production percentile, concurrency or peak-memory measurements.

**Software:** 56 server tests,43 Python fixtures (7 new geometry,6 new pricing; prior30 preserved),9 gate tests (6 prior/3 strict missed-count guards),175-file Biome, app and strict diagnostic typechecks, ordinary/Vercel builds pass. [42 active API cases](national-api.json) exactly match independently recorded candidate cell counts; payload/monotonicity/nondegeneracy checks pass. [15 final local HTTP checks](active-local-http.json) validate config,6/10/12h fixtures, repeat/overlap smoke, malformed/range/geography errors, disabled research and explicitly database-free empty history. Zero provider calls/history writes. No full live DB suite was needed for unchanged persistence.

**Visual:** [candidate review](visual.json) covers deterministic largest frontier gain/loss/older loss on one camera and coastal6h/inland10h/rural12h contours. [Final v9 browser](visual-active.json) confirms reload/default120, automatic30/360 release computation,35,867San Diego6h cells, v9 metadata and explicit model notices. Screenshots: [gain](visual-largest-gain.png), [frontier loss](visual-largest-frontier-loss.png), [older loss](visual-largest-older-loss.png), [inland10h](visual-inland-600.png), [rural12h](visual-rural-720.png), [active30](visual-active-30.png), [active6h](visual-active-360.png). Browser basemap requests are separate from routing; an unrelated wallet-extension ethereum getter error appears, with no app error. Superset CLI/IAB were unavailable; provided Chrome automation was used. Shared model lines connect states, not detailed road geometry. No cloud save was performed.

## Activation, files and recovery

[Finalization](finalization.json) changes only candidate version to `natural-earth-census-2026-grid-v9`. Runtime [coarse-grid-v9.json](../../../src/server/data/coarse-grid-v9.json) is **61,225,511bytes**, SHA `28271c809a04cdfab41ad735ad66b29e3875179b617198b7b1d4490533439bf6`. The app imports v9 and exposes `coarse-road-grid-v9`; warnings identify NE artificial connections as assumptions. Search/decoder logic is unchanged. New versioned verifiers preserve the old scripts; npm points at v9. Git/Vercel/Biome include/exclude rules cover the runtime artifact. V8/UI hashes remain exactly as [start.json](start.json). Final checks/source and prior-evidence bindings are in [checks.json](checks.json); [sha256.json](sha256.json) seals this run's records. No commit/push/deployment, source download, schema/dependency/env change or DB write.

Ignored assets under `data/coarse-quality/`: `connector-timing-candidate-v1/`, `connector-timing-candidate-repeat-v1/`, `connector-timing-evaluation-v1/`, `connector-preview-v1/`, `connector-package-v1/`. Pinned NE/Census/tool locks and original v8 base/layer component proofs remain prerequisites for source reproduction. A fresh clone at37ff14b lacks this new uncommitted work; after commit the bundled runtime alone supports normal app operation. [Exact safe checks and prerequisite locations](../../local-development.md#connector-timing-v9), [ordered next steps](../../next-steps.md).

Safe saved-output audit from repo root:

```sh
python3 -B docs/evidence/coarse-path-features-2026-10-24/audit.py > /tmp/coarse-connector-audit.json
python3 -B docs/evidence/coarse-path-features-2026-10-24/verify.py > /tmp/coarse-v9-bindings.json
```

It reads the ignored candidate and pinned source manifests to check hashes, not services/env/keys. Do not rerun completed source producers/memory sweeps/finalizer as readiness checks. The transient loopback preview was stopped after QA. No production v9 verification has occurred; next review/commit/deploy and run the new hosted app verifier. Do not spend more routing quota without separately approved scope/budget.

## Retained failures and scope corrections

`isolated-vite-failure.log` retains sandbox loopback-listen failure; the transient generated-handler adapter used an approved loopback bind. `local-server-sandbox-failure.log` retains its first restricted bind. Initial static HTML MIME was corrected in that transient adapter before comparison review. A scratch preparation command used unavailable `python`; rerunning with installed `python3` succeeded before any output existed. `server-tests.txt` retains npm/tsx IPC EPERM; the same 56 tests pass via `node --import tsx --test` in `server-tests-node.txt`. `strict-typecheck-v1-failure.txt` retains a missing explicit Uint 16 Array annotation in the new validator; the type-only correction passes strict checking and does not change the already measured runtime checks. `active-local-http-v1-failure.log`/empty JSON retain a production configured-history expectation in the deliberately DB-free preview; a new explicit `--database-free` verifier option fixes local semantics while production still defaults to configured history. No accuracy threshold or failed measurement was overwritten to obtain a pass.
