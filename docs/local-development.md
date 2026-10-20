# Local development and routing contract

Recovering a disconnected session: read [the agent handoff](agent-handoff.md) before starting processes or changing environment values. It explains local-only data, the dirty working tree, safe health checks and the current graph. The local experiment and hosted main page use separate APIs.

## Start the workspace

Use Node 22.12+ (this session used Node 24.5) and npm:

```bash
npm ci
npm run dev
```

Use `npm ci` only when dependencies need installation; the current workspace already has them. Open Vite's printed URL, using `http://127.0.0.1:3000` for the verified local app because another app can occupy IPv6 port 3000. No database or routing service is needed to explore the map and save queries. The default basemap uses the network. To configure services, add the relevant entries from `.env.example` to your existing `.env.local`, preserving existing values, then restart Vite. `VITE_` values are public and compiled into the client; server URLs and database credentials must remain unprefixed.

```bash
npm run check
npm run typecheck
npm test
npm run build
npm run preview -- --port 4173
```

The route generator also runs during Vite builds. Use `npm run generate-routes` if typechecking a newly added route before starting/building Vite. Never edit the generated route tree manually. This sandbox required approval to install packages, use the test runner's IPC socket, and start the preview listener; these are environment restrictions, not application requirements.

## Run the local long-range experiment

```sh
npm run dev:experiment
```

Open Vite's printed URL at `/experiment`. This starts/reuses the loopback Python/native worker with the qualified **`two-hour-region-v2` / `two-hour-region-v2-cuts`** data and enables the local server route only in the app process. `.env.local` and hosted settings are preserved. Python 3.11+, the qualified artifacts and matching macOS native binary must already exist. The launcher checks graph identity and refuses to silently reuse an older worker.

The page starts at **120m**. Try San Diego, then Riverside, Palm Springs, Ensenada or Yuma. Controls accept 1–720 whole minutes. Teal roads are sampled display intervals; counts/search use the full graph. Dashed bounds and reached red data edges make clipping visible. All five reference sources have zero detected edges at two hours; new origins near the perimeter can clip earlier. Filled contours and complete coverage remain unfinished. The local route is always disabled on Vercel. Read [the two-hour baseline, commands and measurements](two-hour-region.md).

To compare the preserved prior graph, stop the current owned worker and run `npm run dev:experiment -- --graph-run experiment-region-v1 --cuts-run experiment-region-v1-cuts`. The smaller `hour-v3 / hour-v3-cuts` pair is also preserved. A launcher stops only a worker it created; an already-running worker it reused remains alive. Use the worker terminal's Ctrl+C, or identify its process with `lsof -nP -iTCP:8787 -sTCP:LISTEN` before stopping it. Do not stop another app using port 3000; use Vite’s printed port and explicit `127.0.0.1`.

`node routing/verify-experiment.mjs --graph-run two-hour-region-v2 --run-name fresh-live-check` checks live app results against independent fields and all-cut evidence. It accepts `--port` for another Vite port and only calls loopback. The source/build/rebuild/qualification/native/cut/release commands are in the regional report. Completed runs refuse overwrite; fresh output names alone do not automatically rebind downstream dependencies. No graph download/build occurs in `dev:experiment`.

The [six-hour preflight](six-hour-preflight.md) has separate, versioned offline planning/source/census commands. It reuses cached October 14 roads and pinned Docker tools with two CPUs / 4 GiB / no swap; it does not switch this app graph or spend hosted quota. The owner profile and first storage calibration build are now complete. The exact repeat has not started; use the [memory follow-up commands](six-hour-preflight.md#memory-follow-up) after the handoff recovery checks. Inspect saved reports and process owners before launching anything, and preserve completed outputs.

## Connect the selected free hosted service

The user chose US coverage first and openrouteservice's free Standard plan. Read [selection, limits and setup](us-routing-service.md). The current workspace already has `ROUTING_PROVIDER=openrouteservice` and a server-only `ORS_API_KEY` configured locally; preserve them and do not request the key again. On a fresh setup, use the documented environment entries and restart with `npm run dev`. The hosted driving cap is 60 minutes (500 requests/day, 20/minute as checked October 16). Loading the page checks key presence without spending quota; a contour verifies actual connectivity. Five US smoke queries and the default browser contour previously succeeded; actual Vercel cloud verification is pending. See [measured hosted findings](archive/hosted-routing-verification.md). `npm run routing:verify:hosted` spends five hosted contour requests, so it is not a quota-free recovery check.

Earlier anchor, graph and memory experiments are collected in [historical routing recipes](archive/historical-routing-recipes.md). Their old defaults and admission holds apply to those named runs.

## Connect the retained Valhalla baseline

Use the pinned [California/northern-Baja local recipe](regional-routing.md) for the verified baseline. It downloads 1.32 GB of dated Southern California/Mexico inputs, merges and clips them, builds Valhalla with resource caps, and retains provenance. Read its disk/RAM assessment and boundary limitations first. From the repository root:

```bash
npm run routing:download
npm run routing:build > data/valhalla-v2/build.log 2>&1
npm run routing:up
npm run dev:routing
# Separate terminal, with the app running:
npm run routing:verify > data/valhalla-v2/verification-report.json
```

Docker must be running. `dev:routing` uses generated `data/valhalla-v2/app.env`; it does not edit existing environment files. [Measured verification](archive/routing-baseline-verification.md) distinguishes real responses from synthetic adapter tests. Use `routing:down` / `routing:up` to stop/restart without rebuilding.

For another service, follow the official [installation](https://valhalla.github.io/valhalla/start/installation/) and [graph-build](https://valhalla.github.io/valhalla/contributing/architecture/mjolnir/) instructions and record its engine/source/checksums/build settings separately. A San Diego graph needs a deliberate treatment of the Mexico boundary; regional cuts can truncate longer journeys even when the origin is inside.

Set the following server-only values for the actual service:

```dotenv
VALHALLA_URL=http://localhost:8002
VALHALLA_MAX_MINUTES=120
VALHALLA_ENGINE_VERSION=your-engine-build
VALHALLA_GRAPH_VERSION=your-osm-snapshot-and-graph-build
VALHALLA_COVERAGE=your-region-and-known-boundary-limitations
VALHALLA_COVERAGE_BOUNDS=[-119.8,30.8,-114.5,35.5]
```

The URL is the base service URL, without `/isochrone`; credentials/URL are never returned to the browser. `GET /api/reachability` checks `/status`, isochrone capability and expected engine identity; the UI enables Compute/Replay only when ready. This check does not prove graph coverage. Compute the default 60-minute query after readiness. Engine errors and warnings remain visible. Missing provenance is reported as `unrecorded`, not inferred from the basemap.

For a separate Valhalla range experiment, both engine limits and the adapter cap would need configuration, a sufficiently buffered graph and independent validation. That is not the current six-hour task: `/experiment` uses our own scoped graph/native pipeline. The Valhalla adapter's fixed 30-second timeout also remains a separate limitation. Do not use a public routing demo as the repeated-query backend.

## Configure regional PMTiles

Prepare a regional **Protomaps basemap-schema** archive using the [regional extraction guide](https://docs.protomaps.com/guide/getting-started). An arbitrary vector PMTiles archive may use different layer names and will need a matching style.

Host the archive with HTTP byte-range support and CORS when cross-origin, then set:

```dotenv
VITE_PMTILES_URL=https://your-tile-host.example/southern-california.pmtiles
```

For local experiments, a same-origin URL such as `/maps/southern-california.pmtiles` also works when the server honors range requests. Verify a Range request returns 206 and `Content-Range`, then inspect roads and labels at multiple zooms in the browser. Keep large archives outside Git. `*.pmtiles` and common local dataset directories are ignored. Do not accidentally package a huge archive into a Vercel deployment.

When `VITE_PMTILES_URL` is set, it takes precedence over `VITE_MAP_STYLE_URL`. Otherwise the default style is `https://tiles.openfreemap.org/styles/liberty`; a custom MapLibre style URL can replace it. For PMTiles, optional `VITE_MAP_GLYPHS_URL` and `VITE_MAP_SPRITE_URL` let you self-host the Protomaps fonts/sprites. Default assets remain online, so a local archive alone does not make the map offline.

## API

### Local experimental API

`GET /api/experiment` returns the qualified worker's nonsecret identity/bounds/range/model metadata. `POST /api/experiment` accepts exactly:

```json
{
  "origin": { "lat": 32.7157, "lon": -117.1611 },
  "budgetMinutes": 120
}
```

The app must run with `LOCAL_ROUTING_EXPERIMENT=1`; `npm run dev:experiment` sets this only in its child process. Any truthy `VERCEL` disables this API. The server calls only `127.0.0.1:8787` with no hosted retries/fallback. GET has a three-second worker timeout; POST waits at most 90 seconds. Invalid inputs, budgets outside 1–720, outside-region origins or no supported road within 100 m produce 400. Disabled/unavailable/loading/failed/timed-out routing produces 503. Results include sampled roads, audited-cut warnings and separate timings; `coverageVerified` stays false.

The selected graph/cuts, query example, expected edge counts and fresh live-verification flags are in [the handoff](agent-handoff.md). Changing `.env.local` or raising Valhalla/provider limits is unnecessary for this local endpoint.

### Main-page provider API

`GET /api/reachability` returns nonsecret configuration, provider, maximum budget and coverage labels, with `Cache-Control: no-store`. Valhalla checks service status/capability/version. Openrouteservice reports key presence and `health: unchecked`; its public API does not expose the self-hosted status endpoint, and GET deliberately spends no contour quota. Hosted provenance comes from successful responses, not configured local graph labels.

`POST /api/reachability` accepts exactly this version-1 shape:

```json
{
  "version": 1,
  "origin": { "lat": 32.7157, "lon": -117.1611 },
  "mode": "auto",
  "direction": "outbound",
  "metric": "time",
  "budgetMinutes": 60
}
```

A successful response includes a run ID, timestamp, normalized query, validated GeoJSON contours (including engine-supplied snapped-location features and warnings), and metadata. Metadata contains engine/graph labels, unknown completeness, speed sources, simplification/denoise settings, upstream bytes, and server timings. The browser adds request and source-to-idle timings to its saved summary.

| Status | Meaning |
| --- | --- |
| 400 | Malformed request JSON |
| 422 | Invalid query/unsupported semantics, outside declared regional origin bounds, or budget above the selected provider maximum |
| 429 | Hosted provider request quota reached; no automatic retry or paid fallback |
| 503 | Selected provider credential/URL missing or routing configuration invalid |
| 502 | Engine/network failure, engine rejection, or invalid/empty polygon response |
| 504 | Upstream timeout |
| 408 | Client signal aborted during the upstream request |

`engineRoundTripMs` measures fetch through reading the upstream body, including engine search/contouring and network. `decodeValidateMs` measures JSON decoding and Zod validation. `serverTotalMs` ends before response serialization/delivery. `clientRequestMs` includes browser HTTP, JSON parsing, and result validation. `sourceToMapIdleMs` begins immediately before updating the map source and includes pending tile work and camera fitting; it excludes map startup when a result arrives before the map is ready. None is an isolated graph-search or precise first-paint measurement.

History is localStorage, capped at 20 entries, with no geometry or shared persistence. JSON exports contain `{ "version": 1, "runs": [...] }`; there is no import flow yet. Replay uses the current graph/configuration, which may differ from the saved run. Browser storage failures produce a visible message and leave in-memory export available. The API has no authentication, rate limiting, global scheduling, or persistent jobs yet; address these before exposing an expensive routing service to public traffic.

API implementation references: [Valhalla isochrones](https://valhalla.github.io/valhalla/api/isochrone/), [Valhalla costing options](https://valhalla.github.io/valhalla/api/route/api-reference/), [MapLibre installation and Vite worker setup](https://maplibre.org/maplibre-gl-js/docs/), [PMTiles integration](https://docs.protomaps.com/pmtiles/maplibre), [Protomaps styling assets](https://docs.protomaps.com/basemaps/maplibre), and [OpenFreeMap quick start](https://openfreemap.org/quick_start/).

## Profiles and Vercel packaging

The retained **Valhalla build's** default is `routing/profiles/california-baja-v2.json` with `data/valhalla-v2/`; this is separate from the local experiment's `two-hour-region-v2` default. The shared source cache remains `data/valhalla/sources/`. Select other Valhalla profiles with `VALHALLA_MANIFEST` and a separate `VALHALLA_DATA_DIR`. An optional `VALHALLA_SOURCE_DIR` changes the cache. These variables do not edit `.env.local`. See [Malta commands and retained evidence](archive/routing-expansion-verification.md). Stop/restart the matching app/service when switching Valhalla graphs; Compose uses port 8002.

```bash
npm run build:vercel
npm run check:vercel
```

The second command requires the selected real graph service. It invokes the generated Vercel handler locally and saves `vercel-verification.json` in its data directory. No deployment is performed. Graphs and `.env` files are excluded from upload/bundling; Vercel needs a separately reachable routing backend or a qualified native implementation. The selected path is [free hosted US routing](us-routing-service.md); worldwide expansion is deferred.
