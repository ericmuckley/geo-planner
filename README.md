# Geo Planner

A mapping and routing research workspace for exploring where you can drive within a time budget. The goal is fast, US-wide **10–12-hour reachability**, with gas stations, public lands, and elevation overlays.

Continuing an existing session or handing off to another coding agent: read [the resume guide](docs/agent-handoff.md) and [documentation index](docs/README.md) first. Current implementation changes are uncommitted, and large datasets/keys are local-only; a fresh clone does not contain this workspace's running baseline.

## What works today

- Interactive MapLibre map with origin/time controls, browser-local saved queries, JSON exports, and query timings.
- Driving isochrones through openrouteservice (up to 60 minutes) or self-hosted Valhalla.
- An offline OpenStreetMap routing pipeline in Python/C++, with reproducible graph builds and independent correctness and resource checks.
- A local `/experiment` view, defaulting to 120 minutes on an 8.14-million-state Southern California/northern Baja/Arizona-border graph. All five reference sources reach no detected data edges within two hours; new origins near the perimeter can clip earlier.

The [six-hour preflight](docs/six-hour-preflight.md) is complete; the larger build is held at the memory gate. A smaller-memory build passes exact payload checks; its repeat and revised resource screen are next in [the handoff](docs/agent-handoff.md). Complete long-range coverage and filled local contours remain unfinished. POI, public-land, and elevation layers are planned. See [current progress](docs/progress.md).

## Run locally

Requires Node.js 22.12+ and npm.

```sh
npm ci
npm run dev
```

Install dependencies only if needed; they already exist in the current workspace. Open Vite's printed URL, using [127.0.0.1:3000](http://127.0.0.1:3000) for the verified local app because a different app can occupy IPv6 port 3000. The map and saved queries work without a database or routing service. Fresh routing setup is documented in [.env.example](.env.example), [hosted setup](docs/us-routing-service.md) and the [retained Valhalla recipe](docs/regional-routing.md). Preserve the existing locally configured key and other environment values.

For the native experiment, run `npm run dev:experiment` after the handoff's health/process checks; its qualified graph and binary already exist in this workspace. See [current experiment setup and limitations](docs/two-hour-region.md). Spatial datasets and routing graphs are not bundled.

## Development

The app uses TanStack Start, React, TypeScript, Tailwind CSS, and MapLibre. Drizzle/PostgreSQL is scaffolded; spatial database features are planned. The web app targets Vercel; the native experiment runs locally.

```sh
npm run check
npm run typecheck
npm test
npm run test:routing
npm run build
npm run build:vercel
```

See [local development](docs/local-development.md) for prerequisites and deployment details, [next steps](docs/next-steps.md) for priorities, and the [documentation index](docs/README.md) for architecture and research results.
