# Geo Planner

A fullstack mapping app for estimating where you could drive within a time budget. The first long-range model provides **coarse contours from 30 minutes to 12 hours across the contiguous US**,  with a two-hour default and a release-to-update time slider.

Continuing an existing session: read [the resume guide](docs/agent-handoff.md) and [documentation index](docs/README.md). Local v9 is qualified and ready for review/commit/deployment. V8/slider remain the last user-reported production model; the current checkout starts at `37ff14b`. The floating-map UI and later accuracy work are also uncommitted.

**V9 is qualified and active locally, uncommitted and not deployed.** It retains the 0.025° grid and changes generic travel costs: Natural Earth artificial connections use 55 km/h, secondary roads 85, major roads 105, Census connections/local travel 25. All rules apply everywhere; locations occur only in validation. Across 83 saved ORS development routes, mean absolute difference falls **34.612→29.257 min**; frontier missed reachable **5→2**,  false reachable **17→11**. All prospective gates pass. [Decision, complete ledger and limits](docs/evidence/coarse-path-features-2026-10-24/README.md).

Gains are uneven: 59 routes improve/24 regress, frontier median worsens 37.254→40.561 min, and the older Valhalla sensitivity means worsen. This is an observed development comparison, not nationwide/area accuracy or a fresh holdout. Cell spacing is unchanged. Both earlier timing candidates remain rejected under their original frozen decisions. No new provider call, download, DB write, env/schema/dependency change, commit or deployment occurred. All 48/6/29 reference budgets are consumed.

## What works today

- Filled 30-minute–12-hour estimates from arbitrary supported contiguous-US land origins, with the same rules everywhere. The time slider starts at two hours and recalculates on pointer/key release with loading feedback.
- **0.025° cells, about 1.8–2.8 km**,  half v7's cell width, rebuilt from national sources with paid Census road states. Routing runs in TypeScript without a provider, DB or worker.
- Full-viewport MapLibre map with a compact, collapsible top-left control panel. History, model/layer settings and run details expand inside; mobile controls scroll independently. [Local UI QA](docs/local-development.md#floating-map-controls).
- Source/model notices, timings, browser-private PostgreSQL history with local fallback, replay and export.
- Lossless storage puts the finer model in a **61.23 MB** bundled file and **65.05 MB** local Vercel function. First packaged computation is about **3.4 s after config**,  with zero routing fetches.

The model still merges crossings, assumes overland travel and omits traffic, turns, terrain, precise access, ferries and international crossings. Cell size is **not an accuracy bound**. [Model](docs/coarse-estimator.md). Next: review/commit/deploy v9, then verify the hosted contract. [Progress](docs/progress.md), [next steps](docs/next-steps.md).

## Run locally

Requires Node.js 22.12+ and npm.

```sh
npm ci
npm run dev
```

Install dependencies only if needed; they already exist in the current workspace. Open Vite's printed URL, using [127.0.0.1:3000](http://127.0.0.1:3000) for the verified local app because a different app can occupy IPv 6 port 3000. The coarse estimator, map and browser-local history work without a database, routing service, API key, Python or Docker. Fresh routing setup is documented in [.env.example](.env.example), [hosted setup](docs/us-routing-service.md) and the [retained Valhalla recipe](docs/regional-routing.md). Preserve the existing locally configured key and other environment values.

For the native experiment, run `npm run dev:experiment` after the handoff's health/process checks; its qualified graph and binary already exist in this workspace. See [current experiment setup and limitations](docs/two-hour-region.md). The compact coarse grid is bundled; detailed research datasets and graphs are not.

## Development

The app uses TanStack Start, React, TypeScript, Tailwind CSS, and MapLibre. Cloud PostgreSQL history and its reviewed additive migration are implemented and verified. History is private to each browser; accounts and cross-device access are future work. Local `DATABASE_URL` lives in ignored `.env`, with no database override in `.env.local`. PostGIS is not required for the estimator. The web app targets Vercel; the native experiment runs locally.

```sh
npm run check
npm run typecheck
npm test
npm run test:coarse-data
npm run routing:verify:coarse
npm run build
npm run build:vercel
npm run check:coarse:vercel
```

Optional candidate comparisons require a prepared artifact path; see [offline augmentation setup](docs/local-development.md#offline-augmentation-candidate). `db:verify` writes and removes a generated temporary test history in the configured database. See [local development](docs/local-development.md) for prerequisites and deployment details, [next steps](docs/next-steps.md) for priorities, and the [documentation index](docs/README.md) for architecture and research results.
