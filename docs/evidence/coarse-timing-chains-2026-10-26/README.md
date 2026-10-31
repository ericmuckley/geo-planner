# Bounded endpoint-connected matching — October 26, 2026

**The frozen geometric hypothesis passes: 14 formerly absent arc/window records have an uncapped declared-valid connected chain.** They represent **21.255 km of original Census source-arc distance**. This is candidate-matching evidence, not new usable-speed coverage or a map accuracy improvement. Every candidate-bearing arc still has unresolved aligned rows; none is promoted to an exhaustive single match. Further acquisition remains stopped.

The [execution recipe](execution-plan.json), SHA `84aa2a9446495d7b00be88b1bc8cb271490e77d3092e9c7586dfe411578fd6f5`, freezes code, inputs, [progress/minimality/cap rules](rules.json) and decision before enumeration. It implements the previous [matching hypothesis](../coarse-timing-compatibility-2026-10-26/next-match-plan.json) on saved files only. All 21 source windows remain incomplete. The source timeout, failed cache preflight and earlier rejected candidates remain preserved. Work is local/uncommitted at `648c731`; v9/grid/UI/env/DB/dependencies/deployment are unchanged.

## Measured result

All **55,120 identities, 2,469 Census arc/window records and 85,629 source samples** reconcile. The original positive weights, 85/105 classes, saved sample memberships and old single/ambiguous/absent classifications remain unchanged.

| Outcome in the five windows with cached rows | Arc records | Original source km |
| --- | ---: | ---: |
| Unresolved, with declared-valid candidates | 32 | 32.495 |
| Unresolved, without a candidate under these rules | 321 | 310.819 |
| No chain under the declared constraints; no aligned rows | 192 | 198.201 |
| Total | 545 | 541.515 |

The sixteen empty-cache windows retain **1,924 records / 1,536.723 source km as unmeasured**. Across all windows there are 2,469 records / 2,078.238 source km. These are weighted arc/window denominators, not deduplicated physical road lengths; reverse arcs or overlapping windows can repeat physical alignments. Empty caches do not establish absent roads or attributes.

The 32 candidate-bearing records contain **82 minimal candidate chains**, from one to sixteen segments. **Fourteen formerly absent records** have a declared-valid multi-segment chain with >=80% original weighted support and no cap; this satisfies the predeclared existential hypothesis. Thirteen candidate chains have all members passing the existing static/bidirectional parser, but unresolved competitors and incomplete data remain. They are not thirteen qualified roads or a new coverage result. The **2.827 provisional eligible-speed km baseline remains unchanged**.

No search hits the 64-row or 4,096-expanded-state caps. All 32 records with candidates have other aligned rows excluded by unresolved metadata/geometry constraints, so no candidate-bearing record receives `single_cached_chain` or `multiple_cached_chains` as an exhaustive result. Individual candidate counts and every alternative remain visible. [Full report](report.json), [decision and positive record roster](decision.json).

## Declared matching rules

[Matcher](../../../scripts/coarse_timing_chains.py), [independent audit](../../../scripts/coarse_timing_chains_audit.py), [17 fixtures](../../../scripts/coarse_timing_chains_test.py). The shared [bounded runner](../../../scripts/offline_timing_runner.py) is unchanged.

Only rows already supporting saved samples are considered for each arc. Car-road geometry candidates use roles supported by the frozen parser, a single decoded line, no nonempty level rules and one distinct connector ID at each raw endpoint (`at` within 1e-9 of 0 or 1). Malformed, missing/interior-only/multiple endpoint IDs, self-loop identity, multipart geometry, explicit level rules and endpoints outside the fixed window stay unresolved. No access, turn or grade permission is inferred.

For each endpoint, nearest **own aligned samples** must lie within 25 m. Distances within 1e-9 km of the minimum form a tied progress interval. The two endpoint intervals must be disjoint and strictly ordered; otherwise the row is unresolved. Rows orient from lower to higher sample progress. Joins require equal exit/entry IDs, endpoint separation <=25 m and the exact increasing sample/progress inequalities in [rules.json](rules.json). These sampled constraints do not prove physical within-row monotonicity, driving connectivity or road identity.

Depth-first enumeration seeds every valid row in ascending source ordinal order, traverses ascending successors and prohibits repeated rows. Support is the union of member sample bitsets counted once, weighted by original Census km, with the unchanged 80% threshold. A candidate is minimal only when no proper contiguous subchain qualifies. Reverse representations share one canonical key; the actual progressing order remains evidence. No first-path selection or speed averaging occurs.

The independent audit reconstructs progress, checks all-pairs adjacency and uses a separate iterative bounded enumerator. It tests every proper contiguous subchain for minimality, reconciles alternatives/caps and preserves frozen parser results and raw scope hashes per member. Shared sealed numeric/geometry/parser primitives, the tested raw metadata filter and source-sample restoration are explicit limitations. This is not independent physical road/access/completeness validation. [Audit](audit.json).

## Unresolved inputs and decision

Reasons below count **arc-row incidences with overlaps**, not unique roads:

| Exclusion reason | Incidences |
| --- | ---: |
| Nonempty level rules remain unsupported | 1,385 |
| Endpoint farther than 25 m from its own aligned samples | 1,171 |
| Unsupported road role | 766 |
| Endpoint outside the fixed window | 181 |
| Tied/nonprogressing endpoints | 37 |

The supported hypothesis demonstrates that some split-ID geometric matches can form chains under the declared endpoint constraints. It does not resolve these competing rows or justify relaxing a filter after seeing the result. Raw level values, access scopes and endpoint constraints remain recorded, with no semantic admission. All 6,230 speed-tagged / 15,022 access-scoped rows and original exclusive parser counts reproduce.

Decision: preserve this prototype and perform **one bounded offline audit of unresolved exclusions** before specifying another matching-input policy. [next-exclusion-plan.json](next-exclusion-plan.json) requires unique-road and incidence denominators, raw level categories, frozen endpoint/progress measurements and all candidate-bearing records. It must distinguish declared exclusions from unknown competitors without claiming they are harmless, and choose one prospective geometry-only hypothesis or stop this input. No revised matcher, source request, scope reinterpretation or timing candidate is authorized by this result.

## Resource and software checks

**17 fixtures pass on host and network-disabled Linux**. Cases include connected/disconnected splits, parallel alternatives, coordinate gaps, reversed geometry, progress ties, minimality, nonuniform weights, unknown metadata, multipart geometry, raw access scopes, real 64-row limits, state-cap partial candidates and end-to-end chain-tamper detection. [Host tests](unit-tests.txt), [Linux tests and guards](linux-tests.txt). Biome checks 197 files; app typecheck and ordinary build pass.

The cached image uses network=none, read-only code/input files/root, cgroup **1 GiB / zero swap**, an independent one-hour watchdog, 128 MiB output and 64 MiB maximum tmp. No source/tool/provider request, image pull, dependency installation, graph-array load or driving-time/contour query occurs. The only graph enumeration is this declared local matching hypothesis.

Worker elapsed **9.497 s** includes loading, matching/output and independent audit; host hashing and Docker setup are excluded. Output is **56,263,079 bytes**, below 128 MiB; plus maximum tmp is 123,371,943 bytes. These are offline-tool scopes, not app/Vercel latency, model memory or measured peak memory. Exit zero/not OOM; owned container removal succeeds. [State](state.json), [container](container-result.json), [cleanup](cleanup.json).

Ignored `data/coarse-quality/overture-timing-chains-v1/` preserves 31 files: raw endpoint/level/scope-hash ledger, all candidate/node/exclusion records, 21 window/class summaries, result/audit/state/container/cleanup and exact recipe. Small measured records are copied here. Preserve this run and all prior source/cache/failure evidence; do not overwrite or replay completed producers.

Read-only proof:

```sh
python3 -B docs/evidence/coarse-timing-chains-2026-10-26/verify.py
python3 -B docs/evidence/coarse-timing-chains-2026-10-26/verify.py --local-assets
```

[Commands and recovery](../../local-development.md#offline-endpoint-chain-matcher), [next task](../../next-steps.md).
