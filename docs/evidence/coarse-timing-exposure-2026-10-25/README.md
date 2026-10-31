# Saved timing errors and path exposures — October 25, 2026

**The saved road-class and partial-corridor features do not justify selecting a new timing rule.** Faster and slower predictions have broadly overlapping class shares; high measured source proximity also occurs among missed-reachable cases. The useful next distinction is modeled travel distance versus assumed travel speed, with unresolved path portions explicitly bounded. No factor or candidate was selected or evaluated. Deployed v9 stays unchanged.

This is local/uncommitted work at HEAD `648c731`. The [frozen recipe](plan.json), SHA `64e35ee018406147d7123950213875fbd2acb84d466c4fdd23643da3844c087a`, implements the prior [join specification](../coarse-road-time-control-2026-10-25/next-diagnostic-plan.json). It reads saved records only: no graph/model load, route/field/contour, fitting, source producer/download, provider/env/key/DB input, runtime/config/dependency change or deployment. Both earlier backbone candidates retain their original rejection decisions.

## Reconciliation and scope

The [standard-library join tool](../../../scripts/coarse_timing_exposure.py) and [six artificial fixtures](../../../scripts/coarse_timing_exposure_test.py) bind exact IDs across all **83 ORS cases/35 older Valhalla sensitivities**. Pure source-road minutes by class are independently reproduced from detailed source kilometers/class speeds and all selected base source-edge proofs. Artificial base connectors, original rounding, local/transfer costs and mixed endpoints remain separate. All original old/held/current component totals and reference/model prices reconcile.

Class exposure describes the **earlier captured unbuffered path**, not the actual rerouted 1.10 path. The earlier [control](../coarse-road-time-control-2026-10-25/README.md) measured only 0.0268 min mean rerouting benefit, but this does not make the two paths identical. Corridor metrics compare the detailed Census subset with ORS; representative base chords and mixed attachments do not acquire complete geometry through this join. No inference of road identity, legal access or whole-route overlap.

All 83 records remain in the coverage ledger. Source-to-ORS proximity is available for **80**, null for **three with no complete Census arc**. Provider-to-empty-subset zeros are retained as structural coverage zeros, not evidence of a different complete route. All 20 predeclared cohort summaries expose available/missing counts, medians and full ranges. Query-budget and frontier-only budget summaries are separate: older 35 use a 720-minute display budget and do not constitute 12-hour travel references.

## Findings

Signed error is model minus ORS time. Shares are per-case pure source-road time in the 105 km/h model class; the label is a model assumption, not a measured speed or speed limit.

| Predeclared cohort | Cases | Median 105-class share | Share range | Median detailed-source share within 3 km of ORS |
| --- | ---: | ---: | ---: | ---: |
| Unbuffered faster than ORS | 74 | 71.12% | 0–100% | 90.19% (71 available, 3 missing) |
| Unbuffered slower than ORS | 9 | 78.45% | 0–99.994% | 100% (9 available) |
| Current allowance faster than ORS | 57 | 76.39% | 0–100% | 92.85% (54 available, 3 missing) |
| Current allowance slower than ORS | 26 | 56.48% | 0–99.994% | 85.96% (26 available) |
| Six new misses | 6 | 53.00% | 4.12–99.994% | 100% (6 available) |
| Two persistent misses | 2 | 82.85% | 78.45–87.24% | 100% (2 available) |
| Original individual-regression limit exceeded | 17 | 82.21% | 4.12–100% | 96.46% (17 available) |

The six new misses also span **0.0061–95.88% in the 85 class**. Their measured detailed-source proximity ranges **58.55–100%**. All eight current misses have some detailed Census geometry; none is one of the three empty-subset cases. Even where the measured subset lies near ORS, the reverse subset coverage remains incomplete and the unmeasured base/attachment geometry remains unresolved. A 100% subset proximity is not proof of an identical full route.

Unbuffered signed-error medians are **−28.096 min** among 74 faster cases and **+14.673 min** among nine slower cases. After the allowance, 57 remain faster and 26 become slower. The [fixed-policy control](../coarse-road-time-control-2026-10-25/README.md) already attributes nearly all of the time increase to direct pricing; this join does not isolate its causes further. Group medians/ranges and overlapping features do not prove that no useful rule exists, but they do not support choosing new class multipliers, a corridor cutoff or a place-specific exception.

[All joined rows, distributions and ledger](report.json), [independent audit](analysis.json), [audit recipe](analysis-plan.json), [decision](decision.json). ORS's observed recommended fallback and older Valhalla disagreement remain explicit; all primary gates and development-data limitations are unchanged. There is no new accuracy, national, traffic, area or holdout claim.

## Decision and next action

**Evidence is insufficient to choose a selective timing correction from these features alone.** The smallest next diagnostic is a saved **distance budget**: sum exact source-road lengths and selected base connectors, account for local/transfer lengths using captured states and unchanged formulas, and bound unresolved endpoint distances. Compare those bounds with saved ORS polyline lengths for all 83 cases, retaining the same cohorts and 35 sensitivity records. This can distinguish evidence of distance differences from cases compatible with similar distances; it cannot establish causal speeds or road identity.

The [next specification](next-diagnostic-plan.json) requires a separately frozen tool/recipe before that calculation. No full path is to be invented from base representative chords; no fitting, second factor, new routing search or provider acquisition. If unresolved geometry prevents a meaningful bound, retain that gap and identify the exact missing provenance. A later candidate still requires a separately frozen hypothesis and every original accuracy/physical/software/package/query/visual gate.

## Verification and recovery

Six synthetic tests pass: source/connector/rounding separation, duplicate/missing identifiers, invalid components/coverage, empty-subset null-versus-zero semantics, older-budget labeling and zero-source shares. Biome checks 197 files; app typecheck and ordinary build pass. The independent audit, which does not import the producer, reproduces all IDs/source sums/coverage and **20 cohort distributions**. The saved join takes **0.0289 s**, excluding prior asset construction and proof checks; this is an offline file-analysis observation, not app/cloud performance.

Ignored `data/coarse-quality/timing-exposure-v1/` contains the completed plan/report. Both are preserved byte-for-byte here. Do not rerun the named output. Read-only checks:

```sh
python3 -B docs/evidence/coarse-timing-exposure-2026-10-25/verify.py
python3 -B docs/evidence/coarse-timing-exposure-2026-10-25/verify.py --local-assets
```

The second check additionally verifies prior ignored assets and installed tools. [Exact completed commands](../../local-development.md#saved-timing-exposure-join), [ordered task](../../next-steps.md).
