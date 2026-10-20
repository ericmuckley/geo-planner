# Completed input reads and bounded graph exports

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

Follow-up: the [restriction-member lookup experiment](routing-member-lookup.md) is now complete, retaining exact frozen bytes at a 1.730 GiB current peak. Its recommended next task is targeted source-evidence indexing; the results below remain the historical I/O baseline.


October 18, 2026. This follows the [preparation/import lifetime experiment](routing-preparation-lifetimes.md). It tests the frozen current graph before attempting larger coverage. All computations use cached data with **zero downloads and zero provider calls**. The app's hosted driving limit remains **60 minutes**; the original 10–12-hour/US-wide capability remains unfinished.

## What changes

`cache_input.py` calls the original OSM parser and barrier transformer, then requests `POSIX_FADV_DONTNEED` after successful completed reads of files at least 8 MiB. The parser returns owned decoded arrays, not file-backed views. Original source files are opened read-only and never synchronized or edited. A newly owned barrier output is synchronized before advice. The two importer function bodies in `cache_import.py` are **AST-identical** to the frozen numeric-key importer; only the parser/transformer imports bind these wrappers.

`cache_lifetime.py` writes the original canonical JSON blocks through completed ranges of at most **16 MiB**, flushing, synchronizing and advising each range. A final durability sync precedes atomic publication using a hard link, which refuses to replace an existing destination. Failed partial files remain for inspection. This bounds pending output ranges, not arbitrary upstream JSON-row sizes or total graph memory. Existing CSR and gzip encoders remain unchanged; completed CSR/gzip reads and writes receive per-file advice. Source-evidence reads finish and receive advice before export. Metadata/progress writes keep the original writer.

A second version, `routing:io:bounded`, also uses `range_hash.py` for SHA-256. It releases completed read ranges of at most 16 MiB instead of retaining a whole file until the digest finishes. `range_manifest.py` has the **same proof-checker function body** as the frozen checker, bound to the new hash reader; artifact and recipe tampering remain rejected. The first version and all its recipes/results remain preserved. No checksum is skipped or replaced with sampled data.

This is operating-system file-cache management. It does not add query-result caching, routing shortcuts, new data, costs, access rules or application dependencies. Advice is a request to the kernel, not guaranteed eviction; measured complete-container accounting governs the result. No global cache drop occurs.

## Reproduction and provenance

```sh
npm run routing:io -- --case downtown-v2
npm run routing:io -- --case corridor-v3
npm run routing:io -- --case wide-v3
npm run routing:io -- --case hour-v3
npm run routing:io:bounded -- --case downtown-v2
npm run routing:io:bounded -- --case corridor-v3
npm run routing:io:bounded -- --case wide-v3
npm run routing:io:bounded -- --case hour-v3
python3 -B docs/evidence/routing-io-2026-10-18/analyze.py
```

Completed defaults are `data/io-pilot/io-v1-{case}` and `data/io-bounded-pilot/iob-v1-{case}` and refuse overwrite. Complete the first series before the bounded series, which verifies its exact predecessor. Use `--series fresh-series` on **all four cases** for a new reproduction. A separate current repeat can use `--run-name fresh-output` with the same completed series. The hour case requires the three same-code smaller proofs. Fresh series names change output/proof locations; equality references remain the canonical `keys-v1-*` and `io-v1-*` series respectively. The wrapper accepts frozen equality cases only; it cannot launch the larger candidate.

Requirements: cached base tools image, frozen `data/keyed-pilot/keys-v1-*` products, their original qualification manifests/fields, and the current native source/binary/report. Run identities bind exact source/profile/recipe/image and prior report/manifest hashes. Docker retains **two CPUs / 4 GiB RAM / no swap / no network / read-only inputs**. The base image is `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`; its tool revision is Valhalla `7fd2228e5863b442bc1ac8d25eece6415dd91bff`. These experiments use our separate static graph builder, not the Valhalla routing service.

The current source is the frozen **451,794,442-byte XML**, SHA-256 `64462b578bd9b688290fa8777bbb2564ea40ed649c47d88146353c72097ab1a1`, bounds `[-117.65,31.9,-116.0,33.6]`. It derives from the cached California/Mexico parent with road snapshot `2026-10-14T20:21:12Z`; full source/parent pins and dates remain in the [two-hour preflight](two-hour-coverage-preflight.md). Northern Baja and uncertain Otay ways **114198251, 185333061, 577149752** remain. Geographic south/east clipping, AZ/NV road gaps, absent Canada, static costs and unmodeled border waits/current eligibility are unchanged.

## Measured result

Both versions pass all four cases: **48 output-artifact comparisons** in total, including all seven current graph/audit/source/CSR/gzip artifacts in each version. Every new run records zero OOM/kill/limit events and zero swap. The unchanged current graph has **3,034,771 roads / 3,036,124 states / 6,411,757 arcs / 1,160 via-way prohibitions**, identity `b50422b83537cecf12f1ecb4f7a3fa4e80df206726796b562135715f3737d048`.

| Workflow | Case | Import s | Complete s | Worker MiB | Container GiB |
| --- | --- | ---: | ---: | ---: | ---: |
| Numeric keys | downtown-v2 | 1.74 | 2.02 | 42.1 | 0.050 |
| Numeric keys | corridor-v3 | 41.39 | 48.74 | 272.7 | 0.479 |
| Numeric keys | wide-v3 | 128.33 | 152.74 | 565.1 | 1.000 |
| Numeric keys | hour-v3 | 424.20 | 501.16 | 1630.1 | 2.925 |
| Input/output advice | downtown-v2 | 2.04 | 2.48 | 42.3 | 0.049 |
| Input/output advice | corridor-v3 | 39.70 | 47.14 | 278.7 | 0.362 |
| Input/output advice | wide-v3 | 129.66 | 154.14 | 570.5 | 0.737 |
| Input/output advice | hour-v3 | 417.20 | 492.64 | 1604.4 | 2.030 |
| Plus bounded SHA-256 | downtown-v2 | 1.74 | 2.04 | 42.9 | 0.051 |
| Plus bounded SHA-256 | corridor-v3 | 41.45 | 48.85 | 282.1 | 0.330 |
| Plus bounded SHA-256 | wide-v3 | 128.92 | 153.29 | 564.8 | 0.646 |
| Plus bounded SHA-256 | hour-v3 | 417.43 | 493.05 | 1617.3 | 1.798 |

The final current workflow peaks at **1,931,075,584 bytes (1.798 GiB)**, **38.5% below** the numeric-key baseline's 3,140,603,904 bytes (2.925 GiB). With the 25% factor, this is **2,413,844,480 bytes (2.248 GiB)**. Current worker RSS is **1,656,116 KiB (1.579 GiB)**. Import is **417.43 s**, complete workflow **493.05 s**. This establishes headroom on the current equality case, not larger-graph admission or a controlled speedup.

The first I/O version reaches **2,180,026,368 bytes (2.030 GiB)** during final verification, after source-evidence peak 1,939,415,040 bytes. This prompted the bounded checksum version. In that final version, post-parse file cache is **38,760,448 bytes (37.0 MiB)**, versus 948,547,584 bytes (904.6 MiB) in the numeric-key baseline. The final workflow's kernel peak is first recorded at `sourceEvidence`; bounded exports and final checksum verification do not increase it.

Final current phase checkpoints (current composition and cumulative peaks, not isolated allocations):

| Phase | Elapsed s | Anonymous GiB | File GiB | Cumulative peak GiB |
| --- | ---: | ---: | ---: | ---: |
| preflight | 2.92 | 0.015 | 0.036 | 0.072 |
| parsed | 48.34 | 0.269 | 0.036 | 0.925 |
| originalBase | 95.52 | 0.478 | 0.036 | 1.336 |
| lookupReady1 | 145.37 | 1.443 | 0.036 | 1.518 |
| lookupReady6 | 396.29 | 1.457 | 0.036 | 1.612 |
| inputsReleased | 396.53 | 1.144 | 0.036 | 1.612 |
| historyBuilt | 410.37 | 1.201 | 0.036 | 1.612 |
| sourceEvidence | 460.15 | 1.178 | 0.036 | 1.798 |
| exported | 492.17 | 1.178 | 0.036 | 1.798 |
| complete | 493.04 | 1.178 | 0.036 | 1.798 |

The highest periodic sample is **1,918,484,480 bytes**, including **1,432,915,968 anonymous** and **482,275,328 file bytes**. It is not the exact instant of the cumulative kernel peak. Whole-file XML evidence reads remain visible; checksum range counts describe requested advice, not physical disk I/O. Graph construction/lookup and retained Python allocations remain substantial.

Existing five-origin full/eight-budget/partial evidence and **258,070,540 native cost/membership comparisons** plus both partials are checksum-verified and reused on identical graph bytes. These parity workflows do not rerun native graph qualification, routes, contours or search timings. Unit tests still exercise small kernel fixtures.


Each case must reproduce graph identity and every graph/audit/source/CSR/gzip byte exactly. The producer verifies original full/bounded/partial field artifacts and current native graph/source/binary/count bindings. The saved analyzer independently checks the raw records, code hashes, unchanged function bodies, source/profile identities, cache-policy paths/ranges and complete-container policy. Existing qualification is **reused by identical graph bytes**; there are no fresh route searches or native timings.

Complete cgroup peaks include import, children and final artifact/proof verification reads. Final small metadata writes, Docker startup and module imports are outside the checkpoint scope. Worker RSS, file/anonymous samples and cumulative kernel peaks have separate scopes; do not sum unrelated maxima. Periodic samples can miss brief composition peaks. Host/cache/VM conditions are uncontrolled, including any overlapping checks recorded in validation. These are preprocessing wall-time observations, not isolated graph-search, HTTP, browser, cloud performance or controlled causal speedups.

## Decision and next task

Next profile the remaining anonymous-memory allocations and version a **restriction-member-only road lookup** on the same frozen current graph. Keep the original global duplicate-directed-geometry detection, even outside candidate member ways, and preserve the existing validation/error priority and conservative fallback reasons. A filtered dictionary without that global check would change semantics. Use explicit code and source-backed duplicate/fallback fixtures; require exact graph/audit/source/CSR/gzip parity and unchanged qualification bindings under the same cap.

Also retain the source/evidence XML-read cache measurements. These legacy parsers finish whole-file passes before advice; bounded checksum reads do not make every parser read bounded. If composition remains significant, test a read-only range-aware stream with identical parsing/output, keeping source bytes and old recipes intact. Qualification/reload storage is a separate remaining resource task before broader coverage.

Keep broader graph admission on hold until a complete versioned workflow passes the recorded 25% margin without pressure. The **20.64 GiB** figure is the older path's conservative scaling forecast, not measured candidate graph/query RAM or a new forecast for this I/O path. This parity experiment does not establish a new larger-build admission rule. Qualification/reload storage needs its own assessment; clipping and missing source geography remain separate from RAM admission.

After resource/source admission, require a fresh graph identity, independent exact rebuild, fresh full/bounded/partial/native checks and all-direction cut inventory at 120 minutes for the selected origins. The current five sampled origins still have no potential cuts within 60 minutes in the unchanged static graph; that is not complete two-hour coverage or a browser contour. National acquisition/10k-anchor batches, range increases and Vercel rollout remain deferred.

Raw records, commands and validation logs are in [the evidence directory](../evidence/routing-io-2026-10-18/README.md). Large source/intermediate/graph files and frozen recipes remain in ignored `data/` directories. Preserve all old attempts, semantic modules and environment values.

Validation: **126 host Python cases (117 pass, nine tool/platform skips)**, **35 scoped Linux cases (no skips)**, **14 adapter cases**, `npm run check`, `npm run typecheck`, `npm run build` and the saved evidence analyzer pass. Existing database lint and upstream build warnings remain; the cached reader lacks a C++ compiler and host kernel/compiler tests pass. All **159 preserved routing/lockfile/generated-route fingerprints** match. Environment values were neither inspected nor changed and nothing is staged. The existing Valhalla container is healthy. Exact commands, log/report hashes, tooling and disk observations are in the validation record.
