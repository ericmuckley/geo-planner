# Expanded local routing baseline

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

**Historical October 18 baseline.** The [two-hour regional baseline](../two-hour-region.md) now supersedes this default. The measurements below describe the preserved 5.4-million-state graph. To run it, use `npm run dev:experiment -- --graph-run experiment-region-v1 --cuts-run experiment-region-v1-cuts`.

Updated October 18, 2026. The larger Southern California/northern Baja graph has passed exact rebuild, independent/native routing and all-cut checks. It was the default local worker for this verification. **Live API and Chrome verification also pass.** The hosted page and its environment values are unchanged; nationwide coverage and complete two-hour/10–12-hour reachability remain unfinished.

## Run and inspect

```sh
npm run dev:experiment -- --graph-run experiment-region-v1 --cuts-run experiment-region-v1-cuts
```

Open **http://127.0.0.1:3000/experiment**, or Vite's printed port. Try San Diego at **90m** and **120m**, then the **Riverside**, **Palm Springs** and **Ensenada** example buttons. The page shows loaded bounds before a query. Teal lines sample reachable directed-road intervals; the search/counts use the full graph. Red markers indicate reached potential data edges, and the dashed rectangle shows loaded coverage. This remains a road-network experiment rather than a filled-area contour.

The launcher checks the worker's graph identity and refuses to silently reuse an older graph. To compare the preserved original:

```sh
npm run dev:experiment -- --graph-run hour-v3 --cuts-run hour-v3-cuts
```

Stop the existing worker first when changing graphs. A launcher stops only a worker it started; a reused worker stays running. Use its terminal's Ctrl+C, or identify the owned process with `lsof -nP -iTCP:8787 -sTCP:LISTEN` before stopping it. No environment-file edit is required. Python 3.11+, qualified local graph/cut artifacts and a matching macOS native binary are prerequisites; the launcher does not build/download them. Local routing is always disabled on Vercel.

## Coverage findings

Bounds expand on every side from **[-117.65,31.9,-116.0,33.6]** to **[-118.0,31.6,-115.5,34.0]**. The graph contains **5,399,625 directed roads / 5,403,080 states / 11,533,044 transitions / 2,952 via-way prohibitions**. Its identity is `07d204dba65950faccf3b328019b80fd5d66e5662b76d8200da07177adccc349`.

| Reference origin | First detected edge | Edges at 60m | At 90m | At 120m |
| --- | --- | ---: | ---: | ---: |
| San Diego | 94m32s | 0 | 0 | 246 |
| El Cajon | 89m09s | 0 | 2 | 252 |
| Tijuana | 112m26s | 0 | 0 | 26 |
| San Ysidro | 108m22s | 0 | 0 | 58 |
| Port incoming road | 106m29s | 0 | 0 | 88 |

San Diego's first detected cut moves **65m05s → 94m32s**. Its 90-minute query reaches no detected boundary; every selected two-hour query still does. At 120 minutes San Diego reaches **201 north / 24 east / 0 south / 21 west** potential edge nodes. New boundaries cross different and sometimes denser roads, so **cut counts across regions are not coverage percentages**: more detected edge nodes can accompany a later first cut and larger reachable geography.

The inventory includes **1,083 nodes / 1,526 states**, with zero missing source links. These are potential continuations; a reached node does not prove a legal outward turn or real-world access. Zero detected edges does not certify complete sources or all-origin coverage; `coverageVerified` stays false.

Riverside, Palm Springs and Ensenada are outside the old rectangle. Their indexed snaps match independent full scans exactly, at **43.05 / 4.83 / 23.61 m** from the chosen centers. This verifies snapping; their new full travel-cost fields are not separately independently qualified. The formal cost-field suite retains four geographic origins plus a partial border-road source for comparison.

## Correctness and resources

All seven build artifacts reproduce byte for byte. Fresh independent checks compare **27,015,400 full / 216,123,200 bounded** labels across five origins/eight budgets and both partial destinations. The unchanged C++ kernel adds **243,138,600 cost / 216,123,200 membership** comparisons and both partials. All twelve city costs and road-ID sequences stay identical to the old graph; both partial costs remain **374 / 1,167,889 ms**. Exactness applies to the imported static model, not actual driving ETAs or every OSM interpretation.

| Phase | Wall time | Complete container peak |
| --- | ---: | ---: |
| Source preparation (previous sealed run) | 284.54 s | 2.327 GiB |
| Old-output verification calibration | 1,088.86 s | 0.993 GiB |
| Build | 971.02 s | 1.721 GiB |
| Rebuild | 936.18 s | 1.736 GiB |
| New independent qualification | 2,202.87 s | 1.687 GiB |
| All-cut inventory | 107.70 s | 2.251 GiB |

Linux stages retain **two CPUs / 4 GiB / no swap / no network**, read-only cached inputs and zero pressure/OOM/kill/swap events. Every measured phase also fits with 25% margin. Host/VM paging is unmeasured. Native verification runs separately on Apple M4/16 GiB macOS: **228.74 s**, Python worker peak **1.211 GiB**, without the Linux container cap. Some jobs overlap, so these are observations rather than controlled performance distributions.

The old whole-workflow forecast was 5.277 GiB. Targeted fixture-ID lookups, bounded label lifetimes/exports and range-advised graph reads preserve old functional results and six CSR/full-field artifacts exactly. The original 2.615 count ratio and 25% margin are retained: build/qualification admission estimates become **3.472 / 3.245 GiB** including margin. The first calibration attempt is preserved as intentionally stopped after its reload peak could not meet that forecast. These were admission estimates; the table records actual completed jobs. No general routing algorithm or access-policy change was needed.

All **28,839** other prior open/blocked decisions are unchanged. Gate node **54646008** at **[-117.3532981,33.6142733]** lies just north of the old rectangle. Its original XML node is byte-identical in both sources, with `barrier=gate`, `access=yes`. The old region closed it as `outside-bounds`; the same frozen explicit-permission rule now includes it. Release checks reject changed in-region permissions or newly included private/unsupported gates. Real operating eligibility remains unverified.

## Live app and browser verification

Fourteen recorded app cases check the four geographic reference origins at 60/90/120 minutes, with 360/720-minute San Diego cases, repeat counts and controlled 721-minute/out-of-region errors. Settled-state counts match the independent full fields, and every cut count/direction/first cost and snap matches the frozen inventory/reference. Six more live cases verify Riverside, Palm Springs and Ensenada at 60/120 minutes. All **20 recorded valid cases**, repeat and error checks pass without provider calls. The new-area cases are smoke tests with independently checked snaps; full new-origin fields are a later qualification task.

| San Diego budget | Reachable directed roads | Native search loop | Road display preparation | App HTTP round trip |
| --- | ---: | ---: | ---: | ---: |
| 60m | 2,209,935 | 206.0 ms | 2986.2 ms | 3353.2 ms |
| 90m | 2,787,588 | 230.7 ms | 3639.9 ms | 3977.6 ms |
| 120m | 3,932,692 | 325.0 ms | 4816.6 ms | 5271.1 ms |
| 360m | 4,925,816 | 505.6 ms | 5928.5 ms | 6562.6 ms |
| 720m | 4,925,816 | 414.3 ms | 5976.4 ms | 6515.0 ms |

These are single local, resident-graph observations. Native search is loop wall time, not isolated CPU time. Native pipe round trip, snap, geometry and worker total are recorded separately. Worker total stops before HTTP JSON serialization. The verifier's HTTP timer includes response-body reading, proxy/server validation, serialization and transfer, and stops before its client JSON parse. It is not graph-search time, a controlled p95 benchmark, cloud timing or cold graph startup. Display preparation dominates these queries. A point-in-time macOS sample during browser verification is **684 MiB Python / 168 MiB native child RSS**, excluding app/browser/VM and not a peak or imposed cap.

Chrome verifies 90-minute San Diego with **0** reached edges, 120 minutes with **246**, Palm Springs at 60 minutes with **42** and Ensenada with **1**; Riverside's button selects the correct coordinates. New origins near the data perimeter can clip well below an hour. Changing origin/budget clears old results, and 721 minutes disables computation. The visible 120-minute browser sample records **374.4 ms native search / 417.5 ms pipe / 4,971.1 ms display / 5,660.4 ms app / 265.7 ms map update-to-idle**. Console capture contains only an existing wallet-extension injection error; no application/MapLibre errors were observed. One automation wait expired before the completed 90-minute UI was observed; the query itself succeeded and the subsequent DOM/screenshot verified its result.

The default launcher reuses the matching larger worker, starts Vite successfully and leaves that reused worker alive when its temporary test app stops. It rejects a mismatching older graph. Normal/type/Vercel builds and **20 adapter / 189 routing tests (9 existing platform/tool skips)** pass; Biome retains the existing database non-null-assertion warning. The generated Vercel handler rejects this local mode even with its opt-in flag set, makes zero outbound calls, and contains no routing datasets/environment files. Cloud deployment remains unperformed.

## Data and engine identity

Prepared XML: **823,266,297 bytes**, SHA-256 `fba7c77ac4b46c7ac714c843c03311731556f5bfad3797dee5fc4b11539a608f`. Graph JSON: **1,542,978,646 bytes**, SHA-256 `2a1b1e7d253e8d7d0fc63a7c1c6e055575c18ecf5034e992883f9aa63a9767e6`. Packed CSR: **113,876,724 bytes**, SHA-256 `675b614c7953917d2e34b8a1f425bda4978da8309873fb0e21652098b38a7283`; gzip is **44,253,532 bytes**.

The cached parent is **677,680,499 bytes**, SHA-256 `7f3cdfc99196d51e732fff06dabb004c0d2f1a4d557442daec9789a19b633dbe`. Profile `california-baja-roads20261014-admin20261016-v2` records bounds **[-119.8,30.8,-114.5,35.5]** and these Geofabrik road snapshots:

| Snapshot | Bytes | SHA-256 |
| --- | ---: | --- |
| `socal-261014.osm.pbf` | 671,540,119 | `4a0cc652b702142cadb77088f68564545628f7650b378847ec969e0d0a8f9a52` |
| `mexico-261014.osm.pbf` | 646,916,392 | `a0a4d8e8411fa3960ec56d4790ed5d45e9407acc396dcee05e49decf5255f81d` |

Road timestamp: **2026-10-14T20:21:12Z**. The parent also carries October 16 administrative supplements; temporal consistency at boundary edges is unverified. California/Mexico sources do not establish Arizona/Nevada coverage despite rectangular bounds. © OpenStreetMap contributors, ODbL 1.0; extracts by Geofabrik. Routing uses cached local data with **zero provider requests**; the browser basemap remains online.

Engine: unchanged C++17 bounded Dijkstra, SHA-256 `1b583ac8e02d7aa033c42d7652f7278eeb4af4da72d447faedf9474bd59a0d29`; Apple Clang 17.0.0 with `-std=c++17 -O3 -Wall -Wextra -Werror`. Model `exploratory-static-car-v3` keeps 5,000 ms signal / 20,000 ms U-turn delays. Linux tools image: `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`. Full compiler/source/binary/recipe pins are in the evidence.

## Reproduction and remaining work

The source preparation and calibration prerequisites remain checksum-bound to the preserved prior experiments. [Original setup and source preparation](local-routing-experiment.md) records those dependencies. On this prepared workspace:

```sh
node routing/region-verify.mjs --stage calibrate
node routing/region-increment.mjs --stage build
node routing/region-increment.mjs --stage rebuild
node routing/region-verify.mjs --stage qualify
sandbox-exec -f routing/native-network.sb python3 -B routing/compact_native.py --run-name experiment-region-v1
node routing/region-increment.mjs --stage cuts
python3 -B routing/region_release.py
npm run dev:experiment
node routing/verify-experiment.mjs
```

Completed run names are sealed and refuse overwrite. Use fresh `--run-name` values for repeats, `--source-run` on rebuild/cuts, matching `--graph-run`/`--rebuild-run`/`--cuts-run` on release, and `--graph-run`/`--cuts-run` on the launcher. The verification wrapper's `--run-name` names its build directory. Frozen same-code calibration can be reused. The API verifier accepts `--graph-run`, a fresh `--run-name` and `--port` for another Vite port. Do not overwrite identities or modify frozen producers to make old attempts pass.

Next: use the new 120-minute cut inventory to choose the next buffered region, especially north/west for San Diego and east for El Cajon, retaining Mexico and its southward cuts. Recompute resource admission from these measured jobs and check actual source coverage before extending toward Arizona/Nevada. The next coverage acceptance remains **zero reached potential cuts within 120 minutes for the selected origins**, with source/access uncertainty separate. Then work toward 6/10/12 hours and US coverage. The three uncertain Otay ways **114198251 / 185333061 / 577149752**, unmodeled border waits/documents/current access, static speeds, conservative unsupported-restriction closures and lack of all-origin completeness remain. Filled contours and long-range Vercel execution are unfinished. PostGIS/elevation/road-distance semantics, caching and unrelated research remain deferred.

Raw reports, logs, source excerpts, measurements and screenshots are in [the evidence directory](../evidence/larger-region-2026-10-18/README.md).
