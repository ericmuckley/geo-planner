# Next steps for coding agents

Updated October 22, 2026. Read [AGENTS.md](../AGENTS.md), [the handoff](agent-handoff.md), [current status](implementation-status.md) and [local development](local-development.md).

## Current direction

Ship a simple fullstack Vercel app estimating long isochrones from arbitrary contiguous-US origins, accepting very coarse estimates first and refining later. The first model is implemented: a bundled, road-informed geographic grid, TypeScript search and filled contours, defaulting to six hours with ten-/twelve-hour presets. [Model, sources and evidence](coarse-estimator.md) explain the deliberate approximations. Nationwide smoke checks and local Vercel-handler execution pass; **cloud deployment and travel-time calibration remain unverified**.

Cloud saved-query persistence is implemented and verified against PostgreSQL. The reviewed additive migration is applied; browser-private cloud history, local fallback, backup/retry UI and model-aware load/replay work. [Local development](local-development.md#saved-history-api) explains ownership, data and checks. The user configured Vercel `DATABASE_URL` and ignored local `.env`; `.env.local` has no database override. Preserve credentials, routing settings, detailed producers and frozen evidence. Do not spend hosted routing quota for routine checks.

## 1. Prove the app on a Vercel preview

Run the local checks first:

```sh
npm run check
npm run typecheck
npm test
npm run db:verify
npm run routing:verify:coarse
npm run build
npm run build:vercel
npm run check:coarse:vercel
npm run db:verify -- --vercel
```

`db:verify` uses the configured real database, creates one temporary test history, checks persistence/isolation/concurrent merges/retention and deletes only that generated test row. The `--vercel` variant uses the generated Vercel handler locally after the build. Both source and generated-handler checks pass against cloud PostgreSQL. Run them when database integration changes; they are not read-only health checks.

`check:coarse:vercel` invokes the generated handler locally with outbound fetches rejected; it is not a deployment. Use the existing TanStack Start/Nitro Vercel setup, without local Python or regional graphs. Coordinate the concrete preview deployment with the user's hosting project when available. Do not enable `/api/experiment` on Vercel. The current `0000_saved_history` migration is already applied to the configured cloud database; run reviewed migrations separately from the web build when deploying to a different database.

Acceptance on the actual preview: GET `/api/estimate` ready; San Diego 6h, Denver 10h, New York 12h, rural and coastal origins produce filled approximate results; invalid geography/budgets fail clearly; a new query is marked Cloud saved and restores after reload; another browser cannot see it; history/export and map controls work; no routing-service requests occur. Record deployed revision, artifact bytes, observed cold/warm HTTP latency, response bytes, concurrent behavior and memory using target-provided measurements. Report observation scope and failures honestly. Do not call process RSS a peak or local invocation time cloud latency.

## 2. Refine the largest observed errors

Before adding complexity, compare a small set of familiar trips and barriers against an independent reference with explicit permission for any quota-bearing queries. Include mountains, lakes, remote origins and highway corridors. Current tests establish software/model behavior, not real driving-time accuracy. Keep the approximate label and distinguish display resolution from error.

Improve missing links, unrealistic overland travel, assumed speeds or coastal cells as evidence warrants. A later OSM-derived compact network can replace this generalized grid behind the same API. Cross-device account access, sharing/import, inactive-history cleanup and public-write rate limits remain future work. Each anonymous browser currently gets at most twenty stored summaries, but there is no global owner-count cap. Traffic, exact turns, border access, POIs/public lands/elevation, PostGIS, caching, national anchor fields and advanced routing algorithms remain deferred until chosen as product priorities.

## Preserved detailed-engine baseline

The outgoing-index calibration is complete: both builds reproduce eight qualified payloads at 2.415/2.416 GiB, with proof binding/checks passing. The revised partial-source six-hour screen remains 9.290 GiB with margin versus 4 GiB: hold. The qualification owner/lifetime diagnostic never started and is parked. [Final calibration evidence](evidence/source-outgoing-2026-10-19/README.md), [six-hour report](six-hour-preflight.md) and [two-hour baseline](two-hour-region.md) retain the original measurements and recipes. Do not rerun completed producers as health checks.
