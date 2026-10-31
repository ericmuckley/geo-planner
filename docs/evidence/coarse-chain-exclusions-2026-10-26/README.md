# Frozen chain-exclusion audit — October 26, 2026

**Decision: retain all level/progress filters and specify one reporting-only declared-role uncertainty test.** The audit finds **3,334 excluded arc-row incidences across 995 retained publisher identities**. Within the 32 candidate-bearing arcs, there are **270 incidences / 120 identities**. Many carry an already-declared unsupported-role label; none of the level-tagged rows is explicitly uniform zero. The result justifies neither a level shortcut nor clearing competing geometry.

[The exact recipe](execution-plan.json), SHA `e11b33da9461de3aaf3a7874fe749896f2050b86722b3de2cc051d0b2546c0f1`, freezes the [categories, measurements and accounting rules](rules.json) before examining retained data. No matcher, adjacency or chain enumeration is replayed. All 55,120 identities, 2,469 arc/window records, 85,629 samples, 21 incomplete windows, original classifications, 82 saved chains/32 unresolved candidate-bearing arcs, fourteen existential positives, zero caps and 2.827 baseline provisional eligible km remain unchanged.

There are **zero new source/tool/provider requests or routing/ETA queries**. V9/grid/UI/env/DB/dependencies/deployment stay unchanged at `648c731`; this work remains local/uncommitted. Previous source/cache failures and sealed producers remain preserved.

## Exclusion accounting

| Cohort | Arc records | Excluded incidences | Unique retained publisher IDs |
| --- | ---: | ---: | ---: |
| All windows | 2,469 | 3,334 | 995 |
| Candidate-bearing | 32 | 270 | 120 |
| Formerly absent with an uncapped chain | 14 | 123 | 58 |
| With cache, without a candidate | 513 | 3,064 | 904 |
| Empty cache, unmeasured | 1,924 | 0 | 0 |

Cohorts overlap: the fourteen positives are within the candidate-bearing group. Unique counts identify fixed retained `id/version` pairs, not physical roads, and cannot be added across cohorts. Arc/window source km may repeat reverse alignments or windows. Full class/window/cohort denominators remain in [report.json](report.json).

| Frozen reason | All incidences / IDs | Candidate-bearing incidences / IDs |
| --- | ---: | ---: |
| Endpoint farther than 25 m from own aligned samples | 1,171 / 387 | 71 / 33 |
| Unsupported road role | 766 / 286 | 171 / 72 |
| Nonempty level rules | 1,385 / 310 | 19 / 9 |
| Tied/nonprogressing endpoints | 37 / 19 | 16 / 8 |
| Endpoint outside the frozen window | 181 / 50 | 6 / 3 |

Reasons overlap within an incidence. Their sum is not the 3,334 distinct incidences. Original reason precedence is preserved: metadata rejection may have prevented the old matcher from applying endpoint/progress checks. The new audit measures those endpoints separately without relabeling or admitting them.

## Raw levels and additional measurements

Of 55,120 retained records:

- **54,045** have missing level rules.
- **353** have whole-span uniform nonzero values.
- **722** have partial intervals. Of these, 696 have uniform nonzero values and 26 mixed values.
- **Zero** have explicit uniform-zero values. No malformed or unsupported-extra-field category occurs in this retained cache.

These are raw observations, not grade/access semantics. Missing values do not mean zero, and numeric zero would not establish ground-level driving connectivity. The 19 level-excluded incidences in candidate-bearing arcs are all partial, with uniform nonzero values. No original level rejection changes.

The independent endpoint measurements retain the frozen 25 m distance and 1e-9 km tie tolerance. Across all excluded incidences they flag 2,723 endpoint-distance and 766 tied/nonprogressing cases, versus the original applied reasons of 1,171 and 37. In candidate-bearing arcs the new measurement flags are 200 and 157, versus original reasons of 71 and sixteen. These overlapping flags include rows already rejected for another reason; they are not revised outcomes or predictions of which rows a future policy would admit.

## Candidate overlap

Among the 270 candidate-case excluded incidences:

| Overlap with saved candidate members | Incidences |
| --- | ---: |
| Samples and raw endpoint IDs | 36 |
| Samples only | 208 |
| Endpoint IDs only | 0 |
| Neither | 26 |

Shared sample weights sum to 25.336 **incidence km**. Repeated rows/candidates can share the same samples; this is not additive road coverage. A shared endpoint ID or sample does not prove a valid join, harmless competitor, drivable access or resolved uniqueness. No new join is tested.

The original candidate-member parser occurrences remain 28 usable, 743 access-scoped/restricted, 23 missing and two partial-scope. These are repeated candidate-member occurrences, not unique roads or newly usable km. All raw speed/access/level/connector values remain preserved in bound source/scopes/metadata inputs; the new ledger copies raw level rules and binds every original row/metadata/scope line and connector hash.

## Next decision

[decision.json](decision.json) records the post-result interpretation. Do not relax level or endpoint/progress rules, change speed/access parsing or acquire more data. [next-role-scope-plan.json](next-role-scope-plan.json) proposes a separate reporting hypothesis: a row already outside the frozen supported-role universe may be distinguished from an unresolved in-role row **only when describing enumeration within that declared universe**.

The future test must add separate fields, preserve every original status/candidate, and keep all caps, in-role uncertainty and incomplete source windows explicit. It must not call a role-scoped result physically or globally unique, grant car permission, change node/chain eligibility or run another matcher. That test has **not** been executed here. No current candidate is promoted or input policy admitted.

## Controls and validation

[Diagnostic](../../../scripts/analyze_chain_exclusions.py), [independent audit](../../../scripts/coarse_chain_exclusions_audit.py), [12 fixtures](../../../scripts/coarse_chain_exclusions_test.py). The shared bounded launcher and old helpers remain byte-identical.

The audit independently reconstructs raw-level categories, endpoint/tie measurements, overlap/cohort/reason counters and unique-ID denominators. It shares sealed raw-metadata, numeric and sample-restoration primitives. It does not establish physical identity, grade/access permission or source completeness. [Audit result](audit.json).

**Twelve tests pass on host and network-disabled Linux**, covering zero versus missing, partial/mixed/malformed/extra fields, overlapping intervals, frozen reason precedence, additional gated measurements, candidate overlap without connectivity inference, repeated incidences, empty windows, tamper detection and explicit prohibition of old adjacency/chain enumeration. Biome checks 197 files; app typecheck and ordinary build pass. [Host tests](unit-tests.txt), [Linux tests and guards](linux-tests.txt).

An initial invocation mistyped a placeholder hash. The plan-binding guard rejected it before creating the data-output directory, checking source inputs or accessing Docker. [That preflight rejection](preflight-rejection.json) remains preserved; no producer analysis occurred and no recipe changed. The correctly bound run then completes once with exit zero, not OOM; owned container removal succeeds.

The cached Linux worker has network=none, read-only code/input files/root, cgroup 1 GiB/zero swap, independent one-hour watchdog, 128 MiB output and 64 MiB maximum tmp. No source/tool/image acquisition, graph arrays or whole-workspace/credential mount. The **10.665 s analysis interval** starts after worker input-hash/preflight checks and includes parsing, inventory/measurements, output and independent audit. Host hashing and Docker setup are also excluded. Output is **47,403,931 bytes**, below 128 MiB; plus maximum tmp is 114,512,795 bytes. These are offline-tool scopes, not application latency, model memory or measured peak memory. [State](state.json), [container](container-result.json), [cleanup](cleanup.json).

Ignored `data/coarse-quality/overture-timing-chain-exclusions-v1/` retains 31 files: per-row raw levels/hashes, all measured exclusion/overlap records, 21 window/class summaries, report/audit/state/container/cleanup and frozen recipe. Small results are copied here. Preserve this run and all old source/cache/failure records; do not overwrite or replay producers.

Read-only verification:

```sh
python3 -B docs/evidence/coarse-chain-exclusions-2026-10-26/verify.py
python3 -B docs/evidence/coarse-chain-exclusions-2026-10-26/verify.py --local-assets
```

[Commands and recovery](../../local-development.md#offline-chain-exclusion-audit), [ordered next task](../../next-steps.md).
