# Geo Planner

A fullstack mapping app for estimating where you could drive within a time budget. The first long-range model provides **coarse 1–12-hour contours across the contiguous US**, with six-/ten-/twelve-hour presets.

Continuing an existing session: read [the resume guide](docs/agent-handoff.md) and [documentation index](docs/README.md). **V5 is active locally; production remains verified v4 at `637746c`.** Runtime support, nationwide v5 data, diagnostics, evidence and docs after that commit are uncommitted. Include the new bundled dataset when publishing; raw inputs, detailed graphs and credentials remain ignored/local-only.

## What works today

- Filled road-informed 1–12-hour estimates from arbitrary supported US land origins, running in TypeScript without a routing service, database or worker.
- MapLibre controls, source/model notices, timings, browser-private PostgreSQL history with local fallback, replay and JSON export.
- Nationwide Census primary/secondary roads augment Natural Earth through paid cell-anchor transfers. The 40.0 MB bundled model produces a locally checked 43.8 MB Vercel function, with zero outbound routing calls.
- Retained comparisons: hosted/Valhalla contours and a detailed regional OSM experiment at `/experiment`.

V5 uses the same rules everywhere; validation trips are never runtime exceptions. A reusable geography index preserves full validation while reducing first local packaged computation from about 22.2 seconds to **2.46–2.47 seconds in three fresh processes**. All 35 saved comparison costs/paths and 42 national cell counts match the accepted national candidate; seven saved cases improve against v4, none regress. Local arbitrary inland/rural/coastal 6/10/12h queries and cloud save/reload/replay pass. These are software/local observations, not cloud latency or national driving accuracy. [V5 evidence](docs/evidence/coarse-v5-2026-10-22/README.md).

The model remains deliberately coarse: 7–11 km display cells, assumed speeds and overland travel without roads. Nearby crossings merge; traffic, terrain, precise access, turns, ferries and international crossings are unmodeled. Cell size is **not an accuracy bound**. [Model and sources](docs/coarse-estimator.md) explain the limits. The next step is actual v5 deployment verification; detailed regional expansion stays parked. See [progress](docs/progress.md) and [next steps](docs/next-steps.md).

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
npm run db:verify
npm run routing:verify:coarse
npm run build
npm run build:vercel
npm run check:coarse:vercel
```

Optional candidate comparisons require a prepared artifact path; see [offline augmentation setup](docs/local-development.md#offline-augmentation-candidate). `db:verify` writes and removes a generated temporary test history in the configured database. See [local development](docs/local-development.md) for prerequisites and deployment details, [next steps](docs/next-steps.md) for priorities, and the [documentation index](docs/README.md) for architecture and research results.
