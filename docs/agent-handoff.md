# Resume Geo Planner

Updated October 19, 2026 after the completed first memory-calibration build and documentation handoff audit. This guide is sufficient to recover the task without the chat. Read [AGENTS.md](../AGENTS.md), then this page, [current status](implementation-status.md), [local setup](local-development.md) and [next steps](next-steps.md). The [two-hour report](two-hour-region.md) contains the detailed proof; older reports live in [the archive](archive/README.md) and describe their named historical runs.

## Where to resume

The **two-hour regional baseline is complete** and still serves the app. The **six-hour preflight is complete, with the larger build held**: the original cached-partial-source forecast is 9.40 GiB with margin against the unchanged 4 GiB gate. That is a heuristic, not measured graph RAM or a revised optimized forecast. No full six-hour road acquisition or graph was attempted.

The bounded owner profile and **first storage calibration build passed**. It reproduces all eight qualified payloads while reducing complete build peak from **2.668 to 2.415 GiB** (about 9.5%). **The exact repeat has not started; no calibration job is running at this checkpoint.** This follow-up is not yet accepted and has not changed the serving graph. [The memory follow-up](six-hour-preflight.md#memory-follow-up) is the single detailed record; [partial build evidence](evidence/source-outgoing-build-2026-10-19/README.md) preserves the stopping point.

After the read-only checks below, the immediate next command is:

```sh
node routing/source-outgoing-region.mjs --stage rebuild
```

This creates `data/compact-pilot/source-outgoing-v1-rebuild` (roughly 25 minutes). Check for an existing repeat/job before launching; do not rerun the finished profile or first build. After it passes, finish the prepared result verifier, revised admission and final evidence collector in [next steps](next-steps.md). These helpers have not run end to end. Preserve the frozen producers and the two-hour app; source gaps remain even if the memory work succeeds. Do not increase limits, spend hosted quota or start a larger graph before a revised complete-source gate.

- Repo: `/Users/eric/Documents/GitHub/geo-planner`, branch `main`, observed HEAD `d00f669` (`initial commit`). Recheck Git on resumption; do not reset, clean or overwrite existing work.
- **Code/docs/evidence include uncommitted and untracked files.** No files were staged or committed by these sessions. A disconnect does not create a Git checkpoint. Keep the whole working directory; a new clone/branch checkout alone does not contain the current implementation.
- **`data/` and `.env.local` are ignored.** Graphs, source snapshots, proof-chain dependencies, binaries and the locally configured provider key exist only in this workspace. They are not in the Git/evidence bundle. Never commit or print secrets.
- Same-workspace health/assets checks pass, and the previous default-launcher smoke passed. A clean-machine bootstrap/portable data bundle is **not** qualified; plan source/proof/tool transfer separately. Recompiling for another platform requires a separately recorded native proof. The original plan remains a proposal, not current implementation status.

## Current baseline

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

The main page `/` uses the separate hosted provider path, capped at 60 minutes. Its key is already configured locally. Offline experiments must not call it or use hosted fallback. Basemap tiles still use the network independently.

## Read-only recovery checks

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

The last verified listeners include **two different apps on port 3000**, one on IPv4 and another on IPv6. Use **`127.0.0.1`**, not an assumed `localhost` mapping. Do not stop the unrelated app. PIDs and tool-session IDs are not durable; discover owners again rather than reusing a PID from old logs.

Verify saved evidence and current producer files without recomputation:

```sh
python3 -B - <<'PYTHON'
import hashlib, json
from pathlib import Path
evidence = Path('docs/evidence/two-hour-region-2026-10-19')
for filename, root in [('evidence-sha256.json', evidence),
                       ('final-recipe-sha256.json', Path('.'))]:
    expected = json.loads((evidence / filename).read_text())
    for name, checksum in expected.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == checksum, name
    print(filename, len(expected), 'files match')
PYTHON
```

At this handoff, **87 baseline evidence / 187 producer files** match. The [six-hour preflight evidence](evidence/six-hour-preflight-2026-10-19/README.md) also matches **79 evidence / 83 producer files**. The new [first-build handoff bundle](evidence/source-outgoing-build-2026-10-19/README.md) binds **28 evidence files / 151 combined build/profile producer files**, and includes its own safe verification command. All eight current first-build payload hashes were rechecked against the qualified manifest. These host checks do not rerun the expensive independent/native proofs or supply new capped resource measurements. Inspect future mismatches against authorized work; do not restore files blindly.

Latest calibration validation: **20 adapter/server passes; 212 routing cases (203 pass, nine existing skips); check/typecheck/regular build pass**, with the existing Biome database warning. The Vercel-target build was not repeated for these offline-only changes. Earlier milestone/preflight test counts and Vercel packaging results remain in their named reports. Fresh app/worker GET checks are ready on the same graph with zero provider calls; no new browser/search performance claim is made.

Historical reports moved into `docs/archive/`; evidence paths and checksum-bound indexes stay fixed, with four top-level forwarding pages preserving their links. Frozen diagnostics can still use former report paths; locate their basenames in the archive. The earlier [handoff audit](evidence/handoff-audit-2026-10-19/README.md) remains historical. Current link/anchor and diff checks pass; latest logs are in the first-build handoff bundle. Preserve sealed evidence and all local-only assets.

## Start or recover the app

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

Native runtime prerequisites are already present: Python 3.13.5, Node 24.5.0, npm 11.6.0, Apple Clang 17 arm64, matching compiled binary and local datasets. Future offline construction also needs Docker and the pinned cached images in the report. Node dependencies are installed; do not install/upgrade tools merely to resume. The host has 16 GiB RAM; about **171 GiB disk was free at this handoff** after the first calibration build. Measure again before expansion. Fresh GET health/config both report ready, the qualified identity and zero provider calls; Docker has only the retained healthy Valhalla container, with no calibration batch running.

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
| `data/resource-pilot/source-outgoing-validation-v1` | Latest checks/health, mutable `active-work.json`, prepared result/evidence helpers; `result.json` not yet produced |
| `data/compact-pilot/source-outgoing-v1-rebuild` | **Not created yet**; next exact-repeat output |
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

The completed owner-profile and source-outgoing build producers are also frozen. The new build manifest binds 149 scripts; `source_outgoing_result.py` and the prepared evidence collector are pending helpers, not completed proofs. Keep `scoped_load.py` and the named restriction policy. The first `two-hour-region-v1` graph and unversioned scoped verifier/cut wrapper preserve rejected or superseded attempts. **Do not edit sealed files, even for formatting**, or overwrite graph/source/report bytes to bypass identity failures. Version a changed producer and bind all dependencies explicitly; a fresh output name alone does not rebind downstream hardcoded paths. Never manually edit `src/routeTree.gen.ts`, commit secrets, erase failed attempts or change the hosted environment to enable the experiment.

## Suggested resume message

> Continue Geo Planner in the existing workspace. Read AGENTS.md, docs/README.md and docs/agent-handoff.md, then status/local development/next steps. Preserve the dirty working tree, ignored data and environment values; run read-only recovery checks. The owner profile and first source-outgoing calibration build passed; exact rebuild has not started. Finish the repeat, prepared verifier, revised admission and evidence collection from docs/next-steps.md. Do not rerun completed producers or edit their frozen files. Keep the qualified two-hour app available; larger coverage remains held. Do not spend hosted quota, deploy or start deferred analytical/caching work.
