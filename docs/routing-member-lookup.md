# Restriction-member road lookup — October 18, 2026

Follow-up: [targeted source-evidence indexing](routing-source-evidence.md) is now complete at a 1.543 GiB current complete peak. Base-graph construction is the next memory target; the results below remain the historical member-lookup baseline.


This follow-up reduces temporary road-lookup storage while reproducing the existing routing graph exactly. It is part of making our own larger road graphs practical without provider quotas. It does not increase the browser's hosted 60-minute cap or establish complete two-hour or 10–12-hour coverage.

The prior [I/O lifetime workflow](routing-io-lifetimes.md) creates a Python dictionary for every directed road on each restriction fallback pass. The new version keeps entries only for ways used by candidate via-way restrictions. It still scans every road to detect duplicate directed geometry, including roads outside those members. All work uses cached data, with zero downloads or public API calls.

## Implementation and safety behavior

New versioned modules are `routing/member_lookup.py`, `member_import.py`, `member_fixtures.py`, `member_parity.py` and `member-parity.mjs`; the focused tests are in `member_lookup_test.py`. Old importers, builders, encoders, qualification evidence and recipes remain unchanged.

The frozen builder emits roads in ascending way-ID order. The lookup checks this ordering, reads the numeric road arrays directly, and holds a duplicate-detection set for one way at a time. A duplicate key is `(way, from-node, to-node)`; reverse directions and equal geometry on different ways remain distinct. Selected dictionary keys retain the original last-write semantics. Storage for the duplicate scan scales with the largest way group, rather than every road in the graph; member storage still scales with the selected restriction members.

Global duplicates produce an explicit flag. The resolver tests that flag in the original position: after member/topology validation, before missing directed segments and blocked paths. A duplicate on an unrelated way still triggers the same per-rule conservative fallback. It does not abort the entire import or silently become acceptable. The resolver's AST differs only in its additional flag argument and that guard expression. The v3 barrier importer body is unchanged. Road costs, access, turn/history semantics, fallback iteration order, audit ordering, canonical JSON, CSR and gzip encoding remain the frozen versions.

Seventeen fresh small OSM fixtures compare the new importer with `cache_import.py` in every parity worker: supported and reversed via ways, unsupported/conditional rules, mode exemptions, no restrictions, selected and unrelated duplicate geometry, validation priority, a chained closure, and five barrier/access cases. They compare graph/audit/CSR/gzip bytes, transformed barrier source bytes, prohibition replays, and every fixture state against independent full/bounded Bellman–Ford costs. Nine focused unit tests also cover the global guard's error priority, array-only access, last-write behavior, ordering and IDs above JavaScript's safe-integer range.

## Reproduce

Prerequisites are the cached qualified graphs and completed canonical `data/io-bounded-pilot/iob-v1-*` records from [the prior workflow](routing-io-lifetimes.md). No environment variables or provider key are read by these commands. The tools image is pinned by the manifests to `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7` (Valhalla tools revision `7fd2228e5863b442bc1ac8d25eece6415dd91bff`; these custom graph imports use Python, not Valhalla search).

```sh
npm run routing:members -- --case downtown-v2
npm run routing:members -- --case corridor-v3
npm run routing:members -- --case wide-v3
npm run routing:members -- --case hour-v3
python3 -B docs/evidence/routing-member-lookup-2026-10-18/analyze.py
```

The completed defaults are sealed in ignored `data/member-pilot/members-v1-*`. To repeat, append the same fresh `--series members-repeat-01` to all four commands, keeping the smaller cases first. The equality baseline remains canonical `iob-v1-*`. The hour case verifies all three same-code smaller proofs, original qualification artifacts, independent/native report hashes, native source/binary bindings and comparison counts before recording success. Changed recipes require a new version; never rewrite a sealed attempt to make it pass.

The wrapper enforces two CPUs, 4 GiB RAM, no container swap, `--pull never`, no networking, read-only sources/recipes/root filesystem and a 256 MiB temporary filesystem. Each output identity includes source/profile/image/code hashes, predecessor manifest/report hashes and original qualification bindings. It snapshots its recipe and preserves failed attempts. No larger-graph build command is added.

## Measurements and graph identity

| Case | Exact artifacts | Max retained keys / roads scanned | Before peak (GiB) | After peak (GiB) | Complete wall time (s), before → after |
| --- | ---: | ---: | ---: | ---: | ---: |
| downtown-v2 | 4 | 615 / 20,430 | 0.051 | 0.052 | 2.04 → 1.94 |
| corridor-v3 | 6 | 2,202 / 387,764 | 0.330 | 0.322 | 48.85 → 46.87 |
| wide-v3 | 7 | 5,580 / 928,307 | 0.646 | 0.653 | 153.29 → 148.97 |
| hour-v3 | 7 | 12,609 / 3,039,480 | 1.798 | 1.730 | 493.05 → 479.98 |

All **24** frozen graph/audit/source/CSR/gzip artifacts match; all four workloads record zero memory-limit/OOM/kill/swap events. On the current case the complete peak is **1,857,077,248 bytes (1.730 GiB)**, **3.8%** below the prior 1.798 GiB observation. With the 25% factor it is **2,321,346,560 bytes (2.162 GiB)**. Worker high-water RSS is **1,569,680 KiB (1.497 GiB)** versus 1,656,116 KiB. Import time is **417.43 → 403.26 s**. Downtown and wide container peaks rise slightly; this is a modest current-workload improvement, not a uniform reduction across cases.

The current first pass retains **12,609 keys out of 3,039,480 scanned roads** (99.6% fewer dictionary entries); the final pass retains 7,900 out of 3,034,771. Global duplicate detection holds at most **2,708 unique geometry pairs** for one way. All six scans together take **3.286 s**. There are no global geometry duplicates in these four real-data graphs, so the synthetic duplicate/fallback cases are necessary safety evidence. Each worker freshly checks **296 full and 888 bounded fixture costs** across the 17 distinct fixtures, separately from regional qualification.

On the current run, completed parsing is at 47.76 s (including barrier preparation), history construction at 396.39 s and source evidence at 446.99 s. Source evidence sets the final **1.730 GiB** peak; export and final verification do not raise it. The highest periodic current-memory sample is 1,853,505,536 bytes, including 1,360,265,216 anonymous and 488,095,744 file bytes; this is a sample, not the exact kernel peak composition. The full-node temporary indexes in `source_examples` and its whole-file XML reads warrant separate measurement next.

These are single local observations on Apple M4/16 GiB with Linux-arm64 Docker/Python 3.12.3. Host/VM/cache conditions are uncontrolled. Container `memory.peak` includes import, fixture checks, source-evidence generation, exports and final artifact verification. Worker RSS is a separate high-water mark; periodic anonymous/file samples may miss brief peaks, and their maxima must not be summed. A 25% factor is a current-workload headroom check, not a forecast or admission for a larger graph. Host/VM paging is unmeasured.

The current source remains `data/coverage-pilot/hour-candidate-v1/car-roads.osm`, 451,794,442 bytes, SHA-256 `64462b578bd9b688290fa8777bbb2564ea40ed649c47d88146353c72097ab1a1`. It derives from the cached California/Mexico snapshot dated `2026-10-14T20:21:12Z`; parent provenance and preparation settings remain in [the two-hour preflight](two-hour-coverage-preflight.md). Bounds remain `[-117.65,31.9,-116.0,33.6]`, with model `exploratory-static-car-v3`, 5,000 ms signal delay and 20,000 ms U-turn delay. Identity remains `b50422b83537cecf12f1ecb4f7a3fa4e80df206726796b562135715f3737d048`: 3,034,771 roads, 3,036,124 states, 6,411,757 arcs and 1,160 via-way prohibitions.

Original regional full/bounded/partial and native qualifications are checksum-verified and reused on identical graph bytes. They are not freshly executed regional searches in this experiment. The saved current native report contains 258,070,540 cost/membership comparisons plus two partial destinations; its original macOS run was not Docker-memory-capped. Fresh fixture costs are reported separately. This experiment measures preprocessing and verification, not graph-search latency, HTTP latency, a contour or Vercel behavior.

## Coverage limits and next task

The unchanged graph has zero potential cuts within 60 minutes for five sampled origins; first cuts occur at 63m32s–77m34s. Every selected 120-minute case reaches cuts. This is sampled static road-graph evidence, not complete all-origin one-hour coverage or an integrated browser contour. Northern Baja is retained; three uncertain Otay ways (`114198251`, `185333061`, `577149752`) remain explicitly reported. Border queues, documents and current crossing eligibility are unmodeled. The larger continuation envelope also exceeds cached source coverage to the east/south; Arizona/Nevada roads are missing. Memory improvements do not resolve those geography gaps.

The next bounded task is to profile and version `barriers.source_examples`: it currently constructs incoming/outgoing indexes for every graph node although the examples select only five control points. Retaining only the required node entries should preserve road order, audit transitions, source excerpts and failures; prove this on fixtures and all four frozen cases under the same cap. Also measure its XML passes separately before choosing read-only range-aware input as the following optimization. Completed-input advice currently waits until whole-file reads finish. Assess qualification/reload memory separately and define a measured complete-workflow admission rule before attempting a larger graph. Preserve source bytes and all old recipes.

Larger graph admission remains **on hold**. The old 20.64 GiB estimate was the earlier workflow's conservative scaling forecast, not measured candidate graph/query RAM and not a forecast for this implementation. Any subsequently admitted graph requires a fresh identity, exact rebuild, independent full/bounded/partial/native checks and all-direction cut inventory at 120 minutes. US-wide data acquisition, the 10k-anchor batch, app range increases, caching and Vercel rollout remain deferred.

The four retained parity directories total **2,086,163,440 logical file bytes (1.94 GiB)**; the workspace still has **221.17 GiB** free after the runs. Inputs were already cached, so no download space or quota was needed.

Validation passes: **135 host Python cases (126 pass, nine tool/platform skips)**, **44 scoped Linux cases (no skips)**, **14 adapter tests**, `npm run check`, `npm run typecheck`, `npm run build` and the saved analyzer. The existing database lint warning and upstream build warnings remain. All **170** pre-existing routing/lockfile/generated-route fingerprints match, the six new recipe fingerprints remain frozen, local documentation links resolve and nothing is staged. Environment values were neither inspected nor changed; `.env.local` remains ignored. The existing Valhalla container is healthy.

Raw records, exact commands and verification logs are in [the evidence directory](evidence/routing-member-lookup-2026-10-18/README.md). Existing app behavior is preserved.
