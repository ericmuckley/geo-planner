# Resume Geo Planner

Updated October 25, 2026 after the user reset the product priority to a coarse nationwide Vercel app. Completed detailed-engine measurements below remain preserved. This guide is sufficient to recover the task without the chat. Read [AGENTS.md](../AGENTS.md), then this page, [current status](implementation-status.md), [local setup](local-development.md) and [next steps](next-steps.md). The [two-hour report](two-hour-region.md) contains the detailed proof; older reports live in [the archive](archive/README.md) and describe their named historical runs.

## Where to resume

**V9 is qualified and active locally, uncommitted and not deployed.** It retains the 0.025° grid and changes generic travel costs: Natural Earth artificial connections use 55 km/h, secondary roads 85, major roads 105, Census connections/local travel 25. All rules apply everywhere; locations occur only in validation. Across 83 saved ORS development routes, mean absolute difference falls **34.612→29.257 min**; frontier missed reachable **5→2**,  false reachable **17→11**. All prospective gates pass. [Decision, complete ledger and limits](evidence/coarse-path-features-2026-10-24/README.md).

Gains are uneven: 59 routes improve/24 regress, frontier median worsens 37.254→40.561 min, and the older Valhalla sensitivity means worsen. This is an observed development comparison, not nationwide/area accuracy or a fresh holdout. Cell spacing is unchanged. Both earlier timing candidates remain rejected under their original frozen decisions. No new provider call, download, DB write, env/schema/dependency change, commit or deployment occurred. All 48/6/29 reference budgets are consumed.

**Checkout/deployment:** HEAD `37ff14b` remains unchanged. A fresh clone at that commit contains v8/min 30 slider and earlier 48 reference tools/results, not the new v9 runtime, later calibration/control/benchmark evidence or floating-map UI. All current work is local/uncommitted; no commit/push/deployment was performed. The two separate UI files retain the starting hashes in [start.json](evidence/coarse-path-features-2026-10-24/start.json). V8/slider through 9 b 3 e 83 b remain the last user-reported hosted model; public API does not expose Git SHA.

**Active artifact:** `src/server/data/coarse-grid-v9.json`,61,225,511 bytes, SHA `28271c809a04cdfab41ad735ad66b29e3875179b617198b7b1d4490533439bf6`. It differs from qualified candidateSHA `2904d0b7…` only in version. V8 remains byte-identical. Product configuration imports 9; npm checks target new v9 verifiers, preserving old sealed scripts. Full source/link/land/visit/physical checks,166 paths, independent repeat,56 server/43 Python/9 gate fixtures,42 API cases,175-file Biome/app+strict typechecks, both builds,15 local HTTP checks and browser qualification pass. Final function 65,047,708 bytes, first local compute 3,442.8 ms after config; retained decoded 158,046,458 bytes and bounded retention over 952,758 inputs. These are local timings/storage, not cloud cold-start/peak/load measurements. [Full proof/limitations](evidence/coarse-path-features-2026-10-24/README.md).

**Recovery/assets:** ignored `data/coarse-quality/connector-timing-candidate-v1/` and `connector-timing-candidate-repeat-v1/` contain grids/source proofs; `connector-timing-evaluation-v1/` all 83 comparisons/paths; `connector-preview-v1/` shared-camera review; `connector-package-v1/` isolated candidate build without env files. New frozen evidence is under `docs/evidence/coarse-path-features-2026-10-24/`. [Exact safe checks and source prerequisites](local-development.md#connector-timing-v9). Do not rerun completed producers/sweeps as health checks.

**Sources:** NE at `data/coarse-sources/natural-earth-v5.1.2/`; 49 Census partitions/289,239,748 bytes in `data/coarse-sources/tiger-2026/national-v1/`, pinned PyShp wheel in `data/coarse-tools/tiger-2026/`. V8 geometry prerequisites remain at `resolution-0025-base-v1/` / `resolution-0025-road-v1/`. Runtime needs none of these ignored assets. All older source/proof/evidence paths remain dependencies; preserve them.

**Preserved failed work:** [95/85 rejection](evidence/coarse-class-calibration-2026-10-23/README.md), [100/82 rejection](evidence/coarse-damped-calibration-2026-10-24/README.md), [six matched refs](evidence/coarse-control-reference-2026-10-24/README.md), [complete83 ORS benchmark](evidence/coarse-benchmark-reference-2026-10-24/README.md). No old producer, checksum record or threshold was edited. The new geometry features are descriptive; different chosen paths and repeated origins prevent causal/national claims.

**UI/history/env:** floating full-viewport controls in [index.tsx](../src/routes/index.tsx)/[research-map.tsx](../src/components/research-map.tsx) predate this timing work and remain byte-preserved. Existing slider 30–720/default 120 automatically computes on pointer/key release, with cancel/latest-result guards. Cloud `DATABASE_URL` stays in ignored `.env` and Vercel; `.env.local` has no DB override. Twenty summaries per private browser owner and local fallback remain unchanged; no DB writes/full integration rerun needed.

**Processes:** the transient final-package loopback preview used port 4184 with server outbound fetch disabled and DB unset; browser validation used a fresh local origin and public fixtures. Rediscover listeners and owners (`lsof -nP -iTCP:4184 -sTCP:LISTEN`, likewise 3000/8787) before reuse; never rely on old PIDs/tool sessions or stop another process. The transient adapter `/tmp/geo-connector-package-server.mjs` is QA-only, not production infrastructure. Final preview is stopped after QA; use normal `npm run dev` for continued work. No routing job or producer remains running.

**Next:** review/commit/deploy local v9 and floating UI, then run the new read-only hosted verifier and browser checks. [Ordered next steps](next-steps.md). No further routing budget is authorized; 48/6/29 are consumed. Detailed regional research remains parked, with 9.290 GiB six-hour partial-source screen against 4 GiB. [Preserved result](six-hour-preflight.md#memory-follow-up).

## Default coarse app

Start or reuse `http://127.0.0.1:3000/`. `npm run dev` is sufficient; no database, Python or Docker is required. Dependencies are already installed here. The browser still uses an online basemap. Safe readiness check:

```sh
curl --fail --silent --max-time 3 http://127.0.0.1:3000/api/estimate
```

Expect `provider: coarse`, `health: ready`, `engineVersion: coarse-road-grid-v9`, `minMinutes: 30`, `maxMinutes: 720`. The slider defaults to two hours; change/release it for automatic estimation, or use the optional compute button for coordinate edits. Connected-provider selection retains the old hosted/Valhalla path; openrouteservice remains capped at 60 m and spends quota only on computation. No hosted computation was made for the coarse milestone.

Earlier v1 saved-history milestone: **30 server tests and live DB integration pass; check/typecheck/ordinary build/Vercel-target build pass**. The local generated Vercel handler computes San Diego 6h, Denver 10h and New York 12h with zero routing fetches, keeps `/api/experiment` disabled, handles missing database configuration, and packages **5,581,861 bytes** without raw inputs, environment files or embedded DB/API-key values. Chrome verifies private cloud save/reload/model replay. [Saved-history evidence](evidence/saved-history-2026-10-22/README.md) records the new checks. The earlier [coarse milestone](evidence/coarse-estimator-2026-10-22/README.md) retains its 42 national in-process cases; the grid model/data were unchanged at that milestone. Current v8 validation is above; older milestones retain their original scope. These are software/local packaging checks; travel-time accuracy, all-origin completeness, cloud cold/warm behavior and peak memory remain unverified.

Raw Natural Earth downloads are cached at ignored `data/coarse-sources/natural-earth-v5.1.2/`; [regeneration commands](local-development.md#regenerate-the-coarse-grid) enforce pinned hashes. The active artifact at `src/server/data/coarse-grid-v9.json` and preserved v1–v8 JSON files are intentionally exempted from the broad `data/` rule in both Git and Vercel ignore files and must accompany a commit/deployment. Ignore-rule checks include these files while excluding raw downloads, evidence and environment files from Vercel uploads. Do not commit the raw downloads or secrets. The schema now contains `saved_histories` and the starter `todos`; PostgreSQL retains twenty summaries per private browser owner. Geometry is not stored. Inactive owners are not purged automatically, and there is no global owner-count cap or public-write rate limit yet.

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
| Qualified coverage | Five reference sources have zero detected cuts at 120 m; first cuts 128 m 05 s–135 m 20 s; six-hour cases clip |
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

Earlier recovery found **two different apps on port 3000**,  one on IPv 4 and another on IPv 6. Those listeners later disappeared; the documented launcher restored the qualified app/worker on October 22. Use **`127.0.0.1`**,  not an assumed `localhost` mapping. Do not stop the unrelated app. PIDs and tool-session IDs are not durable; discover owners again rather than reusing a PID from old logs.

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

At this handoff, **87 baseline evidence / 187 producer files** match. The [six-hour preflight evidence](evidence/six-hour-preflight-2026-10-19/README.md) also matches **79 evidence / 83 producer files**. The new [first-build handoff bundle](evidence/source-outgoing-build-2026-10-19/README.md) binds **28 evidence files / 151 combined build/profile producer files**,  and includes its own safe verification command. The [final calibration bundle](evidence/source-outgoing-2026-10-19/README.md) adds the exact repeat, completed result, fresh checks and next-phase analysis, with 152 combined producer bindings. Both builds’ eight payloads and the existing regional proof bindings were verified end to end. The checksum-only loop above covers all four bundles. These host checks do not rerun the expensive independent/native proofs or supply new capped resource measurements. Inspect future mismatches against authorized work; do not restore files blindly.

Preserved October 21 calibration validation: **20 adapter/server passes; 212 routing cases (203 pass, nine existing skips); check/typecheck/regular build pass**,  with the existing Biome database warning. The Vercel-target build was not repeated for these offline-only changes. Earlier milestone/preflight test counts and Vercel packaging results remain in their named reports. Fresh app/worker GET checks are ready on the same graph with zero provider calls; no new browser/search performance claim is made.

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

Native runtime prerequisites are already present: Python 3.13.5, Node 24.5.0, npm 11.6.0, Apple Clang 17 arm 64, matching compiled binary and local datasets. Future offline construction also needs Docker and the pinned cached images in the report. Node dependencies are installed; do not install/upgrade tools merely to resume. The host has 16 GiB RAM; about **167 GiB disk was free after the exact repeat**. Measure again before expansion. Fresh GET health/config both report ready, the qualified identity and zero provider calls; Docker has only the retained healthy Valhalla container, with no calibration batch running.

A fresh live validation, when justified, uses an unused output name and the actual app port:

```sh
node routing/verify-experiment.mjs --graph-run two-hour-region-v2 --run-name handoff-smoke-new --port 3000
```

This makes local requests only; do not reuse a completed run name. The verifier's no-flag default still targets the older graph, so the explicit flags matter. For a manual smoke, compute San Diego at 120 m: expect **0 / 805** reached edges and an unverified-coverage label. At 360 m expect **628** and an incomplete warning; Yuma can clip much earlier. Documentation writes can reload the development page and clear an in-progress result; pause writes during browser verification.

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

The completed owner-profile and source-outgoing build producers are also frozen. Each build manifest binds 149 scripts. The completed `source_outgoing_result.py` and final collector are now frozen too; they ran unchanged from their pending checkpoint versions. The final recipe index combines 152 producer files, including the result helper. Keep `scoped_load.py` and the named restriction policy. The first `two-hour-region-v1` graph and unversioned scoped verifier/cut wrapper preserve rejected or superseded attempts. **Do not edit sealed files, even for formatting**,  or overwrite graph/source/report bytes to bypass identity failures. Version a changed producer and bind all dependencies explicitly; a fresh output name alone does not rebind downstream hardcoded paths. Never manually edit `src/routeTree.gen.ts`, commit secrets, erase failed attempts or change the hosted environment to enable the experiment.

## Suggested resume message

> Continue Geo Planner from local qualified v9. Read AGENTS.md/current docs and docs/evidence/coarse-path-features-2026-10-24/README.md. HEAD `37ff14b` is unchanged; v9, later evidence/tools and floating UI are uncommitted/not deployed. All prospective gates pass: 83 ORS MAE 34.612→29.257, frontier false 17→11/missed 5→2; 59 improve/24 regress, frontier median and Valhalla means worsen. Geometry remains 0.025°; costs NE connector 55/secondary 85/major 105/Census/local 25 apply globally. Full source/path/repeat/memory/package/software/API/browser checks pass. Next review/commit/deploy then verify hosted v9 with scripts/verify-coarse-deployment-v9.ts; do not claim it live. No new env/DB/schema/dependency or provider request is needed/authorized. All 48/6/29 budgets are consumed. Preserve original failed candidates/gates and all sealed records, source assets, UI bytes and secrets. Rediscover listeners/owners; do not rerun completed producers/sweeps as readiness checks. Detailed research stays parked.
