# First fixed nonregional frontier reference run

October 23, 2026. Base application commit `9b3e83b` (`slider`), user-reported deployed and verified in the [prior hosted run](../coarse-frontier-tool-2026-10-23/README.md). This acquisition, offline diagnostic and current documentation/tooling changes are local/uncommitted. No application/graph/weight change, commit, push or deployment occurred.

**All 48 approved requests succeed and all 48 references pair with the frozen v8 model.** Mean absolute duration difference is **52.273 minutes**, median **37.254**, nearest-rank p90 **116.332**. Mean signed difference (model minus reference) is **−38.967 minutes**: 37 estimates are faster than the reference, 11 slower. This exposes material long-horizon error; it is not an improvement or nationwide accuracy qualification. [Complete comparison](comparison.json), [diagnostics](diagnostic.json).

## Acquisition and provenance

The user replied “Ok, lets continue” directly to the explicit request for 48 public routes through HeiGIT using the existing key, zero paid spending and no retries. [Single-run authorization](authorization.json). The frozen [plan](../coarse-holdout-plan-2026-10-23/plan.json), SHA `77360fec0906c5a3eeedc533eef55cbe8557659266c25badcc4b924412e4271e`, and sealed capture-tool/source bindings were checked before any call. No queries, thresholds or weights changed after reference results arrived.

Exactly **48 POST Directions requests** were attempted from `2026-10-23T19:47:06.202Z` to `2026-10-23T19:52:12.989Z`, all HTTP 200, no retry/fallback/status probe/paid upgrade. Minimum measured start interval **6500ms**, request/body deadline 45s. Returned remaining-quota headers go 1999→1952, consistent with 48 requests against the reported 2000 limit; this is an observation at capture time, not a claim about current remaining quota or a billing audit. The approved single-run budget is consumed; it is not a standing authorization for another run. [Capture summary](capture-summary.json), [raw records and sealed ledger](reference/ledger.json).

The captured response text totals **5,550,371 bytes**, maximum **197,049** per response, below the 2MB bound. No credential echo was detected before copying the 148 capture files into [reference/](reference/sha256.json); Authorization/request cookies are not stored. Provider engine 9.10.0, build 2026-08-13, graph 2026-09-21, OSM 2026-09-13. Engine/data metadata is preserved per case. Maximum measured endpoint snap is **79.63m**; zero cases exceed 100m, so the predeclared sensitivity subset equals the primary set. No failed, skipped, invalid or unpaired cases were removed.

**Reference attribution:** © openrouteservice by HeiGIT | Data from OpenStreetMap. Reference route outputs are recorded under **CC-BY-SA 4.0**, separately from the public-domain NE/Census runtime model; see the [provider conditions reviewed before capture](../coarse-holdout-plan-2026-10-23/README.md#proposed-reference-acquisition). The model is an approximation, and ORS is an independent static routing reference, not traffic truth or observed driving.

## Frozen scoring

These 48 points were deliberately selected 5–20 model-cell minutes inside/outside 6/10/12h frontiers at eight public origins outside the old Southern California reference set. Full point attachments were frozen before capture. They test the model’s boundary placement; they are not random national destinations or a reachable-area sample. Do not interpret the counts below as area accuracy. A reference within ±5 minutes of the budget is ambiguous; other classifications use the frozen whole-cell prediction.

| Horizon | Pairs/planned | Mean absolute difference | Median | p90 | Correct | False reachable | Missed reachable | Ambiguous |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 6h | 16/16 | 33.98min | 29.37min | 76.55min | 7 | 6 | 1 | 2 |
| 10h | 16/16 | 44.06min | 35.12min | 93.70min | 8 | 5 | 2 | 1 |
| 12h | 16/16 | 78.77min | 80.68min | 131.62min | 8 | 6 | 2 | 0 |

**All 48:** 23 correct, 17 false reachable, five missed reachable, three ambiguous; 45 nonambiguous comparisons, 22 misclassified. This is a sparse boundary-probe result. All 48 are finite; pair/planned denominators remain explicit.

| Validation origin | Pairs/planned | Mean signed difference | Mean absolute difference |
| --- | ---: | ---: | ---: |
| astoria-or | 6/6 | -65.09min | 65.09min |
| missoula-mt | 6/6 | -2.37min | 44.95min |
| hays-ks | 6/6 | +20.24min | 24.08min |
| duluth-mn | 6/6 | -1.22min | 20.76min |
| columbus-oh | 6/6 | -34.76min | 34.76min |
| asheville-nc | 6/6 | -61.29min | 61.29min |
| portland-me | 6/6 | -109.50min | 109.50min |
| savannah-ga | 6/6 | -57.74min | 57.74min |

The largest fast error is `portland-me-720-outside`: model 730.993min versus reference 869.952min, **−138.958min**. The largest slow error is `hays-ks-600-outside`: 610.199 versus 567.777min, **+42.422min**. These locations identify validation cases only; no routing rule names a city or region.

## Path diagnosis and selected next experiment

The [new offline inspector](../../../scripts/inspect-coarse-frontier.ts) searches the unchanged bundled v8 to 750 minutes solely to reconstruct outside 720 probes. All 48 point arrivals and cell arrivals match the frozen plan to 1e-8min; every reconstructed path component sum matches its point cost. It calls production `gridTransitions`, including both base/Census states, rather than implementing another routing graph. [All paths](paths.json.gz), [source/plan/report/path bindings](diagnostic.json).

Across these reconstructed paths, road edges account for **98.64%** of total model time. Mean components: road 552.887min, intercell local 2.643min, explicit layer transfer 1.934min, origin attachment 2.734min and destination attachment 0.328min. Endpoint attachment averages 3.062min and cannot by itself explain the 52.273min mean absolute difference. This is a description of selected v8 paths, not a causal decomposition of the error relative to a different reference route. Road-edge costs include source-arc/connector geometry, and short local transfers can also change which route is chosen.

The [additional analysis](analysis.json) maps base-layer road edges to their retained speed tags, without another search or provider call. All tag sums match the road components. Across all cases, 70.96% of road time uses 105-tag base links, 23.90% uses 80-tag base links and 4.71% uses Census-layer roads. The worst fast case has 713.262 of 726.778 road minutes in 105-tag links. The worst slow case has 553.085 of 600.043 road minutes in 80-tag links. This supports investigating class-dependent timing; tags are not actual speed limits or causal source attribution. Model chord/reference distance ratios of 0.955 and 0.982 in those cases do not isolate geometry or prove equal routes. [Reproducible analysis](analyze.py).

**Selected next prototype:** a generic source-class calibration, 105→95km/h and 80→85km/h everywhere; 55/90 classes and 25km/h local travel remain unchanged. Recompute source-geometry road/connector costs in a separately versioned candidate, preserving topology/resolution and fixed 25km/h components. Do not scale aggregate edge costs containing unrelated local transfers, modify v8 or add city/coordinate/region exceptions. This prototype has not been run, selected by a candidate score, activated or deployed. [Predeclared candidate policy and acceptance gates](calibration-plan.json).

Before activation, the candidate must reduce this frontier mean absolute error by at least 10% (<=47.0458min), not worsen its 116.3315min p90, and not worsen either original regional-set mean versus exact frozen v8 results. Keep all 83 development cases and every regression visible; all 35 prior reached/shaded destinations must remain reached/shaded. Physical/geography/path-sum and runtime/Vercel checks must pass. If it fails, preserve/reject it; do not relax the gates or add exceptions. Since these 48 outcomes have now been observed, they become development data for calibration and cannot serve as a fresh holdout for that candidate. A later independent reference run needs a new explicit budget.

## Verification and recovery

Two offline CLI replays match byte for byte. The copied reference manifest, all request/body hashes, 48-case ledger, allowed timings/headers, active graph hash and frozen plan remain intact. [Verification and producer bindings](checks.json), [evidence manifest](sha256.json). Biome (153 files), app/strict diagnostic typechecks and the ordinary [build](build.txt) pass. The new inspector’s meaningful behavior checks are all 48 frozen point/cell matches and path reconstructions; no redundant unit test or full server/DB suite rerun was needed. The prior 67-test tool/server result remains its own unchanged evidence. No Vercel rebuild was repeated for offline-only code.

Local capture: `data/coarse-quality/coarse-frontier-reference-v1/`; report: sibling `coarse-frontier-reference-v1-report.json`; diagnostic: `coarse-frontier-diagnostic-v1/`. The full credential-free capture is included under `reference/` for review/commit. For a fresh clone, copy it once to a new ignored directory and replay without key/network access; see [local development](../../local-development.md#fixed-nonregional-frontier-plan). Never rerun the capture command as a health check or reuse its directory. No env/schema/dependency change, source download, graph producer, memory sweep, hosted history write or detailed research build occurred. [Current next steps](../../next-steps.md).
