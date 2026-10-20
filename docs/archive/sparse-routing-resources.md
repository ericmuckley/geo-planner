# Sparse preparation and complete-workload resource gate

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

Follow-up: the [regional increment](regional-coverage-increment.md) now builds/reproduces/qualifies the admitted source. This page preserves the earlier import/export admission heuristic; the new qualification phase exposes a separate 3.74 GiB peak and remaining geographic cuts.

October 17, 2026. The prepared next region now passes a **25% resource-margin rule for a separate capped import attempt**. It is not a qualified new routing graph. Complete 60-minute and 10–12-hour coverage remain unproven; the app still uses the free hosted 60-minute endpoint.

This follows the [cut inventory/preflight](coverage-increment-preflight.md) and [compact decoded-input qualification](compact-osm-input.md). Original sources, graphs, recipes and unsuccessful attempts remain intact. No application environment values changed. There were **zero routing-provider requests and no new road downloads**. A separate offline reader image adds six pinned Python wheels totaling **2,354,828 bytes**; application/npm dependencies and the lockfile are unchanged.

## What changed

The original frozen-buffer import was profiled through input verification, parse, graph/history construction, source evidence, export and final artifact checks. Its complete container peak was **3.96 GiB**, despite only about 1.26 GiB child worker RSS. Periodic composition samples show substantial file accounting during repeated verification reads. Anonymous and file maxima occur at different times and must not be added.

`routing/sparse_select.py` uses sparse sets of original OSM IDs. It scans raw node locations, selects intersecting ways when **any node** is inside the rectangle, and closes relevant parent relations recursively. Pyosmium runs with `locations=False`, avoiding a node-location cache. Selected way/restriction IDs feed the existing native recursive `osmium getid` extraction and reference checks. IDs, tags and restriction members are retained; nothing is renumbered. See the official [handler API](https://docs.osmcode.org/pyosmium/latest/reference/Handler-Processing/) and [filter documentation](https://docs.osmcode.org/pyosmium/latest/reference/Filters/) for the reader interfaces.

Six native boundary/reference fixtures pass graph/audit comparison, including the case that rejected the earlier simple selector. The sparse recipe also reproduces the **entire frozen-buffer XML byte for byte**, then the entire next-candidate XML and census. Sparse selection alone still fails the chosen margin rule. It is not constant-memory national preprocessing: sets grow with selected objects, and downstream native reference extraction can still use dense indexes.

`routing/paged_io.py` adds a versioned checksum-read policy: after hashing a file of at least 8 MiB, request Linux `POSIX_FADV_DONTNEED` for that file. This is advisory, not guaranteed release. It does not edit file contents or drop global caches. Separate `paged_import.py` and `sparse_paged_prepare.py` controllers preserve the frozen modules and original workflows. The latter reuses the verified sparse calibration and unchanged selector/fixture functions. All seven graph/audit/packed/source outputs of the frozen buffer remain byte-identical.

## Pins and source identity

The existing base is `geo-planner-valhalla-tools:7fd2228e5`, image ID `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`. It retains Valhalla revision `7fd2228e5863b442bc1ac8d25eece6415dd91bff` and Osmium 1.16.0. It is not rebuilt or replaced.

The added Linux arm64/CPython 3.12 reader image is `geo-planner-osm-sparse:4.3.1-v1`, image ID `sha256:025ebba8267c0aad21bc4cb52b40c4726b65a13a1ebe66b8642df5495261ddd5`. [The wheel lock](../../routing/tools/pyosmium-v1.json) records exact public URLs, sizes and SHA-256 values: osmium 4.3.1, requests 2.34.2, charset-normalizer 3.5.2, idna 3.20, urllib3 2.8.0 and certifi 2026.7.22. Lock SHA-256: `8a31a9283390f1fe7cbff4682b829cdec266ee8bf021a83b9cef81f49641ec10`. Dockerfile SHA-256: `9c0e4e9714ef0854366d307270597240f6be758e72535d7e948cffab4e8450c4`. The builder verifies the cached base ID and wheel bytes, builds without network/pulls, and records the resulting image ID. The recipe is currently architecture-specific.

Parent: cached `data/valhalla-v2/region.osm.pbf`, **677,680,499 bytes**, SHA-256 `7f3cdfc99196d51e732fff06dabb004c0d2f1a4d557442daec9789a19b633dbe`. OSM road snapshot: **2026-10-14T20:21:12Z**; separate admin supplementation is October 16. See [regional provenance](../regional-routing.md).

Next candidate: **[-117.65,32.0,-116.3,33.6]**, San Diego/northern Baja, from that cached parent. XML is **442,764,751 bytes**, SHA-256 `f7c4bda33bfa33a1f2f6cc7ca0f32257bac68559ebe31c1488f7b8510effa92e`; census is 2,278,632 nodes, 456,908 ways and 10,053 relations. Directed-road bounds remain **2,858,813–2,946,180**, with **2,950,064** as the history-state ceiling. These are preparation counts, not built graph counts.

The parity graph remains `compact-v1-buffer-v3`: **2,137,982 roads / 2,139,131 states / 4,534,800 arcs**, 974 via-way prohibitions, graph ID `2f5f816407ba914bda6024fa0bda47c5fa69e381f182b8d5e53086a88613615c`. Static v3 costs/access, 5-second signal and 20-second U-turn penalties are unchanged. Existing independent oracle/native evidence is reused only because all graph, audit, packed and source artifacts match exactly; no new route search is claimed.

## Actual resource observations

Every new workload uses **two CPUs, 4 GiB RAM, `--memory-swap 4g` (swap denied), network disabled and read-only cached input mounts**. All five successful new runs record zero OOM, kill and memory-limit events, and zero swap. Host: M4 Mac, 16 GiB RAM; Docker VM about 7.65 GiB. Final host free disk is 261,097,734,144 bytes (about 243 GiB), after retaining all attempts. Source XML and graph exports are separate retained artifacts, so final graph size alone is not a working-disk budget. These runs do not establish national build requirements.

| Workload | Complete cgroup peak | Worker / largest child RSS, KiB | Worker wall, s |
| --- | ---: | ---: | ---: |
| Prior native candidate preparation | 4.00 GiB, 1,056 limit hits | 64,844 / 3,837,016 | 67.86 |
| Fresh unchanged frozen-buffer import/export | 3.96 GiB | child 1,323,856 | child 351.72 |
| Frozen-buffer import/export with checksum advice | **2.09 GiB** | 1,338,068 / — | 377.92 |
| Sparse calibration, six fixtures + old buffer | 3.19 GiB | 1,355,416 / 2,503,392 | 201.64 |
| Sparse candidate, without advice | 3.38 GiB | 1,587,156 / 2,554,824 | 208.13 |
| Sparse candidate, with advice | **2.94 GiB** | 1,587,676 / 2,538,668 | 206.23 |

RSS marks belong to separate processes, not simultaneous sums. The unchanged profile's small outer monitor process is excluded from its worker column; its child report records the actual import worker. Import-stage times were **296.51 s unchanged / 318.21 s advised**. Complete container peak falls **47.1%**, while worker RSS does not improve. Candidate preparation takes roughly three times the old native preparation wall time in these observations.

Sampled maximum file accounting falls from **3,243,511,808 to 1,143,009,280 bytes** in the complete import comparison, and from **1,301,815,296 to 639,647,744 bytes** between the two sparse candidate runs. The final sparse candidate's sampled anonymous maximum is **2,757,410,816 bytes**. The native candidate previously sampled **3,941,556,224 bytes** anonymous, so file advice alone could not fix that selector's memory use.

These are individual preprocessing observations, not controlled performance benchmarks. Some independent jobs shared the host concurrently; host/VM paging and cold-cache behavior were not controlled. The monitor samples composition every 200 ms and can miss brief peaks; kernel `memory.peak` is a separate cumulative counter. Worker wall includes validation/export and artifact hashing up to report assembly; Docker startup, module imports and final small report writes are outside it. The sparse-preparation final checkpoint precedes its last artifact-hash pass, while periodic sampling continues through that pass; the reported cumulative peaks/events are those at recorded checkpoints. The next import should checkpoint again after all verification reads. No number here is isolated graph-search time or HTTP latency.

## Admission rule and result

`routing/resource_admission.py` uses the largest corresponding candidate-to-calibration input/road/history ratio, **1.3790945949546802**, to scale the **measured complete-container import/export peak**. Preparation and import are sequential, so take their maximum, then add 25%:

```text
scaled import = round(2,248,441,856 × 1.3790945949546802)
              = 3,100,814,011 bytes
estimate      = round(max(3,151,962,112, 3,100,814,011) × 1.25)
              = 3,939,952,640 bytes = 3.67 GiB < 4 GiB
```

The rule also requires exact source/graph parity, no swap and no OOM/limit pressure. Without checksum advice, sparse preparation yields **4,540,769,280 bytes with margin**, so that attempt remains a hold. The combined recipe passes.

This estimate is a heuristic, not a memory bound: topology, restriction fallback, file cache and runtime noise may scale differently. It admits **only a separate isolated import under the same cap**, preserving failure evidence. No larger graph has yet been built, no new coverage is verified, and the existing app range stays unchanged. [Machine-readable admission and comparison evidence](../evidence/sparse-resource-2026-10-17/README.md) records hashes and scope.

## Reproduction

Requires Docker, Node/npm and the cached parent, original four `input-v1` semantic proof cases, frozen buffer graph/source, staged calibration/candidate and cut inventory. The reader setup downloads missing locked tooling wheels only; the experiments deny network. Defaults below are already completed and refuse overwrite:

```sh
npm run routing:tools:sparse
npm run routing:resources
npm run routing:sparse -- --case calibration
npm run routing:sparse -- --case candidate
npm run routing:paged
npm run routing:sparse:paged -- --case candidate
python3 -B docs/evidence/sparse-resource-2026-10-17/analyze.py
```

Use a fresh `--run-name name` on each experiment to reproduce it without changing saved attempts. To bind a fresh sparse calibration, pass `--calibration-run name` to either candidate command. The recorded paged candidate reuses `sparse-calibration-v1`; it verifies its scripts, fixtures, artifacts and image before running the unchanged selector. The advised importer binds the four original `input-v1` proof cases and compares all seven frozen-buffer artifacts. Outputs live under ignored `data/resource-pilot/` and `data/sparse-pilot/`; image/wheel records are under `data/tools/`.

Verification: **103 Mac Python cases (99 pass, four tool/platform skips)**, **14 adapter tests**, `npm run check`, `npm run typecheck` and `npm run build` pass. A scoped Linux reader/Osmium/I/O/admission suite passes **12/12 without skips**, covering all four host skips. A full Linux discovery attempt fails because the lightweight image has no C++ compiler; native compiler/kernel tests pass on the Mac. The evidence folder preserves both Linux results. Biome retains the existing database non-null warning; build retains existing upstream warnings.

## Next task and coverage limits

Build and qualify the admitted candidate in a **new output/identity**, using its exact advised-preparation XML, unchanged v3 semantics, explicit no-swap 4 GiB/two-CPU policy and the measured checksum policy. Keep old modules and artifacts frozen. Record actual complete import/export accounting and compare graph counts to the census bounds; retain failures without increasing the cap.

Then run fresh independent full/bounded/partial oracles for five origins/eight budgets, twelve city directions and both partial destinations, followed by the unchanged native kernel comparisons. Rebuild and compare bytes; inventory every reachable potential cut by direction and attach source witnesses. New geography can change best routes/costs: explain differences with legal witnesses rather than forcing equality to truncated old routes.

The current graph's default first potential cut is still **35m17s north**, El Cajon's **22m22s east**, and Mexico origins **24–29 minutes south**. Every selected 60-minute/longer case reaches cuts. This candidate retains Mexico, but a wider rectangle does not prove complete crossing coverage. Otay ways **114198251, 185333061, 577149752** stay explicitly uncertain; current car eligibility and border queues/delays remain unverified/unmodeled. Parent AZ/NV road gaps, absent Canada and coastal/boundary continuations remain constraints. No national acquisition, 10k-anchor batch, browser range increase or Vercel rollout follows from this resource result. PostGIS, elevation, road-distance semantics and advanced routing remain deferred.
