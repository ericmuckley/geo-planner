# Resume Geo Planner

Updated October 23, 2026 after the user reset the product priority to a coarse nationwide Vercel app. Completed detailed-engine measurements below remain preserved. This guide is sufficient to recover the task without the chat. Read [AGENTS.md](../AGENTS.md), then this page, [current status](implementation-status.md), [local setup](local-development.md) and [next steps](next-steps.md). The [two-hour report](two-hour-region.md) contains the detailed proof; older reports live in [the archive](archive/README.md) and describe their named historical runs.

## Where to resume

**V6 is active locally, with a genuinely rebuilt 0.05° grid (about 3.5–5.5 km cells).** The user authorized the finer-resolution work after reporting little visible v5 improvement. Same rules apply to arbitrary contiguous-US land queries at 60–720 whole minutes; validation places never become runtime exceptions. [V6 evidence / side-by-side maps](evidence/coarse-resolution-2026-10-23/README.md), [model](coarse-estimator.md), [next steps](next-steps.md).

Active `src/server/data/coarse-grid-v6.json`: **68,129,975 bytes / SHA-256 `a1ba5ae3eb7419feb458641f00da1886802fc16ec11af86e3d61d42a3b8b3f99`**. The source-built 0.05° candidate/repeat are **68,129,988 bytes / SHA `b3e65e43e4377f98c7bd21cc7e458f09f9a7ade78ef8d100b345dd1c14c686df`**; finalization changes only the version field, with exact active repeat and all graph/source/notice fields identical. Dimensions 1,180×520 = 613,600 cells, 168,149 links, 58,773 NE owners, 135,128 Census visits / 8,678,176 points, 4,455 mixed-shore representatives and 13,597 shore links. V1–v5 and original/failed evidence are preserved. New Git/Vercel exception and Biome exclusion include v6; **include the new artifact when committing**.

**Accuracy tradeoff:** all 35 saved development queries remain finite/reached/shaded; 26 improve and nine regress versus v5. Original mean absolute reference difference 21.944→14.712 min (33.0% lower), broader mean 31.204→23.615 min (24.3% lower). Worst regression +7.092 min; all nine path-component changes and every path sum are recorded. These reused regional/static references do not qualify national/6–12h frontier accuracy. Source gaps, cell mergers, assumed overland travel, fixed-anchor/one-supplemental-visit transfers and terrain/traffic/turn/access limits remain. NE legacy transfer costs retain class speed; Census transfers and shores retain strict continuous-land checks at 25 km/h.

**Runtime/verification:** generic conservative longitude bounds/east-ordered edge bands and early shared-country exit preserve exact geometry decisions and all full visit checks. All 35 costs/paths and 42 counts are unchanged by this optimization. Three fresh local candidate package runs: **3,057.8 / 3,108.7 / 3,121.1 ms** first computation after config (earlier 6.40–6.92s). Final active handler **71,940,272 bytes / 28 files**, first compute 3,092.3ms then 64.1/52.9ms, zero outbound calls. These exclude prior module/config loading and are not cloud cold starts. Incremental retained decoded heap+buffers **57,296,637 bytes**; 405,384 on-land inputs add at most 118,800 heap bytes/no buffers after GC. Offline producer's 2.10GB peak is a separate scope. 51 server tests, nineteen Python fixtures, check (143 files), app/diagnostic typechecks, both builds, physical/shore proofs and 42 active API cases pass.

Local Chrome verifies twelve paired inland/rural/coastal/mountain scenarios at 6/10/12h, synchronized zoom and smaller visible boundary steps. Main-app inland 6h/rural 10h/coastal 12h plus new fixture Cloud saved→reload→Replay pass; only public fixture history is inspected. No full live DB integration suite was repeated because persistence is unchanged. No env variable, migration, dependency, routing reference/provider quota, detailed producer, commit or deployment was needed/performed.

**Git/production:** observed HEAD `08074fb` contains v5. Production is user-reported v5, with independent hosted proof still scoped to v4. New v6 runtime/data/tools/evidence/docs are **uncommitted**, alongside the earlier priority-doc edits. A fresh clone currently contains v5. Separate package/lock/root-layout Speed Insights and favicon edits appeared during this work and were preserved; include their ownership in review rather than reverting them. Final active builds include that workspace state. Do not reset/clean local work. Next: review/publish through the existing user-managed workflow, then verify actual v6 revision/HTTP/browser behavior. Updated hosted verifier now expects v6 and intentionally fails against old v5; do not run it just for docs.

**Local assets/recovery:** accepted source run `data/coarse-quality/resolution-005-v2/` contains grid, build report, compressed link proofs and isolated package probes (`package-probe-indexed/` is final runtime). First `resolution-005-v1/` grid/proofs are identical but its reporting wrapper failed; preserve it. `data/coarse-quality/resolution-evaluation-v1/` contains comparisons, paths, before/after profiles/memory/handler runs, finalization repeats and visual previews. `preview/` preserves the first marker bug; `preview-v2/` is corrected. A loopback comparison server was started at **http://127.0.0.1:4176/preview-v2/** and Vite at **http://127.0.0.1:3000/**; rediscover owners/listeners on resume rather than old PIDs/tool sessions. [Exact commands](local-development.md#finer-resolution-v6).

The 49 Census ZIPs/locks remain under ignored `data/coarse-sources/tiger-2026/`, catalog/manifest in `national-v1/`, 289,239,748 pinned bytes. NE countries/lakes/roads remain under `data/coarse-sources/natural-earth-v5.1.2/`; PyShp wheel/lock under `data/coarse-tools/tiger-2026/`. Existing national-v2/pilot/rejected/compatibility outputs remain untouched. Normal runtime needs none of these raw sources, Python or a DB; do not rerun producers/acquisition to check documentation. [Source recovery](local-development.md#nationwide-census-candidate).

**Cloud history:** preserve server-only `DATABASE_URL` in ignored `.env` and Vercel; `.env.local` retains routing settings without a DB override. Reviewed initial migration is applied. Twenty summaries per browser-private HttpOnly owner, local fallback, no geometry/accounts/cross-device sync. [API](local-development.md#saved-history-api).

**Detailed research stays parked.** Two-hour regional baseline/outgoing-index calibration remain preserved: eight payloads match, peaks 2.415/2.416 GiB, partial-source six-hour forecast 9.290 GiB with margin versus 4 GiB remains held. Do not resume memory profiling/graph expansion or spend provider quota automatically. [Preserved result](six-hour-preflight.md#memory-follow-up). No 0.025° candidate has been built.

## Default coarse app

Start or reuse `http://127.0.0.1:3000/`. `npm run dev` is sufficient; no database, Python or Docker is required. Dependencies are already installed here. The browser still uses an online basemap. Safe readiness check:

```sh
curl --fail --silent --max-time 3 http://127.0.0.1:3000/api/estimate
```

Expect `provider: coarse`, `health: ready`, `engineVersion: coarse-road-grid-v6`, `minMinutes: 60`, `maxMinutes: 720`. Compute San Diego at six hours or use the ten-/twelve-hour presets. Connected-provider selection retains the old hosted/Valhalla path; openrouteservice remains capped at 60m and spends quota only on computation. No hosted computation was made for the coarse milestone.

Earlier v1 saved-history milestone: **30 server tests and live DB integration pass; check/typecheck/ordinary build/Vercel-target build pass**. The local generated Vercel handler computes San Diego 6h, Denver 10h and New York 12h with zero routing fetches, keeps `/api/experiment` disabled, handles missing database configuration, and packages **5,581,861 bytes** without raw inputs, environment files or embedded DB/API-key values. Chrome verifies private cloud save/reload/model replay. [Saved-history evidence](evidence/saved-history-2026-10-22/README.md) records the new checks. The earlier [coarse milestone](evidence/coarse-estimator-2026-10-22/README.md) retains its 42 national in-process cases; the grid model/data were unchanged at that milestone. Current v6 validation is above; older milestones retain their original scope. These are software/local packaging checks; travel-time accuracy, all-origin completeness, cloud cold/warm behavior and peak memory remain unverified.

Raw Natural Earth downloads are cached at ignored `data/coarse-sources/natural-earth-v5.1.2/`; [regeneration commands](local-development.md#regenerate-the-coarse-grid) enforce pinned hashes. The active artifact at `src/server/data/coarse-grid-v6.json` and preserved v1–v5 JSON files are intentionally exempted from the broad `data/` rule in both Git and Vercel ignore files and must accompany a commit/deployment. Ignore-rule checks include these files while excluding raw downloads, evidence and environment files from Vercel uploads. Do not commit the raw downloads or secrets. The schema now contains `saved_histories` and the starter `todos`; PostgreSQL retains twenty summaries per private browser owner. Geometry is not stored. Inactive owners are not purged automatically, and there is no global owner-count cap or public-write rate limit yet.

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

> Continue Geo Planner. Read AGENTS.md and current docs. V6 is active locally at 0.05°/3.5–5.5 km cells; HEAD/user-reported production remain v5 at 08074fb. New v6 code/data/tools/evidence/docs are uncommitted. Include src/server/data/coarse-grid-v6.json (68,129,975 bytes / SHA a1ba5ae3eb7419feb458641f00da1886802fc16ec11af86e3d61d42a3b8b3f99) when publishing. Independent source-built candidate/repeat at data/coarse-quality/resolution-005-v2 and -v1 match; only final version differs. All 35 saved reference queries remain reached/shaded; 26 improve, nine regress by at most 7.092 min. Mean errors drop 33.0%/24.3% on the two development sets; no national accuracy claim. Shared geometry indexing preserves all decisions and brings first local package computation to 3.06–3.12s; final function 71,940,272 bytes/28 files, zero fetches. Memory bounded over 405,384 inputs; 51 server tests/19 geometry fixtures/42 API cases/check/typechecks/both builds/handler/UI/cloud fixture replay pass. Comparison page http://127.0.0.1:4176/preview-v2/ and local app 3000 were started; rediscover listeners. Next publish via existing workflow and verify actual v6, then refine generic remaining transfer/access errors. Updated hosted verifier expects v6, so old live v5 intentionally fails. Preserve all old/failed/source artifacts and credentials. No new env/migration/dependency, fresh references/quota or detailed research work is needed. 0.025° remains unbuilt.
