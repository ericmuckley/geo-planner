# Local development and routing contract

Recovering a disconnected session: read [the agent handoff](agent-handoff.md) before starting processes or changing environment values. It explains local-only data, the dirty working tree, safe health checks and the current graph. The main page defaults to the bundled coarse estimator; the hosted provider and local experiment use separate APIs.

## Start the workspace

Use Node 22.12+ (this session used Node 24.5) and npm:

```bash
npm ci
npm run dev
```

Use `npm ci` only when dependencies need installation; the current workspace already has them. Open Vite's printed URL, using `http://127.0.0.1:3000` for the verified local app because another app can occupy IPv6 port 3000. No database, routing service, API key, Python or Docker is needed to compute coarse 1–12-hour contours, explore the map and save queries. The compact grid is included in source; the large ignored research datasets are unnecessary for this default path. The default basemap uses the network. The cloud `DATABASE_URL` is stored in ignored `.env`; `.env.local` retains the optional routing settings and has no database override. Preserve these values and restart Vite after service configuration changes. `VITE_` values are public and compiled into the client; server URLs and database credentials must remain unprefixed.

```bash
npm run check
npm run typecheck
npm test
npm run build
npm run preview -- --port 4173
```

The route generator also runs during Vite builds. Use `npm run generate-routes` if typechecking a newly added route before starting/building Vite. Never edit the generated route tree manually. This sandbox required approval to install packages, use the test runner's IPC socket, and start the preview listener; these are environment restrictions, not application requirements.

## Cloud database configuration

The user configured `DATABASE_URL` in Vercel and ignored local `.env`. The previous localhost value was removed from `.env.local`, preserving the optional routing provider/key. Local development and Drizzle commands now resolve the cloud URL. A read-only `SELECT 1` through `src/db/index.ts` passed on October 22. The additive `drizzle/0000_saved_history.sql` migration is now reviewed and applied to this initially empty cloud database: it creates `saved_histories`, the existing starter `todos` table, and Drizzle migration bookkeeping. No PostgreSQL process was listening on local port 5432 during the switch.

Drizzle loads `.env.local` before `.env`; Vite also gives `.env.local` priority over `.env`. Leave `DATABASE_URL` out of `.env.local`, preserve the provider's connection/SSL parameters, and keep it server-only (no `VITE_` prefix). A pre-existing shell `DATABASE_URL` can override file values. Both env files are ignored by Git and Vercel uploads; the deployed app uses Vercel's configured environment, not the local files. Keep existing local data; no local database data copy or database deletion was performed.

Use `npm run db:generate` to generate a migration from `src/db/schema.ts`, review it, then apply the intended migrations with `npm run db:migrate`. Do not run `db:push` as a connectivity check. Migrations run separately from the web build. The existing configured cloud database already has the initial migration; a new database needs it before cloud history works. The coarse estimator still works independently of database availability.

`npm run db:verify` performs a live integration check: it writes one generated test owner, verifies fresh-request restoration, browser isolation, concurrent merges and the twenty-entry bound, then deletes only that test owner. It needs database network access and is not read-only. After `npm run build:vercel`, `npm run db:verify -- --vercel` repeats the same integration check through the generated Vercel handler locally, including real PostgreSQL queries; it does not deploy a site. Do not print connection strings or browser cookie values. The pool reuses up to three connections per process, with five-second connection/statement timeouts and ten-second idle timeout.

## Coarse estimator checks

```sh
npm run test:coarse-data
npm run routing:verify:coarse
npm run build:vercel
npm run check:coarse:vercel
```

The geometry command runs six small fixtures; `routing:verify:coarse` runs 42 sequential in-process cases at 6/10/12h across fourteen representative origins; it does not call a routing provider. The last command executes the generated Vercel handler locally with outbound fetches rejected, checks enabled coarse estimates, disabled local research routing, bundle size and server-only data packaging. Build first. Neither command is a cloud deployment, a production memory/latency benchmark or real driving-time calibration. `node --import tsx --test src/server/*.test.ts` is equivalent to the server test command when this sandbox blocks the `tsx` CLI IPC socket.

## Coarse travel-cost comparison

The active v3 candidate can be compared against unchanged v2 and both saved sets without routing requests:

```sh
npm run routing:compare:coarse:candidate
```

An optional artifact path follows `--`. Expected v3: original eleven point costs unchanged; on the same 23 previously finite regional cases, two improve, none regress and mean difference changes 37.7296m → 36.8934m. The formerly missing 24th case is reported separately (145.9848m model / 61.2680m reference). No destination is unshaded. V3 point access uses the same geography-checked direct/retained-road fallback attachments as departure, taking the cheapest supported arrival. These are regression diagnostics, not national accuracy validation. [V3 evidence](evidence/coarse-v3-2026-10-22/README.md).

The broader unchanged-v2 validation is now saved: 24 routes from twelve origins, 23 paired finite arrivals and one unreached shore destination. Replay and inspect it **without any network/service/database**:

```sh
npm run routing:compare:coarse:regional
node --import tsx scripts/inspect-coarse-regional.ts
```

Expected baseline: 24 samples, 23 paired finite cases, one unreached case in each model, 18 improved approximate point cases and five regressions; point mean absolute differences 52.9989m v1 / 37.7296m v2. All means explicitly exclude the unreached case. [Plan, raw references and interpretation](evidence/coarse-regional-2026-10-22/README.md). The command enforces the recorded v2 hash; use a separately versioned run when evaluating another model.

Deliberate new reference acquisition uses `npm run routing:compare:coarse:regional -- --capture <unused-directory>` against fixed loopback port 8002, saving the plan/model identities before requests and recording raw responses exclusively. It makes one status request plus 24 routes with 20-second deadlines, no redirects or hosted fallback. `--resume <incomplete-directory>` reads matching saved records and appends only missing responses, never overwriting a failed/successful response. Do not run capture merely to validate docs. An existing service and ignored regional graph are needed only for capture, not replay; do not build a graph to run routine checks. The first run's sandbox denial/interrupted finite-cost assertion are preserved in its evidence.

For strict diagnostic TypeScript checking (these scripts are outside the app's `tsconfig.json` include list):

```sh
npx tsc --ignoreConfig --noEmit --target ES2022 --module ESNext --moduleResolution bundler --skipLibCheck --strict --types node scripts/compare-coarse-regional.ts scripts/inspect-coarse-regional.ts scripts/compare-coarse-candidate.ts
```

For the original eleven-case v2 diagnostic, use saved reference responses offline (no service or quota):

```sh
npm run --silent routing:compare:coarse:v2 > /tmp/geo-planner-coarse-v2-new.json
```

An optional artifact path follows `--`, e.g. `npm run --silent routing:compare:coarse:v2 -- data/coarse-quality/candidate.json`. Use unused output names. This reproduces v1 cell labels, compares candidate labels at their representative road positions, adds a supplementary 25 km/h straight destination-access comparison for both, and reports shading. The preserved v2 improves all eleven cases under both measures; this is a diagnostic sample that informed the model, not national calibration. [V2 evidence](evidence/coarse-v2-2026-10-22/README.md).

The original live **v1 baseline** command remains available with the retained regional Valhalla service already running on loopback port 8002:

```sh
curl --fail --silent --max-time 5 http://127.0.0.1:8002/status
npm run --silent routing:compare:coarse > /tmp/geo-planner-coarse-comparison-new.json
```

Use an unused output name. The command compares eleven public Southern California destinations from the default San Diego origin with the bundled v1 grid field. It makes one status request and eleven route requests to fixed `127.0.0.1:8002`, with deadlines and no hosted fallback, database access or graph build. Do not start a new graph build to run it. It records raw requests/responses, reference status, cell-center travel costs and whether the destination cell is shaded land. The v1 artifact path is explicit in `scripts/compare-coarse.ts`; when evaluating a new model, select that candidate's artifact deliberately.

These are model-to-model diagnostics, not live driving-time truth or national accuracy validation. Successful execution means the comparison completed, not that accuracy passed. The first run found eleven slower grid estimates and an unshaded Calexico border cell; [preserved baseline findings](coarse-estimator.md#first-regional-travel-cost-comparison). The user reports a working Vercel deployment, but its URL and independent hosted measurements remain pending.

## Regenerate the coarse grid

This is optional for normal development/deployment: the prepared JSON is a source file. To reproduce it, use Python 3.11+ standard library, the unchanged bundled v2 artifact and pinned public-domain Natural Earth inputs. V3 reads the cached roads and v2 country/lake geometry; the full three-source setup below is about 68.8 MB and also supports older builders. Reuse existing pinned downloads:

```sh
mkdir -p data/coarse-sources/natural-earth-v5.1.2
curl --fail --location https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_roads.geojson --output data/coarse-sources/natural-earth-v5.1.2/roads.geojson
curl --fail --location https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_admin_0_countries.geojson --output data/coarse-sources/natural-earth-v5.1.2/countries.geojson
curl --fail --location https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_lakes.geojson --output data/coarse-sources/natural-earth-v5.1.2/lakes.geojson
npm run data:coarse
```

The v3 builder enforces the unchanged bundled v2 artifact and roads-source hashes before writing `src/server/data/coarse-grid-v3.json`. Expected output: **4,673,811 bytes**, SHA-256 `8cfa5616b52138c16d5a8cb8f84fd1ee4345f7e4026e88c104365cad25c523e0`. To check repeatability without replacing the active file:

```sh
python3 -B scripts/build-coarse-grid-v3.py --output data/coarse-quality/grid-v3-repeat.json
```

Preserve v1/v2 artifacts and builders; v3 refuses those output names. It leaves v2 land mask, road anchors, road links/times and speeds unchanged, adding mixed-cell representatives/checked local links and access points from each retained road anchor's own source visit. Raw inputs remain ignored and runtime needs none of them. `python3 -B scripts/build-coarse-grid-v2.py --speed-profile original --output data/coarse-quality/v2-original-speeds-new.json` remains an optional v2 isolation diagnostic; it does not regenerate v3. Do not rerun older builders/producers just to validate docs. [Model and provenance](coarse-estimator.md#v3-general-shore-connectivity).

## Run the local long-range experiment

```sh
npm run dev:experiment
```

Open Vite's printed URL at `/experiment`. This starts/reuses the loopback Python/native worker with the qualified **`two-hour-region-v2` / `two-hour-region-v2-cuts`** data and enables the local server route only in the app process. `.env.local` and hosted settings are preserved. Python 3.11+, the qualified artifacts and matching macOS native binary must already exist. The launcher checks graph identity and refuses to silently reuse an older worker.

The page starts at **120m**. Try San Diego, then Riverside, Palm Springs, Ensenada or Yuma. Controls accept 1–720 whole minutes. Teal roads are sampled display intervals; counts/search use the full graph. Dashed bounds and reached red data edges make clipping visible. All five reference sources have zero detected edges at two hours; new origins near the perimeter can clip earlier. Filled contours and complete coverage remain unfinished. The local route is always disabled on Vercel. Read [the two-hour baseline, commands and measurements](two-hour-region.md).

To compare the preserved prior graph, stop the current owned worker and run `npm run dev:experiment -- --graph-run experiment-region-v1 --cuts-run experiment-region-v1-cuts`. The smaller `hour-v3 / hour-v3-cuts` pair is also preserved. A launcher stops only a worker it created; an already-running worker it reused remains alive. Use the worker terminal's Ctrl+C, or identify its process with `lsof -nP -iTCP:8787 -sTCP:LISTEN` before stopping it. Do not stop another app using port 3000; use Vite’s printed port and explicit `127.0.0.1`.

`node routing/verify-experiment.mjs --graph-run two-hour-region-v2 --run-name fresh-live-check` checks live app results against independent fields and all-cut evidence. It accepts `--port` for another Vite port and only calls loopback. The source/build/rebuild/qualification/native/cut/release commands are in the regional report. Completed runs refuse overwrite; fresh output names alone do not automatically rebind downstream dependencies. No graph download/build occurs in `dev:experiment`.

The [six-hour preflight](six-hour-preflight.md) has separate, versioned offline planning/source/census commands. It reuses cached October 14 roads and pinned Docker tools with two CPUs / 4 GiB / no swap; it does not switch this app graph or spend hosted quota. The outgoing-index owner profile, exact build/rebuild, result verification and evidence collection are complete. Both builds reproduce the qualified payloads at 2.415/2.416 GiB. The revised partial-source screen remains held at 9.290 GiB with margin; the proposed qualification owner/lifetime diagnostic was never started and is now parked after the user’s coarse nationwide product reset. The coarse nationwide MVP is implemented independently; cloud persistence is implemented, and the current priority is measured accuracy refinement, with independent hosted verification when the URL is available. Existing services and environment configuration remain unchanged. Read the [memory follow-up](six-hour-preflight.md#memory-follow-up) and [next steps](next-steps.md). Inspect saved reports and process owners before launching anything; do not rerun completed producers or collectors.

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

### Saved history API

`GET /api/saved-runs` restores this browser's cloud history. With no `DATABASE_URL`, it returns `{ "configured": false, "runs": [] }`, and the UI keeps local history available. A configured database returns `{ "configured": true, "runs": [...] }`. Database failure returns 503 with a useful, credential-free message.

`POST /api/saved-runs` accepts a JSON array of 1–20 validated saved query/run summaries, up to 256 KiB. Each summary has the existing ID, timestamp, query, optional coarse/connected model, optional model metadata and browser timings. Contour geometry is not stored. The server merges IDs, orders newest first and keeps twenty entries under a row lock, preventing concurrent tabs from overwriting saves. Success returns the retained history. Invalid data returns 422, invalid/oversized JSON 400, non-JSON content 415, and cross-origin/cross-site requests 403. Responses use `Cache-Control: private, no-store` and `Vary: Cookie`.

Ownership uses an unguessable server-issued `geo-planner-history` cookie (HttpOnly, SameSite=Lax, path `/`, one-year lifetime; Secure over HTTPS). PostgreSQL stores only its SHA-256 hash and a bounded JSON history row. There is no public global history listing, account or cross-device sync. Clearing cookies loses the browser's cloud-history identity; orphaned histories are not yet purged automatically. The cookie is a bearer credential: never print or commit it.

New query/run saves back up automatically. Existing localStorage entries stay local until the user selects **Back up browser history**. The UI merges cloud and local records, labels Cloud saved/Browser only, keeps export/local saving available, and offers retry when cloud access fails. Failed saves remain queued within the tab; after reload, local-only entries can be uploaded with the backup button. Query model selection survives cloud restoration and controls Load/Replay; old records infer the model from metadata or current selection. Map-idle timing updates remain in the local cache unless that summary is backed up again.

The [saved-history evidence](evidence/saved-history-2026-10-22/README.md) preserves this milestone's measurements. Its source hashes are a dated implementation snapshot, not a frozen routing recipe: product code can evolve normally, and later source differences should be interpreted as changes rather than restored blindly. Preserve the original evidence records and the separately sealed detailed-routing producers.

### Default coarse API

`GET /api/estimate` returns ready configuration with `provider: coarse`, `minMinutes: 60`, `maxMinutes: 720`, grid/model versions and generalized US bounds. `POST /api/estimate` uses the same version-1 query shape as the provider API below, with a whole-minute budget from 60 to 720. It returns filled MultiPolygon GeoJSON, approximation warnings and source/model metadata. Invalid geography/budgets return 422, malformed or oversized JSON returns 400, and an already-cancelled request returns 408. Results/config use `Cache-Control: no-store`.

No environment variables are required. It is enabled on Vercel and never calls a worker, database or routing service. It searches an assumed-speed grid, including overland travel without roads; read [the coarse model](coarse-estimator.md) before interpreting the shading. `searchMs` includes geographic validation and origin attachment; `contourMs` traces the reached cells. Server, HTTP/browser and map-idle timings have distinct scopes.

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

### Optional connected-provider API

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

History uses localStorage plus the optional browser-private PostgreSQL backup described above, capped at 20 summaries per owner, with no geometry. JSON exports contain `{ "version": 1, "runs": [...] }`; there is no import flow yet. Replay uses the current graph/configuration, which may differ from the saved run. Browser storage failures produce a visible message and leave in-memory export available. The API has no authentication, rate limiting, global scheduling, or persistent jobs yet; address these before exposing an expensive routing service to public traffic.

API implementation references: [Valhalla isochrones](https://valhalla.github.io/valhalla/api/isochrone/), [Valhalla costing options](https://valhalla.github.io/valhalla/api/route/api-reference/), [MapLibre installation and Vite worker setup](https://maplibre.org/maplibre-gl-js/docs/), [PMTiles integration](https://docs.protomaps.com/pmtiles/maplibre), [Protomaps styling assets](https://docs.protomaps.com/basemaps/maplibre), and [OpenFreeMap quick start](https://openfreemap.org/quick_start/).

## Profiles and Vercel packaging

The retained **Valhalla build's** default is `routing/profiles/california-baja-v2.json` with `data/valhalla-v2/`; this is separate from the local experiment's `two-hour-region-v2` default. The shared source cache remains `data/valhalla/sources/`. Select other Valhalla profiles with `VALHALLA_MANIFEST` and a separate `VALHALLA_DATA_DIR`. An optional `VALHALLA_SOURCE_DIR` changes the cache. These variables do not edit `.env.local`. See [Malta commands and retained evidence](archive/routing-expansion-verification.md). Stop/restart the matching app/service when switching Valhalla graphs; Compose uses port 8002.

```bash
npm run build:vercel
npm run check:vercel
```

`check:vercel` is the retained Valhalla/provider check: it requires that selected graph service, invokes the generated handler locally and saves `vercel-verification.json` in its data directory. For the default coarse model, use `npm run check:coarse:vercel` instead; no routing service is required. Neither check deploys anything. The compact coarse artifact is bundled server-side, while large research graphs and environment files are excluded. Only the optional connected model requires a reachable provider. Actual cloud verification remains open.
