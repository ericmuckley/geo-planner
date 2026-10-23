# Resume Geo Planner

Updated October 23, 2026 after the user reset the product priority to a coarse nationwide Vercel app. Completed detailed-engine measurements below remain preserved. This guide is sufficient to recover the task without the chat. Read [AGENTS.md](../AGENTS.md), then this page, [current status](implementation-status.md), [local setup](local-development.md) and [next steps](next-steps.md). The [two-hour report](two-hour-region.md) contains the detailed proof; older reports live in [the archive](archive/README.md) and describe their named historical runs.

## Where to resume

**V8 and the slider are committed through `9b3e83b` (`slider`), user-reported deployed.** A fresh clone contains the graph, slider and frozen plan. The bounded capture/replay helper, new offline path inspector, synthetic tests, measured reference run and documentation/evidence follow-up are **local/uncommitted**. Fifteen production HTTP checks pass for v8/min30 and fixed 6/10/12h counts; browser min30/default120/pointer/keyboard/loading/latest-result checks pass. An initial min60 response cleared on the subsequent observation; keep that failed check distinct. The public API does not expose the Git SHA, so deployed revision is user-reported rather than independently read from Vercel. No agent commit/push/deployment. [Latest evidence](evidence/coarse-frontier-tool-2026-10-23/README.md).

**UX committed and hosted:** one native time slider spans **30–720 minutes**, default **120**. Its human-readable value updates during drag, then pointer/key release computes automatically with a visible loading overlay/status. Blur commits pending keyboard changes once; pointer capture covers release outside the track. Existing abort/sequence checks keep the latest request authoritative. The manual compute button remains for coordinate edits/retry. Coarse config/server validation now accept 30 minutes; connected-provider limits remain separate. No graph/data/weights/env/schema change. [UX checks](evidence/time-slider-2026-10-23/checks.json), [local verification](local-development.md#time-slider).

**First nonregional reference run completed:** the user approved the exact 48-request / zero-paid-spend / no-retry budget. All 48 Directions requests succeed, every model/reference pair is finite, returned quota counters are consistent with 48 requests, and no snap exceeds 100m (maximum 79.63m). Mean absolute difference **52.273min**, median **37.254**, p90 **116.332**; mean signed (model minus reference) **−38.967min**. Cell classifications: **23 correct / 17 false reachable / five missed reachable / three ambiguous**. These are deliberately selected frontier point probes, not national or area accuracy. [Measured evidence](evidence/coarse-frontier-reference-2026-10-23/README.md), [comparison](evidence/coarse-frontier-reference-2026-10-23/comparison.json). The approved single-run budget is consumed; no extra live request/retry is authorized.

**Offline diagnosis:** new `scripts/inspect-coarse-frontier.ts` reconstructs all 48 paths through production transitions, verifies frozen point/cell costs and component sums, and makes no provider call. Road edges account for 98.64% of model time; endpoint attachments average 3.062min. The worst fast case uses mostly 105-tag base roads; the worst slow case mostly 80-tag roads. This supports a class-dependent timing experiment, not proof that a global speed change fixes geometry. Proposed next candidate: 105→95 and 80→85 km/h source classes everywhere, with 55/90 classes, fixed 25 km/h costs, geometry/topology and grid resolution retained. It has not been run or activated; its [predeclared gates](evidence/coarse-frontier-reference-2026-10-23/calibration-plan.json) require at least 10% frontier MAE reduction, nonincreasing p90, neither regional-set mean worsened and physical/runtime checks. These 48 observed routes are now development data. Code inspection confirms the optional connected adapter/mock tests already use the new HeiGIT host; the old migration todo was stale.

**Reference recovery:** complete credential-free capture is at `docs/evidence/coarse-frontier-reference-2026-10-23/reference/` and ignored `data/coarse-quality/coarse-frontier-reference-v1/`; saved report is the sibling `coarse-frontier-reference-v1-report.json`. Ignored `coarse-frontier-diagnostic-v1/` holds summary and compressed paths, also copied into the evidence report. Two offline replays match byte for byte; all capture/source/plan/path bindings and key-echo scan pass. Biome 153 files, app/strict diagnostic typechecks and ordinary build pass. The earlier 67-test tool/server result is preserved; no redundant server/DB/Vercel suite was rerun for the offline inspector. [Exact offline restore/replay commands](local-development.md#fixed-nonregional-frontier-plan).

Active v8: **61,208,381 bytes / SHA `2beb2fb6d9af6e07f37c5ba53acdeca2da1334c31a5fadd1371efd5453134910`**. Dimensions **2,360×1,040 = 2,454,400 cells**, 378,515 base links, 123,116 NE owner visits, 317,586 Census visits/states / 10,762,067 points, 346,821 Census-layer links, 10,936 mixed-shore representatives / 36,325 shore links. All masks/anchors/roads/visits/shores were rebuilt, not upsampled. Source classes/speeds, paid transfers and generalized-land checks remain the same rules everywhere. Named places enter validation only.

The raw finer model is 179,924,201 bytes; **lossless per-array gzip/base64** reduces it to 61,208,393 bytes / SHA `f5dd46f223fc4a6d601235adc4c59cb8a31326aa416c6fe0da522e34a14dbb5a`. Independent source/proof/packed repeats match exactly; active/repeat finalization changes only version. The server inflates arrays with built-in Node zlib, retains packed visits without a growing query cache, validates every visit/transfer and reuses aligned native word buffers with an endian/alignment fallback. V1–v7 and all dated evidence remain unchanged.

**Accuracy:** all 35 saved regional/static development trips remain finite/reached/shaded; **29 improve and six worsen versus v7**, worst +3.180 min. Original mean absolute reference difference **11.579→10.288 min**, broader **17.211→12.011 min**. All path sums reconstruct and every regression/component delta is recorded. These reused references do not establish national, fresh-holdout or 6–12h frontier accuracy. One position per layer, merged crossings, assumed overland travel, source gaps, generalized coastlines and traffic/turn/terrain/access/ferry/border limits remain. Cell size is not an accuracy bound.

**Runtime/checks:** full 378,515 base-link / 36,325 shore proofs, all 346,821 new road links / 317,586 transfers, full visit validation, independent repeats and 42 candidate/active API cases pass. A fixed **0.01° latitude index** uses compact band views and a retained flat ring list; exact membership/crossing arithmetic is unchanged. Native word views and direct dense-array validation remove load allocations. All 35 comparisons and 42 counts remain exact through optimization. Three fresh candidate package computations after config take **3,592.4 / 3,597.6 / 3,657.7 ms**. Final v8 function **65,022,874 bytes / 28 files**, first local compute **3,621.4 ms**, then **382.7 / 304.6 ms**, zero outbound calls. These exclude earlier module/config load and do not measure cloud cold starts, peak memory, concurrency or load capacity.

Retained decoded heap+buffers **158,044,242 bytes**, parsed encoded input retained separately. Three sweeps total **952,758 inputs**; post-GC growth at most **98,896 heap bytes / zero buffers**. The fixed finer index increased load heap to 3,862,960 bytes: diagnostic load allowance is explicitly 4 MiB (old 2 MiB attempt failed), while post-load query-growth guards remain 2 MiB heap / 64 KiB buffers. Earlier failed/marginal timing stages, load-guard failure and test error-message mismatch are preserved. **56 server tests, nineteen Python fixtures, check (148 files), app/diagnostic typechecks, both builds and local handler pass.** Browser review covers twelve paired maps and main-app public 6/10/12h fixtures with cloud save/reload/replay; see exact evidence scope.

**Local assets:** `data/coarse-quality/resolution-0025-base-v1/` and `-repeat/` hold raw base grids/proofs; `resolution-0025-road-v1/` and `-repeat/` hold additive road-state grids/proofs. Evaluation, packed outputs, finalization/repeats, profiles, intermediate/final package probes and previews are in `data/coarse-quality/resolution-0025-evaluation-v1/`; final qualified candidate package is `package-probe-direct-arrays/`. [Exact recovery commands](local-development.md#finer-resolution-v8). New paired page **http://127.0.0.1:4178/preview/**; main app **http://127.0.0.1:3000/**. Rediscover listeners/owners, never old PIDs/tool sessions. Preserve v7 source/evaluation/preview directories and v6/failed previews described in their linked reports.

Census ZIPs/locks/catalog remain in ignored `data/coarse-sources/tiger-2026/` (`national-v1/`, 49 sources / 289,239,748 bytes); NE countries/lakes/roads in `data/coarse-sources/natural-earth-v5.1.2/`; pinned PyShp wheel under `data/coarse-tools/tiger-2026/`. Runtime needs none of these raw sources or Python. No source download, env/dependency/DB migration or detailed build occurred. The separate approved reference run above used 48 provider requests; earlier v8 graph-building evidence used none. [Source recovery](local-development.md#nationwide-census-candidate). Do not rerun completed producers/sweeps as health checks.

**Cloud history:** preserve server-only `DATABASE_URL` in ignored `.env` and Vercel; `.env.local` retains routing settings without a DB override. Reviewed initial migration remains applied. Twenty summaries per private HttpOnly browser owner, local fallback, no geometry/accounts/cross-device sync. Only public fixture history is inspected; unchanged full DB integration is not rerun. [API](local-development.md#saved-history-api).

**Next:** implement/evaluate the separate generic class-timing candidate against all 48 saved frontier and 35 prior regional development routes; preserve v8 and all sealed producers/evidence. Do not reacquire references or rerun completed graph producers as readiness checks. The hosted save/reload write was not repeated after automatic approval review rejected Save query; unchanged persistence does not need a full DB suite. Detailed research remains parked: eight calibrated payloads match, peaks 2.415/2.416 GiB, six-hour partial-source forecast 9.290 GiB versus 4 GiB remains held. [Preserved result](six-hour-preflight.md#memory-follow-up).

## Default coarse app

Start or reuse `http://127.0.0.1:3000/`. `npm run dev` is sufficient; no database, Python or Docker is required. Dependencies are already installed here. The browser still uses an online basemap. Safe readiness check:

```sh
curl --fail --silent --max-time 3 http://127.0.0.1:3000/api/estimate
```

Expect `provider: coarse`, `health: ready`, `engineVersion: coarse-road-grid-v8`, `minMinutes: 30`, `maxMinutes: 720`. The slider defaults to two hours; change/release it for automatic estimation, or use the optional compute button for coordinate edits. Connected-provider selection retains the old hosted/Valhalla path; openrouteservice remains capped at 60m and spends quota only on computation. No hosted computation was made for the coarse milestone.

Earlier v1 saved-history milestone: **30 server tests and live DB integration pass; check/typecheck/ordinary build/Vercel-target build pass**. The local generated Vercel handler computes San Diego 6h, Denver 10h and New York 12h with zero routing fetches, keeps `/api/experiment` disabled, handles missing database configuration, and packages **5,581,861 bytes** without raw inputs, environment files or embedded DB/API-key values. Chrome verifies private cloud save/reload/model replay. [Saved-history evidence](evidence/saved-history-2026-10-22/README.md) records the new checks. The earlier [coarse milestone](evidence/coarse-estimator-2026-10-22/README.md) retains its 42 national in-process cases; the grid model/data were unchanged at that milestone. Current v8 validation is above; older milestones retain their original scope. These are software/local packaging checks; travel-time accuracy, all-origin completeness, cloud cold/warm behavior and peak memory remain unverified.

Raw Natural Earth downloads are cached at ignored `data/coarse-sources/natural-earth-v5.1.2/`; [regeneration commands](local-development.md#regenerate-the-coarse-grid) enforce pinned hashes. The active artifact at `src/server/data/coarse-grid-v8.json` and preserved v1–v7 JSON files are intentionally exempted from the broad `data/` rule in both Git and Vercel ignore files and must accompany a commit/deployment. Ignore-rule checks include these files while excluding raw downloads, evidence and environment files from Vercel uploads. Do not commit the raw downloads or secrets. The schema now contains `saved_histories` and the starter `todos`; PostgreSQL retains twenty summaries per private browser owner. Geometry is not stored. Inactive owners are not purged automatically, and there is no global owner-count cap or public-write rate limit yet.

## Preserved detailed baseline

| Item | Value |
| --- | --- |
| App | `http://127.0.0.1:3000/experiment` when the existing server is live; use Vite's printed port after restarting |
| Worker | `http://127.0.0.1:8787`, loopback only |
| Graph / cuts | `two-hour-region-v2` / `two-hour-region-v2-cuts` under `data/compact-pilot/` |
| Graph identity | `52b34545379adf83ad09175e7d29b5c445b7cf4193fee0f9b5d10afe0904fda1` |
| Bounds | `[-118.2,31.5,-114.6,34.7]`, west/south/east/north |
| Graph | 8,136,898 states; `exploratory-static-car-v3` plus **`member-scoped-geometry-v1`** |
| UI default / accepted range | 120 minutes / 1–720 whole minutes; range acceptance is not geographic coverage |
| Qualified coverage | Five reference sources have zero detected cuts at 120m; first cuts 128m05s–135m20s; six-hour cases clip |
| Output | Sampled reachable roads, not a filled experimental isochrone; all-origin/source completeness and real border access unverified |

The optional connected model uses the separate provider path, capped at 60 minutes for hosted driving. Its key is already configured locally. The default coarse estimator and offline experiments must not call it or use hosted fallback. Basemap tiles use the network independently.

## Detailed-engine read-only recovery checks

From the repo root:

```sh
git status --short
git branch --show-current
lsof -nP -iTCP:8787 -sTCP:LISTEN
lsof -nP -iTCP:3000 -sTCP:LISTEN
curl --fail --silent --max-time 3 http://127.0.0.1:8787/health
curl --fail --silent --max-time 3 http://127.0.0.1:3000/api/experiment
```

Both JSON responses should report `ready: true`, the full graph identity above, the same bounds, `maxMinutes: 720` and `publicApiCalls: 0`. GET health/config spends no routing quota. A 503 can mean the worker is loading, the app was launched without the local opt-in, or the local API is disabled on Vercel; inspect the matching terminal/process before restarting.

Earlier recovery found **two different apps on port 3000**, one on IPv4 and another on IPv6. Those listeners later disappeared; the documented launcher restored the qualified app/worker on October 22. Use **`127.0.0.1`**, not an assumed `localhost` mapping. Do not stop the unrelated app. PIDs and tool-session IDs are not durable; discover owners again rather than reusing a PID from old logs.

Verify saved evidence and current producer files without recomputation:

```sh
python3 -B - <<'PYTHON'
import hashlib, json
from pathlib import Path
for directory, recipe in [('two-hour-region-2026-10-19', 'final-recipe-sha256.json'),
                          ('six-hour-preflight-2026-10-19', 'recipe-sha256.json'),
                          ('source-outgoing-build-2026-10-19', 'recipe-sha256.json'),
                          ('source-outgoing-2026-10-19', 'recipe-sha256.json')]:
    evidence = Path('docs/evidence') / directory
    for filename, root in [('evidence-sha256.json', evidence), (recipe, Path('.'))]:
        expected = json.loads((evidence / filename).read_text())
        for name, checksum in expected.items():
            with (root / name).open('rb') as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == checksum, name
        print(directory, filename, len(expected), 'files match')
PYTHON
```

At this handoff, **87 baseline evidence / 187 producer files** match. The [six-hour preflight evidence](evidence/six-hour-preflight-2026-10-19/README.md) also matches **79 evidence / 83 producer files**. The new [first-build handoff bundle](evidence/source-outgoing-build-2026-10-19/README.md) binds **28 evidence files / 151 combined build/profile producer files**, and includes its own safe verification command. The [final calibration bundle](evidence/source-outgoing-2026-10-19/README.md) adds the exact repeat, completed result, fresh checks and next-phase analysis, with 152 combined producer bindings. Both builds’ eight payloads and the existing regional proof bindings were verified end to end. The checksum-only loop above covers all four bundles. These host checks do not rerun the expensive independent/native proofs or supply new capped resource measurements. Inspect future mismatches against authorized work; do not restore files blindly.

Preserved October 21 calibration validation: **20 adapter/server passes; 212 routing cases (203 pass, nine existing skips); check/typecheck/regular build pass**, with the existing Biome database warning. The Vercel-target build was not repeated for these offline-only changes. Earlier milestone/preflight test counts and Vercel packaging results remain in their named reports. Fresh app/worker GET checks are ready on the same graph with zero provider calls; no new browser/search performance claim is made.

Historical reports moved into `docs/archive/`; evidence paths and checksum-bound indexes stay fixed, with four top-level forwarding pages preserving their links. Frozen diagnostics can still use former report paths; locate their basenames in the archive. The earlier [handoff audit](evidence/handoff-audit-2026-10-19/README.md) remains historical. Current link/anchor and diff checks pass; detailed-engine logs are in the final calibration bundle; current app logs are in the saved-history evidence. Preserve sealed evidence and all local-only assets.

## Start or recover the detailed experiment

If the correct app/worker are live, reuse them. Otherwise, after checking for an already-loading worker:

```sh
npm run dev:experiment
```

This starts/reuses the qualified worker, checks graph identity and starts the app with `LOCAL_ROUTING_EXPERIMENT=1` only in its child process. It preserves environment files. Graph verification/reload/indexing takes about two minutes on this Mac; do not launch duplicate workers while it loads. Use Vite's printed port if 3000 is occupied. A mismatched worker causes a clear rejection, not automatic replacement. The launcher stops only children it created; a worker it reused stays alive after Ctrl+C.

If only the worker is missing while the intended opt-in app is already running, start the worker in its own terminal:

```sh
python3 -B routing/experiment.py --graph-run two-hour-region-v2 --cuts-run two-hour-region-v2-cuts --port 8787
```

To switch graphs, identify and stop only the owned worker (prefer its terminal's Ctrl+C), then use the matching graph/cut pair. Previous baseline:

```sh
npm run dev:experiment -- --graph-run experiment-region-v1 --cuts-run experiment-region-v1-cuts
```

Native runtime prerequisites are already present: Python 3.13.5, Node 24.5.0, npm 11.6.0, Apple Clang 17 arm64, matching compiled binary and local datasets. Future offline construction also needs Docker and the pinned cached images in the report. Node dependencies are installed; do not install/upgrade tools merely to resume. The host has 16 GiB RAM; about **167 GiB disk was free after the exact repeat**. Measure again before expansion. Fresh GET health/config both report ready, the qualified identity and zero provider calls; Docker has only the retained healthy Valhalla container, with no calibration batch running.

A fresh live validation, when justified, uses an unused output name and the actual app port:

```sh
node routing/verify-experiment.mjs --graph-run two-hour-region-v2 --run-name handoff-smoke-new --port 3000
```

This makes local requests only; do not reuse a completed run name. The verifier's no-flag default still targets the older graph, so the explicit flags matter. For a manual smoke, compute San Diego at 120m: expect **0 / 805** reached edges and an unverified-coverage label. At 360m expect **628** and an incomplete warning; Yuma can clip much earlier. Documentation writes can reload the development page and clear an in-progress result; pause writes during browser verification.

## Local assets and frozen recipes

| Directory | Role |
| --- | --- |
| `data/resource-pilot/two-hour-base-owners-v1` | Completed bounded owner diagnostic and frozen profile snapshot |
| `data/compact-pilot/source-outgoing-v1` | Completed first storage calibration: eight identical payloads, manifest/report, recipe snapshot and supplemental fixtures |
| `data/resource-pilot/source-outgoing-validation-v1` | Completed `result.json`, fresh checks/health, next-phase analysis, mutable `active-work.json` and final evidence collector |
| `data/compact-pilot/source-outgoing-v1-rebuild` | Completed exact repeat: eight identical payloads, 2.416 GiB / 1,555.84 s, manifest/report and fixtures |
| `data/coverage-pilot/six-hour-plan-v1`, `six-hour-catalog-v2`, `six-hour-checksums-v1` | Unclipped six-hour plan, official current footprints/listings and partial publisher-checksum observations |
| `data/source-pilot/six-hour-cached-v1`, `data/coverage-pilot/six-hour-cached-v1` | Completed cached-source merge and partial census/admission hold; preserve reports and recipe snapshots |
| `data/coverage-pilot/six-hour-validation-v1` | New tests/build/check logs, resource analysis and evidence collector |
| `data/compact-pilot/two-hour-region-v2` | Current graph/CSR/native binary, summary, oracles, manifest, native proof, release and two-hour acceptance |
| `data/compact-pilot/two-hour-region-v2-rebuild` | Independent exact rebuild |
| `data/compact-pilot/two-hour-region-v2-cuts` | Complete source-linked `cut-nodes.json` / report; next preflight input |
| `data/coverage-pilot/two-hour-region-v2` | Prepared OSM XML/census/resource report |
| `data/source-pilot/two-hour-parent-v2` | Merged parent source/report with Arizona |
| `data/compact-pilot/scoped-current-v1` | Scoped restriction-policy calibration against the previous routing payload |
| `data/experiment-pilot/two-hour-map-v2`, `data/experiment-pilot/two-hour-areas-v2` | Raw live API responses/reports |
| `data/experiment-pilot/two-hour-region-v1` | Planning/acquisition/run logs and helpers; the `v1` name here does not mean the rejected graph |
| `data/valhalla/sources`, `data/valhalla-v2` | Dated road inputs, retained prior parent/source/admin products and Valhalla baseline |

Earlier frozen references under `data/` are still dependencies. Preserve the whole existing data/proof chain; the table is not a standalone export manifest. The current builder/reader image IDs are pinned in the report and were confirmed cached during this audit.

The accepted recipe sequence is `two-hour-source-v2.mjs` → `two-hour-region-prepare-v2.mjs` → `scoped-region.mjs` → **`scoped-region-verify-v3.mjs`** (bootstrap plus v2 field verifier) → `scoped_native.py` → **`scoped-region-cuts-v2.mjs`** → `two_hour_release.py`. Calibration prerequisites and exact commands are in the report. These completed producers, native/release checks and the evidence collector **refuse overwrite or create outputs**; do not rerun them as health checks.

The completed owner-profile and source-outgoing build producers are also frozen. Each build manifest binds 149 scripts. The completed `source_outgoing_result.py` and final collector are now frozen too; they ran unchanged from their pending checkpoint versions. The final recipe index combines 152 producer files, including the result helper. Keep `scoped_load.py` and the named restriction policy. The first `two-hour-region-v1` graph and unversioned scoped verifier/cut wrapper preserve rejected or superseded attempts. **Do not edit sealed files, even for formatting**, or overwrite graph/source/report bytes to bypass identity failures. Version a changed producer and bind all dependencies explicitly; a fresh output name alone does not rebind downstream hardcoded paths. Never manually edit `src/routeTree.gen.ts`, commit secrets, erase failed attempts or change the hosted environment to enable the experiment.

## Suggested resume message

> Continue Geo Planner. Read AGENTS.md and current docs. V8 is committed at ee8809f (message v7), including both data artifacts; graph hash remains 2beb2fb6d9af6e07f37c5ba53acdeca2da1334c31a5fadd1371efd5453134910. Current local/uncommitted UX uses a 30–720-minute slider, default120, automatic release/key updates with loading and latest-request cancellation; optional compute handles coordinates/retries. API min30 and boundary/unit/build/handler/browser checks pass, without graph/env/DB changes. Live public config confirms v8 min60, not new UX or exact revision; publish then verify min30. Frozen 48-query frontier plan spans eight public nonregional origins and 6/10/12h inside/outside pairs; independent offline repeats match, no new reference/provider quota or key read. Implement bounded capture/replay and obtain explicit quota authorization before calls. Provider plan/terms/new api.heigit.org prefix checked; old connected host retires Nov2–6, migration remains a focused follow-up. V8 measured 29 improvements/six regressions on 35 regional development routes, not national accuracy. Preserve sealed evidence and raw/failed sources; no producer/sweep rerun is needed. Rediscover local port3000/4178 owners; do not rely on old PIDs. Detailed research remains parked.
