# Cached terminal-fragment result — October 26, 2026

**The fixed geometry hypothesis passes: 96 previously zero-candidate arc/window records gain an uncapped path containing a terminal cut.** Their original Census source weights total **61.774 km**. The independent audit passes, with no search cap. This demonstrates a segment-boundary limitation in the old endpoint-only matcher; it does not establish physical road identity, driving permission, usable-speed coverage or ETA accuracy.

One execution uses the unchanged [frozen recipe](../coarse-timing-fragments-2026-10-26/execution-plan.json), SHA `509e98e071d67659698a550e6672766bad5e820a4f8d82c20688199669913fdd`, and [rules](../coarse-timing-fragments-2026-10-26/rules.json). No code, threshold, cap or decision criterion changes after the result. [Report](report.json), [independent audit](audit.json), [decision](decision.json).

## Geometry result

| Cohort | Arc/window records | Original weighted Census km | New variant paths |
| --- | ---: | ---: | ---: |
| Newly supported with terminal cuts | 96 | 61.774 | 185 |
| Previously candidate-bearing | 32 | 32.495 | 109 |
| All current candidate-bearing | 128 | 94.269 | 294 |

The 109 variants on previously candidate-bearing records include additional terminal intervals. The **82 original endpoint-chain candidates remain unchanged** in immutable nested controls; 294 variant paths are not 294 physical roads. Different intervals can represent the same road. All 32 old candidate-bearing records retain their original unresolved status. The 96 new positives were originally `unresolved_without_candidates`.

| Partially cached window | Census arc records | New supported records | Their original source km |
| --- | ---: | ---: | ---: |
| origin-01 | 81 | 16 | 9.038 |
| origin-02 | 67 | 34 | 26.590 |
| origin-03 | 98 | 6 | 6.351 |
| origin-04 | 265 | 28 | 8.587 |
| origin-05 | 34 | 12 | 11.208 |
| Total | 545 | 96 | 61.774 |

These are fixed validation windows, not location-specific routing rules. New positives include sixty 105 km/h source-class records and thirty-six 85 km/h records. Class values are unchanged model labels, not measured driving speeds. Arc/window km can repeat alignments and windows; they are not deduplicated physical-road km or national coverage.

Across all 2,469 records, statuses are 128 `cached_geometry_candidates`, 417 `no_candidate_under_fragment_rules` and **1,924 empty-cache/unmeasured**. All **21 windows remain incomplete**, including the five with partial rows. Missing source may add competing paths. No no-candidate result establishes road absence.

## Attributes remain the input limitation

[Read-only candidate accounting](metrics.py) uses saved candidates, parser labels and original sample weights without geometry or enumeration replay. [Exact metrics](metrics.json).

| Cohort | Records with any candidate whose members all pass the parser | Such candidate variants | Their saved-sample union km |
| --- | ---: | ---: | ---: |
| Newly supported records | 5 | 7 | 1.033 |
| Previously candidate-bearing records | 13 | 29 | 7.615 |
| All current candidate-bearing | 18 | 36 | 8.649 |

This union counts each original sample once per arc across parser-usable annotated candidates. It is **retained-cache opportunity**, not newly eligible speed coverage, a lower bound, physical/global uniqueness or car permission. Other candidate paths, excluded rows, raw conditional/directional rules, unknown grade/access and incomplete source remain unresolved. Cohorts overlap with wider report groups.

New-positive candidate-member occurrences include 260 access-scoped/restricted, fifteen missing, thirteen usable, two partial-scope and four directional labels. These repeat members across candidate variants; they are not independent roads. All raw metadata and the frozen parser remain unchanged. The **2.827 baseline provisional eligible km** stays an unchanged control, rather than being replaced by 8.649 km.

## Controls and preservation

The worker and independent audit reconcile all 55,120 retained rows, 2,469 original arc/window records, 85,629 sample weights, 85/105 classes, 21 incomplete windows, 82 old candidates, 32 old candidate-bearing outcomes, fourteen old existential positives and zero old/new caps. Every original chain field and original line hash is preserved. Saved full nodes retain eligibility; only terminal cuts have null connector IDs. Interior joins keep original IDs, distance/progress checks, level restrictions and all access/speed metadata.

The independent audit separately reconstructs projections, intervals/windows, all-pairs joins, iterative enumeration, every proper contiguous subchain, sample unions, parser annotations and the fixed decision. Sealed WKB/parser/sample/tangent/hash primitives are explicitly shared. This is no independent physical identity/access review. Eighteen host/Linux synthetic tests and check/typecheck/build from the frozen implementation remain checksum-bound; this execution/documentation follow-up changes no implementation and does not rerun those completed checks.

The cached Linux worker uses network=none, read-only individual inputs/code/root, 1 GiB/zero swap, one-hour independent watchdog, 128 MiB output and 64 MiB maximum tmp. No pull, graph arrays, whole-workspace/env/credential mount or new source/tool/provider request. One correctly bound run exits zero without OOM; owned container removal succeeds. [State](state.json), [container](container-result.json), [cleanup](cleanup.json), [run log](analysis-run.txt).

The **12.250 s worker analysis interval** includes parsing/decoding, geometry/projections, enumeration, output and independent audit after worker input-hash/preflight checks. It excludes host hashing, Docker startup and the later read-only candidate-metric aggregation. This is not application latency or an isolated routing-search measurement. Output is **60,033,722 bytes in 31 files**; plus maximum tmp is 127,142,586 bytes. No measured peak-memory claim.

Ignored `data/coarse-quality/overture-timing-fragments-v1/` retains all original controls, row/hash ledger, fragments/projections/issues/candidates, 21 window/class summaries, report/audit/state/container/cleanup and exact recipe. Preserve this run, all earlier stopped-source/failure records and sealed producers. Do not overwrite or rerun them. This work remains local/uncommitted; deployed v9/grid/UI/env/DB/npm and consumed 48/6/29 provider budgets stay unchanged.

## Next input decision

Keep this partial cache research-only and close further matcher/label tuning for it. The geometry improvement does not supply enough qualified attributes or complete-source evidence to build a timing candidate. This is a decision about the stopped cache, not a conclusion about nationwide publisher coverage.

The next [bounded input-design scope](next-input-design-plan.json) compares at most two primary-documented acquisition approaches, selects one enforceably bounded complete-window pilot or records no-go, and retains every original completeness/usable-limit/match-review/model gate. It permits documentation review, not road-data/tool acquisition, stopped-pilot retry, semantic permission assumptions or runtime changes. Eventual Vercel queries should continue to use compiled static costs without a per-query road-data or database dependency.

Read-only recovery; no geometry or producer replay:

```sh
python3 -B docs/evidence/coarse-timing-fragments-run-2026-10-26/verify.py
python3 -B docs/evidence/coarse-timing-fragments-run-2026-10-26/verify.py --local-assets
```

[Commands/recovery](../../local-development.md#completed-cached-terminal-fragment-run), [ordered next task](../../next-steps.md).
