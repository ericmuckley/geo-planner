# Compact native routing baseline

October 16, 2026. **A small C++ bounded-Dijkstra kernel now reproduces the frozen Python reference and runs substantially faster on that same graph.** It uses downloaded roads, with networking denied and zero public routing API calls. This is a local search baseline; the browser still uses the hosted 60-minute service. Complete 10–12-hour driving coverage remains unimplemented.

## Reproduce it

Prerequisites: the completed [static reference](state-routing-reference.md), macOS with `/usr/bin/sandbox-exec`, Python 3.11+, Node/npm and a C++17 compiler with its standard library. This run used Apple M4/16 GiB, macOS 26.3.1 arm64, Python 3.13.5 and Apple Clang 17.0.0 (`clang-1700.6.4.2`). The cached routing tools container has no C++ compiler, so this benchmark uses the existing host compiler; nothing is downloaded or installed.

From the repository root:

```bash
# Only if the frozen reference has not been prepared; requires cached regional inputs/Docker:
npm run routing:reference

npm run routing:native
# Repeat after compilation/app checks finish; qualification and timings run again:
npm run routing:native

npm run test:routing
npm test
npm run check
npm run typecheck
npm run build
```

Default output: `data/native-pilot/downtown-native-v1/`, ignored by Git. Repeating preserves the graph identity, verifies the existing CSR checksum, recompiles and replaces the timing reports. Copy reports before repeating if retaining individual measurements. Changed worker/model/compiler/platform/profile inputs require a separate output, for example `npm run routing:native -- --run-name downtown-native-v2`. A lock prevents concurrent writers. The input reference is read without modification; all five reference artifact checksums were verified unchanged afterward.

`routing/native.mjs` launches the Python worker and compiler/kernel under `routing/native-network.sb` (`deny network*`). A subprocess must receive a permission denial on a loopback socket operation before computation begins. No external service is contacted by that probe. A direct unsandboxed worker invocation fails this check. No app server or API key is needed; `.env.local` is neither loaded nor changed, and provider environment variables are not forwarded. In the agent tool environment, nesting `sandbox-exec` required an outer sandbox exception; the benchmark's own network denial remained active. The npm wrapper deliberately fails on other operating systems. Linux, WASM and Vercel execution have not been qualified.

## Inputs, engine and correctness

The engine is our `csr-dijkstra-v1` kernel in [native_search.cpp](../routing/native_search.cpp), compiled with `-std=c++17 -O3 -Wall -Wextra -Werror`. Source/compiler/binary hashes, platform, Python version, reference artifacts and settings are retained in the [run manifest](evidence/native-routing-2026-10-16/repeat-manifest.json). No Valhalla search or new speed model is used in this comparison.

The unchanged input has **19,815 directed road-end states and 37,891 transitions**, from the downtown bbox `[-117.18,32.70,-117.13,32.74]`. It retains the reference's `exploratory-static-car-v1` integer-ms weights, turn restrictions, exclusions and source attachments. Graph identity is `e1b193523518171a20a7db72d2a6eb4cfe7e0c6410d11592a2bf72edb46ea489`; source graph JSON SHA-256 is `452e734037cb07422bba2e1ff42e7d405221c4bc0859a3fc23585b00d8618545`.

Roads come from the cached regional PBF (`2026-10-14T20:21:12Z`, SHA-256 `7f3cdfc99196d51e732fff06dabb004c0d2f1a4d557442daec9789a19b633dbe`), originally clipped from pinned Southern California/Mexico snapshots. See [source acquisition/build provenance](regional-routing.md) and the [import model/audit](state-routing-reference.md). Unsupported via-way/conditional restrictions still cause conservative road closures. Signals/U-turns use fixed delays; traffic, queues and time-dependent access are unmodeled. Search agreement does not independently validate those import choices or real driving times.

The [profile](../routing/profiles/native-downtown-v1.json) uses the same default San Diego origin and eight earlier holdouts, ten repetitions per case/output mode, and budgets of **30/60/120/300 seconds plus 2/6/10/12 hours**. The source projection is inherited, rather than timed/recomputed by the kernel: the default input snapped 0.51 m to retained segment `436291033:1`, seeding states `(8656,91 ms)` and `(8657,572 ms)`. Nearest-segment access and snapping realism remain unqualified. There are no new geographic contours or sampled real-world routes in this step.

For each origin, independent flat-edge Bellman–Ford and Python heap Dijkstra must agree on all complete costs. Native complete and bounded costs then match that oracle; bitmap bytes must encode the same memberships. Subsequent repetitions must reproduce the first result hash. Native/Python settled-state and scanned-arc counts also agree for every request.

Each run passed **1,605,015 cost comparisons and 1,426,680 membership comparisons**, with zero mismatches. That comprises nine complete searches and 72 bounded cases; 1,440 bounded requests supply timing samples. Repeat runs reproduced graph/binary/result bytes and deterministic case counters. These are exhaustive state checks for the selected cases, not millions of independent road journeys. Nine added native tests cover packing/corruption, turn-aware/partial/multiple starts, disconnected and zero-cost graphs, random directed graphs, large accumulated costs and invalid requests. At this baseline step, all **41 Python tests and 14 adapter tests** passed. Biome, typecheck and production build passed with the existing database assertion and bundler warnings. The later v2 model adds separate tests/evidence.

## Packed data and outputs

`graph.csr` is a little-endian compressed sparse row representation. The 48-byte header holds magic `GPCSR001`, unsigned 32-bit state/arc counts and the raw 32-byte graph identity. Arrays follow: `N+1` unsigned 32-bit offsets, `M` targets and `M` nonnegative integer-ms weights. Parallel/zero-cost arcs and state order are preserved. The worker verifies file size/SHA-256; the kernel checks header identity, exact length, monotone offsets and target ranges. The kernel itself does not calculate SHA-256.

| Asset | Bytes |
| --- | ---: |
| CSR adjacency graph | 382,440 |
| CSR gzip (mtime 0) | 158,178 |
| Local arm64 executable | 60,768 |
| Complete cost-vector reply | 158,520 |
| Membership bitmap reply | 2,477 |

CSR SHA-256: `d89d8b6bd60f268fd831d2c10fc9a5e012f012651d7dbe441b108e45c67ebb7c`. The binary hash is `862325d3d62b7f3280042faab18f86eccbc11782550cafa74f4538846ebe9c39` in both builds. CSR excludes geometry, OSM identifiers, attribution and a snapping index; these remain in the reference assets. Comparing its size with the 4.07 MB source JSON is therefore not a pure compression comparison or a full deployment footprint.

The persistent process loads one graph, receives source attachments/budget over stdin, and replies with a JSON metadata line plus an exactly sized binary payload. Costs are unsigned 64-bit ms; `18446744073709551615` is infinity. For a bounded query, infinity means absent within that budget, not globally unreachable. A complete query establishes reachability only within the imported model. Overflow-safe bounded addition preserves accumulated costs above 32 bits. Bitmap bits are LSB-first by state ID, with zero padding. Neither output contains polygon geometry or partial destination-road reachability.

## Measurements and their limits

All timings are sequential on the same Mac. The comparison Python searches run on that host too; earlier Docker cell timings are a separate experiment. The table uses the repeat run and shows the median of nine per-origin p50 values, ten samples per case/mode. Native setup+search adds paired sample durations before aggregation. Per-case p95 is the largest of ten observations; every raw sample is retained.

| Budget | Python setup + search | Native search loop | Native setup + search | Cost reply + Python decode | Bitmap reply + checked view | Origins with cut warning |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 30 seconds | 0.040 ms | 0.00033 ms | 0.0022 ms | 0.481 ms | 0.022 ms | 4/9 |
| 60 seconds | 0.060 ms | 0.0021 ms | 0.0041 ms | 0.477 ms | 0.023 ms | 4/9 |
| 120 seconds | 0.133 ms | 0.0080 ms | 0.0100 ms | 0.496 ms | 0.026 ms | 6/9 |
| 300 seconds | 2.388 ms | 0.194 ms | 0.195 ms | 0.683 ms | 0.199 ms | 9/9 |
| 2 hours | 6.262 ms | 0.712 ms | 0.714 ms | 1.165 ms | 0.679 ms | 9/9 |
| 6 hours | 6.423 ms | 0.716 ms | 0.718 ms | 1.151 ms | 0.694 ms | 9/9 |
| 10 hours | 6.381 ms | 0.663 ms | 0.665 ms | 1.110 ms | 0.698 ms | 9/9 |
| 12 hours | 6.249 ms | 0.669 ms | 0.671 ms | 1.119 ms | 0.642 ms | 9/9 |

Search time measures only the native heap/adjacency loop. Source setup includes cost-array allocation/initialization and attachment parsing/seeding, but excludes coordinate snapping. Encoding is separately instrumented. The last two timing columns include pipe command/reply transfer, scheduling, setup/search/encoding and Python decoding; **they are neither HTTP timings nor isolated graph-search times**. Cost decoding expands all labels; bitmap decoding only creates a checked memory view and checks padding. Full correctness comparisons are outside these timings. Cost and bitmap columns come from separate sequential requests, so subtracting their medians would not isolate transfer overhead. Sub-microsecond loop samples are especially sensitive to timer/cache effects.

At the default San Diego origin, the first run's 12-hour native search p50 was 0.837 ms versus 7.132 ms Python. It settled 15,885 states, scanned 31,545 arcs, made 17,981 heap pushes and peaked at 758 queued entries. Two holdouts occupy tiny disconnected components; all origin cases and counters remain visible in the raw evidence.

First/repeat packing took 41.3/42.4 ms; compilation 516.7/667.5 ms; preflight+packing+compilation 691/831 ms. Worker time before final report/snapshot writing was 5.31/5.10 seconds, including qualification and all queries; npm launch is excluded. Python worker maximum RSS was 68,992/68,832 KiB (about 67 MiB); the persistent native process reached 2,768 KiB in the first run. These are per-process OS-reported maxima, not combined build/system memory or enforced memory caps.

The first executable launch after each compilation took **275/195 ms** through the hello reply, while internal graph load/structural validation took 0.317/0.459 ms. The cause of that launch overhead was not isolated. Three later fresh processes per run took 1.81–2.71 ms through hello and 2.68–3.67 ms through the first 12-hour bitmap reply; their internal graph loads were 0.195–0.227 ms and RSS 2,176 KiB. Preserve both sets of observations. Fresh processes do not flush OS caches or reproduce a Vercel cold start. There is no Linux/WASM/cloud, concurrency, cold-device, HTTP, WAN or browser performance claim.

## Coverage and next task

The default source can reach a cut exit in **215,966 ms (3m35.966s)**. All nine selected origins have a cut warning at five minutes and every larger budget. The 2/6/10/12-hour results saturate this small graph; they test arithmetic and search semantics, not genuine long-range coverage. A missing road outside the extract cannot become reachable by increasing the budget. Conservative import closures create further undercoverage even inside it. Keep `coverageVerified: false`.

This downtown instance contains no Mexico crossing. Broader San Diego work must include and qualify Mexico roads, cross-border access and an explicit queue policy; a US-only clip can omit valid paths that leave/re-enter the US. US West alone also omits Canada and is not automatically a complete 12-hour buffer. Existing regional sources are reusable without provider quota; broader bulk acquisition remains a separate, checksum-pinned preparation step.

The [v2 maneuver/interior-destination qualification](maneuver-routing-model.md) and [regional capacity probe](regional-routing-capacity.md) are now complete, preserving this frozen v1 benchmark. The larger corridor has 387,236 states and matching native/oracle costs, but a wider import exhausts 4 GiB and border-access exclusions remain. Next qualify barriers and reduce importer memory before further expansion. The [bulk-source/resource assessment](offline-anchor-pilot.md#broader-data-assessment) is a starting point, not a national capacity guarantee. Carry cut detection into every larger experiment.

Keep this direct kernel as the baseline when revisiting gateway shortcuts, selected landmark fields or the proposed 10k-anchor cache. Current measurements do not justify that national batch. WASM/Node packaging and geometry/output construction still need separate qualification to preserve the single TanStack Start app on Vercel goal; do not connect a local Mac executable to production or raise the browser limit yet. PostGIS, elevation, road-distance semantics, cloud rollout and worldwide coverage remain deferred.

See [all evidence and aggregation commands](evidence/native-routing-2026-10-16/README.md).
