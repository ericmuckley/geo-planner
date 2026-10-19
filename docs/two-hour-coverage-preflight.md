# Two-hour frontier and resource preflight

October 18 follow-up: [preparation/import lifetimes](routing-preparation-lifetimes.md) now qualifies four-batch preparation at 2.60 GiB with exact frozen bytes and no pressure. It also profiles a byte-identical lower-memory current importer. The findings below preserve the original preflight; larger graph admission and geographic coverage remain unresolved.

October 17, 2026. The [one-hour graph](hour-coverage-qualification.md) has 3,036,124 states and zero reachable potential cuts within 60 minutes for five selected origins. Its two-hour samples still reach 106–116 cuts. This follow-up chooses a broader candidate from every reached frontier, calibrates lower-memory geographic selection and measures preparation/census before admitting a larger graph.

All old graphs, recipes, fields, failures and environment values remain intact. New work uses cached data and pinned tools, with **zero routing-provider requests, zero downloads and zero new application dependencies**. The live app/provider/limits do not change. This preflight does not build or qualify a new graph.

## Candidate selection and source limits

There are **116 unique reached cut nodes / 550 origin–cut pairs** at 120 minutes. For each pair, the remaining budget and the unchanged static model's **160 km/h** maximum supported speed define a spherical continuation envelope around the recorded endpoint. The sphere radius **6,371,008.8 m** matches `import_roads.distance_m`; edge costs round upward and turn/signal costs are nonnegative. Existing margins are retained, the union rectangle rounds outward to 0.1 degree and is clipped to the cached parent. The [profile](../routing/profiles/coverage-two-hour-v1.json) records **[-118.8,30.8,-114.5,35.0]**.

These envelopes are conditional on the recorded inside-graph prefixes and unchanged topology. Enlarging an extract can restore restrictions/roads and change shortest paths; this is a geographic planning heuristic, **not a coverage certificate**. It deliberately uses the maximum supported speed, not an assumption that every road is that fast. Every potential cut is included, even without a way-only plausible continuation. No western hits is not proof of western/source completeness.

The envelope extends beyond the parent on its **east and south** sides. Clipping is recorded explicitly, not treated as newly covered data. Parent road gaps in Arizona/Nevada and absent Canada remain. Even successful preparation/resource admission cannot establish complete two-hour source coverage; a fresh graph and all-direction cut checks would still be required.

## Paged original-ID selection

`paged_ids.py` stores node membership in a dictionary of **4,096-ID bitmap pages (512 bytes each)**. Only occupied pages are allocated, keyed by original ID. It does not remap IDs or allocate an array up to the highest ID. Way/relation sets and recursive parent closure remain unchanged. Membership stays exact. Widely scattered IDs can waste one page per ID; national memory requirements remain unmeasured.

`paged_select.py` follows the frozen selector with the membership container changed and storage diagnostics added. `two_hour_prepare.py` preserves the original preparation and six-fixture function bodies exactly, binding the new selector. The staged complete-way selection, original source tags/IDs, native recursive reference completion, reference checking and disk-backed census remain unchanged. Tests compare clustered/far-apart IDs and duplicate handling against Python sets, include very large IDs, and compare actual selected IDs/parent closure with the frozen selector.

Before larger geography, calibration must pass all six fixture graph/audit comparisons and reproduce the **current region's exact XML and full census**. Candidate preparation requires that same code/profile/image proof. Worker/container peaks and node-container storage statistics have different scopes; Python container-size statistics exclude allocator/runtime/source caches and are not a RAM bound.

## Source, engine and policy pins

Current graph identity: **`b50422b83537cecf12f1ecb4f7a3fa4e80df206726796b562135715f3737d048`**. Calibration source `data/coverage-pilot/hour-candidate-v1/car-roads.osm`: **451,794,442 bytes**, SHA-256 `64462b578bd9b688290fa8777bbb2564ea40ed649c47d88146353c72097ab1a1`, bounds **[-117.65,31.9,-116.0,33.6]**.

Cached parent `data/valhalla-v2/region.osm.pbf`: **677,680,499 bytes**, SHA-256 `7f3cdfc99196d51e732fff06dabb004c0d2f1a4d557442daec9789a19b633dbe`. Road snapshot **2026-10-14T20:21:12Z**; separate admin supplementation October 16. See [source provenance](regional-routing.md). Source object extents do not prove coverage outside the nominal rectangle **[-119.8,30.8,-114.5,35.5]**.

Preparation uses cached image **`sha256:025ebba8267c0aad21bc4cb52b40c4726b65a13a1ebe66b8642df5495261ddd5`**, Pyosmium **4.3.1** / CPython **3.12.3** / Linux arm64. Its [wheel lock](../routing/tools/pyosmium-v1.json) and base image **`sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`** remain pinned; Valhalla tools revision **`7fd2228e5863b442bc1ac8d25eece6415dd91bff`**. No image/tool download occurs. This is our separate static v3 experiment, not a rebuilt Valhalla service graph.

All new Linux work retains **two CPUs / 4 GiB RAM / no swap / no network / read-only inputs** on the unchanged 16 GiB M4 host. Per-file cache advice follows completed large checksum reads; no global cache drop or file edits. Existing source/native/full-field evidence is reused by exact identity; no new native run or timing is claimed.

## Exact commands

```sh
npm run routing:coverage:two-hour -- --case calibration
npm run routing:coverage:two-hour -- --case candidate
python3 -B docs/evidence/two-hour-preflight-2026-10-17/analyze.py
```

Requires the current graph, source, rebuild, qualification/native/fixture/cut proofs and cached images. No provider key is used. Defaults under `data/coverage-pilot/two-hour-calibration-v1` and `two-hour-candidate-v1` refuse overwrite. Reproduction accepts fresh `--run-name` outputs; candidate additionally accepts `--calibration-run fresh-calibration-name`. Code, profile and image must match. Changed prerequisites require a new versioned identity; preserve failed attempts.

## Measured calibration

All **six fixture graph/audit comparisons** pass. The new preparation reproduces the exact **451,794,442-byte current XML** and full census: **2,334,810 nodes / 462,588 ways / 10,095 relations**, **2,955,664–3,043,312 road-state interval / 3,047,196 history ceiling**.

Geographic membership includes **19,044,070 original node IDs**, stored in **156,834 bitmap pages / 80,299,008 payload bytes**. Reported Python container size is **98,872,858 bytes**, excluding runtime/allocator/source caches. This is exact membership storage, not a routing graph or analytical index.

| Same-source preparation workflow | Worker peak | Largest child peak | Complete cgroup peak | Worker wall |
| --- | ---: | ---: | ---: | ---: |
| Previous sparse Python set | 1,612,792 KiB / 1.54 GiB | 2,542,300 KiB | 3,145,691,136 B / 2.93 GiB | 208.06 s |
| Paged bitmap calibration | 542,504 KiB / 0.52 GiB | 2,619,288 KiB | 3,343,458,304 B / 3.11 GiB | 211.27 s |

**Worker peak falls 66.4%, while complete-container peak rises 6.3%.** The latter is now dominated by native reference completion, not bitmap membership. Do not claim a lower whole-workload peak or isolate causality from these observations: proof/fixture work, retained Python allocations and host/cache conditions differ. All new calibration checkpoints record zero OOM/kill/limit events and zero swap. The resource rule includes the **larger measured preparation peak**, irrespective of the worker reduction.

Recorded all-frontier envelope is approximately **[-118.7941014,30.7743148,-114.3922720,34.9166501]**. Outward rounding gives **[-118.8,30.7,-114.3,35.0]**; cached-parent clipping yields the recorded candidate. Both lost southern/eastern margins remain explicit source limitations.

## Candidate measurements and decision

Candidate preparation/reference checks/census complete in **252.81 seconds**. Output `data/coverage-pilot/two-hour-candidate-v1/car-roads.osm` is **1,540,059,541 bytes**, SHA-256 **`5a80178511c04cbd20b14518b92fe8cffcaf43db0f92cbde90541f68549c4117`**. Census database is **101,457,920 bytes**. Source nodes/ways/relations are **7,310,230 / 1,579,840 / 54,814**; measured road-state interval is **9,733,657–10,121,327**, with **10,140,777 history-state ceiling** and **8,729 candidate via-way rules**. These are counts/bounds, not an imported graph.

Geographic membership covers **82,136,356 original node IDs** in **590,936 pages / 302,559,232 bitmap bytes** (reported Python container size **373,760,392 bytes**). Worker RSS peaks at **1,243,104 KiB / 1.19 GiB**, largest child **3,305,676 KiB**. Complete cgroup peak reaches **4,294,967,296 bytes / 4 GiB**, with **3,750 memory-limit events**, zero OOM/kill events and zero swap. The reference-completion stage hits the cap. Successful completion is not headroom.

**Decision: HOLD; no larger graph is built.** The largest count ratio is **5.429816741**, from source relations. The conservative rule forecasts **17,729,794,167 bytes import/export**, **9,410,968,801 qualification**, **7,363,728,073 inventory**, and measured preparation **4,294,967,296**. Maximum plus 25% is **22,162,242,709 bytes / 20.64 GiB**, above the unchanged 4 GiB cap. This is an unvalidated scaling forecast, **not measured graph memory or a claim that queries require 20 GiB**. A road/history-only sensitivity gives **13,632,649,286 bytes / 12.70 GiB including margin**, still far above the cap; source-relation scaling is not the only reason to hold. Actual preparation limit pressure independently fails admission.

Source-envelope clipping on the south/east sides is a second, separate limitation. Cached California/Mexico roads do not establish Arizona/Nevada coverage. Reference completeness within this selected source does not fill those geographic gaps. The unchanged current graph and its sampled one-hour result remain the qualified baseline.

## Resource rule and measurement scope

The largest candidate/calibration node, way, relation, eligible-segment, restriction-rule/prefix, road-ceiling and history-ceiling ratio (at least one) scales the **worst measured build/rebuild peak**, and independently scales qualification and cut inventory. Include measured calibration/candidate preparation, take the maximum of sequential phases, then add **25% margin**. Require exact XML/census/six-fixture calibration, checksum-bound full/bounded/partial/native evidence and explicit no-swap policy with no OOM/limit pressure. This is a heuristic, not a memory bound. Resource admission remains separate from source-envelope clipping and known road gaps.

Resource checkpoints include final artifact/proof verification reads; final small report writes, Docker startup and module imports are excluded. Worker/child RSS, complete cgroup peak and sampled anonymous/file maxima must not be summed. Periodic samples can miss brief composition peaks; host/cache conditions are uncontrolled. Old/new complete workflows have different proof/fixture work, despite identical calibration XML. These are preprocessing observations, not a controlled selector speedup, HTTP round trip or isolated graph-search benchmark.

## Recommended next task and validation

First qualify a separate-process selection boundary so its retained Python heap is released before native reference completion. If necessary, prototype bounded-memory completion separately. Require exact six-fixture/current/candidate XML+census parity, no limit pressure and whole-container headroom. Do not delete this capped attempt or attribute whole-workload savings to the bitmap alone.

Then profile the **current qualified graph's import/export composition** and version a storage/lifetime or partitioned/disk-backed improvement under the same cap. Preserve routing semantics and prove exact frozen graph/audit/source/CSR/gzip bytes and retained or fresh full/bounded/partial/native evidence. Only retry larger build admission after the measured workflow plus 25% margin passes. The rectangle is conservative and contains roads that may be unreachable; this census does not establish the minimum two-hour dataset. Source extension beyond the cached parent and missing AZ/NV roads must be addressed separately with pinned, assessed inputs.

Validation: **115 host Python cases (110 pass, five tool/platform skips)**, **24 scoped Linux cases (no skips)**, **14 adapter cases**, `npm run check`, `npm run typecheck`, `npm run build` and the new evidence analyzer pass. The cached reader lacks a C++ compiler; existing compiler/kernel tests pass on the Mac. No new full Linux discovery/native qualification run is claimed; the prior native evidence remains bound to unchanged graph/fields/source/binary hashes. Existing Biome database and upstream build warnings remain. Exact commands and log hashes are in the evidence validation record.

Final integrity checks match **139 preserved routing/lockfile/generated-route hashes**. `.env.local` remains ignored and was neither read nor changed; nothing is staged. The existing Valhalla service is healthy and host disk has approximately **235 GiB free** after retained products.

## Limits carried forward

The current graph's sampled one-hour clipping result is unchanged. **No new two-hour routes, contour or complete coverage are claimed.** Three source-marked uncertain Otay ways **114198251, 185333061, 577149752** stay explicit; legal static-model witnesses do not establish current ordinary-car eligibility. Border queues, delays and document requirements remain unmodeled. Mexico is retained; there is no US-only clipping rule.

The app remains free hosted openrouteservice with a **60-minute driving cap**. Original **10–12-hour/US-wide** capability and Vercel long-range execution remain unfinished. National anchors/acquisition, PostGIS layers, elevation, road-distance semantics, query caching and advanced routing remain deferred.

[Reports, identities, recalculated resource rule and validation logs](evidence/two-hour-preflight-2026-10-17/README.md) retain the measurements and decision.
