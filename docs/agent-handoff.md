# Resume Geo Planner

Updated October 22, 2026 after the user reset the product priority to a coarse nationwide Vercel app. Completed detailed-engine measurements below remain preserved. This guide is sufficient to recover the task without the chat. Read [AGENTS.md](../AGENTS.md), then this page, [current status](implementation-status.md), [local setup](local-development.md) and [next steps](next-steps.md). The [two-hour report](two-hour-region.md) contains the detailed proof; older reports live in [the archive](archive/README.md) and describe their named historical runs.

## Where to resume

**The first coarse nationwide slice is implemented.** The main page `/` defaults to a six-hour road-informed grid estimate with 6/10/12h presets, filled contours, approximation warnings, timings, browser-local history and export. `/api/estimate` runs in the existing TypeScript server without a database, worker, API key or routing-service fetch. The active compact 4.67 MB v3 grid is included in source. [The model report](coarse-estimator.md) explains generalized Natural Earth sources, assumed speeds, 7–11 km display cells, shoreline tolerance and uncalibrated accuracy.

**Saved-query persistence is implemented.** Cloud PostgreSQL is configured in Vercel (user-reported) and ignored local `.env`; `.env.local` retains only routing settings. The reviewed additive `drizzle/0000_saved_history.sql` migration is applied to the initially empty cloud database. New queries/runs back up automatically, older browser history uploads only through the backup button, and model-aware Load/Replay works. The private HttpOnly cookie scopes each browser's twenty summaries; no global list or cross-device sign-in exists. Local saving/export remain usable without the database. [API, ownership and commands](local-development.md#saved-history-api).

**Deployment/quality update:** the user reports that the Vercel-hosted app works, while calling the output rudimentary and inaccurate. Its URL and deployed revision have been requested; independent hosted verification and resource measurements remain pending. The estimator/cloud-history implementation is now committed at `0ffd6c8`; this quality follow-up is uncommitted.

**V2 correction implemented locally:** the app now serves `coarse-road-grid-v2`, using retained road geometry, consistent per-cell road positions, charged transfers and revised explicit class speeds (55–105 km/h; local access remains 25). Road-supported display cells fix the Calexico gap without adding general water travel. Across eleven preserved regional routes, mean cell-arrival difference falls from 42.4m to 20.3m, all improving; with approximate destination access added to both it falls from 51.5m to 31.4m. Geometry alone at original speeds has little aggregate gain (42.4m → 41.4m). This sample informed the speed assumptions, so it is not held-out or national accuracy validation. [V2 model and caveats](coarse-estimator.md#v2-cost-correction-and-border-shading), [new evidence](evidence/coarse-v2-2026-10-22/README.md).

**Verification:** 33 server tests, three Python geometry tests, 42 national smoke cases, Biome, typecheck and ordinary/Vercel builds pass. The 4,460,777-byte artifact reproduces exactly; the generated function is 8,242,734 bytes and runs three representative queries with zero outbound fetches. Server-only packaging, detailed-route disablement and database-free history fallback pass. The geometry tests include a physical lower bound for all 33,398 road links. Browser observations are in the new evidence. Live PostgreSQL write tests were not repeated because database code is unchanged; their earlier milestone remains preserved.

**Broader validation complete:** a fixed 24-route set from twelve new origins was captured with v2 unchanged. All local static references succeed. Both grids reach 23/24 destination cells; cell mean difference changes 44.7m → 27.3m (19 improve), and approximate point mean changes 53.0m → 37.7m (18 improve, five regress), on paired finite cases only. Four of five mountain cases worsen. Salton City → Bombay Beach is unreached in both models; the destination's lake-center cell is enabled only when it is the origin. Reference snap is within 9 m. Big Bear has no generalized road links in its cell/eight neighbors. [Plan, raw responses, diagnostics and proof](evidence/coarse-regional-2026-10-22/README.md). No v2 product/model change was made during this validation; one status plus 24 loopback routes, zero hosted routing calls. Safe replay: `npm run routing:compare:coarse:regional`. Check, app typecheck, explicit strict diagnostic typecheck and ordinary build pass. Vercel/database/browser checks were not repeated for offline diagnostics.

**V3 general shore correction is implemented locally:** runtime now serves `coarse-road-grid-v3`, with the same v2 land mask, existing road anchors, weights and speeds. Generic geometry checks add 1,535 mixed shore representatives and 4,599 bidirectional local links. A further 245 source-derived road access points preserve explicit bridge/tunnel access; all supported fallback attachments seed the query. Input access may use up to 1 km of water only at its input end, never ignore later channels, and unconnected islands stay isolated. No city-name, example-coordinate or regional exceptions are allowed; that user requirement is now durable in AGENTS.md.

The original eleven point costs stay unchanged. Across the same 23 common-finite regional cases, mean difference improves 37.730m → 36.893m: two improve, none regress. The formerly missing 24th shore destination is reached/shaded at 6h/12h, with symmetric point cost 146.0m versus the static reference’s 61.3m. Accuracy remains poor there; membership is fixed, missing roads are not. Rejected land-only and greedy attachment attempts are preserved because they stranded New York/Key West. The final generic road-access/multiple-seed fix restores those origins. [V3 model](coarse-estimator.md#v3-general-shore-connectivity), [evidence](evidence/coarse-v3-2026-10-22/README.md).

Fresh verification: **39 server tests, six Python geometry tests, 42 national smoke cases, check, app/diagnostic typecheck and ordinary/Vercel builds pass**. All new shore links and road-access physical bounds are tested. The artifact reproduces at 4,673,811 bytes / SHA-256 `8cfa5616b52138c16d5a8cb8f84fd1ee4345f7e4026e88c104365cad25c523e0`; the generated Vercel function is 8,464,942 bytes with outbound fetches blocked, no grid/secrets in client JS and database-free fallback. Browser observations are in the v3 evidence. Live database integration was not repeated because database code is unchanged. No hosted routing call or graph build was made.

**Next:** bounded assessment of local-access detours and missing generalized roads, then a single measured refinement if justified; see [next steps](next-steps.md). Hosted v3 verification remains pending the public URL/revision. A task-related Vercel deployment overview is open in Chrome; inspect available project context read-only before asking the user for the URL again. No new environment variables or migration are required. HEAD remains `0ffd6c8`; all v2/v3 code/data/diagnostics/docs are uncommitted and no deployment was performed. A fresh clone of that commit still runs v1. Preserve v1/v2 artifacts, all original/failed evidence, credentials and the parked detailed engine.

**The detailed regional engine is parked as a reference. Do not resume qualification-memory profiling or six-hour expansion automatically.** The two-hour regional baseline remains available. The owner profile, source-outgoing build/rebuild, result and collector are complete: all eight payloads match, complete peaks are 2.415 / 2.416 GiB, and worker wall times are 1,494.59 / 1,555.84 s. Existing regional search proofs/resources were reused on identical bytes. [The memory follow-up](six-hour-preflight.md#memory-follow-up) and [final evidence](evidence/source-outgoing-2026-10-19/README.md) preserve that result; the [first-build checkpoint](evidence/source-outgoing-build-2026-10-19/README.md) is unchanged.

The detailed model's revised partial-source six-hour forecast remains **9.290 GiB with margin versus 4 GiB: hold** (original screen: 9.400 GiB). That gate applies to that recipe, not a separately designed coarse MVP. No calibration job is running. The previously proposed qualification owner/lifetime diagnostic was never started and is now parked. Preserve frozen producers and original resource gates; do not rerun completed outputs, download larger detailed-engine inputs or spend hosted quota for this planning reset.

- Repo: `/Users/eric/Documents/GitHub/geo-planner`, branch `main`, observed HEAD `0ffd6c8` (`simplification`). Recheck Git on resumption; do not reset, clean or overwrite existing work.
- **The coarse app, cloud history and prior evidence are committed at `0ffd6c8`; Git was clean at the start of this follow-up.** The new quality comparison and deployment/status updates are uncommitted. A disconnect does not create a Git checkpoint. A fresh clone includes the coarse app/artifact/migrations, while the detailed research baseline still requires the ignored data/proof chain and cloud credentials remain local/Vercel-only.
- **`data/`, `.env` and `.env.local` are ignored.** Graphs, source snapshots, proof-chain dependencies, binaries and the locally configured provider key exist only in this workspace. They are not in the Git/evidence bundle. Never commit or print secrets.
- Same-workspace health/assets checks pass, and the previous default-launcher smoke passed. A clean-machine bootstrap/portable data bundle is **not** qualified; plan source/proof/tool transfer separately. Recompiling for another platform requires a separately recorded native proof. The original plan remains a proposal, not current implementation status.

## Default coarse app

Start or reuse `http://127.0.0.1:3000/`. `npm run dev` is sufficient; no database, Python or Docker is required. Dependencies are already installed here. The browser still uses an online basemap. Safe readiness check:

```sh
curl --fail --silent --max-time 3 http://127.0.0.1:3000/api/estimate
```

Expect `provider: coarse`, `health: ready`, `minMinutes: 60`, `maxMinutes: 720`. Compute San Diego at six hours or use the ten-/twelve-hour presets. Connected-provider selection retains the old hosted/Valhalla path; openrouteservice remains capped at 60m and spends quota only on computation. No hosted computation was made for the coarse milestone.

Earlier v1 saved-history milestone: **30 server tests and live DB integration pass; check/typecheck/ordinary build/Vercel-target build pass**. The local generated Vercel handler computes San Diego 6h, Denver 10h and New York 12h with zero routing fetches, keeps `/api/experiment` disabled, handles missing database configuration, and packages **5,581,861 bytes** without raw inputs, environment files or embedded DB/API-key values. Chrome verifies private cloud save/reload/model replay. [Saved-history evidence](evidence/saved-history-2026-10-22/README.md) records the new checks. The earlier [coarse milestone](evidence/coarse-estimator-2026-10-22/README.md) retains its 42 national in-process cases; the grid model/data were unchanged at that milestone. Current v2 validation is above. These are software/local packaging checks; travel-time accuracy, all-origin completeness, cloud cold/warm behavior and peak memory remain unverified.

Raw Natural Earth downloads are cached at ignored `data/coarse-sources/natural-earth-v5.1.2/`; [regeneration commands](local-development.md#regenerate-the-coarse-grid) enforce pinned hashes. The active artifact at `src/server/data/coarse-grid-v3.json` and preserved `coarse-grid-v1.json` / `coarse-grid-v2.json` are intentionally exempted from the broad `data/` rule in both Git and Vercel ignore files and must accompany a commit/deployment. Ignore-rule checks include these files while excluding raw downloads, evidence and environment files from Vercel uploads. Do not commit the raw downloads or secrets. The schema now contains `saved_histories` and the starter `todos`; PostgreSQL retains twenty summaries per private browser owner. Geometry is not stored. Inactive owners are not purged automatically, and there is no global owner-count cap or public-write rate limit yet.

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

> Continue Geo Planner in the existing workspace. Read AGENTS.md, docs/README.md and docs/agent-handoff.md, then status/local development/next steps and docs/coarse-estimator.md. HEAD remains 0ffd6c8, while uncommitted v3 now serves a generic shore correction: 1,535 land representatives, 4,599 checked local shore links and 245 retained-road access points, with v2 road data/speeds unchanged. No city/coordinate/region-specific runtime exceptions are permitted. All supported fallback attachments seed search, preserving bridge-connected islands without open-water snapping. Original eleven costs stay unchanged; two of 23 common regional cases improve and none regress against v2. All 24 destinations are reached, but the newly reached shore trip is still 146m versus a 61.3m static reference. Thirty-nine server tests, six geometry tests, 42 national smoke cases, check/typechecks and both builds pass; generated Vercel handler works locally with outbound requests blocked. Rejected land-only/greedy attachment attempts are preserved. Next assess local-access detours and missing generalized roads within the simple fullstack design; do not restart detailed graph expansion or memory profiling. Hosted URL/revision remain pending. No deployment, hosted quota, new env var or database migration was needed/performed. Preserve all evidence, old artifacts and credentials.
