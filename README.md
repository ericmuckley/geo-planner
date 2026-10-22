# Geo Planner

A fullstack mapping app for estimating where you could drive within a time budget. The first long-range model provides **coarse 1–12-hour contours across the contiguous US**, with six-/ten-/twelve-hour presets.

Continuing an existing session: read [the resume guide](docs/agent-handoff.md) and [documentation index](docs/README.md). V3, cloud history and their evidence are committed at `887ab50`; the active v4 road-attachment refinement, access diagnostics and current-doc updates are uncommitted. Compact datasets are included in source; detailed research graphs and keys remain local-only.

## What works today

- Filled, road-informed grid estimates from US land origins, running in the TypeScript server without routing-service requests, a database or a local worker.
- MapLibre map controls, model warnings, timings, cloud-backed saved queries/replay with browser-local fallback and JSON exports.
- An 8.00 MB bundled grid and a locally verified 13.45 MB Vercel function. The user accepted the earlier deployed baseline; v4 is verified locally and ready for deployment.
- Retained comparisons: hosted/Valhalla contours and a detailed regional OSM experiment at `/experiment`.

This first model uses generalized roads and assumed travel speeds, including coarse overland travel without roads. Cells are about 7–11 km across; this is display resolution, **not an accuracy bound**. V4 adds charged access along retained road geometry while preserving the v3 graph and shore correction. It improves 31 of 35 saved point comparisons, with four unchanged and no regressions; all destinations remain reached. Its geography rules apply across the dataset; test trips are never runtime exceptions. These development samples do not validate nationwide accuracy. Traffic, terrain, precise access, turns, ferries and international crossings are unmodeled. [Model, sources and evidence](docs/coarse-estimator.md) explain the limits. The detailed regional expansion is parked. PostgreSQL saved history is implemented. Generic road attachment is implemented. Missing source roads and access through other roads in a cell remain; next deploy v4, then prioritize compact source completeness. See [progress](docs/progress.md) and [next steps](docs/next-steps.md).

## Run locally

Requires Node.js 22.12+ and npm.

```sh
npm ci
npm run dev
```

Install dependencies only if needed; they already exist in the current workspace. Open Vite's printed URL, using [127.0.0.1:3000](http://127.0.0.1:3000) for the verified local app because a different app can occupy IPv6 port 3000. The coarse estimator, map and browser-local history work without a database, routing service, API key, Python or Docker. Fresh routing setup is documented in [.env.example](.env.example), [hosted setup](docs/us-routing-service.md) and the [retained Valhalla recipe](docs/regional-routing.md). Preserve the existing locally configured key and other environment values.

For the native experiment, run `npm run dev:experiment` after the handoff's health/process checks; its qualified graph and binary already exist in this workspace. See [current experiment setup and limitations](docs/two-hour-region.md). The compact coarse grid is bundled; detailed research datasets and graphs are not.

## Development

The app uses TanStack Start, React, TypeScript, Tailwind CSS, and MapLibre. Cloud PostgreSQL history and its reviewed additive migration are implemented and verified. History is private to each browser; accounts and cross-device access are future work. Local `DATABASE_URL` lives in ignored `.env`, with no database override in `.env.local`. PostGIS is not required for the estimator. The web app targets Vercel; the native experiment runs locally.

```sh
npm run check
npm run typecheck
npm test
npm run test:coarse-data
npm run routing:compare:coarse:v2
npm run routing:compare:coarse:regional
npm run routing:compare:coarse:candidate
npm run db:verify
npm run routing:verify:coarse
npm run build
npm run build:vercel
npm run check:coarse:vercel
```

`db:verify` writes and removes a generated temporary test history in the configured database. See [local development](docs/local-development.md) for prerequisites and deployment details, [next steps](docs/next-steps.md) for priorities, and the [documentation index](docs/README.md) for architecture and research results.
