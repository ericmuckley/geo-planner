# Implementation status

Updated October 22, 2026. Use [the resume guide](agent-handoff.md) for recovery and [next steps](next-steps.md) for the next task. The main page now implements a **coarse contiguous-US estimator at 1–12 hours**, defaulting to six hours. A bundled road-informed grid runs entirely in the TanStack Start TypeScript server and returns filled contours without a database or routing-provider quota. [The model report](coarse-estimator.md) describes assumptions, pinned sources and current evidence. The Vercel-target handler works locally; the user now reports the Vercel-hosted app works, with rudimentary/inaccurate output. The hosted URL/revision and independent cloud measurements remain pending. Cloud PostgreSQL is configured locally in ignored `.env` and on Vercel (user-reported). The old localhost override was removed from `.env.local`; Vite development/production env resolution and a read-only Drizzle `SELECT 1` pass. The reviewed additive initial migration is applied. Browser-private cloud history now stores up to twenty query/run summaries, with local fallback, backup/retry feedback and model-aware Load/Replay. Hosted operation is user-reported; independent agent verification remains pending.

The detailed two-hour regional engine remains a reference. Its memory profiling and six-hour expansion are parked. Its completed smaller-memory calibration passes exact build/rebuild/proof binding, but the partial-source screen remains held at 9.290 GiB with margin. This gate does not constrain the separately implemented coarse model.

## Implemented

| Surface | Current behavior | Limits |
| --- | --- | --- |
| `/experiment` → `/api/experiment` → loopback Python/native worker | Own OSM graph, 1–720 whole minutes, default 120m, indexed road snapping, sampled reachable-road display, source-linked edge warnings, separate timings, JSON result export | Regional/static model; sampled lines rather than a filled contour; API opt-in and always disabled on Vercel |
| `/` → `/api/estimate` (default) | MapLibre, 60–720 minutes, 6/10/12h presets, filled road-informed grid contours, model warnings/timings, cloud-backed/browser-local history and export | Generalized 0.1° grid; assumed 25 km/h land travel and 55–105 km/h roads, geometry-based costs and approximate cell transfers; no calibrated accuracy, precise road access, traffic, turns or ferries |
| `/` connected-model selection → `/api/reachability` | Existing hosted/Valhalla provider, filled contours and provider metadata; existing local openrouteservice key preserved | Hosted driving remains capped at 60m and spends provider quota on computation |
| Retained Valhalla service | Pinned California/northern-Baja graph, real contour/route verification and reproducible build recipe | Separate baseline with unresolved contour/route and nesting discrepancies; not the current experimental engine |

The browser uses an online OpenFreeMap basemap independently of routing. PMTiles support exists but a regional archive is unverified. History on the main page merges localStorage with browser-private PostgreSQL backup, retains twenty summaries and uses each saved coarse/connected model for Load/Replay. New saves back up automatically; older local entries upload only through the backup button. It does not store geometry or provide cross-device accounts. The schema adds `saved_histories` alongside the starter `todos` table; the initial additive migration is applied to the configured cloud database. No PostGIS/POI/public-land/elevation datasets have been imported. The `/mcp` demo is separate.

## Preserved detailed regional graph

| Item | Qualified value |
| --- | --- |
| Run / cuts | `data/compact-pilot/two-hour-region-v2` / `two-hour-region-v2-cuts` |
| Graph identity | `52b34545379adf83ad09175e7d29b5c445b7cf4193fee0f9b5d10afe0904fda1` |
| Extent, west/south/east/north | `[-118.2,31.5,-114.6,34.7]` — Southern California, northern Baja and Arizona border area |
| Size | 8,131,472 directed roads; 8,136,898 states; 17,662,110 transitions; 4,666 via-way prohibitions |
| Model | `exploratory-static-car-v3` plus **`member-scoped-geometry-v1`** restriction policy; 5,000 ms signal / 20,000 ms U-turn delays |
| Source | October 14 road snapshots, plus retained October 16 administrative supplements; exact hashes/settings in [the regional report](two-hour-region.md) |
| Boundary audit | 805 nodes / 1,173 states, every node source-linked; all five reference sources reach zero cuts at 120m |
| First potential edge | San Diego 128m04.582s; all five 128m05s–135m20s rounded |

The five sources are San Diego, El Cajon, Tijuana, San Ysidro and a port incoming-road state. Riverside/Palm Springs/Ensenada/Yuma have independent snap checks and live app smoke tests, not independently qualified full cost fields. Near-perimeter origins can clip within an hour. At six hours the reference sources reach 627–628 potential cuts. Bounds and zero detected cuts do not prove source completeness or every origin.

## Current semantics and limits

Our experimental kernel computes static directed, turn-aware travel costs with partial-road source/destination treatment. The scoped restriction policy prevents an unrelated repeated geometry from disabling valid via-way prohibitions. It is part of graph identity; the legacy compact loader alone does not validate this graph. Use the scoped loader/native/cut entry points listed in the handoff.

Snaps require a supported road within 100 m. Search/counts use the full graph; up to 30,000 road segments are sampled for display. A reached potential data edge produces an explicit incomplete warning. `coverageVerified` stays **false**, even when no edge is reached. Missing source roads, unknown access and restored topology remain separate concerns.

Mexico is retained because reachable paths cross the border. No live traffic, queues, documents or current crossing eligibility are modeled. Otay ways `114198251`, `185333061`, `577149752` retain explicit source uncertainty. Finite cross-border model routes are not real eligibility or ETA guarantees.

The separately selected hosted endpoint retains provider semantics and its 60m cap. Its HTTP timings include provider/network/contouring work; they are not isolated graph-search times. The optional Valhalla adapter has its own cap/configuration and no automatic cut detector. This differs from `/experiment`, which detects cuts in its audited regional graph. Raising a budget never supplies missing geography.

The coarse model supports arbitrary land origins within its generalized lower-48 boundary, including a 1 km shoreline/border input tolerance and a query-local land cell for the origin. Small ferry-only islands may return a single cell; coasts and water crossings remain approximate. Shaded cells include assumed travel without roads, and nearby crossings merge. Smoke checks do not prove all-origin geography or driving-time accuracy. The detailed experimental display remains sampled roads rather than filled contours.

Cross-device accounts, shared history, PostGIS layers, elevation, road-distance/dual-budget semantics, caching and advanced routing research remain deferred. PostgreSQL can store saved queries and later cached results; it is not needed for searching the bundled grid.

## First accuracy diagnostic and deployment report

The user reports a working Vercel-hosted version. The app/persistence implementation is committed at `0ffd6c8`; the deployed revision and URL are not yet independently verified. This is a deployment milestone, not evidence of accurate driving times.

A new bounded comparison with eleven routes on the existing local static Valhalla service finds v1 destination-cell costs **18.9–86.9m longer** (mean absolute difference **42.4m**) and a road-reachable but unshaded Calexico border cell. A traced LA grid path travels 228.8 km of 90 km/h cell steps plus origin attachment, compared with the reference route's 195.8 km. This is model-to-model diagnosis with different path/access semantics, not live ground truth or national validation. This describes the preserved v1 baseline; the local working tree now serves v2. [Detailed findings](coarse-estimator.md#first-regional-travel-cost-comparison), [evidence](evidence/coarse-quality-2026-10-22/README.md) and [next checks](next-steps.md).

**V2 correction implemented locally:** road geometry, consistent representative positions and explicit transfer/origin costs; revised assumed class speeds; 495 road-supported display cells without added overland water connections. The same eleven cell-arrival comparisons improve from 42.4m to 20.3m mean difference, all eleven improving. With approximate destination access added to both models, the mean changes from 51.5m to 31.4m. Geometry alone at original speeds only changes 42.4m to 41.4m; the class-speed update supplies most of the aggregate gain. An invalid naive formula was rejected and preserved. This sample informed the model and is not held-out or national validation. [Detailed v2 interpretation](coarse-estimator.md#v2-cost-correction-and-border-shading), [new evidence](evidence/coarse-v2-2026-10-22/README.md).

Fresh v2 checks pass: **33 server tests, three Python geometry tests, 42 national smoke cases, Biome, typecheck and both builds**. The 4,460,777-byte artifact reproduces exactly. The generated Vercel function is 8,242,734 bytes and runs the three representative queries with zero outbound fetches, no data in public JS and database-free fallback. Browser verification is recorded in the v2 evidence. These are local checks; hosted v2 and cloud resources are unverified. Database code is unchanged; live write integration was not repeated.

## Broader regional validation

A fixed new **24-route/twelve-origin** set evaluates unchanged v2 against the retained static Valhalla service. All 24 references succeed; both coarse grids reach 23/24 destination cells. On paired finite cases, mean cell-arrival difference is **44.7m v1 → 27.3m v2** (19 improve), and approximate point mean difference is **53.0m → 37.7m** (**18 improve, five regress**). The unreached case remains explicit outside the means. Four of five mountain cases regress; endpoint representative detours and missing generalized road coverage remain consequential. These routes span 15.2–272.2m and do not validate long-horizon boundaries or national accuracy. [Interpretation](coarse-estimator.md#broader-regional-validation), [fixed plan/raw references/diagnostics](evidence/coarse-regional-2026-10-22/README.md).

That v2 diagnostic selected shore-cell arrival/departure symmetry: Bombay Beach's lake-center cell had no road links or traversal/display membership, while origin-only activation let departure work. The reference snaps to a road within 9 m. V3 below implements the separately versioned correction at unchanged speeds; mountain detours and missing roads remain queued. The diagnostic also finds no retained road links in Big Bear's cell or eight neighbors.

Only diagnostic scripts, the plan and documentation changed in this follow-up. Check, app typecheck, explicit strict diagnostic typecheck and ordinary build pass; offline replay reproduces capture analysis with zero network calls. The running reference image/mount and fresh configuration/archive hashes match the retained graph. Exactly one local status plus 24 route requests were made; zero hosted routing calls, no graph builds, no database/environment/product changes and no deployment. Vercel/browser/database suites were not repeated for offline diagnostics; prior evidence retains its scope. New source hashes are observational; original v1/v2/evidence bytes remain intact.

## V3 shore correction

The active local app serves `coarse-road-grid-v3`. General geography rules add **1,535** mixed-cell land representatives, **4,599** bidirectional local shore connections and **245** access points following retained road visits to their unchanged v2 anchors. V2 road costs/speeds and original land mask are unchanged. Every new local segment stays on continuous generalized land in one country polygon component; source access may use the existing 1 km input-end tolerance or explicit retained-road geometry, with positive distance cost. Multiple supported fallback seeds preserve bridge-connected islands; isolated islands acquire no open-water connection. There are no example/city/coordinate-specific production rules. [Details](coarse-estimator.md#v3-general-shore-connectivity), [evidence and failed prototypes](evidence/coarse-v3-2026-10-22/README.md).

The original eleven costs remain unchanged. On **the same 23 common-finite regional cases**, v2 → v3 point mean difference is **37.730m → 36.893m**, two improve and none regress. The previously missing 24th shore destination is now reached/shaded at 6h/12h and has a symmetric modeled point cost **146.0m**, versus the static reference’s **61.3m**. This fixes membership, not the missing-road/time gap. Earlier mountain regressions remain queued; this is not national or long-horizon accuracy validation.

Fresh checks pass: **39 server tests, six Python geometry tests, all 42 national smoke cases, check/typechecks and both builds**. New tests catch narrow water gaps, diagonal contact, shared-cell islands, explicit road access and degenerate connected origins. A land-only prototype stranded New York/Key West; a greedy fallback still stranded Key West, so both were rejected and preserved. Final New York/Key West retain road access. The reproducible 4,673,811-byte artifact is server-only; the generated **8,464,942-byte** Vercel function runs representative contours with zero outbound calls and database-free fallback. Browser verification is in the evidence. No live DB integration rerun, new env var, migration, hosted request, graph build, commit or deployment occurred. Next assess generic local-access detours/missing roads while keeping the small bundled app.

## Saved-history verification

Fresh October 22 follow-up: **30 server tests pass; check/typecheck/ordinary build/Vercel-target build pass**. The previous database non-null assertion is removed. Live PostgreSQL checks through both the source API and the generated Vercel handler verify persisted restoration, owner isolation, concurrent saves and twenty-entry retention, removing only their generated test rows afterward. Chrome verifies Save query → Cloud saved, reload restoration, and model-aware Load/Replay from connected selection to a coarse six-hour contour. Older local entries remain Browser only.

The current generated Vercel-handler check verifies database-free local fallback, enabled coarse estimates, disabled detailed routing, no embedded database/API-key values in function/client output, and server-only grid packaging. It still invokes the handler locally; no actual web cloud-deployment or cloud performance claim follows. [Saved-history evidence](evidence/saved-history-2026-10-22/README.md) records the scope. [API and setup](local-development.md#saved-history-api) describe the private bearer cookie, validation and retention. There are no accounts, global owner cap, inactive-owner cleanup or public-write rate limits yet.

## Coarse estimator verification

Original coarse milestone, October 22: **26 server tests pass; 42 sequential in-process origin/budget cases pass; check, typecheck, ordinary build and Vercel-target build pass**. The existing Biome database warning remains. The generated Vercel handler returns approximate contours at 6/10/12h with network fetches rejected; the local-only detailed API still returns 503. The server function is about 5.3 MB, with no raw source/worker/environment files or grid data in public JavaScript. This is local packaging evidence, not a cloud deployment or cloud performance measurement.

Chrome flows verified default San Diego 6h, New York 12h, connected-model selection and replay of a saved coarse result. No hosted routing computation was made. [The model report](coarse-estimator.md) and [new evidence](evidence/coarse-estimator-2026-10-22/README.md) give limits and exact commands. Accuracy calibration and target-platform resources remain open.

## Preserved detailed-engine verification

The [sealed October 19 evidence](evidence/two-hour-region-2026-10-19/README.md) records:

- Eight byte-identical build/rebuild artifacts; all 2,952 previous via-way prohibitions, 62,797 barrier decisions and twelve sampled city route costs/sequences preserved.
- Fresh five-source independent full/bounded/partial checks; native verification of 366,160,410 costs and 325,475,920 memberships plus both partial destinations.
- Complete source-linked cuts, explicit two-hour acceptance, **22 valid live API cases**, repeat/error checks and Chrome flows at 90/120/360m plus Yuma 60m.
- **20 passing adapter/server tests**; **200 routing tests run: 191 pass / 9 existing platform/tool skips**. Check, typecheck, regular build and Vercel-target build pass. Biome has the existing `src/db/index.ts` non-null-assertion warning.
- Local generated Vercel-handler GET/POST experiment requests return 503, with zero outbound calls and no local data/environment files bundled. No cloud deployment occurred.

Complete Linux peaks: **2.668 GiB build / 2.653 GiB rebuild / 2.636 GiB qualification / 2.202 GiB cuts**, each passing the unchanged 4 GiB/no-swap cap and 25% admission margin without pressure/OOM/kill/swap. Native/browser workers run separately on macOS; their RSS is not a capped Linux measurement.

One San Diego 120m API observation is **511.8 ms native search / 6,097.5 ms geometry / 6,754.4 ms HTTP**. Native search is instrumented loop wall time, not CPU-only time. Worker, pipe, HTTP, browser parse/validation and map-idle scopes differ. See raw samples in the report; these are not production p50/p95 claims.

The documentation audit rechecks saved evidence/recipe hashes and live health rather than rerunning completed graph producers or spending provider quota. Older test counts, admission holds and “next” instructions are preserved in [historical snapshots](archive/handoff-history-2026-10-19.txt), not active directions.

## Six-hour preflight result

[The preflight evidence](evidence/six-hour-preflight-2026-10-19/README.md) retains the full unclipped six-hour plan and source assessment. Cached SoCal/Mexico/Arizona preparation passed reference checks at a measured **3.175 GiB / 717.64 s**; its census has **22.9 million eligible directed segments**. Scaling complete qualified build/rebuild/independent/cut peaks forecasts **9.40 GiB with margin**, versus 4 GiB: **hold**, with no new graph or road download. Full missing-source demand remains unknown. Five missing extract listings total about 1.47 GB; current polygons are not dated coverage proofs. Disk is sufficient for the partial forecast; host/native/full-region requirements remain unqualified.

The original preflight validation records 20 server/adapter passes and 205 routing cases (196 pass, nine existing skips). The subsequent [memory follow-up](six-hour-preflight.md#memory-follow-up) identifies the temporary outgoing-node dictionary and replaces it with source-node offsets. Its first complete build matches all eight qualified payloads at **2.415 GiB / 1,494.59 s**, versus the previous 2.668 GiB peak. The exact repeat completed October 21 at **2.416 GiB / 1,555.84 s**, reproducing all eight payloads and supplemental fixtures with zero pressure/OOM/kill/swap and 25% margin. The result verifier passes without revision and binds existing independent/native/cut proofs to identical bytes; those searches/resources were reused, not rerun. The revised partial-source screen is **9.290 GiB with margin versus 4 GiB: hold**, dominated by retained independent qualification at 2.636 GiB. The original 9.40 GiB screen above remains the original recipe’s result. No calibration job is running; the proposed qualification owner/lifetime diagnostic never started and is parked after the product reset.

Fresh October 21 validation: **20 server/adapter passes; 212 routing cases (203 pass, nine existing skips); check/typecheck/regular build pass**, with the existing Biome database warning. The Vercel-target build was not repeated for these offline-only changes. App/worker health is ready on the unchanged two-hour graph with zero provider calls; no new browser/search performance claim is made. [Final calibration evidence](evidence/source-outgoing-2026-10-19/README.md) binds the completed result and next-phase analysis. The earlier [first-build checkpoint](evidence/source-outgoing-build-2026-10-19/README.md) is preserved unchanged. Final October 22 GET health/config checks follow recovery through the documented launcher; no browser/search performance claim is added.

## Code map

| File(s) | Responsibility |
| --- | --- |
| `src/routes/experiment.tsx`, `src/lib/experiment.ts` | Experimental controls, result metadata and validated contract |
| `src/routes/api.experiment.ts`, `src/server/experiment.server.ts` | Opt-in loopback API, validation, 90s wait and Vercel guard; no hosted fallback |
| `routing/experiment.mjs`, `routing/experiment.py` | Graph-aware launcher; Python reload/snap index/geometry/cut reporting and native IPC |
| `routing/native_search.cpp`, `routing/native_support.py` | Native CSR bounded search and process protocol |
| `routing/scoped_region.py`, `routing/scoped_import.py`, `routing/scoped_member_lookup.py`, `routing/scoped_load.py` | Versioned two-hour construction, scoped restrictions and identity-aware reload |
| `routing/scoped_region_verification_v3.py`, `routing/scoped_region_verification_v2.py`, `routing/scoped_native.py`, `routing/scoped_cuts.py`, `routing/two_hour_release.py` | Reference bootstrap, independent/native/cut qualification and acceptance; exact entry points in the handoff |
| `routing/two_hour_source_v2.py`, `routing/two_hour_region_prepare_v2.py` and matching `.mjs` wrappers | Pinned source merge, buffered extraction, census and resource admission |
| `routing/six_hour_preflight.py`, `routing/six_hour_sources.py`, `routing/six_hour_source.py`, `routing/six_hour_prepare.py` and matching wrappers | Six-hour envelope, official source metadata and partial-source capped census; no graph promotion |
| `routing/base_memory_profile.py`, `routing/base-memory-profile.mjs` | Completed bounded owner census; diagnostic, not complete-phase admission |
| `routing/source_outgoing*.py`, `routing/source-outgoing-region.mjs` | Source-node offset calibration and fixtures; exact build/rebuild complete; `source_outgoing_result.py` verifies proof reuse and revised partial-source admission |
| `routing/verify-experiment.mjs`, `routing/*_test.py`, `src/server/*.test.ts` | Live local checks and meaningful regression tests |
| `src/routes/index.tsx`, `src/lib/reachability.ts`, `src/lib/saved-runs.ts` | Main workspace, model selection, query/result/history schemas and localStorage |
| `src/routes/api.estimate.ts`, `src/server/coarse-estimate.server.ts` | Default coarse config/estimate API; validation and result metadata |
| `src/server/coarse-grid.ts`, `src/server/coarse-contours.ts`, `src/server/coarse-data.server.ts`, `src/server/data/coarse-grid-v3.json`, `src/server/coarse-geography.ts` | Bundled grid, bounded search, geographic validation and filled cell-union contours |
| `scripts/compare-coarse-regional.ts`, `scripts/fixtures/coarse-regional-v1.json`, `scripts/inspect-coarse-regional.ts` | Fixed broader regional reference capture, quota-free replay and cell/access diagnostics |
| `scripts/build-coarse-grid-v3.py`, `scripts/compare-coarse-candidate.ts`, `scripts/compare-coarse-v2.ts`, `scripts/verify-coarse.ts`, `scripts/verify-coarse-vercel.mjs` | Pinned offline artifact builder, national smoke checks and generated-handler packaging check |
| `src/server/reachability.server.ts`, `src/routes/api.reachability.ts` | Server-only provider selection and hosted/Valhalla adapter |
| `src/components/research-map.tsx`, `src/components/map-client.ts` | Browser-only MapLibre lifecycle, layers, attribution and map-idle timing |
| `src/db/schema.ts`, `src/db/index.ts`, `drizzle/`, `.env.example` | Saved-history/starter schema, reviewed additive migrations, bounded server-only pool and nonsecret configuration template |
| `src/routes/api.saved-runs.ts`, `src/server/saved-runs*.ts` | Browser-private cloud API, bounded input validation, cookie ownership and transactional PostgreSQL storage |
| `src/lib/use-cloud-history.ts`, `src/lib/saved-runs.ts`, `scripts/verify-saved-history.ts` | Queued cloud backup/retry, local/cloud merge helpers and live DB integration check |

Earlier algorithm/storage producers are checksum-bound dependencies. Their detailed maps and measurements remain in [historical recipes](archive/historical-routing-recipes.md) and the individual reports. Never manually edit `src/routeTree.gen.ts`, overwrite a completed run or bulk-format sealed producers. Preserve all local work and environment values; the previous implementation handoff is committed at `289d08e`; the coarse/persistence implementation is committed at `0ffd6c8`; the v2/v3 refinements/diagnostics and deployment-status documentation are uncommitted, and detailed research data remain local-only. The compact coarse artifact is included in source for fresh clones after commit. See [handoff continuity](agent-handoff.md) before switching workspaces.
