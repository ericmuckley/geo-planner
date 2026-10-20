# Implementation status

Updated October 19, 2026. Use [the resume guide](agent-handoff.md) for recovery and [next steps](next-steps.md) for the next scoped task. The goal remains US-focused, quota-independent **10–12-hour** driving reachability before long-range Vercel deployment. The current milestone is a qualified **two-hour regional** baseline. The [six-hour preflight](six-hour-preflight.md) is complete, with the larger graph held at the memory gate; the first smaller-memory calibration build passed exact payload checks; its exact repeat and revised screen are pending.

## Implemented

| Surface | Current behavior | Limits |
| --- | --- | --- |
| `/experiment` → `/api/experiment` → loopback Python/native worker | Own OSM graph, 1–720 whole minutes, default 120m, indexed road snapping, sampled reachable-road display, source-linked edge warnings, separate timings, JSON result export | Regional/static model; sampled lines rather than a filled contour; API opt-in and always disabled on Vercel |
| `/` → `/api/reachability` → selected provider | MapLibre, query controls, filled contours, provider metadata/warnings, browser-local query/run history; user configured openrouteservice locally | Selected hosted driving path remains capped at 60m; consumes provider quota on computation; no long-range cloud engine |
| Retained Valhalla service | Pinned California/northern-Baja graph, real contour/route verification and reproducible build recipe | Separate baseline with unresolved contour/route and nesting discrepancies; not the current experimental engine |

The browser uses an online OpenFreeMap basemap independently of routing. PMTiles support exists but a regional archive is unverified. History on the main page uses localStorage, retains 20 summaries and replays against the current provider; it does not store geometry or provide shared persistence. Database schema remains the starter `todos` table. No PostGIS/POI/public-land/elevation datasets have been imported. The `/mcp` demo is separate.

## Current graph

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

The main-page hosted endpoint retains provider semantics and its 60m cap. Its HTTP timings include provider/network/contouring work; they are not isolated graph-search times. The optional Valhalla adapter has its own cap/configuration and no automatic cut detector. This differs from `/experiment`, which detects cuts in its audited regional graph. Raising a budget never supplies missing geography.

Long-range Vercel execution, filled experimental contours, US-wide coverage, database-backed history, PostGIS layers, elevation, road-distance/dual-budget semantics, national anchors, caching and advanced routing research remain unfinished/deferred. Preserve the single fullstack TanStack Start app deployment goal; current build compatibility is not deployed native routing.

## Verification

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

The original preflight validation records 20 server/adapter passes and 205 routing cases (196 pass, nine existing skips). The subsequent [memory follow-up](six-hour-preflight.md#memory-follow-up) identifies the temporary outgoing-node dictionary and replaces it with source-node offsets. Its first complete build matches all eight qualified payloads at **2.415 GiB / 1,494.59 s**, versus the previous 2.668 GiB peak. Exact repeat, final proof binding and revised admission remain pending; the original 9.40 GiB forecast above is not a new optimized forecast. No calibration job is running at the handoff.

Latest validation: **20 server/adapter passes; 212 routing cases (203 pass, nine existing skips); check/typecheck/regular build pass**, with the existing Biome database warning. The Vercel-target build was not repeated for these offline-only changes. App/worker health is ready on the unchanged two-hour graph with zero provider calls; no new browser/search performance claim is made. [Partial build evidence](evidence/source-outgoing-build-2026-10-19/README.md) preserves this precise stopping point.

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
| `routing/source_outgoing*.py`, `routing/source-outgoing-region.mjs` | Source-node offset calibration and fixtures; first build complete, exact repeat pending; `source_outgoing_result.py` is prepared but not yet run end to end |
| `routing/verify-experiment.mjs`, `routing/*_test.py`, `src/server/*.test.ts` | Live local checks and meaningful regression tests |
| `src/routes/index.tsx`, `src/lib/reachability.ts`, `src/lib/saved-runs.ts` | Main workspace, query/result/history schemas and localStorage |
| `src/server/reachability.server.ts`, `src/routes/api.reachability.ts` | Server-only provider selection and hosted/Valhalla adapter |
| `src/components/research-map.tsx`, `src/components/map-client.ts` | Browser-only MapLibre lifecycle, layers, attribution and map-idle timing |
| `src/db/schema.ts`, `src/db/index.ts`, `.env.example` | Starter schema, server-only DB connection and nonsecret configuration template |

Earlier algorithm/storage producers are checksum-bound dependencies. Their detailed maps and measurements remain in [historical recipes](archive/historical-routing-recipes.md) and the individual reports. Never manually edit `src/routeTree.gen.ts`, overwrite a completed run or bulk-format sealed producers. Preserve all local work and environment values; the current changes are not committed. See [handoff continuity](agent-handoff.md) before switching workspaces.
