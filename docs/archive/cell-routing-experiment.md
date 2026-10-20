# Grouped road-state reachability experiment

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

October 16, 2026. **The grouped certificates are safe on the frozen downtown model and reduce detailed index reads. The exact query pipeline is still slower than bounded Dijkstra.** This experiment does not expand the browser's range or establish complete 12-hour coverage.

## Run it

First prepare the [static state reference](state-routing-reference.md), then:

```bash
npm run routing:cells
npm run test:routing
npm test
npm run check
npm run typecheck
npm run build
```

The command reads `data/reference-pilot/downtown-static-v1/` through a read-only container mount. It verifies the reference graph, complete landmark fields, origin definitions and audit against the reference manifest. Existing roads and weights are preserved. Docker uses the cached tools image, `--pull never`, `--network none`, two CPUs and a 2 GiB memory limit. No app server, provider key, remote fallback or road download is used. `.env.local` remains unchanged.

Output: `data/cell-pilot/downtown-cells-v1/`. Each candidate has its own `leaf-64/`, `leaf-256/` or `leaf-1024/` directory. Repeating the command verifies/reuses those indexes and reruns qualification/timings. Changed code/input/profile requires a new `--run-name`; `run-identity.json` also protects partial builds from mixing versions. A single-writer lock protects output. Missing/corrupt files fail before benchmarking; short range reads fail rather than representing absent roads as unreachable.

The [profile](../../routing/profiles/cell-downtown-v1.json) fixes three leaf capacities, five repetitions and the same nine origins/four **30/60/120/300-second** budgets as the reference. Candidates were compared on the same cases; these cases were not held out from every earlier experiment. No nationwide generalization or statistically representative driving benchmark is claimed. Full reports and every candidate timing sample are in [retained evidence](../evidence/cell-summary-2026-10-16).

## Method and safety

Partition directed states by their road-head coordinates using a deterministic binary median split on the largest longitude/latitude span. Leaves contain at most the chosen number of states. The hierarchy has contiguous state-order ranges, allowing one certificate to represent many states. It is a spatial grouping, not a graph separator or a routing shortcut. Co-located directions remain distinct; paths may leave and re-enter groups.

For each landmark a and group C, store minimum/maximum complete forward costs d(a,v) and reverse costs d(v,a), over every v in C. For a fixed starting state s, valid bounds for **every state in the group** are:

```text
lower = max(0, min_C d(a,v) - d(a,s), d(s,a) - max_C d(v,a))
upper = d(s,a) + max_C d(a,v)
```

Maximize valid lower bounds and minimize valid upper bounds over landmarks. Skip undefined infinity-minus-infinity; complete fields allow some disconnection proofs. For multiple permitted starting states, add each attachment cost and take the minimum across starts. Classify a whole group if upper ≤ budget or lower > budget; descend otherwise. A mixture of finite/infinite costs weakens a group certificate, which is deliberate.

At an uncertain leaf, read its detailed landmark rows and classify individual states. Remaining uncertainty is resolved by a target-bounded Dijkstra variant, which may stop when all unresolved targets settle or the budget frontier is exhausted. **Certified groups stay available as transit paths.** Removing them from search would be unsafe without a suitable gateway/shortcut proof. Tests cover paths through intermediate states, early completion, one-way/turn cases, disconnected/zero-cost components and multiple partial starts.

The returned representation consists of certified state-order ranges, detailed state decisions and refined memberships. Materializing all state memberships is timed separately for verification. A group certificate applies to its assigned road states; it does not certify every road or square metre inside a geographic rectangle. No filled contour or browser display is generated.

This uses established directed landmark bounds. Partition-based isochrone methods also have substantial prior art; this small implementation is not isoCRP/isoPHAST and makes no novelty claim. See [ALT research](https://www.microsoft.com/en-us/research/wp-content/uploads/2005/01/soda05.pdf) and [Fast Computation of Isochrones in Road Networks](https://arxiv.org/abs/1512.09090).

## Data format and access accounting

Each candidate's manifest records graph identity, complete-field status, landmark order, partition settings, exact file sizes and SHA-256 checksums. The binary files are little-endian:

- `cells.bin`: fixed records of two signed 32-bit child IDs (`-1` for leaves), unsigned start/end state-order positions, then four unsigned costs per landmark: forward min/max, reverse min/max. Eight landmarks produce a 144-byte record.
- `details.bin`: reordered per-state rows of all forward then all reverse landmark costs, 64 bytes per state for eight landmarks.
- `states.u32le`: position → graph-state ID; `positions.u32le`: graph-state ID → position. Each occupies 79,260 bytes for this graph.

Cost sentinel `4294967295` means infinity in the **complete imported model**, with the same coverage caveats as the reference. No extra rounding/quantization is introduced. Query code reads source rows, visited summary records and uncertain leaf blocks with actual `pread` calls; it does not consult the full reference field arrays. The full arrays are loaded separately for preprocessing/baselines/oracle verification.

`logicalIndexBytesRead` counts bytes returned by those calls, including source/mapping/detail reads. It excludes manifest/preflight hashes, resident graph data, source snapping, full output expansion and downstream geometry. Preflight reads full files to verify them once per batch and is reported separately. These are logical file bytes on a local machine, **not physical disk reads or measured network savings**. Fresh handles/application state do not flush the OS page cache.

| Maximum states per leaf | Summary nodes | Summary bytes | All binary index files |
| --- | ---: | ---: | ---: |
| 64 | 1,023 | 147,312 | 1,573,992 |
| 256 | 255 | 36,720 | 1,463,400 |
| 1,024 | 63 | 9,072 | 1,435,752 |

These are additional experimental assets, not total app/graph storage. The source graph JSON is 4,070,390 bytes. Original landmark fields are 1,268,160 bytes raw or 550,298 bytes gzip. This prototype uses uncompressed detail blocks; comparing range bytes only with the raw field size would overstate a possible advantage over a whole compressed download. The files and small manifests are not packaged into the app.

## Measured results

Apple M4, 16 GiB host RAM; Docker Desktop approximately 7.65 GiB VM RAM. Initial candidate construction/verification took approximately 140/111/92 ms for leaf capacities 64/256/1,024. The first run overlapped the ordinary app build; these preparation timings are single observations. The subsequent warm run used the saved indexes and took **24.61 seconds** for the complete benchmark/oracle checks, with **74,704 KiB (73 MiB)** maximum worker RSS and approximately 106 ms reference preflight. OS caches were not flushed.

All three candidates passed **2,140,020 state/budget certificate checks** and the same number of exact final-membership comparisons against Bellman–Ford, with **zero unsafe certificates or membership mismatches**. Each candidate had 36 cases and five timing repetitions, for 540 candidate timing samples. Independent Dijkstra/Bellman–Ford agreement was rechecked for all nine origins. Repeating the job reused identical index files and reproduced classification counts, bytes/range calls and search-work counts. Timing values naturally vary.

Warm results for 64-state leaves are below. Timing columns are medians of nine per-origin p50 values, with five samples per case. Access counts are deterministic per case; the table shows their median across origins. The raw report retains per-case p50/p95 and all candidate samples.

| Budget | Detailed states read | Logical index bytes | Range calls | Grouping + detail + exact refinement | Direct bounded search |
| --- | ---: | ---: | ---: | ---: | ---: |
| 30 seconds | 310 | 25,036 | 61 | 1.79 ms | 0.041 ms |
| 60 seconds | 966 | 77,420 | 133 | 4.32 ms | 0.065 ms |
| 120 seconds | 2,244 | 174,404 | 269 | 9.67 ms | 0.138 ms |
| 300 seconds | 9,907 | 775,264 | 1,219 | 44.17 ms | 2.358 ms |

At 30 seconds this visits a median 45 summary nodes and reads detail for 310 of 19,815 states. It saves much of the full landmark scan, whose median was approximately 32 ms. At five minutes the grouped pipeline takes longer than that full scan as well as direct search. Source attachments, file-open/source reads, tree traversal, detail decoding and classification are included in grouped-query timing; graph refinement is timed separately. Output expansion and verification are excluded and explicitly measured in the raw report. There is no HTTP or isolated national search claim.

Larger leaves reduce summary traversal but read more details. At 300 seconds, 256/1,024-state leaves read medians of 13,315/17,338 detailed states and took approximately **58.22/67.19 ms** including refinement. The summary-only stage is cheap—roughly 0.06–2.51 ms across the shown configurations/budgets—but it leaves uncertain groups and is only a partial road-state preview, not a finished answer.

In **34 of 36 cases per candidate**, exact refinement settled the same number of states as direct bounded search. The two exceptions were 120/300-second queries from one small disconnected component: no uncertain targets remained, so refinement settled zero states instead of 24. This does not establish useful search savings on connected long-range journeys. Many summaries certify states outside the short budget or disconnected by the model's exclusions; a large certified percentage alone does not establish better routing.

There can be dozens to thousands of tiny reads per local query. A remote implementation would need batching, sensible block sizes and likely summary preloading; translating each call into a serial network request is unvalidated and could overwhelm any byte saving. Neither cloud latency nor cold device/OS-cache performance was measured.

Validation: 32 Python pilot/reference/cell tests and 14 adapter tests pass. Biome, TypeScript and production build pass with the existing assertion/bundler warnings. No application route/UI changes were needed; the route generator ran normally during the build.

## Decision and next task

Keep this as a correctness/data-access experiment. **Do not adopt the hybrid as the app's exact router or start the national 10k batch on the strength of these timings.** It demonstrates selective index access and safe grouped previews; it does not solve long-range graph traversal or geographic output.

The recommended [compact native baseline](native-routing-baseline.md) is complete on this unchanged graph. It matches all selected costs/memberships and separates loading, setup, search, encoding and pipe transfer. It provides a faster direct-search baseline before gateway shortcuts. Native local results still need separate WASM/Vercel checks to preserve the single-app deployment goal.

Retain the cell format/proofs for a later gateway/shortcut or batched-loading comparison. A separate [v2 model](maneuver-routing-model.md) now qualifies unambiguous prohibited via-way history and interior destinations, preserving these v1 indexes. Conditional/ambiguous exclusions, downtown cuts and Canada/Mexico crossing uncertainty remain. The [regional capacity probe](regional-routing-capacity.md) is complete; next qualify barrier access and reduce importer memory before wider coverage. The original 10–12-hour requirement, national data preparation and browser integration remain active work. No additional datasets, PostGIS/elevation layers or paid services were introduced here.
