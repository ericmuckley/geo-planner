# Routing preparation and importer lifetimes

October 18, 2026. This follow-up tests memory ownership against frozen data before expanding the graph. The experiments run on the separate self-built static v3 graph. The [two-hour preflight](two-hour-coverage-preflight.md) remains the source/coverage plan. The app still uses hosted openrouteservice with its **60-minute driving cap**; the original 10–12-hour/US-wide requirement remains unfinished.

The subsequent [I/O lifetime follow-up](routing-io-lifetimes.md) now completes the input/export/checksum cache task on frozen graphs, reducing complete current peak to 1.798 GiB. It records the next lookup/storage work while retaining the larger-graph hold. The measurements below preserve this earlier experiment.

## Inputs and limits

All computations use the cached parent PBF and existing source/graph/oracle files. **Zero downloads and zero routing-provider requests**; no application dependencies or environment values change. Both wrappers deny network access and swap, use read-only inputs, two CPUs and **4 GiB RAM**. Native preparation uses the pinned reader image; graph parity uses the pinned base tools image. Image IDs, recipe file hashes and prior report/source hashes are saved in each run identity. Prior recipes and attempts remain unchanged.

The cached `data/valhalla-v2/region.osm.pbf` is **677,680,499 bytes**, SHA-256 `7f3cdfc99196d51e732fff06dabb004c0d2f1a4d557442daec9789a19b633dbe`, with road snapshot `2026-10-14T20:21:12Z`. Current-region bounds are `[-117.65,31.9,-116.0,33.6]`; the larger candidate is `[-118.8,30.8,-114.5,35.0]`. California/Mexico source gaps in AZ/NV and the continuation envelope extending beyond the parent's south/east edges remain. Reference completion cannot fill missing geographic source coverage. Northern Baja, crossing uncertainty and static v3 access rules stay intact.

## Preparation changes

`selection_process.py` runs the frozen paged selector in a separate process. Its parent waits for successful exit before starting native reference completion, releasing the selector heap instead of relying on Python's allocator to return it. The **isolated** mode then follows the original single `osmium getid --add-referenced` path.

The **batched** mode divides the exact selected-ID file into up to four contiguous parts, runs recursive reference completion separately, then uses `osmium merge` to deduplicate the sorted results. Output is streamed through a 16 MiB completed-range policy: flush, `fdatasync`, then `POSIX_FADV_DONTNEED`. This is advice on completed output ranges, not a global cache flush or a changed routing model. Batch files remain as reproducible evidence and consume extra disk. It trades extra source reads/merge/I/O for a lower peak. The completed batched runs retain approximately **0.92 GiB (current)** and **3.15 GiB (larger)** of generated files, including XML, census, batch files, logs and recipe copies. These are observed output-directory sizes, not a peak temporary-disk bound; cached parent/proofs/graphs and preserved other attempts require additional space.

Each mode must pass the same six graph/audit fixtures and reproduce **both current and candidate selected IDs, XML bytes and census exactly**. Fixture equivalence alone would not establish source parity. Candidate runs require a completed calibration using the same code/profile/image/mode.

| Region | Recipe | Wall s | Parent worker MiB | Largest child MiB | Container GiB | Limit events |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Current | old | 211.27 | 529.8 | 2557.9 | 3.11 | 0 |
| Larger | old | 252.81 | 1214.0 | 3228.2 | 4.00 | 3750 |
| Current | isolated | 214.82 | 67.4 | 2529.2 | 2.89 | 0 |
| Larger | isolated | 256.89 | 69.1 | 3275.5 | 4.00 | 1626 |
| Current | batched | 266.98 | 66.8 | 2164.2 | 2.17 | 0 |
| Larger | batched | 315.93 | 68.9 | 2583.1 | 2.60 | 0 |

In the new modes the worker is the parent coordinator; selector allocations live in a separate child. Lower parent RSS alone is not a whole-workload improvement. Child RSS and the complete cgroup peak include that work.

Both new modes preserve the frozen current **451,794,442-byte XML** (SHA-256 `64462b578bd9b688290fa8777bbb2564ea40ed649c47d88146353c72097ab1a1`) and larger **1,540,059,541-byte XML** (SHA-256 `5a80178511c04cbd20b14518b92fe8cffcaf43db0f92cbde90541f68549c4117`), selected-ID bytes and census. Both same-mode six-fixture graph/audit calibrations pass. Every new run records zero OOM/kill/swap; isolation alone still incurs **1,626 limit events** on the larger candidate.

The batched larger workflow's complete measured peak is **2,796,601,344 bytes (2.60 GiB)**. With the recorded 25% factor it is **3,495,751,680 bytes (3.26 GiB)**, below the 4 GiB cap with zero pressure. This qualifies **preparation only**. Compared with the original capped observation, peak falls 34.9%, while whole-workflow time rises from 252.81 to 315.93 s. Process isolation alone is insufficient. The batched change also includes output advice and extra merge/read work; these observations do not isolate the causal contribution of each change.


## Importer change

`keyed_import.py` reuses the frozen base builder, lookup, maneuver resolution, input storage and barrier policy. Its function bodies preserve the original importer except for retained original-road membership and profiling checkpoints. `road_keys.py` retains the existing way/segment/direction numeric arrays by reference: **13 payload bytes per original road**, excluding allocator/object overhead. A sorted merge identifies restored roads without retaining millions of formatted ID strings and a Python set. Both original and final keys must be unique and numerically sorted; an unexpected order fails explicitly. Only restored rows need materialized road dictionaries for the unchanged audit.

The parity runner requires same-code downtown v2, corridor v3 and wider v3 proofs before reimporting the current hour graph. It compares graph identity plus every graph/audit/source/CSR/gzip artifact with frozen outputs. Existing full/bounded/partial/native evidence is checksum-bound and reused on identical graph bytes; **no new search or timing qualification is claimed**.

| Case | States | Identical artifacts | Import s | Complete s | Worker MiB | Container GiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| downtown-v2 | 20,332 | 4 | 1.74 | 2.02 | 42.1 | 0.050 |
| corridor-v3 | 387,236 | 6 | 41.39 | 48.74 | 272.7 | 0.479 |
| wide-v3 | 926,900 | 7 | 128.33 | 152.74 | 565.1 | 1.000 |
| hour-v3 | 3,036,124 | 7 | 424.20 | 501.16 | 1630.1 | 2.925 |

All four cases pass, with zero OOM/kill/limit events and zero swap. The current graph retains **3,034,771 roads / 3,036,124 states / 6,411,757 arcs / 1,160 via-way prohibitions**. Its original-road arrays retain **39,349,323 payload bytes for 3,026,871 keys**. All **seven** graph/audit/source/CSR/gzip artifacts match the frozen current graph exactly; the unchanged full/bounded/partial and **258,070,540 native cost/membership comparisons** plus two partials are verified and reused by identity. They are not new searches or benchmarks.

Current import is **424.20 s**, complete parity workflow **501.16 s**. Worker RSS is **1,669,192 KiB (1.592 GiB)**, about **13.9% below** the original current build's 1,938,536 KiB. Complete cgroup peak is **3,140,603,904 bytes (2.925 GiB)**, only **3.8% below** the original 3,265,265,664 bytes (3.041 GiB). The original independent rebuild measured 3,243,671,552 bytes (3.021 GiB). Different proof/host/cache conditions prevent a causal speedup claim; the importer change does not remove the dominant export/verification cache peak.

Current phase checkpoints (current values, not isolated allocations):

| Phase | Elapsed s | Anonymous GiB | File GiB | Cumulative peak GiB |
| --- | ---: | ---: | ---: | ---: |
| parsed | 48.39 | 0.268 | 0.883 | 1.155 |
| originalBase | 96.83 | 0.423 | 0.883 | 2.192 |
| lookupReady1 | 147.28 | 1.448 | 0.883 | 2.373 |
| lookupReady6 | 401.61 | 1.506 | 0.883 | 2.474 |
| inputsReleased | 401.86 | 1.193 | 0.883 | 2.474 |
| historyBuilt | 416.17 | 1.243 | 0.883 | 2.474 |
| sourceEvidence | 466.68 | 1.200 | 0.883 | 2.474 |
| exported | 499.93 | 1.200 | 0.937 | 2.893 |
| complete | 501.16 | 1.200 | 0.456 | 2.925 |

The highest periodic current-memory sample contains **1,805,107,200 bytes of file cache (1.681 GiB)** and **1,288,208,384 anonymous bytes (1.200 GiB)**. It is not the exact instant of the cumulative kernel peak. File cache already holds roughly 0.88 GiB after parsing and grows during export/verification. This makes targeted input/output cache lifetimes the next measured target, alongside lookup storage; a smaller worker alone is insufficient.


## Exact commands

From the repository root, with the recorded cached inputs/images:

```sh
npm run routing:lifetime -- --mode isolated --case calibration
npm run routing:lifetime -- --mode isolated --case candidate
npm run routing:lifetime -- --mode batched --case calibration
npm run routing:lifetime -- --mode batched --case candidate

npm run routing:keys -- --case downtown-v2
npm run routing:keys -- --case corridor-v3
npm run routing:keys -- --case wide-v3
npm run routing:keys -- --case hour-v3

python3 -B docs/evidence/routing-lifetimes-2026-10-18/analyze.py
```

Preparation defaults are `data/coverage-pilot/lifetime-{mode}-{case}-v1`. Import defaults are `data/keyed-pilot/keys-v1-{case}`. Completed attempts refuse overwrite. For a fresh preparation use `--run-name fresh-name`, with candidate `--calibration-run fresh-calibration-name`; keep the same mode. For a fresh parity series use `--series fresh-series` on every case, and optionally `--run-name fresh-output` only for an additional current-graph repeat. Preserve previous outputs/recipes, including failed attempts.

Reports record Linux worker and child RSS separately from the complete cgroup peak. Periodic anonymous/file/kernel samples can miss brief peaks, and field maxima are not simultaneous; never sum them. Final checkpoints follow artifact/proof verification reads. Small final report writes, Docker startup and module import are outside those scopes. Host/cache/VM conditions are uncontrolled. These are preprocessing wall times and resource observations, not HTTP round trips, isolated graph-search time, cloud performance or controlled causal speedups.

## Decision and next task

**Larger graph admission remains on hold.** The new batched preparation passes its own complete-container check, but the candidate admission report still uses frozen build/rebuild/qualification/inventory observations and returns the same **20.64 GiB whole-workload forecast including margin**. That is a conservative scaling heuristic, not measured candidate graph/query RAM or the minimum geography needed for two-hour journeys. A single current-graph parity reimport does not establish a new whole-workload admission rule. No admitted larger-build wrapper exists; `routing:keys` accepts frozen equality cases only.

Next version the remaining import/export lifetimes against the same current source: profile completed-read input cache, dirty output pages and per-pass lookup allocations; use targeted per-file advice/streamed exports where measurement supports it. A restriction-member-only lookup is another candidate, but it must retain the original global duplicate-directed-geometry detection and conservative fallback decisions. Require exact seven-artifact parity and checksum-bound full/bounded/partial/native evidence under the unchanged cap. Qualification/reload storage also needs its own resource work before scaling. Recompute admission only from a measured, versioned complete workflow with 25% margin and no pressure; do not extrapolate parent RSS alone.

Inventory/extend cached source coverage separately, retaining dates/checksums/Mexico/boundary audits. After resource and source admission, require a new graph identity, exact independent rebuild, fresh reference/native qualification and all-direction cuts at 120 minutes for the selected origins. National acquisition/10k-anchor batches, application range increases and Vercel rollout remain deferred.

The qualified hour graph remains `b50422b83537cecf12f1ecb4f7a3fa4e80df206726796b562135715f3737d048`, with 3,036,124 states and 6,411,757 arcs. Its five sampled origins reach no potential cuts within 60 minutes; that does not establish complete two-hour coverage, real border eligibility or a browser contour. Keep uncertainty for Otay ways 114198251, 185333061 and 577149752. No new larger graph, browser contour, native run or Vercel deployment is part of this follow-up.

Raw reports, run identities, comparison analysis and validation logs are in [the evidence directory](evidence/routing-lifetimes-2026-10-18/README.md). Large source/intermediate/graph files remain in ignored `data/` directories, with recorded hashes and frozen recipe copies.

Validation: **120 host Python cases (113 pass, seven tool/platform skips)**, **29 scoped Linux cases (no skips)**, **14 adapter cases**, `npm run check`, `npm run typecheck`, `npm run build` and the saved comparison analyzer pass. The cached Linux reader lacks a C++ compiler; host compiler/kernel tests pass. Existing database lint and upstream build warnings remain. All **148 preserved routing/lockfile/generated-route hashes** match. No environment values were inspected/changed and nothing is staged. The existing Valhalla container remains healthy; the M4/16 GiB host has approximately **227 GiB free disk** after retained products. Exact commands/log hashes/tool versions are in the evidence validation record.
