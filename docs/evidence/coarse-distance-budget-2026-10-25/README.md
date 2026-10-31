# Saved travel-distance budget — October 25, 2026

**Longer modeled travel does not explain the missed-reachable cases.** All six new misses and both persistent misses have unbuffered modeled distance intervals below the saved ORS polyline lengths. Across all 83 cases, intervals are shorter in **57**, longer in **five**, and overlap the recorded reference length in **21**. This supports prioritizing generic timing-model work; it does not select a speed factor or establish real-road speeds. Deployed v9 remains unchanged.

Local/uncommitted work at HEAD `648c731`. The [recipe](plan.json), SHA `f7e17bf75921fe89c85aa3b8e96e83bd99d5f461fc930a5f7251246ef54d25ab`, and [bound derivation](bound-derivation.json) froze before measurement, implementing the [prior specification](../coarse-timing-exposure-2026-10-25/next-diagnostic-plan.json). No graph/model load, routing search, field/contour, fitting, source producer/download, provider/env/key/DB input, runtime/config/dependency change, commit or deployment. Both earlier candidates retain their original rejection decisions.

## Accounting and bounds

The [standard-library tool](../../../scripts/coarse_distance_budget.py) checks each captured transition against the existing source/base proofs. **22,316 full-source occurrences and 6,576 base-road occurrences** retain original cumulative source kilometers and selected connector lengths. Revisited roads are counted per occurrence. Source geometry chords and base representative chords never replace these lengths.

Local and transfer steps use captured state coordinates because their model explicitly prices straight movement at 25 km/h. Local costs reproduce without rounding; transfer costs include upward decisecond rounding and a minimum 1/600-minute charge. Extra rounded time is separate from distance, including zero-length positive-charge transfers. All captured prices, component totals, pure class minutes and occurrence counts reconcile.

Mixed origin/destination attachment geometry stays unresolved. Each gets the conservative interval **[0, paid minutes × 105/60] km**. The unchanged base decoder caps visit speeds at 105; the frozen source policy uses 105/85; local movement uses 25. Existing full-cost checks establish that arc prices cover source distance, and `sourceMinutes`/outer rounding only add cost. Every eligible selected attachment therefore pays at least its weighted distance at 105. Zero remains the lower bound; paid time is not treated as exact distance and no particular physical attachment is inferred. [Full derivation and limitations](bound-derivation.json).

All **83 cases/35 older sensitivities** remain; all intervals are finite, no missing/unbounded case. Endpoint interval width is median **3.975 km**, maximum **14.312 km**. The distance is the **recorded unbuffered model walk-weight total**, not a fully reconstructed geometric route. Current-residual cohorts retain their previous memberships, not newly computed current-path lengths.

## Findings

Ratios below compare each model distance bound with the saved full ORS decoded-polyline length. Lower/upper columns are separate medians of case bounds, not the interval of one representative route. “Overlap” concerns these recorded numeric lengths only.

| Predeclared cohort | Cases | Shorter | Longer | Overlap | Median lower ratio | Median upper ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All | 83 | 57 | 5 | 21 | 97.32% | 99.07% |
| Frontier | 48 | 43 | 3 | 2 | 97.51% | 98.04% |
| Original | 11 | 4 | 1 | 6 | 97.85% | 101.15% |
| Regional | 24 | 10 | 1 | 13 | 92.38% | 100.18% |
| Unbuffered faster than ORS | 74 | 50 | 5 | 19 | 96.98% | 98.77% |
| Unbuffered slower than ORS | 9 | 7 | 0 | 2 | 98.99% | 99.28% |
| Six new misses | 6 | 6 | 0 | 0 | 98.73% | 99.14% |
| Two persistent misses | 2 | 2 | 0 | 0 | 99.17% | 99.51% |
| Original individual-regression limit exceeded | 17 | 12 | 1 | 4 | 98.55% | 99.39% |

None of the nine already-slower unbuffered cases has a definitely longer recorded modeled length. Seven are shorter; two overlap. All eight current misses are shorter even after conservative endpoint upper bounds. The earlier [fixed-policy control](../coarse-road-time-control-2026-10-25/README.md) showed almost no rerouting offset, while the [exposure join](../coarse-timing-exposure-2026-10-25/README.md) found broad class-share overlap. Together these observations do not support a blanket distance correction, another uniform time allowance or more display resolution as the answer to these timing failures.

They support **examining timing features beyond coarse class averages**. Different road choices, source dates, source generalization, provider semantics and timing assumptions remain confounded. Shorter recorded distance with longer recorded time demonstrates a pace/cost difference in these records; it does not establish the correct speed of a road or a causal traffic/turn delay. A speed adjustment is not selected by this audit.

Both modeled local/transfer distances and saved provider polyline lengths use spherical haversine with Earth diameter 12,742 km. Source lengths retain their frozen construction conventions, including approximate geographic treatment of source coordinates. Provider polyline quantization and generalized/missing model geometry are not physical uncertainty bounds. Numerical 1e-8 km comparison tolerance handles arithmetic only. Neither similar distance nor overlapping intervals establishes road identity, driving legality or true route length. ORS recommended-fallback semantics and 35 older Valhalla sensitivities stay explicit; no new Valhalla distance comparison or national/traffic/area/holdout claim.

[All rows, 20 cohorts and ledger](report.json), [per-occurrence audit](edge-audit.json.gz), [independent audit](analysis.json), [audit recipe](analysis-plan.json), [decision](decision.json).

## Decision and continuation

Prioritize **generic timing features**, retaining the existing geometry/display during the next design step. Before another candidate, inventory timing attributes and source-junction/turn information already available in the cached sources, graph and captured references. Distinguish original source junctions from artificial cell-crossing/simplification nodes. Source incidence/angles are not verified intersections, legal turns or observed delay. The [next specification](next-timing-plan.json) requires a concrete implementable hypothesis and separate freeze before any candidate; if essential attributes are missing, identify them and a bounded acquisition proposal instead of inventing speeds or retrying factors.

All original accuracy, physical/source, software/API, packaging/storage, first-query and visual gates remain. No production activation is justified by this diagnostic.

## Verification and recovery

Six artificial tests pass for repeated source occurrences, endpoint bounds/invalid prices, local/minimum transfer charges, source-versus-connector/chord accounting, mismatched proofs/chains and interval classification. Biome checks 197 files; app typecheck and ordinary build pass. Independent Python, without importing the producer, verifies **29,247 transitions**, every source/base occurrence and cost, local/transfer distances, endpoint intervals, comparisons and all **20 cohorts**.

The saved calculation takes **0.0796 s** after loading its captured-path file, including other evidence reads and accounting, excluding hash checks/earlier source production/output serialization. This is offline diagnostic time, not application/cloud latency or memory qualification.

Ignored `data/coarse-quality/distance-budget-v1/` holds the completed plan/report/compressed occurrence audit. All are preserved byte-for-byte here. Do not rerun the named output. Read-only recovery:

```sh
python3 -B docs/evidence/coarse-distance-budget-2026-10-25/verify.py
python3 -B docs/evidence/coarse-distance-budget-2026-10-25/verify.py --local-assets
```

[Exact completed commands](../../local-development.md#saved-travel-distance-budget), [ordered next task](../../next-steps.md).
