# San Diego and northern Baja coverage increment

October 17, 2026. The admitted candidate builds **2,937,639 roads / 2,938,992 states / 6,205,235 transitions** under the unchanged cap. This follows the [sparse preparation/resource gate](sparse-routing-resources.md). The experiment uses the admitted cached candidate, unchanged static v3 costs/access and the same **4 GiB RAM, two CPUs, no container swap and no network**. Original sources, graphs, recipes, failed attempts and environment values stay intact. No routing-provider requests, new road downloads or application dependencies are needed.

Follow-up: [qualification headroom and one-hour preflight](hour-coverage-preflight.md) now reduces complete qualification peak to **1.55 GiB** with unchanged results, and prepares the proposed east/south candidate. Its **3.85 GiB** estimate including 25% margin admits a separate capped build; no new candidate graph or complete-hour result is claimed. The measurements and commands below remain the original increment evidence.

## Source and model

Bounds: **[-117.65,32.0,-116.3,33.6]**, expanding the previous San Diego/northern-Baja graph in every direction. Input is `data/sparse-pilot/sparse-paged-candidate-v1/car-roads.osm`: **442,764,751 bytes**, SHA-256 `f7c4bda33bfa33a1f2f6cc7ca0f32257bac68559ebe31c1488f7b8510effa92e`. Sparse preparation preserves original IDs, tags and complete references and matches the prior native preparation exactly.

Cached parent PBF: **677,680,499 bytes**, SHA-256 `7f3cdfc99196d51e732fff06dabb004c0d2f1a4d557442daec9789a19b633dbe`. Road snapshot: **2026-10-14T20:21:12Z**; separate admin supplementation is October 16. See [regional provenance](regional-routing.md). Parent Arizona/Nevada road gaps and absent Canada remain. Object extents outside the nominal parent rectangle do not establish coverage there.

Importer: unchanged `input_import.py`, compact typed arrays/CSR and maneuver history. Model: `exploratory-static-car-v3`, 5-second signal penalty and 20-second U-turn penalty. Qualified explicit car permissions at recognized controls are retained; private/unknown/conditional closures and restriction fallbacks remain conservative. These static costs are not real ETAs. The per-file checksum-read advice policy is reused; no global cache drop or file-content change occurs.

Build image remains `geo-planner-valhalla-tools:7fd2228e5`, immutable ID `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`, from Valhalla revision `7fd2228e5863b442bc1ac8d25eece6415dd91bff`. The research importer/kernel are our separate static model; this is not a new Valhalla service graph. The new sparse-reader image is only a prerequisite of the completed preparation.

## Workflow and reproduction

`routing/increment.py` composes the frozen importer, compact reloader and cut-inventory primitives. A separate `increment_qualification.py` calibrates and runs the independent oracle/route checks. Each stage has its own identity/report/resource checkpoints; completed identities refuse overwrite. A build manifest stays frozen when qualification adds a separate final manifest. The independent rebuild compares all seven graph/audit/packed/source artifacts exactly.

Requires the cached candidate and sparse admission evidence, completed `paged-import-v1`, old buffer and four original `input-v1` semantic proofs, downtown maneuver fixtures and cached tools image. No provider key is used. Recorded defaults:

```sh
# Fresh import/export, with source/admission/recipe validation.
npm run routing:increment

# Reload the new graph, reproduce CSR, then run independent Python checks.
npm run routing:increment:qualify

# Fresh import of the same XML; compare all seven output artifacts.
npm run routing:increment -- --stage rebuild

# Unchanged native compiler/kernel/verifier, with network denied on macOS.
npm run routing:compact:verify -- --run-name increment-v3

# Every audited cut and history state, including original source links.
npm run routing:increment -- --stage cuts

python3 -B docs/evidence/coverage-increment-2026-10-17/analyze.py
```

Outputs are ignored under `data/compact-pilot/increment-v3`, `increment-v3-rebuild` and `increment-v3-cuts`. To reproduce, use `--run-name fresh-name` for build, then **the same name** for qualification; it adds a qualification identity without changing the build manifest. Rebuild/cuts use a fresh output name and `--source-run fresh-build-name`. Pass that build name to the native verifier too. The evidence analyzer binds the recorded defaults. Failed partial qualifications require a fresh build/output; do not remove their identity to retry in place. The native verifier writes its report/binary into the new graph directory and should be run once per recorded output.

## Verification scope

Qualification uses four geographic origins (San Diego, El Cajon, Tijuana, San Ysidro) plus an incoming port lane. Source snapping remains within 100 meters, with explicit road/fraction attachments. The independent queue-based Bellman–Ford oracle first has to reproduce all **10,695,655 state costs** in the five frozen buffer fields, previously qualified by flat-edge Bellman–Ford. Its implementation has no priority queue or Dijkstra calls; 200 deterministic small directed-graph cases compare it with both old algorithms, including zero-cost cycles, duplicate seeds and disconnected states. A versioned qualification function retains the frozen function body exactly and changes its oracle import only. The flat-scan qualification path remains available as `routing:increment -- --stage qualify` as a slower alternative; it was not run for this recorded graph.

Five fresh full Dijkstra fields are then compared with independent queue Bellman–Ford fields, then bounded searches are checked at **5/15/30/60/120 minutes and 6/10/12 hours**. Twelve directed city routes retain legal history-state witnesses. Two partial destinations use independent sink oracles, including the deliberately uncertain Otay branch.

The unchanged native C++ kernel checks full fields, bounded labels, membership and traversal counts against the fresh Python evidence. The 4 GiB cap applies to the Linux build, Python qualification and inventory containers. Native verification is a separate network-denied Mac process with recorded RSS, without an imposed Docker RAM cap. These comparisons qualify the imported static model. Numeric 12-hour budgets on a clipped graph do not establish complete 12-hour geographic reachability.

Cut inventory covers **every audited endpoint/history state**, attaches original boundary segments and records reachable counts by north/east/south/west for every origin/budget. A way-only outward permission does not prove legal node/turn/history continuation beyond the extract. Source boundary links and potential cuts are retained even when blocked or unreachable. GeoJSON route endpoints use the actual partial source/destination fractions.

## Measurements and findings

Build identity: `e8a6bc98cac1729637f73fd75a22519e7bcfc1f108d1207d7b7a286a09afb3a8`. Roads fit the admitted **2,858,813–2,946,180** interval and states fit the **2,950,064** ceiling. There are **1,160 via-way prohibitions**. Graph JSON is **832,551,201 bytes**; packed CSR is **61,397,900 bytes**, **23,480,471 bytes gzip**. JSON SHA-256: `f4248742d2d7f3c1b30f98f7d71c0ec5da2249bf1409a5ae265aae2c6ecd1631`; CSR SHA-256: `8941a425b4bed702368625363792dee2f1f439fcc7cee155ecfd81dbfb815694`.

First import takes **411.18 s**, complete build/export/verification **485.77 s**, worker peak **1,887,360 KiB (1.80 GiB)** and complete cgroup peak **3,151,319,040 bytes (2.94 GiB)**. There are zero OOM, kill, limit-hit or swap events. The measured peak is about 1.6% above the scaled-import component of the admission heuristic, within its 25% margin; the estimate was not a strict bound.

The independent rebuild reproduces all seven graph/audit/packed/source artifacts exactly. It takes **502.77 s** complete, peaks at **1,869,916 KiB worker / 3,192,205,312 bytes (2.97 GiB) cgroup**, and records zero OOM, kill, limit-hit or swap events. Full Python qualification, including calibration and both original flat-edge sink checks, takes **1,705.86 s (28.43 minutes)**, with **3,011,984 KiB worker / 4,021,116,928 bytes (3.74 GiB) cgroup**, also with all events/swap zero. It compares **14,694,960 full state costs + 117,559,680 bounded costs**, twelve city directions and both partial destinations. This exposes a verification-memory constraint that the earlier import/export admission heuristic did not forecast. With 25% margin, qualification would require **4.68 GiB**, so it lacks comfortable headroom for another increment.

The unchanged native kernel passes **132,254,640 cost + 117,559,680 membership comparisons (249,814,320 total)** and both partial destinations. Full native verification takes **129.32 s**, including **41.06 s** compact Python reload. The Mac verifier's peak RSS is **715,728 KiB**; native per-request peak RSS is **168,352 KiB**, recorded separately. For San Diego at 60 minutes, five label-mode observations give median **200.30 ms search-loop wall / 0.34 ms source setup / 2.61 ms encoding / 213.72 ms local pipe round trip**. Process startup/hello is **403.31 ms**, including **59.61 ms** child graph load/validation; parent time includes process launch/handshake. These are overlapping scopes, not additive totals. Native verification overlaps the cut-inventory job, and p95 is the largest of five samples. No HTTP or CPU-only search claim is made. Fast regional traversal does not fix clipped coverage.

All twelve city routes retain the previous buffer's exact road-ID paths and costs. Four geographic source snaps also retain their physical segments/coordinates, at **0.51 / 13.59 / 4.56 / 17.87 meters** for San Diego / El Cajon / Tijuana / San Ysidro. Every prior barrier open/blocked decision remains unchanged; the larger area has **1,413 explicitly permitted controls**. Sampled city routes avoid the uncertain Otay ways. The forced uncertain branch remains reachable in the model at **1,167,889 ms** and explicitly warns about source access uncertainty; the port partial target costs **374 ms**, without any border queue or real crossing-delay claim.

The [evidence folder](evidence/coverage-increment-2026-10-17/README.md) binds graph/source/code/manifest hashes, fresh oracle results, rebuild equality, complete-workload resources and route/cut comparisons with the previous buffer. Preprocessing wall times include input validation, import or reload, export and final artifact verification as applicable. Final resource checkpoints follow verification reads; final small metadata writes are excluded. Worker RSS, complete cgroup peaks and periodic anonymous/file samples have separate scopes and must not be added.

Native search-loop wall time, source setup, encoding, process startup and local pipe round trip are reported separately. These are local observations, not HTTP timing, CPU-only benchmarks, controlled cold-cache measurements or Vercel results. Qualification and rebuild overlap on the host; app checks also run during some preprocessing. Their wall times are individual observations, not controlled throughput comparisons. Host is the same 16 GiB M4 Mac; each Docker workflow remains capped independently. The full Linux suite's missing C++ compiler is an existing lightweight-image limitation; native tests/verifier use the Mac compiler, and scoped Linux source/resource tests cover host skips.

## Boundary findings

All **309 audited cut nodes / 365 history states** have original source boundary links. The sealed inventory confirms:

| Origin | Previous first cut | New first cut | Previous / new cut nodes within 60 min | New 60-min sides |
| --- | ---: | ---: | ---: | --- |
| san-diego | 35m17s | 57m47s | 188 / 1 | east 1 |
| el-cajon | 22m22s | 42m15s | 184 / 6 | east 6 |
| tijuana | 24m38s | 57m23s | 69 / 9 | east 6, south 3 |
| san-ysidro | 29m09s | 56m50s | 126 / 7 | east 7 |
| port-incoming | 29m11s | 56m52s | 137 / 7 | east 7 |

San Diego and El Cajon first reach Kumeyaay Highway/east; San Ysidro and the port lane first reach Carretera La Rumorosa–Tecate (Cuota)/east; Tijuana first reaches Carretera Tijuana–Ensenada (Cuota)/south. All selected 60-minute cases still reach potential cuts. At 120 minutes San Diego reaches **119** cut nodes (88 north, 26 east, 5 south); every origin reaches **137** by 12 hours. The changing number of clipped endpoints is not a percentage of geographic coverage. Zero reachable west cuts does not establish western/source completeness.

Cut inventory takes **55.57 s**, with **577,552 KiB worker / 1,745,215,488 bytes (1.63 GiB) cgroup**, zero OOM/kill/limit events and zero swap. It binds the final qualification manifest and rechecks every oracle witness.

## Remaining limits

Three Otay ways **114198251, 185333061, 577149752** remain explicitly source-marked as uncertain. Qualifying source permissions and finding legal-in-model witnesses do not verify current ordinary-car eligibility, queues, delays or document requirements. The forced uncertain branch keeps that warning visible even when sampled city routes avoid it. Mexico remains in coverage; there is no US-only clipping rule.

The interactive app still uses free hosted openrouteservice with a **60-minute driving cap**. This offline experiment adds no browser contour, long-range production engine, national index or Vercel deployment. Full 60-minute and original 10–12-hour coverage must be assessed from cuts, not assumed from graph size or fast search. National anchors/acquisition, analytical layers, elevation, road-distance semantics, caching and advanced routing remain deferred until model/coverage/storage gates are credible.

## Original next task (completed in the follow-up)

The resource work and preparation described below are now complete; see the [current findings and next build task](hour-coverage-preflight.md). This section preserves the original recommendations in context.

First reduce qualification memory before admitting more geography: the observed **3.74 GiB** qualification peak exceeds the 4 GiB cap once the chosen 25% margin is added. Import/export headroom does not establish oracle headroom. A versioned queue-based sink oracle with a virtual terminal can avoid copying every adjacency row and materializing a second flat arc list. Require exact agreement with the recorded independent flat-scan partial results on frozen and new graphs, including same-road/unreachable/turn-history cases; preserve the original oracle and all evidence. A per-file checksum/read-advice boundary after compact reload is another measured option, not a global cache drop.

Then preflight a focused **east/south buffer for complete 60-minute coverage in this static model**, while retaining and checking the northern/western margins. An initial hypothesis is `[-117.65,31.9,-116.0,33.6]`, entirely within the cached parent rectangle; it is neither prepared nor admitted. Choose the actual bounds from all reachable cut witnesses and add margin, not just from the single minimum endpoint. Keep Mexico and recheck every side and all five origins: expanded topology can change best routes. Parent gaps and source access uncertainty remain separate from clipping.

Require six preparation fixtures and exact current-region XML/census calibration, then fresh source/profile/checksum identities and a measured road/history census. Forecast against the largest observed complete-workload peak with 25% margin, including qualification resources separately from import/export. If that fails, improve a versioned per-file read/advice policy at stage boundaries or the independent sink-oracle storage before expanding. Prove frozen graph bytes and full/partial costs unchanged; retain failures and the cap. Do not assume the current resource admission permits another large jump. After admission, rerun independent routes/native comparisons/rebuild/all-cut checks. A credible complete hour is the next geographic milestone toward the still-unfinished 10–12-hour requirement.

Validation: **106 host Python cases (102 pass, four tool/platform skips)**, **15 scoped Linux cases (no skips)**, **14 adapter tests**, `npm run check`, `npm run typecheck`, `npm run build`, the new evidence analyzer and the prior sparse-resource analyzer pass. The lightweight Linux image lacks a C++ compiler, so compiler/kernel tests and native verification run on the Mac; no new full Linux discovery pass is claimed. Existing Biome database and upstream build warnings remain. All 118 preserved routing/lockfile/generated-route hashes match, `.env.local` remains ignored, no application/environment values changed, nothing is staged, and the existing Valhalla service remains healthy. Final free host disk is about 240 GiB; retained graph/source/rebuild/oracle artifacts are separate from the packed query graph.
