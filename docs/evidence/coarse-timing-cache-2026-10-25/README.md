# Partial timing-cache analysis — October 25, 2026

**Decision: do not download more with the current reader/matcher recipe or use this cache for a timing correction.** The offline analysis and independent accounting pass, but eligible single-segment matches cover only **2.827 km** provisionally. First diagnose geometric segmentation and scope exclusions using the same saved data. This is a decision about the current approach, not a nationwide rejection of Overture or proof that its missing records lack useful attributes.

The [original source attempt](../coarse-timing-pilot-2026-10-25/README.md) remains stopped, with 123,155,489 received bytes, 1,115 attempted GETs and zero retries. This task makes **zero source/tool/provider requests**. All **21 source windows remain incomplete**, including the five with some saved records; the other sixteen are unmeasured. V9, its display grid, app/env/DB/dependencies and deployment remain unchanged. Work is local/uncommitted at `648c731`.

## Observed cache

| Measured item | Result |
| --- | ---: |
| Retained unique road identities reconciled | 55,120 |
| Records with a nonempty speed-limit field | 6,230 (11.30%) |
| Records passing the frozen whole-span/static/bidirectional limit parser | 3,608 |
| Clipped cached publisher geometry, all road roles | 6,347.506 km |
| Geometry passing that parser | 464.064 km (7.31%) |
| Census arc/window records reconciled | 2,469 |
| Original weighted Census geometry across all 21 windows | 2,078.238 km |
| Original weighted Census geometry in the five windows with cached rows | 541.515 km |
| Provisional eligible single-candidate arc records | 10 |
| Provisional eligible matched Census km | 2.827 km |
| Its fraction of Census km in the five windows with cached rows | 0.522% |
| Its fraction across all 21 windows | 0.136% |

The percentages describe this partial cache only. They are **neither final coverage nor conservative lower bounds on final usable matching**: missing roads may add competitors. The original 50% feasibility screen and independent road-identity review are not qualified or repeated. A speed limit is not an average journey speed.

The preserved classification counts are 19,795 unsupported road roles, 18,925 missing limits, 12,740 access-scoped/restricted, 3,608 parser-eligible, 51 partial-scope and one directional. These are exclusive parser outcomes. Overlapping raw flags additionally retain all 185 partial, 167 conditional and six directional speed-rule records, including cases masked by the parser's access-first rejection. Raw source/license, access, turn, level, unit, heading and between fields remain hash-bound per record. All 55,120 records have source attribution; no licensing or car-access admission is inferred from field presence.

| Window | Cached rows | Clipped publisher km | Weighted Census km | Provisional eligible matched Census km |
| --- | ---: | ---: | ---: | ---: |
| origin-01 | 11,621 | 1,346.594 | 78.676 | 2.827 |
| origin-02 | 9,151 | 1,261.193 | 66.714 | 0 |
| origin-03 | 3,325 | 424.838 | 104.711 | 0 |
| origin-04 | 24,393 | 2,385.596 | 240.478 | 0 |
| origin-05 | 6,630 | 929.285 | 50.935 | 0 |

[The full report](report.json) retains all 21 windows, every observed publisher class including empty groups, Census 85/105 classes, field/scoping counts and separate geometry/source-km denominators. Publisher km clip retained line parts using geodesic approximations. Census km preserve original source cumulative weights, with per-window membership counted separately; these are different quantities. Natural Earth/base alignment is unresolved and excluded from the Census denominator.

## Matching interpretation and decision

The unchanged 25 m/80%/15° helper yields **2,297 absent-in-cache, 99 ambiguous-in-cache and 73 single-in-cache arc records**. They account for 2,010.341 / 32.423 / 35.474 original Census km respectively. Of the single-candidate source km, 25.859 are access-scoped/restricted, 4.906 unsupported role, 1.742 missing limit and 2.966 parser-eligible. The last becomes 2.827 provisional matched km after the helper's sampled overlap fraction.

The helper requires one publisher segment to cover at least 80% of an individual Census arc. Fragmented publisher segments and access/scoping rules are plausible limitations, but this run does not establish the cause of absent matches. Clearing access only for a separate speed-field inventory does not make a road usable. No rule, threshold, speed or scope was retuned after the result.

[decision.json](decision.json) records the post-result decision and exact arithmetic. Further acquisition is stopped under this recipe. The [next offline diagnostic](next-diagnostic-plan.json) will distinguish no nearby geometry from partial/union geometry support at the same sampling/distance/tangent settings, and inventory raw scopes. A union of nearby segments is only an overlap diagnostic; it is not a connected route, unique road match or usable speed coverage. Any later new matching policy or acquisition needs a separate specification; the original failed capture is never resumed.

## Execution, failure preservation and checks

[Analysis/accounting](../../../scripts/analyze_timing_cache.py), [independent audit](../../../scripts/coarse_timing_cache_audit.py), [corrected runner](../../../scripts/run_timing_cache.py), [14 analysis fixtures](../../../scripts/coarse_timing_cache_test.py), [three network-guard fixtures](../../../scripts/coarse_timing_cache_runner_test.py).

The [first execution recipe](execution-plan.json), SHA `b2f53de08632e136f3163fbfeb79bbdf391c7e54fc90c80c799b2e2ccf1c98eb`, stopped in preflight before analyzing cache rows or decoding geometry arrays. The host had already read input bytes to verify hashes; the worker produced no data-analysis result. Its guard incorrectly expected sysfs to contain only loopback. Docker's network-disabled namespace also exposes dormant kernel tunnel devices and a `bonding_masters` sysfs entry. [The failed attempt and all original file hashes](failed-attempt.json) remain preserved; there was no OOM, source request or data result.

The separately frozen [v2 recipe](execution-plan-v2.json), SHA `d50ebaa3d9efbee3bd3c88c61a6135d3577c49c98551c85d5d94be022bbd4cf2`, changes only the launcher/guard. It verifies Docker network mode `none` before start/after exit, checks process-namespace interface flags and IPv4/IPv6 routes, and permits dormant tunnel devices without active non-loopback links/routes. Data, parser, matcher, weights, thresholds and caps are unchanged. The 14 analysis tests plus three guard tests pass on host and Linux; the actual Linux namespace readiness check passes. [Linux log](linux-tests-v2.txt), [host log](unit-tests-v2.txt).

The cached image runs with a read-only root/code/cache/geometry, no whole-workspace/credential mount, 1 GiB cgroup/zero swap, an independent one-hour watchdog, 64 MiB maximum tmp and 128 MiB budgeted output. No PyArrow import/install, image pull or app dependency is needed. V2 exits zero without OOM and removes its owned container; v1's owned container was also removed. [State](state.json), [container](container-result.json), [cleanup](cleanup.json).

The independent [audit](audit.json) reconciles every raw identity/scoped-field hash, clipped geometry length, Census arc/window roster and original cumulative weight, and all class/window totals. It uses separate clipping/accounting code and the sealed geometry decoder/parser. It does not run a second full geometric matcher or prove physical road identity. Fixtures cover unsupported scopes, malformed geometry, disconnected parts, bbox false positives, empty windows, original weights, added parallel-road ambiguity, duplicate rows, output/time guards and tampered source weights.

Measured worker elapsed **25.671 s** includes cached-array loading, extraction accounting, matching, output and independent audit; it excludes host-side input hashing and Docker setup. Output is **37,196,604 bytes**, below 128 MiB; including maximum tmp is 104,305,468 bytes. This is offline-tool scope, not app/Vercel latency, retained model memory or peak memory. The hard 1 GiB limit is enforced; peak usage was not measured. Biome checks 197 files; app typecheck and ordinary build pass. No app/API/browser/DB/routing-producer test is needed for unchanged runtime behavior.

Large per-row/match ledgers and both completed output rosters remain ignored under `data/coarse-quality/overture-timing-cache-analysis-v1/` and `...-v2/`. Do not overwrite or rerun them. Small measured records are copied here. Source capture data and all prior evidence remain unchanged.

Read-only proof:

```sh
python3 -B docs/evidence/coarse-timing-cache-2026-10-25/verify.py
python3 -B docs/evidence/coarse-timing-cache-2026-10-25/verify.py --local-assets
```

[Recovery and commands](../../local-development.md#offline-timing-cache-analysis), [ordered next task](../../next-steps.md).
