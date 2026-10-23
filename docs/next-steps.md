# Next steps for coding agents

Updated October 23, 2026. Read [AGENTS.md](../AGENTS.md), [handoff](agent-handoff.md), [status](implementation-status.md) and [local development](local-development.md).

## Completed: v8, hosted slider and first frontier references

**V8 and the slider/frozen plan are committed through `9b3e83b` (`slider`), user-reported deployed.** Fifteen hosted API checks and automatic slider/loading/latest-result browser checks pass. Public responses do not expose Git SHA; hosted history writes were not repeated. [Hosted evidence](evidence/coarse-frontier-tool-2026-10-23/README.md). Runtime remains v8 at 0.025° / about 1.8–2.8km; no new graph/model/weight change or deployment has occurred.

The user approved the exact single-run budget and **all 48 reference requests succeeded**, with no retry/fallback/status probe/paid upgrade. All 48 pair; no snap exceeds 100m. Mean absolute difference is **52.273min**, median **37.254**, p90 **116.332**, mean signed **−38.967min**. At 6/10/12h the mean absolute differences are **33.985 / 44.060 / 78.775min**. Cell classifications: 23 correct /17 false reachable /five missed reachable /three ambiguous. These are selected boundary point probes at eight public origins, not national/area accuracy. [Complete results, raw records and diagnosis](evidence/coarse-frontier-reference-2026-10-23/README.md).

All 48 reconstructed model paths match the frozen point/cell costs and component sums. Road edges account for 98.64% of model time; endpoint attachments average 3.062min. Speed-tag differences between large fast/slow errors support a class-dependent experiment, not causal proof. The approved 48-request budget is **consumed**; no extra live request or retry is authorized. The now-observed 48 cases are development data for calibration, not a fresh candidate holdout.

Capture/replay tools, the new path inspector, synthetic tests, measured evidence and docs are **local/uncommitted**. Biome (153 files), app/strict diagnostic typechecks and ordinary build pass. The earlier 67-test tool/server result is preserved; no redundant server/DB/Vercel suite was rerun for the offline diagnostic. No env/schema/dependency/source-data change. Preserve all older/failed evidence and local source assets; do not rerun completed graph producers as health checks.

<a id="1-publish-and-verify-latest-v8"></a>
<a id="1-publish-and-verify-the-time-slider"></a>
<a id="1-authorize-and-acquire-the-frozen-reference-set"></a>

## 1. Prototype generic road-class timing calibration

Use the [predeclared candidate plan](evidence/coarse-frontier-reference-2026-10-23/calibration-plan.json), written before any candidate evaluation:

1. Version a new offline producer/candidate. Map source classes **105→95km/h** and **80→85km/h** everywhere; retain 55/90 classes, fixed 25km/h costs, geometry/topology/resolution and paid physical-transfer rules. Recompute source-arc/connector costs under the new class mapping; do not blindly scale aggregate costs that include unrelated fixed local transfers. Preserve all sealed producers and v8 bytes. Reuse pinned local sources; no download or provider request.
2. Add a candidate comparison path around the saved reference durations, leaving the sealed acquisition/scoring producer intact. Run exact searches for all 48 saved frontier cases and all 35 earlier regional cases, with the same attachments/cell classification rules and full per-case regression ledger. These are development comparisons, not an independent accuracy qualification. Never replace a query or add a city/coordinate/region exception.
3. Show the resulting contour/path differences at shared cameras and retain failures/regressions. Keep the deployed/default v8 unchanged until the candidate passes the gates below. A finer grid, paid provider or DB migration is unnecessary for this experiment.

**Pass before activation:** frontier mean absolute difference <=**47.0457883min** (at least 10% below 52.2730981); p90 <=**116.3315349min**; neither original regional-set mean absolute difference worse than the exact frozen v8 result. Retain all 83 cases and all 35 prior reached/shaded destinations, with full path sums, source-distance/geography/connector proofs and visible per-origin/per-route regressions. Runtime retained-memory, initialization, payload/package limits, server-only secrets and Vercel compatibility must continue to pass. Use the existing check/typecheck/build and relevant geometry/server/package checks when implementation changes.

If the candidate fails, preserve/reject it and diagnose source-class or route-geometry causes using the existing raw routes. Do not change the gates, hide regressions, replace cases or tune location-specific rules to make it pass. No candidate has been evaluated yet; improvement and runtime footprint are unmeasured.

## 2. Preserve reproducible offline reference access

The complete credential-free capture is available under `docs/evidence/coarse-frontier-reference-2026-10-23/reference/`; the current ignored original and diagnostic paths are in [local development](local-development.md#fixed-nonregional-frontier-plan). Safe current replay:

```sh
node --import tsx scripts/compare-coarse-holdout.ts --replay data/coarse-quality/coarse-frontier-reference-v1 > /tmp/coarse-frontier-reference-replay.json
```

It must be byte-identical to [comparison.json](evidence/coarse-frontier-reference-2026-10-23/comparison.json); all 48 attempts/pairs and all failure/skipped denominators are retained. Fresh-clone restore/replay commands have also been verified offline. Never reuse/modify a sealed capture directory or rerun acquisition as a health check. Any future fresh reference run needs its own explicit budget and independently frozen query plan.

## Deferred scope

Further resolution increases, precise topology/traffic/turns/terrain/access, border eligibility, exact coastlines, caching, accounts/sharing/import, history cleanup/rate limits, PostGIS/spatial layers and advanced routing research remain deferred. Unchanged persistence does not need the full DB integration suite rerun. The connected adapter and its endpoint mock already use the new HeiGIT host; no migration change is needed. Overture remains an alternative without measured extraction footprint.

Detailed outgoing-index calibration is complete: eight payloads reproduce at 2.415/2.416GiB. Partial-source six-hour forecast remains 9.290GiB with margin versus 4 GiB: hold. Profiling/expansion stay parked. [Evidence](evidence/source-outgoing-2026-10-19/README.md), [six-hour report](six-hour-preflight.md), [two-hour baseline](two-hour-region.md).
