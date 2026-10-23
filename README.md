# Geo Planner

A fullstack mapping app for estimating where you could drive within a time budget. The first long-range model provides **coarse contours from 30 minutes to 12 hours across the contiguous US**, with a two-hour default and a release-to-update time slider.

Continuing an existing session: read [the resume guide](docs/agent-handoff.md) and [documentation index](docs/README.md). **V8 and the time slider are committed through `9b3e83b` (`slider`) and user-reported deployed.** Fifteen hosted API checks and automatic slider updates pass. The approved 48-route reference run is complete: all succeed, but mean absolute difference is **52.27 minutes** (12-hour probes: **78.77 minutes**). The tool/diagnostic/evidence remain local/uncommitted. [New measurements and next prototype](docs/evidence/coarse-frontier-reference-2026-10-23/README.md). Raw sources, detailed graphs and credentials remain local-only.

## What works today

- Filled 30-minute–12-hour estimates from arbitrary supported contiguous-US land origins, with the same rules everywhere. The time slider starts at two hours and recalculates on pointer/key release with loading feedback.
- **0.025° cells, about 1.8–2.8 km**, half v7's cell width, rebuilt from national sources with paid Census road states. Routing runs in TypeScript without a provider, DB or worker.
- MapLibre controls, source/model notices, timings, browser-private PostgreSQL history with local fallback, replay and export.
- Lossless storage puts the finer model in a **61.21 MB** bundled file and **65.02 MB** local Vercel function. First packaged computation is about **3.6s after config**, with zero routing fetches.

Across all 35 saved development references, **29 estimates improve and six worsen** versus v7, at most +3.18 min. Mean absolute reference difference falls **11.58→10.29 min** and **17.21→12.01 min**; all destinations remain reached/shaded. These regional references do not prove national or long-horizon accuracy. [Paired maps, results and limits](docs/evidence/coarse-finer-2026-10-23/README.md).

The model still merges crossings, assumes overland travel and omits traffic, turns, terrain, precise access, ferries and international crossings. Cell size is **not an accuracy bound**. [Model](docs/coarse-estimator.md). Next: prototype a generic road-class timing calibration in a separate candidate and compare it with the preserved v8 baseline; no timing change is implemented yet. Detailed research stays parked. [Progress](docs/progress.md), [next steps](docs/next-steps.md).

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
