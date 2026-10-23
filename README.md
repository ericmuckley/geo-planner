# Geo Planner

A fullstack mapping app for estimating where you could drive within a time budget. The first long-range model provides **coarse 1–12-hour contours across the contiguous US**, with six-/ten-/twelve-hour presets.

Continuing an existing session: read [the resume guide](docs/agent-handoff.md) and [documentation index](docs/README.md). **V6 is active locally; production is user-reported v5 at `08074fb`.** The new finer dataset/runtime/tools/evidence/docs are uncommitted. Include the v6 artifact when publishing; raw sources, ignored candidates, detailed graphs and credentials remain local-only.

## What works today

- Filled 1–12-hour estimates from arbitrary supported contiguous-US land origins, with 6/10/12h presets and the same rules everywhere.
- A genuinely rebuilt **0.05° grid, about 3.5–5.5 km cells**, half v5's cell width. Nationwide Census roads augment Natural Earth; routing runs in TypeScript without a provider, DB or worker.
- MapLibre controls, source/model notices, timings, browser-private PostgreSQL history with local fallback, replay and export.
- A 68.13 MB bundled model and locally checked 71.94 MB Vercel function; first local packaged computation is about 3.1 seconds, with zero routing fetches.

Across all 35 saved development references, **26 estimates improve and nine worsen** versus v5, with no unreachable/unshaded sample destinations. Mean absolute reference difference falls 21.94 → 14.71 min in the original set and 31.20 → 23.61 min in the broader set; worst regression is +7.09 min. These reused regional references do not prove nationwide or long-horizon accuracy. [Side-by-side maps, results and limits](docs/evidence/coarse-resolution-2026-10-23/README.md).

The model still merges crossings, assumes overland travel without roads and omits traffic, turns, terrain, precise access, ferries and international crossings. Cell size is **not an accuracy bound**. [Model](docs/coarse-estimator.md). Next: publish/verify v6, then refine remaining generic access/transfer errors. Detailed research stays parked; 0.025° is not built. [Progress](docs/progress.md), [next steps](docs/next-steps.md).

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
