# Geo Planner

A fullstack mapping app for estimating where you could drive within a time budget. The first long-range model provides **coarse contours from 30 minutes to 12 hours across the contiguous US**, with a two-hour default and a release-to-update time slider.

Continuing an existing session: read [the resume guide](docs/agent-handoff.md) and [documentation index](docs/README.md).

**V9 is committed at `648c731` (commit message `v8`), user-reported deployed and verified.** The agent's 15 production API checks also pass for `coarse-road-grid-v9`, min 30/max 720 and the saved 6/10/12 h counts. No provider call or history write was needed. Public model metadata does not expose deployed Git SHA; hosted browser verification is user-reported. [Hosted result and latest preflight](docs/evidence/coarse-backbone-preflight-2026-10-25/README.md).

**Production.** Release `b765050` adds **Browse trailheads** and **Browse campgrounds** to the v9 app. The live six-hour Flagstaff check verified both lists, their pins and the elevation filter. The replacement engine remains held after seven failed release checks. [Hosted release checks](docs/evidence/usgs-area-layers-2026-11-18/browse-lists-release-v1.json).

**In the working tree.** The [local preview](http://127.0.0.1:4203/) adds **Directions in Google Maps** to trailhead and campground popups. The link uses the estimate’s starting point and the place’s mapped coordinates. [Behavior and checks](docs/evidence/usgs-area-layers-2026-11-18/README.md#directions-links).


## What works today

- Filter trailheads and campgrounds by mapped public land, minimum elevation, or both. [Filter behavior and verification](docs/evidence/usgs-area-layers-2026-11-18/README.md#outdoor-place-filters).
- Search for a town, natural landmark or street address to set an origin or check a destination. [Place search details](docs/evidence/place-search-2026-11-18/README.md).
- The [live app](https://geo-planner-orcin.vercel.app/) includes **Check a destination** and optional layers for **Fuel stops**, **Trailheads**, **Campgrounds**, **Public lands** and **Elevation**. Estimate an area and enable the layers you want to see. [Overlay data and limits](docs/evidence/usgs-area-layers-2026-11-18/README.md).
- Filled 30-minute–12-hour estimates from arbitrary supported contiguous-US land origins, with the same rules everywhere. The time slider starts at two hours and recalculates on pointer/key release with loading feedback.
- **0.025° cells, about 1.8–2.8 km**, half v7's cell width, rebuilt from national sources with paid Census road states. Routing runs in TypeScript without a provider, DB or worker.
- Full-viewport MapLibre map with a compact, collapsible top-left control panel. History, model/layer settings and run details expand inside; mobile controls scroll independently. [Local UI QA](docs/local-development.md#floating-map-controls).
- Source/model notices, timings, browser-private PostgreSQL history with local fallback, replay and export.
- Lossless storage puts the finer model in a **61.23 MB** bundled file and **65.05 MB** local Vercel function. First packaged computation is about **3.4 s after config**, with zero routing fetches.

The model still merges crossings, assumes overland travel and omits traffic, turns, terrain, precise access, ferries and international crossings. Cell size is **not an accuracy bound**. [Model](docs/coarse-estimator.md).

Offline OpenStreetMap capture, national count/topology audits and the captured-data road-only cost prototype are complete. Complete app footprint and countrywide ETA accuracy still need qualification. Large research assets remain ignored and absent from a fresh clone. [Progress](docs/progress.md), [next steps](docs/next-steps.md).

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
npm run routing:verify:coarse
npm run build
npm run build:vercel
npm run check:coarse:vercel
```

Optional candidate comparisons require a prepared artifact path; see [offline augmentation setup](docs/local-development.md#offline-augmentation-candidate). `db:verify` writes and removes a generated temporary test history in the configured database. See [local development](docs/local-development.md) for prerequisites and deployment details, [next steps](docs/next-steps.md) for priorities, and the [documentation index](docs/README.md) for architecture and research results.
