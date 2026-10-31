# Cached geometry and scope compatibility — October 26, 2026

**Decision: test one conservative connected-segment matcher using the same cache. Keep further acquisition stopped and leave speed/access parsing unchanged.** The frozen single-ID constraint excludes 163 Census arcs whose nearby parallel geometry, taken across several publisher segments, supports at least 80% of their original weighted length. This establishes a limitation of that matcher; it does not establish physical road identity, connected driving access or a cause of every failed match.

The [exact recipe](execution-plan.json), SHA `6361ce288088706c74722d39112acd7a9da31e364446f08fa84458145c41c3df`, binds code, inputs, thresholds and output before execution. The diagnostic uses saved records only: **zero new network/tool/provider requests, zero routing/ETA queries**. All 21 source windows remain incomplete, including the five with cached rows. The original source timeout, cache-run preflight failure and rejected candidates remain preserved. V9/grid/UI/env/DB/dependencies/deployment are unchanged; this work is local/uncommitted at `648c731`.

## Geometric result

All **55,120 retained identities, 2,469 Census arc/window records and 85,629 samples** reconcile. Sampling retains the original cumulative source-km weights, midpoint spacing <=25 m, distance <=25 m and undirected tangent <=15°. At each sample, support from several publisher segments counts only once. Multipart gaps never gain joining lines.

| Geometry in the five windows with cached rows | Arc records | Original Census km | Sample-supported Census km |
| --- | ---: | ---: | ---: |
| No aligned cached geometry | 192 | 198.201 | 0 |
| Partial support, below 80% | 18 | 15.486 | 5.199 |
| At least 80% union support, no qualifying single segment | 163 | 259.931 | 259.381 |
| Existing single-in-cache match | 73 | 35.474 | 35.474 |
| Existing ambiguous-in-cache match | 99 | 32.423 | 32.423 |
| Total | 545 | 541.515 | 332.477 |

The union supports **61.398%** of these 541.515 original weighted Census km. The **0.522% provisional eligible-speed result remains unchanged at 2.827 km**. These metrics have different meanings: geometric support alone supplies neither speed eligibility nor connectivity. Missing publisher records can add competitors; neither value is final coverage or a conservative lower bound on eventual unique/usable matching.

The other sixteen windows have no cached records and remain **unmeasured**, not evidence of absent roads or attributes. Including them preserves 2,469 records / 2,078.238 Census km. All original classifications reproduce exactly: 2,297 absent-in-cache, 99 ambiguous and 73 single. The 163 union-supported records are a partition of existing absences, not replacements for the old results. [Full report](report.json), [post-result arithmetic and decision](decision.json).

The union combines nearby aligned geometry regardless of publisher ID, role, access or level. It may combine separate carriageways, paths or unrelated pieces. It is not a chain, connected route, unique road, usable speed coverage, national estimate or proof that real-road fragmentation explains those cases. No road-chain enumeration occurs in this run. Natural Earth/base alignment remains unresolved and outside the Census denominator. Publisher clipped geometry km remain separate from original weighted Census km.

## Raw scopes

All raw rules and source record IDs remain bound per retained row. Rule-level leaf/value counts are distinct from row counts; scope flags overlap.

| Raw inventory | Rows | Rules |
| --- | ---: | ---: |
| Nonempty speed limits | 6,230 | 6,496 |
| Missing speed limits | 48,890 | — |
| Nonempty access restrictions | 15,022 | 17,655 |
| Missing access restrictions | 40,098 | — |

Speed-rule rows include 185 partial spans, 167 conditional mode scopes, six heading scopes and 207 with multiple maximum values. These are raw observations: different values across spans/modes do not automatically conflict. The frozen speed-only parser reports zero conflicting rows. Raw maximum-unit occurrences are 6,482 mph and fourteen km/h. Conditional mode occurrences include 162 hgv and five bicycle values; these are not ordinary-car speed assertions.

Access rows include 6,623 heading scopes, 5,916 recognition scopes, 3,354 mode scopes, 1,004 purpose/using scopes, 191 vehicle-dimension scopes and eleven time scopes. Rule-level access types are 8,723 allowed, 7,883 denied and 1,049 designated. The full nested values, units, intervals, headings, modes and conditions are retained; **an allowed value is not bidirectional car permission**. No rule interpretation or parser outcome changes.

All original exclusive parser outcomes reproduce: 19,795 unsupported roles, 18,925 missing, 12,740 access-scoped/restricted, 3,608 parser-eligible, 51 partial and one directional. Clearing access for the existing speed-only inventory remains observational; it grants no usability. [Detailed field/value and classification report](report.json).

## Controls and validation

[Diagnostic](../../../scripts/analyze_timing_compatibility.py), [independent audit](../../../scripts/coarse_timing_compatibility_audit.py), [shared bounded launcher](../../../scripts/offline_timing_runner.py), [14 fixtures](../../../scripts/coarse_timing_compatibility_test.py).

The cached Linux image uses network=none, a read-only root/code/input files, 1 GiB cgroup/zero swap, an independent one-hour watchdog, 64 MiB maximum tmp and 128 MiB budgeted output. The proven process-interface/route guard permits dormant kernel tunnels while rejecting active non-loopback links/routes; Docker network mode is checked before and after execution. No image pull, PyArrow/global/app installation, credential mount or whole-workspace mount occurs. Only the owned worker is removed.

The independent [audit](audit.json) checks every raw identity/field checksum and scope denominator, independently recomputes numerical sample memberships, weights and union partitions, and reconciles every window/class summary. It shares sealed geometry clipping/binning/decoder/parser and the tested new scope-profile function. It does not prove source completeness, physical road identity, connected chains or car-access semantics.

**14 tests pass on host and network-disabled Linux**, including split segments, parallel ambiguity without double counting, crossings/far parallels, disconnected parts, missing cache, original nonuniform weights, fixed thresholds, reversed geometry, overlapping scopes, malformed rules and end-to-end sample-tamper detection. Biome checks 197 files; app typecheck and ordinary build pass. [Host tests](unit-tests.txt), [Linux tests and actual guards](linux-tests.txt).

The worker completes in **39.465 s**, including input loading, diagnostic output and independent audit; host hashing and Docker setup are excluded. Output is **45,848,482 bytes**, below 128 MiB; with maximum tmp it is 112,957,346 bytes. These are offline-tool scopes, not app/Vercel latency, model memory or measured peak memory. Exit zero, not OOM; owned container removal is verified. [State](state.json), [container](container-result.json), [cleanup](cleanup.json).

Ignored `data/coarse-quality/overture-timing-compatibility-v1/` retains 31 files: raw-rule/ID ledger, per-sample support memberships, all 21 window/class reports, summary/audit/state/container/cleanup and frozen recipe. Small measured results are copied here. Do not overwrite or rerun this producer, mutate sealed helpers or retry the stopped source capture.

## Next action

[next-match-plan.json](next-match-plan.json) specifies one separately frozen matching-only prototype. It will require equal raw endpoint connector IDs, bounded coordinate/progress checks and explicit ambiguity/cap outcomes before calling any cached segments a plausible chain. All original data, weights, classifications and incomplete windows remain. The existing parser stays unchanged; no access/level/turn permission, speed averaging, ETA model, original 50% gate or runtime admission follows.

The geometric hypothesis must either find a declared-valid uncapped chain for at least one formerly absent arc or be rejected under that recipe. Any later road-data acquisition or timing policy still needs its own specification and original qualification gates.

Read-only verification:

```sh
python3 -B docs/evidence/coarse-timing-compatibility-2026-10-26/verify.py
python3 -B docs/evidence/coarse-timing-compatibility-2026-10-26/verify.py --local-assets
```

[Commands and recovery](../../local-development.md#offline-timing-compatibility-diagnostic), [ordered next task](../../next-steps.md).
