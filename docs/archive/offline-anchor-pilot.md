# Offline anchor pilot

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

October 16, 2026. The first reusable-data experiment runs against our downloaded California/northern-Baja graph. **It makes zero public routing API calls.** It tests acquisition separation, directed matrix storage, checkpoints and resumption. It does not implement a nationwide index, conservative landmark bounds or a 12-hour contour.

## Run it

Use the existing [regional graph recipe](../regional-routing.md). The completed default graph must be in `data/valhalla-v2/`. Its `build-complete.json` records the pinned engine, sources and artifact checksums. This pilot neither downloads missing inputs nor starts/uses the app's routing service.

The regional build already creates the tools image. If that cached image is missing, build it once:

```bash
docker build -t geo-planner-valhalla-tools:7fd2228e5 routing
```

That setup command may download the pinned base image and OS packages. Subsequent pilot commands use `--pull never` and `--network none`. The tools image is resolved to its immutable local image ID and recorded; the engine version must match the completed graph. The Python bindings inside it match Valhalla `3.9.1-7fd2228e5`, unlike the earlier Node-binding experiment.

```bash
# Compute eight rows, each with all 32 targets.
npm run routing:anchors -- --max-new-rows 8

# Validate the same inputs/checkpoints, then compute only missing rows.
npm run routing:anchors

# Run again: validate and reuse all rows; zero routing computations.
npm run routing:anchors

npm run test:routing

# Check every packed value and inspect directed/triangle consistency offline.
PYTHONDONTWRITEBYTECODE=1 python3 routing/analyze_anchors.py data/anchor-pilot/california-baja-roads20261014-admin20261016-v2-timedistancematrix-32
```

Default output: `data/anchor-pilot/california-baja-roads20261014-admin20261016-v2-timedistancematrix-32/`. Everything under `data/` remains ignored by Git. Select a different completed graph with the existing `VALHALLA_MANIFEST` and `VALHALLA_DATA_DIR` overrides. Missing/mismatched artifacts fail before native routing starts.

Supported options: `--count 2..1000`, `--max-new-rows 0..count`, `--algorithm timedistancematrix|costmatrix`, and `--run-name name`. A changed worker, graph, image, model, algorithm or anchor selection requires a new run name; old rows are preserved and rejected rather than mixed. `--max-new-rows 0` validates inputs/saved rows without new routing; a complete matrix is re-exported. A single-writer lock prevents concurrent writers. Complete rows survive interruption; an unfinished `.part` row is replaced on resumption. Host-side tests/analysis need Python 3.11+; computation uses Python 3.12 inside the cached image.

The container has no external network, a read-only root filesystem/graph/recipe, a writable output mount, a 256 MiB temporary filesystem, two CPUs and a 2 GiB cgroup memory limit. The wrapper does not read `.env.local`, pass an API key or accept a routing URL. It cannot fall back to openrouteservice. The interactive browser app remains configured separately and still spends provider quota when Compute/Replay is used.

## What the files mean

- `manifest.json`: full graph/source/model provenance, runtime configuration, tools image ID, worker checksum, ordered anchor coordinates/OSM IDs and dataset identity hash.
- `worker.py`: the worker snapshot for this dataset.
- `anchors.geojson`: inspectable point selection, indexed in matrix order.
- `rows/00000.json`, etc.: independently checksummed response checkpoints. They retain times, route costs, distances, reported correlated coordinates, warnings, algorithm and per-row measurements.
- `times.u32le`: complete row-major matrix of little-endian unsigned 32-bit elapsed seconds. Entry `(i,j)` is at byte offset `4 * (i * count + j)`. `4294967295` means **unknown**, not certified unreachable. No time rounding is introduced; unexpected fractional/overflow values fail validation.
- `times.u32le.gz`: losslessly compressed matrix; `summary.json` records sizes and the unpacked checksum.

Candidate extraction reads `highway=motorway_junction` nodes from the checksum-verified regional PBF using cached Osmium 1.16.0. It found 4,540 candidates inside the declared bbox. Selection starts at the lowest OSM node ID and repeatedly chooses the geographically farthest candidate from the selected set, with a mean-latitude longitude adjustment. This is a reproducible seed selection, not driving-time gap coverage. Junctions include freeways other than interstates and locations in Mexico. Interstate way/relation membership and separate carriageway/turn states remain unqualified.

The request is Valhalla `auto`, `freeflow`/`constrained` speed types, kilometers, verbose matrix output, no date/time and otherwise engine defaults. The pilot selects the matrix algorithm and raises only its in-memory matrix limits to 2,000 km straight-line separation and 1,000 pairs per request; it leaves the app/service configuration untouched. See the engine's [matrix API](https://valhalla.github.io/valhalla/api/matrix/) and [configuration source](https://github.com/valhalla/valhalla/blob/7fd2228e5863b442bc1ac8d25eece6415dd91bff/scripts/valhalla_build_config). No elapsed-time horizon is requested. A returned long route is not evidence of complete surrounding reachability. Missing traffic/timezone databases remain known limitations; the native logger reported the absent traffic archive even though response warning arrays were empty.

**These are coordinate-to-coordinate elapsed times along engine-selected routes.** Engine preference costs differ from elapsed time; correlated start/end states can differ across connections. The values are neither independently verified minimum-time distances nor guaranteed composable through an anchor. Do not feed them into exact ALT lower-bound formulas or claim certified reachability. Null connections preserve uncertainty about graph cuts, disconnection and search limits. Source access, prohibited turns, border costs, partial-edge snapping and independent optimality still need qualification.

## Measurements and scaling decision

Hardware: Apple M4, 16 GiB host RAM; Docker Desktop approximately 7.65 GiB VM RAM. These are sequential local in-process measurements, without page-cache flushing. `actorCallMs` includes snapping, native search, matrix assembly and JSON serialization; Python decode/validation is separate. There is no HTTP timing or isolated graph-search claim. Worker RSS includes resident mapped pages and is not the same measurement as Docker cgroup charged memory. `workerWallMs` is sampled before final packing/summary serialization and excludes Docker launch and host-side image inspection.

The first 256-target `costmatrix` probe saved eight rows: 2,048 ordered entries, zero nulls or response-warning rows, approximately 6.6–13.7 seconds per call, 100.25 seconds of worker wall time including 10.34 seconds of preflight, and 2,420,176 KiB maximum process RSS. One Docker sample showed 1.644 GiB charged memory. A single 256-target `timedistancematrix` comparison took 7.35 seconds including Python decoding and reported 1,184,280 KiB RSS. It ran while the other probe was active, so this is not a controlled performance comparison or an equivalence proof.

The smoke pilot therefore uses **32 anchors before scaling to 256/1,000**. A partial run checkpointed eight rows in 29.29 seconds including 8.33 seconds preflight, with 1,202,532 KiB worker RSS. The next run reused those eight rows and completed the other 24 in 70.64 seconds including 8.31 seconds preflight. Across all 32 calls, p50 was 2,570.8 ms, p95 3,136.8 ms, total 83.16 seconds; maximum worker RSS across the two runs was 1,220,388 KiB (about 1.16 GiB). This is a small regional distribution, including first requests after actor construction, not a national or cold-cache benchmark.

The complete 1,024-entry table had zero nulls and no response-warning rows. Checkpoints totaled **130,885 bytes**; the lossless time-only export is **4,096 bytes**, or **2,631 bytes gzip**. These sizes exclude the manifest, anchors, graph, worker and raw distance/cost/snapping metadata retained in checkpoints. The maximum returned route time was 24,725 seconds (6h52m05s); that does not prove complete reachability at that budget.

A third run took 8.22 seconds of worker time to revalidate/reuse all 32 rows and made **zero native routing calls**. SHA-256 comparisons verified that every checkpoint remained byte-for-byte unchanged. Packed/gzip exports match every saved time entry. See [retained measurements and checks](../evidence/anchor-pilot-2026-10-16). Do not extrapolate these regional samples linearly to national preprocessing.

## Correctness findings

All diagonal times were zero. All 496 unordered anchor pairs had directional differences, with a maximum difference of 2,953 seconds; reverse directions must remain separate. Among 29,760 finite ordered triples of distinct anchors, **138 violated the elapsed-time triangle inequality by more than two seconds**. The largest was source 19 → target 3: 15,947 seconds directly versus 14,246 seconds summed through anchor 18, a 1,701-second difference. An intermediate coordinate does not prove the two route states compose into a permitted path. These observations can reflect preference objectives, state/snapping differences or search behavior; this pilot does not isolate the cause.

The earlier 256-target `costmatrix` rows and the matching 32-target `timedistancematrix` subset also differed on 150 of 256 compared elapsed times, by up to 2,128 seconds. Algorithm and target count changed together; this is a disagreement diagnostic, not a controlled algorithm comparison or independent accuracy test. **Neither table is approved for exact landmark lower bounds.** Keep both as baselines while building the independent fixed-model reference.

## Broader data assessment

No additional bulk data was downloaded for this pilot. The host had approximately 257 GiB free at its start. Existing road sources total 1.32 GB; the default graph archive is 922 MB. See [regional provenance and build resources](../regional-routing.md).

The [Geofabrik US West listing](https://download.geofabrik.de/north-america/us-west.html) offers a matching `us-west-261014.osm.pbf` snapshot at **3,417,392,464 bytes**. Adding the already-cached Mexico file would yield approximately 4.06 GB of road inputs. This is the candidate next bulk source for a bounded western experiment; retain and verify its published checksum/header, then pin our SHA-256 before building. US West coverage alone does not prove every 12-hour journey from San Diego is contained, and omits Canada. Mexico remains relevant for near-border origins and routes that leave/re-enter the US.

For comparison, the matching [US snapshot](https://download.geofabrik.de/north-america/us.html) is 12,206,447,982 bytes and [North America](https://download.geofabrik.de/north-america.html) is 19,501,717,071 bytes. These are compressed downloads, not graph size or build-memory requirements. They have not been acquired. US-only data would also need an explicit decision about Canada/Mexico crossings and separate Alaska/Hawaii handling.

Disk appears sufficient for another bounded pilot; **broader build RAM is not established**. The existing regional build already reached 3.73 GiB child RSS under a 4 GiB build limit. Do not assume a larger PBF fits that same container. Before acquisition/build, set an explicit clip, border policy, intermediate/output disk budget and staged memory limits; measure and retain failures as well as successes. Use a new data directory so current graphs remain intact. Detect/flag cut-boundary uncertainty rather than raising the budget and calling it complete.

The [small static turn-aware reference](state-routing-reference.md) imports separate real roads/weights and checks Dijkstra/landmark certificates against Bellman–Ford and held-out cases. The [cell-summary comparison](cell-routing-experiment.md) reduces detail reads but leaves exact queries slower than direct search. The [compact native baseline](native-routing-baseline.md) matches this small graph's selected results with faster direct search. A separate [v2 model](maneuver-routing-model.md) now qualifies prohibited via-way history and interior destinations. The [regional capacity probe](regional-routing-capacity.md) now measures 387,236 states; border-access exclusions and a wider-import OOM must be addressed before scaling preprocessing. Keep this coordinate table as an operational/storage baseline. Increase anchor count only when the computational method and data semantics justify it; nationwide 10k preprocessing remains deferred.
