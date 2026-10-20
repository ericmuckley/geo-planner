# Two-hour regional expansion

Completed October 19, 2026. The new **8.14-million-state** graph is now the local `/experiment` default at **120 minutes**. Exact rebuild, independent/native, source-linked cuts, live API and Chrome checks pass. The [previous expansion](archive/larger-region-experiment.md) remains preserved for comparison.

For session recovery, read [the agent handoff](agent-handoff.md). The commands below document completed recipes; they are not startup/health checks and must not overwrite completed runs. Code and large local assets have different Git/portability status, recorded in the handoff.

The milestone **passes: zero reached potential data edges at 120 minutes for all five reference origins**, retaining Mexico. This is a geographic milestone for selected origins in our static model, not complete source coverage, real traffic ETAs or all-origin correctness. Six-to-twelve-hour and nationwide coverage remain unfinished.

The expanded graph's complete edge inventory produces a conservative 160 km/h remaining-time envelope of `[-118.13166654,31.59974301,-114.62092469,34.61078881]`. Outward rounding gives **[-118.2,31.5,-114.6,34.7]**, without clipping to the cached parent's rectangle. Restored roads/restrictions can change interior shortest paths; the envelope is planning evidence, not a certificate. Fresh cuts decide the result.

## Source gap and acquisition

Current [Geofabrik California](https://download.geofabrik.de/north-america/us/california/socal.poly) and [Mexico](https://download.geofabrik.de/north-america/mexico.poly) footprints expose a gap around Yuma in the continuation estimate. The California/Mexico rectangle does not supply Arizona roads. We downloaded the dated [Arizona snapshot](https://download.geofabrik.de/north-america/us/arizona.html), **303,543,535 bytes**, SHA-256 `d008fac4857d0b520f0ab461bea57063d664f802473720385a359a952c825552`. Its header matches **2026-10-14T20:21:12Z**. Footprints were retrieved October 19, so they are an assessment of current extract extents, not pinned October 14 extent proofs. A sampled perimeter assessment is not exact containment or a land/road completeness test.

The new source merges the preserved California/Mexico parent with Arizona. It is **984,225,764 bytes**, SHA-256 `1ab94d3c9fdd92f179873addd32fe083c57770e07f839d54347962e9c9c929dc`. Osmium reports ordered objects and no multiple versions. The previous October 16 administrative supplements remain; temporal consistency at source boundaries remains unverified. Nevada data is absent. All original files are preserved. © OpenStreetMap contributors, ODbL 1.0; extracts by Geofabrik.

The Arizona file's size matches the official listing; SHA-256 was computed locally and is pinned in the recipe. The publisher's separate MD5 endpoint returned HTTP 503, then timed out, so no publisher-MD5 match is claimed. The first merge attempt rejected an unsupported command option before producing output; its recipe/logs remain. The corrected merge uses the documented [Osmium merge command](https://docs.osmcode.org/osmium/latest/osmium-merge.html).

This is one data download, followed by offline computation; no routing API is called. Only small source-footprint files were additionally fetched. The browser basemap remains online independently.

## Commands and acceptance

The source snapshot must be at `data/valhalla/sources/arizona-261014.osm.pbf`. Acquisition used:

```sh
curl --fail --location --max-time 300 \
  https://download.geofabrik.de/north-america/us/arizona-261014.osm.pbf \
  --output data/valhalla/sources/arizona-261014.osm.pbf.partial
shasum -a 256 data/valhalla/sources/arizona-261014.osm.pbf.partial
```

Compare the exact size/SHA above before renaming the partial file to its final name. The source recipe independently refuses mismatched bytes. Preserve any existing final file. Existing source/tool/calibration prerequisites are described in the expanded baseline; these are prepared-workspace reproduction commands. A fresh bootstrap needs the pinned earlier road/admin snapshots and proof chain. Do not substitute newer source bytes under an old identity.

```sh
node routing/two-hour-source-v2.mjs
node routing/two-hour-region-prepare-v2.mjs
node routing/regional-cuts.mjs
node routing/scoped-region.mjs --stage calibrate
node routing/scoped-region.mjs --stage build
node routing/scoped-region.mjs --stage rebuild
node routing/scoped-region-verify-v3.mjs
sandbox-exec -f routing/native-network.sb python3 -B routing/scoped_native.py --run-name two-hour-region-v2
node routing/scoped-region-cuts-v2.mjs --stage candidate
```

After the graph proofs, require the explicit two-hour acceptance:

```sh
python3 -B routing/two_hour_release.py
```

Defaults preserve attempts and refuse overwrites. Build/prepare/source/boundary wrappers accept fresh `--run-name` values; the qualification wrapper selects an existing built run. Dependencies between stages currently use the named runs above. Reproducing the full chain under other names requires a distinct bound recipe; changing only a stage's output name does not rebind later stages.

Each Linux phase retains two CPUs, **4 GiB RAM, no swap, no network, read-only inputs**, plus the **25% resource admission margin**. Car access/cost/search rules remain unchanged; restriction duplicate handling uses the explicitly versioned policy below. Boundary-reader calibration must reproduce both existing boundary artifacts exactly; it retains only incident ways and neighboring nodes instead of decoding the whole source for evidence. Independent full/bounded/partial checks and a fresh native run pass before the app switch.

## Measurements and outcome

The California/Mexico-only preparation completed in **308.10 seconds**, at **2,674,397,184 bytes** complete-container peak with zero pressure/OOM/kill/swap events. It measured **7,844,764–8,111,375 road states / 8,126,651 history-state ceiling**. This attempt is preserved, but it does not fill the Arizona gap and will not become the app default.

Its conservative count ratio against the latest qualified graph is **1.558399107**. Build/rebuild/qualification forecasts fit the cap plus margin; the old whole-source boundary reader forecast does not (**4,707,819,478 bytes including margin**). These are preprocessing admission estimates, not measured new graph or query memory.

The Arizona-inclusive preparation completes in **421.44 seconds**, at **2,563,608,576 bytes / 2.388 GiB** complete-container peak, with zero pressure/OOM/kill/swap. It measures **7,891,401–8,158,379 road states / 8,173,662 history-state ceiling**, from **5,861,210 nodes / 1,281,106 ways / 39,149 relations**. XML is **1,227,625,737 bytes**, SHA-256 `dd51507e70388e4658e58de5342e5fc162bc99b0d1b7b3e969c77478ea8dcdbc`. Osmium verifies source references. These are census bounds, not built graph counts.

The targeted boundary audit reproduces both current artifacts exactly (**1,083 nodes / 1,526 history states**, zero missing links) in **111.25 seconds**, at **1,566,101,504 bytes / 1.459 GiB** complete-container peak. This includes range-advised graph reads and targeted source reads; no isolated causal performance claim is made. The Arizona-inclusive count ratio is **1.560591565**, retaining all source/restriction/road/history ratios. The new boundary forecast is **3,055,055,998 bytes including 25% margin**, below the unchanged 4 GiB cap. Build/rebuild/qualification are separately admitted from the latest qualified measurements.

Across **101,160** one-degree circle-perimeter samples, adding Arizona reduces points outside the assessed source-footprint union from **134 to zero**. This is a sampled source-planning check with current polygons, not proof of dated source completeness. Fresh independent cost, all-edge and native checks pass before release acceptance.

## Rejected build and restriction fix

The first Arizona-inclusive build (`two-hour-region-v1`) completes in **792.25 seconds**, at **2,805,874,688 bytes / 2.613 GiB** peak with no pressure/swap, but is **rejected**. Its first lookup detects two duplicate directed geometries. The frozen global duplicate guard causes every via-way restriction to fall back: **8,102,396 road states, zero via-way prohibitions**. The fallback closes member roads, suppressing valid connectivity throughout the region. This is not an acceptable expanded baseline. Its graph, source, recipe and rejection record remain intact; it is not qualified or served.

The repeated directed pairs belong to **way 1497196798**, between nodes **13233928511 / 1025690516**. It is not a candidate restriction member. Its complete original way/node excerpt is retained with the evidence. The replacement introduces the explicitly named **`member-scoped-geometry-v1`** restriction policy. A repeated geometry affects only restrictions that reference its way. Existing member/topology/access checks and error priority are retained; ambiguous member ways remain conservatively rejected. Unrelated repeated geometry can no longer disable valid prohibitions across the whole region. Road costs, signal/U-turn delays, barrier/unknown-crossing access rules and graph-search algorithms stay the same. This is a deliberate restriction-resolution behavior change, not a claim of byte identity on affected inputs.

The policy is recorded as `model.restrictionGeometryPolicy` alongside the v3 car/barrier model and bound into graph identity. Seventeen fresh source fixtures pass **416 full / 1,248 bounded** independent cost comparisons and prohibition replay: sixteen preserve graph/audit behavior after normalizing model metadata and identity, while the unrelated-duplicate case deliberately retains its valid prohibition.

The full previous-graph reimport calibration **passes**. Its canonical graph normalizes to SHA-256 `2a1b1e7d253e8d7d0fc63a7c1c6e055575c18ecf5034e992883f9aa63a9767e6`, exactly the previous graph. Its prior CSR is byte-identical with the prior identity header; all four source/access/audit artifacts are byte-identical. Five existing oracle bindings remain valid for this identical routing payload. This is identity normalization for the prior-graph policy calibration; the replacement graph requires its own exact unnormalized rebuild and fresh independent/native checks. Calibration finishes in **1,116.69 seconds**, at **1,840,365,568 bytes / 1.714 GiB** complete-container peak, zero pressure/swap, including the full-payload comparison. Some jobs overlap, so wall times are observations, not controlled speedup measurements. The replacement build, exact rebuild and independent checks pass. Native and source-linked boundary release gates also pass.

The car/barrier model remains **`exploratory-static-car-v3`**, with **5,000 ms signal / 20,000 ms U-turn** delays and the same conservative access/conditional rules. The additional restriction-policy key explicitly versions the changed duplicate handling. Native search remains the C++17 bounded Dijkstra source pinned in the expanded baseline; fresh compiler/binary pins are recorded with native verification. Linux builder image remains `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`; the source reader remains `sha256:025ebba8267c0aad21bc4cb52b40c4726b65a13a1ebe66b8642df5495261ddd5`.

The replacement build completes in **1,483.71 seconds**, at **2,864,418,816 bytes / 2.668 GiB** complete-container peak with zero pressure/OOM/kill/swap. Graph identity is **`52b34545379adf83ad09175e7d29b5c445b7cf4193fee0f9b5d10afe0904fda1`**: **8,131,472 directed roads / 8,136,898 states / 17,662,110 transitions / 4,666 via-way prohibitions**. All **2,952** prior qualified prohibitions remain present. The exact rebuild finishes in **1,505.24 seconds**, at **2,848,931,840 bytes / 2.653 GiB**, with no pressure/swap. All eight artifacts match byte for byte: graph, audit, CSR, gzip, transformed source, two source excerpts and the fixture proof. Independent/native/boundary and app checks all pass before promotion.

Graph JSON is **2,339,349,342 bytes**, SHA-256 `bbabfbd594fcf148742ac7b3b98dec7c8ddf1134eefe43f6707939dd1e493404`. CSR is **173,844,524 bytes**, SHA-256 `7bcd8987a28eb462fc3350dd8f81b351604b4335314b1663d2ceca1a66955941`.

Four new-area indexed snaps match independent full scans exactly: **Riverside 43.052 m / Palm Springs 4.825 m / Ensenada 23.605 m / Yuma 22.532 m**. All requested town centers remain unchanged. The check takes **187.13 seconds on macOS**, including graph reload, index construction and four full scans, under network denial. It is not isolated snap timing, a Linux resource-cap observation or independent qualification of those towns' full travel-cost fields. Their live app cases remain separate smoke tests.

The first verification attempt then catches an integration error: the legacy compact loader does not include the new declared policy in identity recomputation. It fails before producing new cost fields. This attempt's log, identities and last progress snapshot are preserved; no final failed-phase memory peak is claimed. The versioned loader retains the frozen parser and explicitly checks legacy or declared scoped identities. Tests cover legacy payload equality, the new identity round trip, a missing policy and an unsupported policy. Native, boundary and runtime readers must use this loader for the new graph.

The second verification attempt uses separate identity files in the same immutable build directory. Its completed virtual-sink calibration is reused from the first attempt only after checking recipe, build, reference-manifest and exact destination-cost bindings. Full/bounded cost fields are still computed fresh. Rebuild remains independent of this loading change. The named policy, loader and original failed recipes remain separate; no graph/source bytes are rewritten to make identity checks pass.

The v3 entry point creates that reference-sink calibration directly when absent, then calls the same v2 field verifier. Fresh reproduction does not need to run a failed loader. `--sinks-only` checks or creates only this reference component. Both the existing-component path and a standalone fresh-bootstrap check pass; the latter uses immutable build-artifact links and freshly reproduces **374 / 1,167,889 ms** destination costs. This test does not claim another graph build or candidate cost-field qualification.

Evidence and raw intermediate products are under ignored `data/experiment-pilot/two-hour-region-v1`, `data/source-pilot/two-hour-parent-v2` and `data/coverage-pilot/two-hour-region-v2`. Final native, boundary and app evidence is archived below. The experiment worker/default now use the new graph; hosted-service environment values remain unchanged.

## Independent qualification

The successful v2 field qualification completes in **3,843.74 seconds**, at **2,830,807,040 bytes / 2.636 GiB** complete-container peak. All limit/OOM/kill/swap counters remain zero; adding the 25% admission margin gives **3.296 GiB**, below the unchanged 4 GiB cap. This long verification batch is not interactive query latency.

Five fresh complete Dijkstra fields equal an independent Bellman–Ford oracle: **40,684,490 full-state cost comparisons**. Eight budgets per source (5/15/30/60/120/360/600/720 minutes) add **325,475,920 bounded-cost comparisons**. Both partial-road destinations match fresh virtual-terminal checks; twelve city directions remain finite. The partial costs are **374 ms** on the port road and **1,167,889 ms** on the explicitly uncertain Otay road. These are static model costs, not verified border travel times.

| Reference source | First potential edge | Detected edge within 120m |
| --- | --- | --- |
| San Diego | 128m04.582s | No |
| El Cajon | 130m45.685s | No |
| Tijuana | 130m47.556s | No |
| San Ysidro | 135m18.925s | No |
| Port incoming road state | 135m20.411s | No |

Zero detected cuts for these selected sources does not prove source completeness, every origin, real access or accurate ETAs. Six-to-twelve-hour requests still reach missing geography. Northern Baja remains essential: the model can cross the border, with no traffic, queue, document or current operating-eligibility calculation. Otay ways **114198251 / 185333061 / 577149752** retain explicit uncertainty.

## Source-linked boundary audit

The new inventory checks **805 potential cut nodes / 1,173 states including maneuver history**. Every node has source boundary links; **zero links are missing**. It completes in **175.68 seconds**, at **2,364,760,064 bytes / 2.202 GiB** complete-container peak, zero limit/OOM/kill/swap. The 25% margin gives **2.753 GiB**. Three enabled XML/graph streams reach EOF with successful range advice; eviction remains advisory, and field maxima are not simultaneous.

All five sources have **zero reached cuts at 120 minutes**. At 360 minutes they reach **628 / 628 / 627 / 627 / 628** cuts respectively; at 600/720 minutes each reaches 628. Thus the accepted request range is not complete six-to-twelve-hour geography. Counts refer to this perimeter and model, not a percentage of missing national roads. Source-linked potential outward geometry is not verification of real legal continuation.

CSR gzip is **68,296,837 bytes**, SHA-256 `5d2acfacae32ac27c79d34d3ca042345b7928f636c0f05b3051ec6d313190caa`. With intermediate qualification files, the graph run currently occupies about **4.1 GiB**, preparation about **2.6 GiB** and the merged-source run about **945 MiB**. These are observed directory sizes, not minimal deployment storage or national forecasts. About **183 GiB** of host disk remains free; old runs are retained.

## Native and release checks

The unchanged C++17 bounded Dijkstra kernel passes **366,160,410 cost / 325,475,920 membership comparisons**, plus both partial destinations. All complete native label files equal the independent fields; every bounded/membership output equals its thresholded oracle. Five sequential observations per case/mode are retained, so the reported p95 is simply the largest of five samples, not a production latency estimate. Native search is steady-clock loop wall time, not CPU-only time or HTTP latency.

The fresh macOS run takes **339.61 seconds**, including **119.77 seconds** compact reload and verification overhead; Python peak RSS is **2,084,720 KiB / 1.988 GiB**. It is network-denied, but is not a Linux 4 GiB cgroup observation. Native graph loading/validation is **157.34 ms**, and process startup/hello **373.63 ms**. These scopes are distinct from loading/indexing the Python web worker.

Compilation uses **Apple Clang 17.0.0 (clang-1700.6.4.2), arm64**, `-std=c++17 -O3 -Wall -Wextra -Werror`. Source SHA-256 is `1b583ac8e02d7aa033c42d7652f7278eeb4af4da72d447faedf9474bd59a0d29`; the freshly compiled **60,768-byte** binary SHA-256 is `862325d3d62b7f3280042faab18f86eccbc11782550cafa74f4538846ebe9c39`. Host is an M4 Mac with **16 GiB RAM**, Python 3.13.5, Node 24.5.0 and npm 11.6.0; Linux workers use Python 3.12.3. Both tooling images are pinned above; no package/image upgrades occur.

`two_hour_release.py` passes all graph/resource/provenance gates and the explicit five-source two-hour acceptance. All **twelve city route costs and road sequences are identical** to the previous qualified expansion; all **62,797 previous barrier decisions** and **2,952 via-way prohibitions** remain. No previously covered control-point decision changes. This establishes the specified model’s consistency, not real-world eligibility at every crossing.

## Live app measurements

`node routing/verify-experiment.mjs --graph-run two-hour-region-v2 --run-name two-hour-map-v2` passes **14 recorded valid app queries** (San Diego 60/90/120/360/720m, the other three geographic reference sources 60/90/120m), plus a repeat 120m query and controlled 721m/outside-region errors. Settled-state counts match every independent field label; cuts, snap coordinates, side counts and first-edge costs match the source-linked evidence. Reachable-road counts are monotone, display samples stay within 30,000 segments and all incomplete results warn. The separate incoming-road-state source is covered by graph/native/cut checks, not these geographic API cases.

| San Diego budget | Settled states | Reached edges | Native search loop | Geometry stage | HTTP body received |
| --- | ---: | ---: | ---: | ---: | ---: |
| 60m | 2,209,709 | 0 | 226.8 ms | 3187.6 ms | 3595.7 ms |
| 90m | 2,786,870 | 0 | 252.9 ms | 4044.6 ms | 4429.8 ms |
| 120m | 4,520,397 | 0 | 511.8 ms | 6097.5 ms | 6754.4 ms |
| 360m | 7,441,551 | 628 | 716.7 ms | 8873.8 ms | 9718.3 ms |
| 720m | 7,442,665 | 628 | 676.5 ms | 8983.6 ms | 9808.2 ms |

These are sequential development-server observations, not controlled cold/warm or production p50/p95 benchmarks. **HTTP round trip is not isolated graph search.** Its timer stops after receiving the response text, before the verifier parses JSON. Native search is the instrumented loop’s wall time; source setup, native encoding/pipe round trip, Python snap/geometry work, HTTP serialization/proxy/body transfer, browser parsing/validation and map update-to-idle are distinct stages. Python `workerTotalMs` ends before HTTP JSON serialization. Browser app time includes its own parsing/validation; map update-to-idle remains separate. Source/basemap network behavior also differs.

## New-area checks

`node data/experiment-pilot/two-hour-region-v1/expanded-smoke.mjs` passes eight additional live queries. All indexed snaps equal the independent full-scan proof above, and reachable-road counts are positive and monotone. The requested centers are not moved to make the tests pass. These origins’ **full travel-cost fields are not independently qualified**; this is app/snap smoke coverage.

| Example | Potential edges at 60m | At 120m |
| --- | ---: | ---: |
| Riverside | 185 | 523 |
| Palm Springs | 0 | 337 |
| Ensenada | 3 | 5 |
| Yuma | 67 | 69 |

The two-hour milestone applies to the five reference sources, not every location in the rectangle. Riverside, Ensenada and Yuma can clip within an hour. The Yuma case explicitly exercises Arizona-area roads near the eastern perimeter; it does not establish Arizona-wide coverage. Together the two API checks record **22 valid cases**, plus reference repeat/error checks, without calling a routing provider.

## Run the qualified app

```sh
npm run dev:experiment
# With the app running, choose a fresh evidence output name:
node routing/verify-experiment.mjs --graph-run two-hour-region-v2 --run-name fresh-live-check
```

Open **http://127.0.0.1:3000/experiment**, or Vite’s printed port. The page starts at **120m**; choose **Compute reachable roads**. The default worker/cut runs are `two-hour-region-v2 / two-hour-region-v2-cuts`. It displays the road date, model/policy and graph identity. The launcher only enables the local API in its child app process; `.env.local`, hosted provider settings and keys are preserved. It does not download/build the graph or call a routing API.

Python 3.11+, the completed graph/proofs and matching macOS native binary are prerequisites. Reloading/indexing takes roughly two minutes on this machine before the worker is ready. The launcher’s default smoke test successfully reuses the qualified worker and starts Vite at **3001** because the original app is on 3000; stopping that temporary app leaves the worker and original apps alive. Selecting the old graph while this worker is active correctly fails its identity guard. Stop only the identified worker before changing graphs; then use `npm run dev:experiment -- --graph-run experiment-region-v1 --cuts-run experiment-region-v1-cuts` for rollback. All old graphs remain intact.

## Browser, checks and handoff

Chrome verifies San Diego **90m / 120m with zero cuts**, **360m with 628 cuts and an incomplete warning**, and **Yuma 60m with 67 eastern cuts / 22.5 m displayed snap distance**. Changing budget/origin clears old results; 721 minutes disables computation. The 120m browser sample displays **429.9 ms native search / 466.9 ms pipe / 5,656.1 ms geometry / 6,144.8 ms worker / 6,301 ms app / 192 ms map update-to-idle**. It renders **29,972 sampled segments from 4,525,404 reachable directed roads**; settled-state and partial-road counts have different meanings. Timings are single development observations with the scopes described above.

A handoff-document write reloaded the development page during the first 90m attempt; repeating with writes paused produces the verified result. Console capture contains only the existing wallet-extension `ethereum` setter error, with extension source URLs; no application/MapLibre errors were observed. The screenshots show the explicit regional warnings, dashed extent and sampled geometry.

Point-in-time macOS RSS during browser testing is **720,400 KiB Python worker / 181,696 KiB native child**. These are resident observations, not peaks, a summed Linux cgroup measurement or a national memory forecast. Larger Linux phase peaks are **2.668 GiB build / 2.653 GiB rebuild / 2.636 GiB qualification / 2.202 GiB cuts**. Each passes its separate 25% margin and records zero pressure/OOM/kill/swap.

All final checks pass:

```sh
npm test
npm run test:routing
npm run check
npm run typecheck
npm run build
npm run build:vercel
node data/experiment-pilot/two-hour-region-v1/vercel-check.mjs
```

There are **20 passing adapter/server tests**, and **200 routing tests run: 191 pass / 9 existing platform-specific skips**. Biome passes with the existing `src/db/index.ts` non-null-assertion warning. Both application targets build. The generated Vercel handler, invoked locally with `VERCEL=1` and `LOCAL_ROUTING_EXPERIMENT=1`, returns **503 for GET/POST experiment calls**, with zero outbound calls. The function contains **27 files / 3,284,495 bytes**, with no routing dataset or environment files bundled. This verifies packaging/guard behavior, not a cloud deployment or a Vercel long-range engine.

[Archived evidence](evidence/two-hour-region-2026-10-19/README.md) includes source/build/rebuild/qualification/native/cut/release reports, rejected attempts, raw-response hashes, browser screenshots/DOM/console, logs, recipe hashes and document/preservation validation. `collect-evidence.py` in that folder records the exact collection checks; large graphs and raw responses stay ignored. All previous producers and generated routes remain unchanged; only three existing runtime/UI files intentionally change from the preserved session start. No secrets, lockfile changes, dependency/image upgrades, provider requests or cloud deployment occur.

**Next recommended task:** preflight a six-hour continuation region from **this graph’s complete cut inventory**, retaining Mexico and checking actual neighboring-state footprints before downloads. Measure source size, disk, road/history/restriction counts and whole-phase RAM, keep the 4 GiB/no-swap/25% gates, then build/rebuild and independently qualify an admitted region. Do not extrapolate national coverage or production latency from this result. Filled contours, 10k national anchors, PostGIS/elevation, road-distance semantics, caching and unrelated research remain deferred; the hosted main page stays at 60 minutes.
