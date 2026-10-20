# Cut inventory and next coverage preflight

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

Follow-ups: [sparse preparation/resource profiling](sparse-routing-resources.md) passes the import admission rule, and the [regional coverage increment](regional-coverage-increment.md) now builds and qualifies that source with exact rebuild bytes. This page preserves the original near-cap measurements, rejected selector and admission hold. Complete 60-minute/10–12-hour coverage remains unproven.

October 17, 2026. This follows the [compact OSM input qualification](compact-osm-input.md). Everything uses cached files, with zero routing-provider requests, no new road downloads, two CPUs, a **4 GiB container cap and swap disabled**. Original graphs, source data, recipes and failed attempts are preserved. No larger routing graph or new contour is claimed.

## Inventory findings

`routing/cut_inventory.py` verifies the frozen 2,139,131-state graph, reloads its compact representation, and reads the five saved full-cost oracle vectors. It enumerates every state ending at an audited cut node, including maneuver-history states. It checks all five minimum cut costs against the earlier qualification, then attaches source segments, outward way direction/access and outside coordinates. These are potential exits: a source way permission does not prove legal node/turn/history continuation beyond the graph.

There are **337 cut nodes / 407 cut states**, and all 337 have source boundary links. The full inventory contains 209 north, 80 east, 48 south and zero west endpoints. Within 60 minutes:

| Origin | Reachable cut nodes | North | East | South |
| --- | ---: | ---: | ---: | ---: |
| San Diego | 188 | 130 | 30 | 28 |
| El Cajon | 184 | 126 | 30 | 28 |
| Tijuana | 69 | 11 | 27 | 31 |
| San Ysidro | 126 | 66 | 29 | 31 |
| Incoming port lane | 137 | 77 | 29 | 31 |

All five origins reach 216 cut nodes within 120 minutes. Some audited endpoints are unreachable; some reachable arrivals lack a way-only outward permission. The inventory retains those distinctions and the blocked-node flags. Side counts can overlap at corners in general. Zero west endpoints in this extract does not prove a sufficient western margin for expanded geography.

The default first potential cut remains **35m17s north**, El Cajon's **22m22s east**, and Mexico origins **24–29 minutes south**. These costs reuse the existing static-model oracle fields; no new route searches, real border eligibility or driving ETAs are verified.

## Prepared candidate and resource gate

The candidate **[-117.65,32.0,-116.3,33.6]** expands all four bounds, guided by the north/east/south inventory and a wider coastal margin. It retains northern Baja. The parent is the cached California/Mexico `data/valhalla-v2/region.osm.pbf`, 677,680,499 bytes, SHA-256 `7f3cdfc99196d51e732fff06dabb004c0d2f1a4d557442daec9789a19b633dbe`. Road snapshot: October 14, 2026, with the original Geofabrik timestamp/provenance in [regional routing](../regional-routing.md). Parent clipping, missing AZ/NV roads and absent Canada remain; object extents outside the nominal parent bbox do not establish coverage there.

The staged recipe selects complete ways geographically, filters supported highway/restriction **IDs without reference completion**, then recursively obtains their references from the original parent. It retains tags and original OSM IDs and runs `osmium check-refs --check-relations`. The cached immutable tools image remains `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7` (Osmium 1.16.0). Six fixtures compare graph/audit bytes with the original smart extraction, including conditional/non-car restrictions and outside boundary members. Calibration then reproduces the entire original 333,753,728-byte buffer XML exactly, SHA-256 `7dbc429816a6cac878b1274580034ab22d35cb17c6265ed55f3e6ecaeae5c81e`.

An attempted lower-memory `simple` selector **failed the boundary fixture**: its selected data omitted ways 10/40 and restrictions 100/101, changing the resulting graph. It was rejected. The preserved first attempt also exposed a missing version header in the minimal test XML, which was corrected. The final recipe uses `complete_ways`; do not substitute the rejected selector. This is a measured fixture finding for the pinned tool/recipe, not a general claim about other versions. Failed and superseded attempts retain their identities/snapshots.

The parent has 89,776,916 nodes, 10,435,256 ways and 113,780 relations; its highest node ID is 14,284,658,989. Osmium documents that extraction memory depends on the highest ID and strategy, which helps explain why a small rectangle can still require substantial RAM. See the [pinned 1.16.0 extraction manual](https://github.com/osmcode/osmium-tool/blob/v1.16.0/man/osmium-extract.md#memory-usage) and [recursive reference completion](https://github.com/osmcode/osmium-tool/blob/v1.16.0/man/osmium-getid.md).

The prepared candidate contains **2,278,632 nodes, 456,908 ways, 10,053 relations**. Disk-backed census measures a **2,858,813–2,946,180 road-state interval** and **2,950,064 history-state ceiling**. These are count bounds; no new routing graph or exact state count exists. Candidate `car-roads.osm`: **442,764,751 bytes**, SHA-256 `f7c4bda33bfa33a1f2f6cc7ca0f32257bac68559ebe31c1488f7b8510effa92e`.

| Run | Worker / maximum child RSS | Observed container peak | Limit hits | Worker wall |
| --- | ---: | ---: | ---: | ---: |
| Cut inventory | 439,632 / 0 KiB | 1,883,951,104 bytes | 0 | 39.40 s |
| Final extraction calibration | 55,544 / 3,827,308 KiB | 4,061,392,896 bytes | 0 | 61.33 s |
| Candidate preparation/census | 64,844 / 3,837,016 KiB | 4,294,967,296 bytes | **1,056** | 67.86 s |

Every run records zero OOM/kill events and swap max/current/peak zero. `buffer_resources.py` samples cgroup composition every 200 ms as well as checkpointing cumulative kernel peaks/events. Candidate observed anonymous memory peaks at **3,941,556,224 bytes**, file accounting at **1,160,634,368 bytes**; these maxima are from different times and must not be summed. Kernel `memory.peak` captures the cap being reached. Periodic composition samples may miss brief peaks. Host/VM paging and controlled cold-cache behavior are unmeasured; the same 16 GiB M4/Docker VM is used. Worker/child high-water marks are separate, not simultaneous sums. Timings cover preparation/census/checking up to final report generation, excluding Docker startup and module imports; none is isolated graph-search time or HTTP latency.

The largest measured input ratio is 1.3785× the current buffer. Scaling the qualified compact-input worker peak and adding 25% headroom estimates **2,324,784,559 bytes / 2.17 GiB**. This heuristic fits the RAM cap **for the worker alone**. The admission decision remains **hold**: preparation already has limit pressure, and the earlier complete import/export still approached 4 GiB. The worker estimate does not include a trustworthy whole-container margin.

## Commands and handoff

```bash
npm run routing:cuts
npm run routing:coverage:next -- --case calibration
npm run routing:coverage:next -- --case candidate
python3 -B docs/evidence/cut-buffer-2026-10-17/analyze.py
npm run test:routing
npm test
npm run check
npm run typecheck
npm run build
```

Recorded directories are ignored under `data/coverage-pilot/buffer-cut-inventory-v1`, `staged-calibration-v2-r4` and `staged-candidate-v2`. Existing identities refuse overwrite. To reproduce, use `--run-name fresh-name` for each stage and pass `--calibration-run fresh-calibration-name` to the candidate. Candidate selection binds the recorded default cut inventory. Changed cut code/source requires a versioned candidate recipe. Each identity binds source/profile/image/code and resource policy; candidate provenance additionally binds cut/calibration/import-measurement reports. Small reports, inventories, logs, rejected fixtures and validation are in [evidence](../evidence/cut-buffer-2026-10-17/README.md).

Next reduce preparation's dense-ID memory requirement with a sparse or disk-backed approach that preserves original IDs, tags and complete restriction references. Gate it against all fixtures and the exact existing buffer XML. Separately profile the frozen buffer import/export with the new composition monitor, including sequential verification reads; control file-page accounting only through a recorded, measured policy. Preserve old behavior and do not raise the cap. Establish whole-workload headroom before admitting the prepared candidate to import. A new graph then needs fresh full/bounded/partial oracle checks, border/source-uncertainty fixtures, native comparisons and all-direction cut diagnostics.

Complete 60-minute and 10–12-hour coverage remain unfinished. The hosted app keeps its 60-minute provider cap. The three uncertain Otay ways, static access assumptions, border queue/current eligibility limitations and Vercel architecture remain unchanged. National anchors, analytical layers, elevation, road-distance semantics and cloud rollout stay deferred.
