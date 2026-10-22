# Next steps for coding agents

Updated October 22, 2026. Read [AGENTS.md](../AGENTS.md), [the handoff](agent-handoff.md), [current status](implementation-status.md) and [local development](local-development.md).

## Current direction

Ship a simple fullstack Vercel app estimating long isochrones from arbitrary contiguous-US origins, accepting very coarse estimates first and refining later. The first model is implemented: a bundled, road-informed geographic grid, TypeScript search and filled contours, defaulting to six hours with ten-/twelve-hour presets. [Model, sources and evidence](coarse-estimator.md) explain the deliberate approximations. Nationwide smoke checks and local Vercel-handler execution pass; **the user reports the hosted Vercel app works, while travel-time accuracy is poor**. Its URL, deployed revision and independent hosted measurements remain pending. The implementation/persistence milestone is committed at `0ffd6c8`.

Cloud saved-query persistence is implemented and verified against PostgreSQL. The reviewed additive migration is applied; browser-private cloud history, local fallback, backup/retry UI and model-aware load/replay work. [Local development](local-development.md#saved-history-api) explains ownership, data and checks. The user configured Vercel `DATABASE_URL` and ignored local `.env`; `.env.local` has no database override. Preserve credentials, routing settings, detailed producers and frozen evidence. Do not spend hosted routing quota for routine checks.

## 1. Assess generic local access and missing-road limits

The v3 shore correction is implemented and verified. It adds 1,535 mixed land representatives, 4,599 continuous-land local connections and 245 retained-road access points, preserving v2 road weights/speeds. All original eleven costs are unchanged; on the same 23 common-finite regional cases two improve and none regress. The previously missing 24th destination is reached/shaded, but still costs 146.0m versus a 61.3m static reference. Strict land-only and greedy nearest-only prototypes failed New York/Key West and are preserved; the final multiple-supported-attachment rule restores those origins. [V3 findings](coarse-estimator.md#v3-general-shore-connectivity), [evidence](evidence/coarse-v3-2026-10-22/README.md).

**User requirement:** every production correction must apply generically to arbitrary supported locations/queries. Named routes/coordinates are tests only; never introduce place/region-specific runtime exceptions or claim a few examples establish general accuracy. Keep this simple fullstack Vercel app usable while refining it.

Safe baseline commands:

```sh
npm run routing:compare:coarse:candidate
npm run routing:compare:coarse:regional
npm run test:coarse-data
npm run routing:verify:coarse
```

Expected v3 comparison: 11 unchanged original cases; 23 common-finite regional cases with mean point difference 37.7296m v2 / 36.8934m v3, two improved, zero regressed, plus the newly reached case separately. The older regional replay still evaluates fixed v2 against v1, reporting 23/24 finite. Six geometry tests and 42 national smoke cases pass; connected sample origins must not collapse to a few cells. The 39 server tests check all new shore links/access points and unchanged road-link lower bounds. All replay commands are offline; do not recapture references merely to validate docs.

Next make a bounded diagnosis of representative-position access detours and missing generalized roads. Existing mountain regressions remain: Palm Springs → Idyllwild is still 96.4m modeled versus a 53.2m reference, while Big Bear has no retained road links in its cell/eight neighbors. Separate access/transfer distance from missing-road/overland assumptions. Do not improve a benchmark merely by permitting unrealistic overland shortcuts or increasing every speed. Prefer the smallest generic correction justified by evidence; do not restart regional graph construction.

Acceptance: record the cost/path or source-coverage evidence for the largest remaining limits, choose one scoped generic refinement (or explain why a source replacement is necessary), and retain the app's coarse labels and current deployment design. Any candidate must preserve v1/v2/v3 artifacts and frozen/rejected evidence, compare both saved sets on common-finite denominators, report reachability separately and explain regressions. The saved sets now guide refinement and are not fresh holdout validation. New independent references require explicit authorization for quota-bearing calls; national/long-horizon accuracy remains unvalidated.

When implementation changes, run relevant tests, check/typecheck, 42 national smoke cases, ordinary/Vercel builds and generated-handler packaging checks. Database integration tests are needed only if that code changes. Finer grids, coastline clipping, nationwide reference acquisition, OSM network replacement, caching and detailed graph/memory research remain deferred until chosen as product priorities.

## 2. Independently verify the hosted app when its URL is available

Run the local checks first:

```sh
npm run check
npm run typecheck
npm test
npm run test:coarse-data
npm run db:verify
npm run routing:verify:coarse
npm run build
npm run build:vercel
npm run check:coarse:vercel
npm run db:verify -- --vercel
```

`db:verify` uses the configured real database, creates one temporary test history, checks persistence/isolation/concurrent merges/retention and deletes only that generated test row. The `--vercel` variant uses the generated Vercel handler locally after the build. Both source and generated-handler checks pass against cloud PostgreSQL. Run them when database integration changes; they are not read-only health checks.

`check:coarse:vercel` invokes the generated handler locally with outbound fetches rejected; it is not a deployment. Use the existing TanStack Start/Nitro Vercel setup, without local Python or regional graphs. The local working tree serves v3, but v3 has not been committed or deployed by this session. Coordinate the concrete preview deployment with the user's hosting project when available; no new environment variables or database migration are required for v3. Do not enable `/api/experiment` on Vercel. The current `0000_saved_history` migration is already applied to the configured cloud database; run reviewed migrations separately from the web build when deploying to a different database.

Acceptance on the actual preview: GET `/api/estimate` ready; San Diego 6h, Denver 10h, New York 12h, rural and coastal origins produce filled approximate results; invalid geography/budgets fail clearly; a new query is marked Cloud saved and restores after reload; another browser cannot see it; history/export and map controls work; no routing-service requests occur. Record deployed revision, artifact bytes, observed cold/warm HTTP latency, response bytes, concurrent behavior and memory using target-provided measurements. Report observation scope and failures honestly. Do not call process RSS a peak or local invocation time cloud latency.

## 3. Continue measured refinement

Before adding complexity, compare a small set of familiar trips and barriers against an independent reference with explicit permission for any quota-bearing queries. Include mountains, lakes, remote origins and highway corridors. Current tests establish software/model behavior, not real driving-time accuracy. Keep the approximate label and distinguish display resolution from error.

Improve missing links, unrealistic overland travel, assumed speeds or coastal cells as evidence warrants. A later OSM-derived compact network can replace this generalized grid behind the same API. Cross-device account access, sharing/import, inactive-history cleanup and public-write rate limits remain future work. Each anonymous browser currently gets at most twenty stored summaries, but there is no global owner-count cap. Traffic, exact turns, border access, POIs/public lands/elevation, PostGIS, caching, national anchor fields and advanced routing algorithms remain deferred until chosen as product priorities.

## Preserved detailed-engine baseline

The outgoing-index calibration is complete: both builds reproduce eight qualified payloads at 2.415/2.416 GiB, with proof binding/checks passing. The revised partial-source six-hour screen remains 9.290 GiB with margin versus 4 GiB: hold. The qualification owner/lifetime diagnostic never started and is parked. [Final calibration evidence](evidence/source-outgoing-2026-10-19/README.md), [six-hour report](six-hour-preflight.md) and [two-hour baseline](two-hour-region.md) retain the original measurements and recipes. Do not rerun completed producers as health checks.
