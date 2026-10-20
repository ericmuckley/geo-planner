# Compact OSM input and explicit no-swap recipe

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

The subsequent [cut inventory/preflight](coverage-increment-preflight.md) prepares a larger cached candidate. The latest [sparse preparation/resource follow-up](sparse-routing-resources.md) passes a whole-workload margin rule for a separate capped import, preserving exact source/graph bytes. The subsequent [regional increment](regional-coverage-increment.md) builds and qualifies that source; complete 60-minute/10–12-hour coverage remains unproven. This page preserves the input-storage qualification.

October 17, 2026. This follows the [compact graph qualification](compact-routing-import.md). The purpose is to reduce preprocessing memory before expanding coverage again. Routing costs, access rules, model identity and graph coverage remain frozen. These runs use cached files only, with **zero downloads and zero public routing API requests**.

`routing/input_storage.py` stores node IDs and double-precision coordinates in typed arrays, keeping tag dictionaries only for tagged nodes. Way IDs, reference offsets and node references use arrays; way tags use a UTF-8 JSON byte store and are decoded for one way at a time. References expose a small sequence view. Ordered IDs use binary search. Unordered/duplicate IDs preserve the original dictionary's insertion order and last value through a fallback index; tests cover that path. The measured real inputs all use the ordered path. Array/tag-byte counts describe payloads, not total Python allocation or a national memory bound.

`routing/input_import.py` is a versioned copy of the frozen compact importer. It changes decoded storage, iterates sorted way IDs without collecting all way dictionaries, and uses lazy way-reference lookup for restriction resolution. It retains the original candidate/fallback order, access exclusions, signal/turn costs, segment rounding, maneuver history and v3 barrier policy. Relations, sparse node tags, outgoing lists, road-ID sets and directed-road restriction lookups still scale with the input. The previous importer, graph storage, recipes, sources, failed attempts, oracle vectors and native binary remain untouched.

`routing/offline-no-swap.mjs` is a separate recipe version so historical `offline.mjs` commands retain their original behavior. It sets **`--memory 4g --memory-swap 4g --cpus 2 --network none --pull never --read-only`**; Docker's equal memory/combined-memory limit disables swap. The worker independently requires cgroup `memory.max=4294967296` and `memory.swap.max=0`, records current/peak swap and memory events at every stage, and fails on swap or OOM events. Inputs/recipe are read-only; only the selected output and bounded `/tmp` are writable. No app environment file or credential is needed.

The five cases reimport downtown v2, corridor v2/v3, wider v3 and the qualified 2,139,131-state buffer. Every original artifact is checksum-verified before use. Exported graph JSON, audit, CSR and gzip must match exactly, along with prepared barrier XML, barrier examples and uncertain-crossing excerpts where applicable. The larger case requires four completed proofs using the same script fingerprints. Expensive prior full/bounded/partial oracle checks are reused only after identical graph/artifact identities; these are **new preprocessing measurements**, not new route or search measurements.

## Reproduce

Prerequisites: cached pinned tools image, the five completed `data/compact-pilot/compact-v1-<case>/` runs and their frozen sources. See the [previous recipe](compact-routing-import.md) for acquisition and graph qualification. The tools image is `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`; it contains Python 3.12 and the pinned Valhalla/Osmium tools. This experiment builds our `exploratory-static-car-v2/v3` graphs, rather than changing Valhalla's graph or service.

Run the cases sequentially:

```bash
npm run routing:inputs -- --case downtown-v2 --series input-v1
npm run routing:inputs -- --case corridor-v2 --series input-v1
npm run routing:inputs -- --case corridor-v3 --series input-v1
npm run routing:inputs -- --case wide-v3 --series input-v1
npm run routing:inputs -- --case buffer-v3 --series input-v1
```

The recorded series is already complete; use a **new series name on all five commands** to reproduce it. Existing successful or failed identities refuse overwrite. Outputs and recipe snapshots are ignored under `data/input-pilot/<series>-<case>/`. Manifests bind the image, source, model/profile, prior manifest, code/wrappers, resource policy and smaller parity proofs. Reports distinguish parsing, base/restriction rebuilds, history, import, export and whole-worker wall time.

The larger input is cached `data/coverage-pilot/san-diego-tijuana-buffer-preflight-r2/car-roads.osm`: 333,753,728 bytes, SHA-256 `7dbc429816a6cac878b1274580034ab22d35cb17c6265ed55f3e6ecaeae5c81e`. Roads date to **2026-10-14T20:21:12Z**. Bounds are **[-117.4,32.3,-116.6,33.2]**, including San Diego and northern Baja. The parent comes from Southern California plus Mexico and has missing Arizona/Nevada roads even within its rectangle; Canada is absent. Source provenance, parent checksums and distinct admin supplementation are recorded in [regional routing](../regional-routing.md) and [preflight evidence](coverage-buffer-preflight.md).

## Verification and findings

See [raw reports, manifests, logs and analysis](../evidence/compact-input-2026-10-17/README.md). The checked-in evidence is small; large inputs, graph exports and oracle vectors stay in ignored `data/`.

All five cases pass exact graph/audit/source/packed equality:

| Case | Parsed worker peak | Complete worker peak | Observed container peak | Import / worker wall |
| --- | ---: | ---: | ---: | ---: |
| Downtown v2 | 31,980 KiB | 46,164 KiB | 57,303,040 bytes | 1.68 / 1.94 s |
| Corridor v2 | 70,272 KiB | 318,828 KiB | 583,999,488 bytes | 34.22 / 38.54 s |
| Corridor v3 | 72,756 KiB | 321,980 KiB | 736,870,400 bytes | 40.94 / 48.32 s |
| Wider v3 | 128,724 KiB | 650,432 KiB | 1,587,027,968 bytes | 128.03 / 151.75 s |
| Buffer v3 | 231,864 KiB | 1,317,520 KiB | 4,292,444,160 bytes | 297.30 / 351.79 s |

The buffer's parsed peak falls **83.1%**, from 1,375,596 to 231,864 KiB (1.31 GiB to 226.4 MiB). Its matched import/complete worker peak falls **46.8%**, from 2,478,776 to 1,317,520 KiB (2.36 to 1.26 GiB). Import increases from **247.55 to 297.30 s**, approximately 20%. Wider v3's worker peak falls 46.0%, with import increasing from 107.31 to 128.03 s. Corridor worker savings are approximately 43%, with slower imports too. This representation trades CPU time for memory.

All five containers record **zero OOM, kill and limit-hit events**, with swap max/current/peak all zero. However, the buffer's observed container peak is still **99.94% of its 4 GiB cap** at final artifact checking, compared with approximately 3.65 GiB after history construction. This does not establish comfortable container headroom for a larger extract. Cgroup anonymous/file/dirty breakdowns were not captured, so the exact contribution of each cannot be inferred from worker RSS. Record `memory.stat` in the next resource preflight and measure preparation/export as well as graph construction.

The larger decoded input contains 1,652,946 nodes (114,459 tagged), 376,997 ways, 2,145,087 references and 8,251 relations. Node arrays occupy 39,670,704 payload bytes; way/reference arrays 26,208,640; encoded way tags 35,608,435. Sparse node tags, relations, Python containers and allocation slack are additional. The complete five-case series adds about **1.80 GB / 1.68 GiB** of logical files, including recipe snapshots, without copying old oracle vectors. About 248 GiB remained free after the run.

Measurements are single fresh-container observations on the same 16 GiB Apple M4/Docker VM, with two CPUs/4 GiB RAM and container swap disabled. The Docker VM has 8,218,034,176 bytes allocated; host/VM paging is not measured by these container counters. Filesystem caches are not controlled; cgroup accounting includes charged file pages and temporary/export allocations. Worker RSS is a separate high-water mark. Comparisons use corresponding parsed/history-built checkpoints; the earlier buffer's 51-minute complete qualification includes oracle work deliberately omitted here. Do not compare those complete-worker durations as equivalent workloads.

Worker wall time includes prior-artifact validation and output checking up to final report generation; Docker startup, Python module imports and final small report/manifest writes are outside it. Import includes v3 barrier preparation, parsing, repeated base/restriction resolution and maneuver history. These are preprocessing measurements, not search timings.

Synthetic tests cover exact graph/audit/packed equality, independent all-source Bellman–Ford costs, maneuver fallback/modes, barrier permissions/closures, unordered/duplicate IDs, missing references, Unicode, large IDs, coordinate precision and reference slicing. The older complete graph/oracle/native qualification remains bound to byte-identical outputs. No HTTP round-trip is reported as isolated graph-search time.

## Coverage and next task

This storage change adds no roads. The default first potential cut remains Avocado Highway/north at **35m17s**; El Cajon reaches Kumeyaay Highway/east at **22m22s**, and the Mexico origins reach Boulevard Popotla/south at **24–29 minutes**. Those witnesses are reachable inside endpoints of cut ways; legal continuation beyond the extract remains unqualified. Every selected 60-minute/longer case reaches a potential cut. Complete 60-minute and 10–12-hour contours remain unfinished.

Keep the three explicitly uncertain Otay ways, conservative closures and car-eligibility flags. Border queues, delays, current crossing eligibility and time-dependent access remain unmodeled. The hosted app still uses its 60-minute provider cap; native local results do not establish browser/WASM/Vercel performance or national coverage.

Next inventory **all reachable potential cuts**, rather than only each origin's first witness, using the saved audit/oracle fields. Then preflight a cached-data buffer extending **north, east and south**, retaining Mexico and checking the coast/western margin too, with an explicit no-swap policy. Address Osmium's earlier near-cap extraction separately; use disk-backed preparation or smaller reproducible extraction steps rather than raising the RAM cap. Count nodes/ways/references and road/history bounds, apply the new measured importer profile with headroom, and admit a full graph only if the preparation and import gates pass. New geography then requires fresh independent full/bounded/partial checks and cut diagnostics. National anchors, road-distance semantics, analytical layers and cloud rollout remain deferred.
