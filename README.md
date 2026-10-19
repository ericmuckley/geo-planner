# Geo Planner

A mapping and routing research workspace for exploring where you can drive within a time budget. The goal is fast, US-wide **10–12-hour reachability**, with gas stations, public lands, and elevation overlays.

## What works today

- Interactive MapLibre map with origin/time controls, browser-local saved queries, JSON exports, and query timings.
- Driving isochrones through openrouteservice (up to 60 minutes) or self-hosted Valhalla.
- An offline OpenStreetMap routing pipeline in Python/C++, with reproducible graph builds and independent correctness and resource checks.
- A local `/experiment` view showing sampled reachable roads and data-edge warnings, tested at 90/120 minutes in the San Diego–northern Baja region.

Complete long-range coverage and filled local contours remain unfinished. POI, public-land, and elevation layers are planned. See [current progress](docs/progress.md).

## Run locally

Requires Node.js 22.12+ and npm.

```sh
npm install
npm run dev
```

Open [localhost:3000](http://localhost:3000). The map and saved queries work without a database or routing service. To compute contours, configure routing in `.env.local` using [.env.example](.env.example): [hosted setup](docs/us-routing-service.md) or [self-hosted Valhalla](docs/regional-routing.md).

For the native experiment, run `npm run dev:experiment` after preparing its regional graph and native binary; see [experiment setup and limitations](docs/local-routing-experiment.md). Spatial datasets and routing graphs are not bundled.

## Development

The app uses TanStack Start, React, TypeScript, Tailwind CSS, and MapLibre. Drizzle/PostgreSQL is scaffolded; spatial database features are planned. The web app targets Vercel; the native experiment runs locally.

```sh
npm run check
npm run typecheck
npm test
npm run test:routing
npm run build
```

See [local development](docs/local-development.md) for prerequisites and deployment details, [next steps](docs/next-steps.md) for priorities, and the [documentation index](docs/README.md) for architecture and research results.
