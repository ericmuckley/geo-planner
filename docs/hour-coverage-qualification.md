# East/south one-hour coverage qualification

October 17, 2026. This follows the [qualification headroom and preparation gate](hour-coverage-preflight.md). The admitted **[-117.65,31.9,-116.0,33.6]** candidate expands the eastern/southern frontiers while retaining the northern/western margins and northern Baja. This experiment builds a separate static v3 graph; it does not change the live Valhalla graph or the app's hosted provider.

Follow-up: [two-hour frontier/resource preflight](two-hour-coverage-preflight.md) now completes the recommended census. Exact source/fixture calibration passes, but larger preparation hits 4 GiB with limit pressure and graph admission is on hold. The one-hour measurements below remain unchanged; the next task is complete-workload memory reduction and explicit source-gap handling.

## Reproduce the experiment

Requires the cached parent, preparation/qualification/rebuild/fixture evidence and pinned tools image. No provider key, network download or routing-provider request is used.

```sh
npm run routing:hour
npm run routing:hour -- --stage qualify
npm run routing:hour -- --stage rebuild
npm run routing:compact:verify -- --run-name hour-v3
npm run routing:hour -- --stage cuts
python3 -B docs/evidence/hour-qualification-2026-10-17/analyze.py
```

For the recorded measurements, rebuild and native verification run in separate terminals after qualification; the code block also works sequentially for reproduction. Timings retain the recorded overlap.

Outputs are ignored under `data/compact-pilot/hour-v3`, `hour-v3-rebuild` and `hour-v3-cuts`. Completed and failed attempts refuse overwrite. Reproduce with a fresh `--run-name name` for build and qualification; pass that same name to the native verifier. Rebuild/cuts take separate fresh `--run-name` outputs and `--source-run name`. Do not delete an identity to retry or rerun the native verifier over a recorded output.

`routing/hour_increment.py` is a distinct version of the frozen increment recipe. It recomputes the recorded admission rule from checksum-bound preparation, calibration, qualification and worst build/rebuild reports. The source/profile/image/scripts must agree before import. Build and qualification have separate identities and manifests. Qualification seals an additional identity before calibration, so failed calibration is preserved too. Existing recipes, graphs, failures and environment values remain intact.

## Source, model and tooling

Source XML: `data/coverage-pilot/hour-candidate-v1/car-roads.osm`, **451,794,442 bytes**, SHA-256 **`64462b578bd9b688290fa8777bbb2564ea40ed649c47d88146353c72097ab1a1`**. It retains original IDs/tags, complete selected ways and recursive references. The current-region preparation reproduces exact XML/census and all six preparation fixtures. The [pinned profile](../routing/profiles/coverage-hour-v1.json) and [admission evidence](evidence/hour-preflight-2026-10-17/admission.json) bind this new geography. Road-state interval: **2,955,664–3,043,312**; history ceiling: **3,047,196**. The measured build contains **3,034,771 roads / 3,036,124 states / 6,411,757 arcs**, within those bounds, with **1,160 via-way prohibitions**.

Parent `data/valhalla-v2/region.osm.pbf`: **677,680,499 bytes**, SHA-256 `7f3cdfc99196d51e732fff06dabb004c0d2f1a4d557442daec9789a19b633dbe`. Road snapshot **2026-10-14T20:21:12Z**, separate admin supplementation October 16. See [provenance](regional-routing.md). Missing Arizona/Nevada roads and absent Canada remain; object extents do not establish coverage outside the nominal parent rectangle.

Static model remains **exploratory-static-car-v3**, including **5,000 ms signal / 20,000 ms U-turn penalties**, original car-access/restriction logic and qualified explicit control-point permissions. Private/unknown/conditional closures remain conservative. Profile identity is `san-diego-baja-hour-v3`. The compact importer, decoder, queue oracle, virtual terminal and native kernel are unchanged.

Linux jobs use the cached image **`sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`**, based on Valhalla revision **`7fd2228e5863b442bc1ac8d25eece6415dd91bff`**. The separate cached preparation image/Pyosmium wheel lock remain bound by preflight; no new tooling or dependencies are installed. This is our research model, not a Valhalla engine rebuild.

## Verification and measurement scope

The previously qualified virtual-terminal oracle first reproduces two old-buffer costs from the preserved flat-edge oracle. Fresh qualification checks five origins (San Diego, El Cajon, Tijuana, San Ysidro and incoming port lane), all full state costs and **5/15/30/60/120-minute, 6/10/12-hour** bounded costs against independent queue Bellman–Ford. The qualification and diagnostic function bodies remain frozen. Twelve city directions have legal history-state witnesses, and two partial destinations have independent terminal checks, including the deliberately uncertain Otay branch.

An independent reimport must reproduce all seven graph/audit/source/CSR/gzip artifacts exactly. The unchanged native verifier runs freshly against this new graph/full fields, testing costs, membership, traversal counts and both partial destinations. The all-cut inventory attaches source links to every audited endpoint/history state and compares each minimum witness with the full oracle files at every budget and direction. Route/cut GeoJSON uses actual partial endpoints. New best routes may differ from old clipped paths; the comparison reports these changes instead of requiring old routes.

All Linux build, qualification, rebuild and inventory work retains **two CPUs / 4 GiB RAM / no container swap / no network / read-only inputs**, on the unchanged 16 GiB M4 host. The preflight forecast **4,137,164,740 bytes / 3.85 GiB including 25% margin** is a heuristic for a capped attempt, not a bound. Keep failures and the cap. Per-file `POSIX_FADV_DONTNEED` requests follow completed large checksum reads; no global cache drop or file-content change occurs.

Worker/child RSS, cgroup peak and sampled anonymous/file/kernel maxima have distinct scopes and must not be summed. Preprocessing wall spans include validation, calibration/import/reload, output and verification reads as applicable, excluding Docker startup/module imports/final small metadata writes. Native verification is a separate network-denied Mac process with recorded RSS, without the Docker RAM cap. In this run it overlaps the independent Linux rebuild; they write separate products and share only immutable inputs. Timing samples are observations under that load, not an isolated comparison. Native search timings are steady-clock loop wall time; setup, encoding, process startup and local-pipe round trips are separate. None is an HTTP, isolated CPU, browser, cloud or controlled cold-cache benchmark.

## Measured results

Graph identity: **`b50422b83537cecf12f1ecb4f7a3fa4e80df206726796b562135715f3737d048`**. JSON is **860,365,940 bytes**; packed CSR is **63,438,604 bytes**, SHA-256 `fa859ec57d55f838d4cd9615c34b51f0f09b94fd82edd407bb2e383f5044760a`; gzip is **24,237,364 bytes**. Packed graph size excludes source XML, JSON, audit, rebuild, full fields and geometry/snapping metadata.

First import takes **425.70 seconds**; complete validation/build/export/verification takes **502.78 seconds**. Worker peak is **1,938,536 KiB / 1.85 GiB**, complete cgroup peak **3,265,265,664 bytes / 3.04 GiB**, with zero OOM/kill/limit events and zero swap. Actual build peak is below the **3,309,731,792-byte** pre-margin import/export forecast; this single observation does not make the heuristic a bound.

The independent rebuild reproduces **all seven graph/audit/CSR/gzip/source artifacts byte for byte**, with the same graph identity and counts. Import takes **439.53 seconds**, complete rebuild **517.50 seconds**, worker peak **1,947,420 KiB / 1.86 GiB**, cgroup peak **3,243,671,552 bytes / 3.02 GiB**, zero OOM/kill/limit/swap. Native verification overlaps part of this rebuild; resource/time observations retain that concurrency. The larger measured build/rebuild peak is **3.04 GiB**.

Fresh Python qualification compares **15,180,620 full + 121,444,960 bounded state costs** without a mismatch. All twelve city directions have legal witnesses; their external road-ID paths and costs remain unchanged from the previous graph. Both partial destinations match their independent terminal oracles: port `468334902:1:f` at half fraction is **374 ms**; uncertain Otay `114198251:0:f` is **1,167,889 ms**. Complete qualification, including frozen sink calibration, takes **963.26 seconds / 16.05 minutes**, worker peak **1,681,420 KiB / 1.60 GiB**, cgroup **1,733,201,920 bytes / 1.61 GiB**, zero OOM/kill/limit/swap. These are preprocessing observations, not an isolated search benchmark.

Fresh native verification passes **136,625,580 cost + 121,444,960 membership comparisons (258,070,540 total)** and both partial destinations, with matched traversal counts. It takes **134.82 seconds**, including **42.69 seconds** compact reload; Mac Python worker RSS peaks at **1,102,928 KiB / 1.05 GiB**. Native startup/hello is **374.12 ms** in the parent versus **56.08 ms** child graph load/validation. For five sequential default San Diego 60-minute label queries, medians are **0.34 ms source setup / 195.16 ms search loop / 2.68 ms encoding / 212.03 ms local pipe round trip**. Search p95 is **200.01 ms**, the largest of five samples. The native run overlaps the independent rebuild. These observations do not establish an improvement over the previous graph, isolated CPU time, HTTP latency, a rendered contour or Vercel performance.

## Coverage and remaining limits

The all-cut inventory covers **433 nodes / 538 history states**, with **zero missing source boundary links**. Every selected origin reaches **zero** potential cut nodes within 60 minutes in every direction. The sampled one-hour clipping target passes; general `coverageVerified` remains **false** because source completeness, all-origin coverage, current access and real-world costs are separate questions.

| Origin | Prior first cut | New first cut / side | Prior → new 60-minute cut nodes |
| --- | ---: | --- | ---: |
| san-diego | 57m47s | 65m05s / north | 1 → 0 |
| el-cajon | 42m15s | 63m32s / east | 6 → 0 |
| tijuana | 57m23s | 73m03s / south | 9 → 0 |
| san-ysidro | 56m50s | 77m34s / south | 7 → 0 |
| port-incoming | 56m52s | 77m02s / north | 7 → 0 |

Exact new first-cut costs are **3,904,583 / 3,812,295 / 4,382,526 / 4,653,895 / 4,622,333 ms** in table order. San Diego/port first reach Escondido Freeway/north; El Cajon reaches an unnamed source road (way **35324587**) at the eastern edge; Tijuana/San Ysidro reach Calle Primera/south. Source witnesses and geometry remain inspectable in the evidence.

At **120 minutes**, reachable cut nodes are **115 / 116 / 106 / 106 / 107**, respectively. San Diego has **88 north / 6 east / 21 south / 0 west**. All origins still reach cuts for longer budgets; zero western hits does not establish western/source completeness. Endpoint counts are not a percentage of covered area or accuracy.

Inventory takes **56.57 seconds**, worker peak **590,748 KiB / 0.56 GiB**, cgroup **1,356,165,120 bytes / 1.26 GiB**, zero OOM/kill/limit/swap. Every oracle minimum witness and budget/direction count is checked. A way-only plausible outward permission remains separate from legal turn/history continuation beyond the extract.

The target is **no reachable potential cut within 60 minutes for the selected origins**, not proof of complete regional source data or all-origin coverage. Every direction must be checked: added geometry can change paths to an unchanged northern/western frontier. A way-only outward permission does not prove legal node/turn/history continuation outside the extract. Even a zero-cut sample cannot establish current road completeness or real-world ETAs.

Three Otay ways **114198251, 185333061, 577149752** remain source-marked uncertain, with a forced branch retaining the warning. Static source permissions and legal model witnesses do not verify current ordinary-car eligibility. Border queues, delays and document requirements remain unmodeled; Mexico is retained, without a US-only clipping rule.

The original **10–12-hour** and US-wide requirements remain unfinished. The interactive app still uses free hosted openrouteservice with a **60-minute driving cap**. No long-range browser contour or Vercel deployment is added. National anchors/acquisition, PostGIS layers, elevation, road-distance semantics, query caching and advanced routing remain deferred.

## Original next task (preflight completed) and final checks

Preflight a **buffered two-hour candidate using every 120-minute frontier**, retaining Mexico and checking all directions. The default alone reaches 88 northern cuts at two hours, so another east/south-only expansion would be insufficient. Keep current sources/graphs/oracles/failures and recipes immutable. Version the new preparation/profile; first reproduce exact current-region XML/census and six preparation fixtures, then measure candidate road/history bounds and complete preparation resources.

The largest measured Linux phase peak is **3,265,265,664 bytes / 3.04 GiB**; including 25% margin for these same counts gives **4,081,582,080 bytes / 3.80 GiB**. This leaves some headroom for the current workload, not automatic admission for another region. Scale the worst actual build/rebuild and independent qualification separately, include measured preparation, and take the sequential maximum plus 25%. Keep two CPUs/4 GiB/no swap/no network; if the next census fails the gate, record a hold and improve a versioned memory/storage path with frozen byte/cost parity before another build. Do not raise the cap or begin national anchors from this result.

Validation passes **111 host Python cases (107 pass, four tool/platform skips)**, **20 scoped Linux cases (no skips)**, **14 adapter tests**, `npm run check`, `npm run typecheck`, `npm run build`, the new full evidence analyzer and prior preflight analyzer. The cached Linux image lacks a C++ compiler; compiler/kernel tests and fresh native qualification pass on the Mac. No new full Linux discovery pass is claimed. Existing Biome database/upstream build warnings remain.

All **136 preserved routing/lockfile/generated-route hashes match**; `.env.local` remains ignored and was neither read nor changed. Nothing is staged, the existing Valhalla service remains healthy, and final host free disk is approximately **237 GiB**. There were **zero routing-provider requests, zero road/tool downloads and zero new application dependencies**. The validation record contains exact commands, raw-log hashes and timing/load scopes.

[Raw reports, identities, comparisons and verification logs](evidence/hour-qualification-2026-10-17/README.md) record the completed measurements and decision.
