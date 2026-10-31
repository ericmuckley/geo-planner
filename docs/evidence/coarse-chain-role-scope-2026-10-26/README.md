# Declared-role reporting test — October 26, 2026

**The fixed reporting hypothesis fails: zero of the 32 candidate-bearing records becomes exhaustive.** Separating rows outside the already-declared supported-role universe leaves unresolved in-role evidence on every candidate-bearing record. Close this reporting branch; no match, speed coverage or model is promoted.

The [execution recipe](execution-plan.json), SHA `755e53b44276429638969645629ab85a0c475a6a1a59a22e07b055f95a3724b2`, freezes code, inputs and [reporting rules](rules.json) before execution. It implements the preceding [prospective plan](../coarse-chain-exclusions-2026-10-26/next-role-scope-plan.json). Support required at least one newly exhaustive candidate-bearing record. That criterion is unchanged after seeing the result. [Decision](decision.json), [full report](report.json).

## Result and denominators

| Cohort | Arc records | Outside declared roles: incidences / IDs | Unresolved in-role: incidences / IDs | Newly exhaustive candidate records |
| --- | ---: | ---: | ---: | ---: |
| All windows | 2,469 | 766 / 286 | 2,568 / 709 | 0 |
| Candidate-bearing | 32 | 171 / 72 | 99 / 48 | 0 |
| Formerly absent with an uncapped chain | 14 | 68 / 31 | 55 / 27 | 0 |
| With cache, without a candidate | 513 | 595 / 228 | 2,469 / 676 | 0 |
| Empty cache, unmeasured | 1,924 | 0 / 0 | 0 / 0 | 0 |

An incidence is an excluded row within an arc/window record. IDs are retained publisher `id/version` pairs, not independently identified physical roads. Cohorts overlap and their unique counts cannot be added. Source km can repeat alignments/windows; weighted samples remain the original Census denominator.

All **32 original `unresolved_with_candidates` outcomes** retain that original status and become `unresolved_in_role_with_candidates` in the additional reporting field. They retain all **82 saved candidates**. The remaining candidate-cohort blockers carry these frozen reasons:

| In-role reason | Incidences |
| --- | ---: |
| Endpoint farther than 25 m from own aligned samples | 71 |
| Tied/nonprogressing endpoints | 16 |
| Nonempty level rules | 6 |
| Endpoint outside the fixed window | 6 |

Reasons may overlap. The 171 out-of-role incidences retain every additional reason, including thirteen level-rule labels. Moving those rows outside this particular declared graph universe does not dismiss their physical relevance or grant car permission.

Across all records, **192** have scoped `no_declared_role_chain` status; these were already exhaustive `no_cached_chain` records under the old declared constraints. They are not new successes. **321** remain unresolved without candidates. The **1,924 empty-cache records remain unmeasured**. All **21 source windows remain incomplete**; five contain partial cache data. Future source records could add competitors.

All 55,120 rows, 2,469 arc/window records, 85,629 weighted samples, 85/105 source classes, fourteen original existential geometric positives, zero caps and **2.827 baseline provisional eligible km** remain unchanged. This is no new usable-speed coverage, physical/global identity, access or ETA accuracy evidence.

## Implementation and controls

[Classifier](../../../scripts/classify_chain_uncertainty.py), [independent audit](../../../scripts/coarse_chain_uncertainty_audit.py), [12 fixtures](../../../scripts/coarse_chain_uncertainty_test.py).

The output adds only `declaredRoleScope` and `reportingProvenance` to each saved chain record. Every original JSON field, node, candidate, reason and exhaustiveness flag equals its saved value; original input bytes remain untouched. A row is outside declared roles exactly when its frozen reasons include `unsupported_road_role`. All other excluded rows remain unresolved in-role. Scoped exhaustiveness requires nonempty cache, an uncapped original search and no unresolved in-role rows. Zero/single/multiple labels use the unchanged saved candidate count.

The independent audit reconstructs partitions, cache/cap/status priorities, candidate/cohort/window/class aggregates and the fixed hypothesis decision. It verifies every original field, source weight and raw role/scope/level/connector binding. Shared sealed parser/hash primitives are explicit. No geometry sampling, node creation, adjacency, chain enumeration, graph arrays or completed producer is replayed. [Audit](audit.json).

**Twelve tests pass on host and network-disabled Linux.** Fixtures cover mixed role/level reasons, unresolved in-role blockers, caps, empty cache, multiple candidates, unchanged original fields and weights, and rejection of a physical-identity assertion. Geometry and matcher functions raise if called by the new reporting path. Biome checks 197 files; app typecheck and ordinary build pass. [Host tests](unit-tests.txt), [Linux tests and guards](linux-tests.txt).

One correctly bound real run exits zero, without OOM; owned container removal succeeds. Cached Linux uses network=none, read-only code/inputs/root, 1 GiB/zero swap, independent one-hour watchdog, 128 MiB output and 64 MiB maximum tmp. No image pull, source/tool/provider request, whole-workspace or credential mount. The **8.984 s analysis interval** includes parsing, reporting, output and independent audit after worker input-hash/preflight checks; host hashing and Docker startup are also excluded. Output is **54,406,676 bytes**; plus maximum tmp is 121,515,540 bytes. These are offline-tool scopes, not application latency or measured peak memory. [State](state.json), [container](container-result.json), [cleanup](cleanup.json).

Ignored `data/coarse-quality/overture-timing-chain-role-scope-v1/` preserves 31 files: row/hash inventory, additive reporting records, 21 window/class summaries, report/audit/state/container/cleanup and exact recipe. Small results are copied here. All prior source/cache/failure records and sealed producers remain untouched. This work is local/uncommitted; deployed v9, grid/UI/env/DB/npm and all 48/6/29 provider budgets remain unchanged.

## Next input decision

Keep the incomplete cache research-only and stop refining reporting labels. The next [implementation and synthetic-test plan](next-fragment-plan.json) tests a concrete geometry limitation: Census and publisher segments need not end at the same places. A separate terminal-fragment matcher may clip the ends of a connected path while retaining original connector requirements for interior joins, unchanged level/access filters and all ambiguous alternatives.

That prototype has **not** been implemented or executed. Its exact projection/interval rules, code, inputs, resource controls and real-data hypothesis must be frozen before any new cached-data enumeration. Synthetic segmentation/reversal, overhanging endpoints, invalid joins, parallel/crossing geometry, ambiguous projections, scoped metadata and caps must be tested first. No acquisition, old matcher retuning, timing policy or production change follows from this report.

Read-only recovery; neither command reruns a producer:

```sh
python3 -B docs/evidence/coarse-chain-role-scope-2026-10-26/verify.py
python3 -B docs/evidence/coarse-chain-role-scope-2026-10-26/verify.py --local-assets
```

[Commands and asset requirements](../../local-development.md#offline-declared-role-reporting), [ordered next task](../../next-steps.md).
