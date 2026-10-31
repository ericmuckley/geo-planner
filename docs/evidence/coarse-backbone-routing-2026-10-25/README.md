# Source-backbone routing candidate — October 25, 2026

**The first source-backbone candidate is rejected under the frozen accuracy gates.** One generic candidate was implemented and frozen before testing/search. Active v9 and production configuration remain unchanged. The [design](design-v2.json) and [execution recipe](execution-plan.json) bind the byte-identical binary/base qualified by the [previous package/load probe](../coarse-backbone-binary-2026-10-25/README.md). No provider calls, credentials/env files, DB input, downloads, new dependencies or deployment.

| Metric | Active v9 | Rejected candidate |
| --- | --- | --- |
| ORS mean absolute error, all 83 | 29.257 min | **43.234 min** |
| Frontier 48 mean absolute error | 44.629 min | **64.187 min** |
| Original 11 /regional 24 means | 7.223 /8.613 min | **16.832 /13.430 min** |
| Overall p90 absolute error | 70.048 min | **104.930 min** |
| False reachable /missed | 11 /2 | **32 /2** |
| Worst added error, frontier /older | — | **88.504 /27.269 min**, limits 20 /5 |
| Older Valhalla means, original /regional | 14.896 /13.389 min | **4.023 /5.050 min** |

Fourteen of 21 gates fail. All 83 cases remain finite; all 166 saved-baseline/candidate component sums and 35 older destinations shaded at 720 pass. The different Valhalla result remains visible and does not override the primary failure. Source-line/storage qualification did not establish travel-time accuracy. [Full report](report.json), [raw comparison](comparison.json), [normalized independent audit](analysis.json), [captured candidate paths](paths.json.gz).

The candidate uses original source-junction and cell-crossing nodes, bidirectional full arcs with their unchanged 105/85 source costs, and the existing coarse NE/local base. Cross-layer transfers use source nodes in their containing closed cells, strict continuous-land geometry and paid physical distance at 25 km/h, rounded upward to at least 0.1 second. Separate source occurrences do not merge by coordinate or display cell. Closed-cell enumeration includes the upper/right floor cells so forward/reverse transfers agree at exact grid crossings. No persistent expanded transfer index or query cache is added.

Arbitrary-point access enumerates sparse indexed arcs in the input cell and eight neighbors. It streams each arc's delta geometry, considers segment endpoints/projections and interpolates the stored full-source cumulative distances. Partial road costs retain a geodesic speed lower bound; local access pays 25 km/h. The existing v9 input boundary tolerance remains explicit. Same-arc origin/destination access avoids artificial endpoint detours while paying local and partial-road costs. Transfers between the base and source graph use zero water tolerance. Explicit source road geometry can cross generalized water; local transfers cannot.

Display arrival is separate from point timing: base labels plus source-segment arrival infima feed the existing whole-cell contour tracer. The own-origin cell remains visible for an accepted isolated input. Grid resolution stays 0.025°; source-line simplification remains bounded by 25 m. Neither establishes exact land/road access or national accuracy.

Thirteen synthetic tests pass, including an independent Bellman-Ford comparison, positive/symmetric paid transfers, separate source incidence, same-arc partial access, varint corruption/rounding, lake/island barriers, explicit source bridges, partial whole-cell arrival and arbitrary input validation. Biome checks 190 files; application and strict runner TypeScript checks and ordinary build pass. The initial runner typecheck command failed before checking code (TypeScript 6 TS5112); the [command correction](typecheck-command.json) adds `--ignoreConfig`, without changing candidate code or gates. The initial provisional design's diagnostic cap is corrected from 2160 to the confirmed prior-runner 900 minutes in design-v2 before implementation/testing; both documents remain preserved.

The single comparison completes all 21 origins and 83 ORS/35 Valhalla cases. [Independent Python audit](../../../scripts/analyze-backbone-routing.py) recalculates all 21 gates and166 component sums from saved outputs and confirms rejection. Every predicted trip becomes faster by mean 19.136 min; 13 absolute errors improve and 70 regress. Mean road/local costs fall 16.169/3.595 min while transfer cost rises 1.305; full Census edges account for 70.11% of candidate time, excluding mixed input/destination attachments. Those descriptive component shifts do not isolate the causal effect of topology, costs or reference-provider differences. No model rule, source, cost or threshold was changed based on results.

The raw runner spreads prior comparator rows and retains inherited `baselinePointMinutes`, `baselineErrorMinutes` and `candidateErrorMinutes` scalar fields. Those may describe the older v8/v9 comparison and are unused by gates. Use explicit nested `baseline` (v9)/`candidate` (backbone) objects or normalized `analysis.json` rows, whose errors are derived independently. Original code/exports are preserved unchanged.

Diagnostic fields use the same 900-minute cap as the prior comparator; origin preparation plus Dijkstra (`searchMs`) ranges 3.052–24.720 s. Binary/module loading, the display-arrival pass and polygon tracing are separate; this comparator does not trace contours. These are local offline diagnostic timings. Full public 30–720-minute packaged-query, retained/peak/cloud memory, physical/source/API/visual activation qualification stops after accuracy failure. No candidate Vercel build or deployment was attempted; v9 remains active.

## Recovery and next step

[Exact commands](../../local-development.md#source-backbone-routing-candidate). Ignored `data/coarse-quality/backbone-routing-candidate-v1/` preserves 45 files, including per-origin output and the complete rejected run. Root modules/runner/tests/analysis, this evidence and current docs remain uncommitted; a fresh clone at HEAD lacks them and all ignored assets. Do not rerun the candidate or graph producers as a readiness check.

```sh
python3 -B docs/evidence/coarse-backbone-routing-2026-10-25/verify.py
python3 -B docs/evidence/coarse-backbone-routing-2026-10-25/verify.py --local-assets
```

Next implement the [offline saved-path/provider diagnostic](next-diagnostic-plan.json), binding exact tools/commands/reference geometry inputs before execution. Use all 83/35 existing cases, captured full-source arc IDs/costs and reference options/source dates/snaps, with explicit coverage/missing-data accounting for unresolved attachments/coarse base chords. Compare source-path/corridor and cost exposure descriptively before another model policy. No new route search, references/provider calls, source downloads, speed fit or activation. The original accuracy/physical/runtime gates and consumed 48/6/29 budgets remain unchanged.
