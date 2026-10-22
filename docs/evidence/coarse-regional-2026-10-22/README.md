# Broader regional v2 validation — October 22, 2026

The fixed [24-route plan](reference/plan.json) uses twelve Southern California origins, all different from the San Diego tuning origin. Routes cover highway corridors, mountains, remote access, the coast and Salton Sea detours. Plan/model hashes were recorded **before** reference requests. V2 was unchanged throughout; no speed fitting or product change was made. [Current model report](../../coarse-estimator.md#broader-regional-validation).

## Results

All 24 local static Valhalla routes succeeded. Both grids reach **23/24** destination cells within the 720-minute search. On those paired finite cases, mean absolute difference changes:

- Cell arrival: **44.7m v1 → 27.3m v2**, with 19/23 improving.
- Approximate point arrival, adding straight destination access at 25 km/h to both: **53.0m → 37.7m**, with **18/23 improving and five regressing**. All finite v2 point estimates are slower than the reference.
- Salton City → Bombay Beach remains unreached in **both** grids; it stays in the report and is excluded from timing means, never counted as a zero error.

| Category | Planned / paired finite | Point mean difference v1 → v2 | Improved point cases |
| --- | ---: | ---: | ---: |
| Highway corridor | 5 / 5 | 65.2m → 30.1m | 5 |
| Mountain | 5 / 5 | 32.5m → 46.2m | 1 |
| Coastal | 4 / 4 | 53.1m → 24.6m | 4 |
| Remote | 6 / 6 | 48.8m → 30.9m | 5 |
| Lake | 4 / 3 | 75.1m → 67.5m | 3 |

[Full comparison](comparison.json) includes every route, representative positions, access costs, signed differences and both model hashes. Unlike the original eleven tuning cases, this new set exposes regressions. It remains one regional model comparison, with approximate access and no live ETA truth. Reference times span **15.2–272.2 minutes**; these routes do not validate six-/twelve-hour contour boundaries or national accuracy.

## Diagnosis and selected next correction

[Offline cell/access diagnostics](diagnostics.json) establish:

1. **Bombay Beach destination membership is asymmetric.** Cell 54962 has center `[-115.75,33.35]`, lake mask, no retained road links, no traversal and no display eligibility. The input itself lies inside the generalized lake but is accepted as an origin by the existing shoreline tolerance. Seed-only activation lets a query leave it; arrival from Salton City is blocked. The local reference snaps to a road within 9 m. Generalized lake membership does not establish actual water at the input. Fix land-supported shore-cell arrival/departure symmetrically while preserving open-water/island barriers.
2. **Mountain access regresses.** Palm Springs → Idyllwild is 53.2m in the reference. V1's approximate point cost is 56.0m; v2's is 96.4m. Combined endpoint access rises from 12.8m to 35.1m, and intercell cost rises from 43.2m to 61.3m. Representative positions explain part of the regression; this does not isolate every geometry/transfer effect or prove realistic mountain travel.
3. **Missing roads remain consequential.** Bakersfield → Big Bear is 186.8m reference versus 271.9m v2 with approximate access. The destination cell and all eight neighbors have no retained road links. Overland fallback substitutes for local road travel. The largest finite point differences are Bombay Beach → Salton City (**+99.4m**), Bakersfield → Big Bear (**+85.1m**) and Bombay Beach → Indio (**+73.8m**). Missing-road/access refinement is queued; increasing all speeds would not resolve the blocked shore cell.

The **next implementation task is shore-cell connectivity/display symmetry**, with class speeds held constant and a separately versioned candidate. Keep both original comparison sets and this unchanged-v2 validation. Mountain representative detours and missing generalized roads follow; do not resume detailed graph construction. Once this set informs another model, it is a regression set rather than a new holdout.

## Provenance and reproducibility

- [Capture header](reference/capture.json) binds the pre-request plan and unchanged model. The `reference/` directory contains status plus all 24 raw request/response records, named `<from>--<to>.json`.
- [Selected container](reference-container.json) mounts only the retained `data/valhalla-v2` graph read-only. [Graph provenance](reference-graph.json) records its manifest, static-road timestamp, limitations and fresh configuration/archive hash matches. Observed engine: `3.9.1-7fd2228e5`. No new graph build or source download occurred.
- Exactly **one successful local status request and 24 route requests**, zero hosted routing calls. No reference snap exceeds 100 m; no sampled returned route shape leaves or approaches within 5 km of the requested reference rectangle. These are diagnostics, not a source-completeness proof.
- [Capture issues](capture-issues.json) preserve an initial sandbox denial and an interrupted diagnostic that assumed every coarse label was finite. Its [source snapshot](interrupted-diagnostic.ts) is retained. Seventeen responses were preserved and the remaining seven appended; no successful response was overwritten or requested again. Null model costs are now explicit in analysis.
- [Verification](verification.json) records exact offline replay agreement, unchanged model/product files, check/typecheck/build and evidence bindings. [Provenance](provenance.json) identifies script/plan hashes; these are observations, not freezes on normal diagnostic code. Prior model/evidence bundles remain intact.

Safe default replay makes **zero network requests**:

```sh
npm run routing:compare:coarse:regional
node --import tsx scripts/inspect-coarse-regional.ts
```

To capture a deliberately new reference run, use `npm run routing:compare:coarse:regional -- --capture <unused-directory>` with the existing local service already running. `--resume <incomplete-directory>` only appends missing responses and never overwrites existing records; the failed request itself must be preserved in a separate run. Do not rerun capture to validate documentation. No database integration, Vercel build, deployment or browser flow was repeated for this offline-diagnostic-only change. The existing V2 packaging/browser/database proofs retain their original scope.
