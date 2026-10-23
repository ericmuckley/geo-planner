# Local development and routing contract

Recovering a disconnected session: read [the agent handoff](agent-handoff.md) before starting processes or changing environment values. It explains local-only data, the dirty working tree, safe health checks and the current graph. The main page defaults to the bundled coarse estimator; the hosted provider and local experiment use separate APIs.

## Start the workspace

Use Node 22.12+ (this session used Node 24.5) and npm:

```bash
npm ci
npm run dev
```

Use `npm ci` only when dependencies need installation; the current workspace already has them. Open Vite's printed URL, using `http://127.0.0.1:3000` for the verified local app because another app can occupy IPv6 port 3000. No database, routing service, API key, Python or Docker is needed to compute coarse 30-minute–12-hour contours, explore the map and save queries. The compact grid is included in source; the large ignored research datasets are unnecessary for this default path. The default basemap uses the network. The cloud `DATABASE_URL` is stored in ignored `.env`; `.env.local` retains the optional routing settings and has no database override. Preserve these values and restart Vite after service configuration changes. `VITE_` values are public and compiled into the client; server URLs and database credentials must remain unprefixed.

```bash
npm run check
npm run typecheck
npm test
npm run build
npm run preview -- --port 4173
```

The route generator also runs during Vite builds. Use `npm run generate-routes` if typechecking a newly added route before starting/building Vite. Never edit the generated route tree manually. This sandbox required approval to install packages, use the test runner's IPC socket, and start the preview listener; these are environment restrictions, not application requirements.

## Time slider

The main page defaults to **120 minutes** and uses one native slider from **30 to 720 whole minutes** for the coarse model. Pointer movement/key repeats preview the human-readable time without requests; pointer release/key-up/blur commits a pending value once. Pointer capture covers release outside the control. Automatic requests use the existing cancellation/sequence guard and show loading on the map/status. The optional submit button remains for coordinate edits/retry. The connected model keeps its own provider minimum/maximum and valid default.

`GET /api/estimate` now reports `minMinutes: 30`; `POST` accepts 30 and rejects 29. No graph/data/hash, env, dependency, schema or migration change. Existing saved queries/replay still work. The unchanged persistence suite need not repeat.

```sh
npm run check
npm run typecheck
node --import tsx --test src/server/*.test.ts
npm run build
npm run build:vercel
npm run check:coarse:vercel
```

Checks pass locally, including a generated-handler 30-minute result. For browser QA, reload once after builds/docs finish, confirm default120/min30/max720, click/release the track (375 minutes at its center), observe `Updating area…`, and wait for matching run metadata without using submit. Test Home→30, End→720, rapid End/ArrowLeft→719, reset→120 and keyboard auto-computation, then fixture Cloud saved→reload→Replay. Inspect only new public fixture history. [Evidence](evidence/time-slider-2026-10-23/checks.json).

The public live configuration still advertises min60. After publishing this update, use the existing hosted verifier; it deliberately requires min30. No compute/provider/history request was made during the one configuration observation. Native range controls need no new UI dependency.

## Fixed nonregional frontier plan

[The frozen 48-query plan](evidence/coarse-holdout-plan-2026-10-23/README.md) and its hashes are prepared before reference calls. Reproduce offline into a fresh ignored directory only when preparation changes:

```sh
node --import tsx scripts/prepare-coarse-holdout.ts data/coarse-quality/coarse-holdout-plan-new
npx tsc --ignoreConfig --noEmit --target ES2022 --module ESNext --moduleResolution bundler --skipLibCheck --strict --types node scripts/prepare-coarse-holdout.ts
```

Expected plan SHA `77360fec0906c5a3eeedc533eef55cbe8557659266c25badcc4b924412e4271e`, eight public origins × three horizons × two sides = 48 requests, zero provider/DB calls or key reads. Existing runs `data/coarse-quality/coarse-holdout-plan-v1/` and `-repeat/` match byte for byte. Preparation only searches bundled v8; its diagnostic 750-minute labels supply points outside 720 without changing the public API. No raw sources or Python are needed.

A bounded capture/replay helper is the next implementation task; none exists yet and no fresh references were requested. Obtain explicit authorization for the 48-request, zero-paid-spend cap before calls. The plan records the new HeiGIT Directions endpoint, current public limits/terms, exact bodies, no retries and all scoring/failure denominators. It is a model-conditioned frontier check, not a random national accuracy sample. The optional connected adapter still uses the legacy ORS host, announced for retirement November 2–6, 2026; follow up with a focused endpoint migration and mock checks before relying on it then. [Primary migration notice](https://ask.openrouteservice.org/t/deprecating-api-openrouteservice-org-in-favour-of-api-heigit-org/7912).

## Speed Insights

The shared root at [src/routes/__root.tsx](../src/routes/__root.tsx) calls `injectSpeedInsights()` from `@vercel/speed-insights` in a mount-only `useEffect`. Effects run only in the browser, and the SDK prevents duplicate scripts. The package and lockfile already include version 2.0.0; no app environment variable is needed.

After deploying the change to Vercel, visit the app and verify a successful `/_vercel/speed-insights/script.js` request in the browser Network panel, then inspect the project's **Speed Insights** dashboard as visitor measurements arrive. The installed SDK uses Vercel's debug script during development. Local checks/builds do not verify hosted collection. See [Vercel's quickstart](https://vercel.com/docs/speed-insights/quickstart).

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

The geometry command runs nineteen small fixtures; `routing:verify:coarse` runs 42 sequential in-process cases at 6/10/12h across fourteen representative origins; it does not call a routing provider. The last command executes the generated Vercel handler locally with outbound fetches rejected, checks enabled coarse estimates, disabled local research routing, bundle size and server-only data packaging. Build first. Neither command is a cloud deployment, a production memory/latency benchmark or real driving-time calibration. `node --import tsx --test src/server/*.test.ts` is equivalent to the server test command when this sandbox blocks the `tsx` CLI IPC socket.

## Coarse travel-cost comparison

The candidate comparison now requires an explicit artifact path and uses **v4** as its baseline. It checks all 35 v4 point costs against the preserved v4 evidence before comparing both saved sets, without routing requests. The [offline candidate](#offline-augmentation-candidate) must exist first:

```sh
npm run routing:compare:coarse:candidate -- data/coarse-quality/census-augmentation-pilot-v1/grid.json
```

Expected pilot: one of eleven original cases improves, ten unchanged (22.181 → 21.944 min mean absolute reference difference); six of all 24 broader cases improve, eighteen unchanged (34.234 → 31.204 min). None regress and all remain reached/shaded. These development sets do not establish national accuracy. The earlier v3 → v4 comparison remains in [preserved v4 evidence](evidence/coarse-v4-2026-10-22/README.md).

For the completed access diagnosis, use the existing pinned roads cache (no download or routing service):

```sh
node --import tsx scripts/inspect-coarse-access.ts
# Active v4 decomposition:
node --import tsx scripts/inspect-coarse-access.ts src/server/data/coarse-grid-v4.json docs/evidence/coarse-v4-2026-10-22/comparison.json
```

Expected: all 35 saved point costs for the selected model and reconstructed endpoint/road/local path sums match; 23 distinct endpoints have approximate nearest-source-road observations. This reads `data/coarse-sources/natural-earth-v5.1.2/roads.geojson`, checks its recorded hash and the v3 artifact identity, and prints JSON without writing inputs or calling any service. Raw source data are needed only for this diagnostic, never runtime deployment. [Findings and scoped next candidate](evidence/coarse-access-2026-10-22/README.md).

The broader unchanged-v2 validation is now saved: 24 routes from twelve origins, 23 paired finite arrivals and one unreached shore destination. Replay and inspect it **without any network/service/database**:

```sh
npm run routing:compare:coarse:regional
node --import tsx scripts/inspect-coarse-regional.ts
```

Expected baseline: 24 samples, 23 paired finite cases, one unreached case in each model, 18 improved approximate point cases and five regressions; point mean absolute differences 52.9989m v1 / 37.7296m v2. All means explicitly exclude the unreached case. [Plan, raw references and interpretation](evidence/coarse-regional-2026-10-22/README.md). The command enforces the recorded v2 hash; use a separately versioned run when evaluating another model.

Deliberate new reference acquisition uses `npm run routing:compare:coarse:regional -- --capture <unused-directory>` against fixed loopback port 8002, saving the plan/model identities before requests and recording raw responses exclusively. It makes one status request plus 24 routes with 20-second deadlines, no redirects or hosted fallback. `--resume <incomplete-directory>` reads matching saved records and appends only missing responses, never overwriting a failed/successful response. Do not run capture merely to validate docs. An existing service and ignored regional graph are needed only for capture, not replay; do not build a graph to run routine checks. The first run's sandbox denial/interrupted finite-cost assertion are preserved in its evidence.

For strict diagnostic TypeScript checking (these scripts are outside the app's `tsconfig.json` include list):

```sh
npx tsc --ignoreConfig --noEmit --target ES2022 --module ESNext --moduleResolution bundler --skipLibCheck --strict --types node scripts/compare-coarse-regional.ts scripts/inspect-coarse-regional.ts scripts/compare-coarse-candidate.ts scripts/inspect-coarse-access.ts
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

These are model-to-model diagnostics, not live driving-time truth or national accuracy validation. Successful execution means the comparison completed, not that accuracy passed. The first run found eleven slower grid estimates and an unshaded Calexico border cell; [preserved baseline findings](coarse-estimator.md#first-regional-travel-cost-comparison). V4 is committed at `637746c` and independently verified on Vercel; cloud peak memory and cold/warm classification remain unmeasured.

## Hosted v4 verification

This heading preserves historical links. [Hosted v4 proof](evidence/coarse-hosted-2026-10-22/README.md) remains unchanged; v8 is committed at `ee8809f` and a public configuration read confirms its model with the prior 60-minute minimum. **The current verifier expects v8 with the new 30-minute minimum**, so run after publishing the local slider update. Run deliberately after the new deployment is Ready:

```sh
node --import tsx scripts/verify-coarse-deployment.ts https://geo-planner-orcin.vercel.app
npx tsc --ignoreConfig --noEmit --target ES2022 --module ESNext --moduleResolution bundler --skipLibCheck --strict --types node scripts/verify-coarse-deployment.ts
```

It makes fifteen app requests, checks saved v8 counts/model/notices and errors/disabled research/no-cookie history, sends no history writes/cookies and calls no connected-routing endpoint. Old v6/v7 fail the version assertion; pre-slider v8 fails the updated minimum assertion. No key/env change is needed. First/repeat HTTP calls do not establish cold/warm state, isolated search time, load or peak memory. Do not run it for documentation alone. [Local v8 proof](evidence/coarse-finer-2026-10-23/README.md).

## Offline road-source pilot

This optional historical source-coverage/size diagnostic changes no active dataset. Python 3.11+ reads a pinned Census ZIP and imports a hash-verified PyShp 2.3.1 wheel directly from ignored data; no pip/global/app installation or env variable is required. Both files are already cached. On a fresh clone, fetch only missing files at the recorded lock paths:

```sh
mkdir -p data/coarse-sources/tiger-2026 data/coarse-tools/tiger-2026
test -f data/coarse-sources/tiger-2026/tl_2026_06_prisecroads.zip || curl --fail --location --proto '=https' https://www2.census.gov/geo/tiger/TIGER2026/PRISECROADS/tl_2026_06_prisecroads.zip --output data/coarse-sources/tiger-2026/tl_2026_06_prisecroads.zip
test -f data/coarse-tools/tiger-2026/pyshp-2.3.1-py2.py3-none-any.whl || curl --fail --location --proto '=https' https://files.pythonhosted.org/packages/98/2f/68116db5b36b895c0450e3072b8cb6c2fac0359279b182ea97014d3c8ac0/pyshp-2.3.1-py2.py3-none-any.whl --output data/coarse-tools/tiger-2026/pyshp-2.3.1-py2.py3-none-any.whl
python3 -B scripts/inspect-coarse-road-source.py \
  --source-lock docs/evidence/coarse-source-2026-10-22/source.json \
  --tool-lock docs/evidence/coarse-source-2026-10-22/tool.json
```

The script checks both hashes before import/read, preserves multipart boundaries and verifies geographic NAD83/record counts. Expected: 7,350 records, 1,245,029 points, 19/23 nearer endpoints and four farther; raw selected owner geometry is 4,497,541 JSON bytes for this one state. These are approximate source observations, not a new routing graph/ETA or national-size proof. [Findings, locks, source alternatives and next implementation](evidence/coarse-source-2026-10-22/README.md). Preserve current cached files; a mismatch is an error to investigate rather than overwrite.

## Offline augmentation candidate

The generic Census adapter and packed geometry pilot are preserved historical inputs; they change no active import. The ignored candidate already exists at `data/coarse-quality/census-augmentation-pilot-v1/grid.json`, with an identical repeat under `census-augmentation-pilot-v1-repeat/`. Fresh clones need the cached ZIP/wheel from the previous section. Build into a new directory; overwrites and production-data output paths are refused:

```sh
mkdir -p data/coarse-quality/census-augmentation-replay-new
python3 -B scripts/build-coarse-augmentation.py \
  --source-lock docs/evidence/coarse-source-2026-10-22/source.json \
  --tool-lock docs/evidence/coarse-source-2026-10-22/tool.json \
  --output data/coarse-quality/census-augmentation-replay-new/grid.json \
  > data/coarse-quality/census-augmentation-replay-new/build.json
node --import tsx scripts/verify-coarse-augmentation.ts \
  data/coarse-quality/census-augmentation-replay-new/grid.json \
  data/coarse-quality/census-augmentation-replay-new/build.json
node --import tsx scripts/compare-coarse-candidate.ts \
  data/coarse-quality/census-augmentation-replay-new/grid.json \
  > data/coarse-quality/census-augmentation-replay-new/comparison.json
node --import tsx scripts/inspect-coarse-access.ts \
  data/coarse-quality/census-augmentation-replay-new/grid.json \
  data/coarse-quality/census-augmentation-replay-new/comparison.json
node --expose-gc --import tsx docs/evidence/coarse-augmentation-2026-10-22/measure-decoding.mjs \
  data/coarse-quality/census-augmentation-replay-new/grid.json
node --expose-gc --import tsx scripts/verify-coarse-memory.ts \
  data/coarse-quality/census-augmentation-replay-new/grid.json
```

Expected: 7,788,709 bytes / SHA-256 `aca0fe8f62e463f3dee1ac64c2c3f993d1424ad9ca1c06715aa11cec3ad4e1f5`; 1,004 new links / eight lowered costs / 2,212 supplemental visits / 346,989 points. Source locks can be repeated for additional partitions; no place/region rule exists in the adapter or runtime. All v4 anchors/masks/shore paths remain intact. Census edges pay source arc/class time plus continuous-land transfers at 25 km/h; supplemental access pays the same physical transfer. No dependency installation, env change, DB or routing service is needed.

[Evidence and measured limits](evidence/coarse-augmentation-2026-10-22/README.md) include the exact repeat, all 35 point/path sums, all changed-edge checks, packing bytes and local memory/query observations. Packing is lossless relative to the existing quantized visits; it does not remove source bends. Packed decoding now retains buffers plus a fixed cell index and materializes only a requested visit, with no cache. Load still validates every visit; legacy v4 JSON visits keep their Map path. The new explicit-GC memory verifier checks low decoded heap and bounded retention across three full supplemental-input sweeps. [Memory evidence](evidence/coarse-memory-2026-10-22/README.md) records 51.91 → 6.88 MB retained heap + buffers and identical routes. The national source pass below and v5 local activation are complete. Preserve the pilot and all original artifacts/evidence; it remains a historical development candidate.

## Nationwide Census candidate

The accepted ignored artifact/repeat are `data/coarse-quality/census-national-v2/grid.json` and `census-national-v2-repeat/grid.json`. Expected: **39,976,621 bytes / SHA-256 `119a463d0a876bc83761efb235e1a8a7d9f9105c990b720c9751699c7076b95d`**, 36,742 added links, 73 lowered existing costs, 51,159 supplemental visits / 6,220,841 points. All 49 ZIPs/sidecar locks live in `data/coarse-sources/tiger-2026/`; their pinned catalog/manifest is under `national-v1/`. That directory name identifies acquisition, while the accepted model is v2. Rejected national-v1 outputs and failed compatibility attempts stay preserved.

On a fresh clone, restore the captured catalog/manifest without replacing existing local files; restore the pinned PyShp wheel from the earlier source-pilot section. This acquires only missing public files (289.2 MB total), checks expected hashes before installing, and verifies existing caches:

```sh
mkdir -p data/coarse-sources/tiger-2026/national-v1
test -f data/coarse-sources/tiger-2026/national-v1/catalog.html || cp docs/evidence/coarse-national-2026-10-22/catalog.html data/coarse-sources/tiger-2026/national-v1/catalog.html
test -f data/coarse-sources/tiger-2026/national-v1/sources.json || cp docs/evidence/coarse-national-2026-10-22/sources.json data/coarse-sources/tiger-2026/national-v1/sources.json
node scripts/acquire-coarse-census.mjs data/coarse-sources/tiger-2026/national-v1 --download
# Existing complete caches: offline verification, no downloads.
node scripts/acquire-coarse-census.mjs data/coarse-sources/tiger-2026/national-v1
```

Missing files without `--download`, hash mismatches or unpinned cached files are errors to investigate, not permission to overwrite. The catalog's FIPS selection is offline scope preparation; runtime has no state/region branches. Multipart geometry stays separate, exact geometry/class dedup is direction-independent and shared grid anchors merge partition links with paid land transfers. The national recipe also bounds interpolated source arcs by their physical chord. Legacy `--source-lock` defaults preserve the earlier pilot hash; `--deduplicate` enables the newer source preparation explicitly.

Build only for an intentional new source/recipe run into an unused path; ordinary runtime work can read the existing candidate:

```sh
mkdir -p data/coarse-quality/census-national-replay-new
python3 -B scripts/build-coarse-augmentation.py \
  --source-manifest data/coarse-sources/tiger-2026/national-v1/sources.json \
  --tool-lock docs/evidence/coarse-source-2026-10-22/tool.json \
  --output data/coarse-quality/census-national-replay-new/grid.json \
  > data/coarse-quality/census-national-replay-new/build.json
node --import tsx scripts/verify-coarse-augmentation.ts \
  data/coarse-quality/census-national-v2/grid.json \
  docs/evidence/coarse-national-2026-10-22/build.json --anchor-inputs
node --import tsx scripts/compare-coarse-candidate.ts data/coarse-quality/census-national-v2/grid.json
node --import tsx scripts/verify-coarse-national.ts data/coarse-quality/census-national-v2/grid.json
node --expose-gc --import tsx scripts/verify-coarse-memory.ts data/coarse-quality/census-national-v2/grid.json --anchor-inputs
```

`--anchor-inputs` samples guaranteed on-land source-visit anchors for physical/memory query checks; the default first-vertex mode can include generalized water. Populations and their timing scopes differ. Three complete national sweeps can take several minutes; run them for justified implementation/resource changes, not docs alone. [National evidence](evidence/coarse-national-2026-10-22/README.md) records the original 35 saved paths, 42 national cases, retained storage, rejected v1 and exact repeat. V5 below completes initialization and notices.

An isolated package probe copies source/config plus the candidate (no env files, credentials or raw sources), symlinks existing `node_modules` and changes only the copied estimator import/engine label. This never switches the real app or deploys. Use a fresh directory:

```sh
node scripts/prepare-coarse-package-probe.mjs data/coarse-quality/census-national-v2/grid.json data/coarse-quality/census-national-v2/package-probe-new
(cd data/coarse-quality/census-national-v2/package-probe-new && npm run build:vercel)
node scripts/verify-coarse-vercel.mjs data/coarse-quality/census-national-v2/package-probe-new coarse-road-grid-candidate
```

The handler checker now defaults to active project/v8 without args. Biome excludes ignored `data/`, including isolated source copies and frozen/local assets. The original candidate package took about 22 seconds for first computation; indexed validation now takes 2.46–2.47 seconds in three fresh local processes. V5 was activated at that milestone; v8 below is now active locally. No env variable, migration or runtime dependency is added. Preserve all old/failed outputs. [V5 evidence](evidence/coarse-v5-2026-10-22/README.md).

## Finer-resolution v6

This historical recipe reproduces preserved `src/server/data/coarse-grid-v6.json`, committed at `ffd7fec` and user-reported verified live. Normal development/deployment now uses v8 below and needs no source producer or Python. Expected: **68,129,975 bytes / SHA `a1ba5ae3eb7419feb458641f00da1886802fc16ec11af86e3d61d42a3b8b3f99`**. The runtime remains TypeScript with no new DB/key/env requirement. [Evidence](evidence/coarse-resolution-2026-10-23/README.md).

For an intentional source rebuild, Python 3.11+, all three pinned NE files, all 49 Census ZIPs/locks, manifest/catalog and the checked PyShp wheel must exist. Current caches already contain them. A fresh clone needs the [Census recovery](#nationwide-census-candidate) and wheel setup above. NE files belong under `data/coarse-sources/natural-earth-v5.1.2/`; source URLs/hashes are in the preserved v5 JSON and enforced by `original.load`. Restore only missing public files, preserving existing caches:

```sh
mkdir -p data/coarse-sources/natural-earth-v5.1.2
# Only for missing files on a fresh source-preparation machine:
test -f data/coarse-sources/natural-earth-v5.1.2/countries.geojson || curl --fail --location https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_admin_0_countries.geojson --output data/coarse-sources/natural-earth-v5.1.2/countries.geojson
test -f data/coarse-sources/natural-earth-v5.1.2/lakes.geojson || curl --fail --location https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_lakes.geojson --output data/coarse-sources/natural-earth-v5.1.2/lakes.geojson
test -f data/coarse-sources/natural-earth-v5.1.2/roads.geojson || curl --fail --location https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_roads.geojson --output data/coarse-sources/natural-earth-v5.1.2/roads.geojson
```

Hash/partial-file mismatches are errors to investigate, not permission to overwrite. Build only into a new directory; no completed producer needs rerunning for normal runtime/docs checks:

```sh
mkdir -p data/coarse-quality
python3 -B scripts/build-coarse-resolution.py --step 0.05 \
  --source-manifest data/coarse-sources/tiger-2026/national-v1/sources.json \
  --tool-lock docs/evidence/coarse-source-2026-10-22/tool.json \
  --output data/coarse-quality/resolution-005-replay-new
```

Expected candidate: **68,129,988 bytes / SHA `b3e65e43e4377f98c7bd21cc7e458f09f9a7ade78ef8d100b345dd1c14c686df`**, 613,600 cells / 168,149 links. Outputs `grid.json`, hash-bound `links.json.gz` and `build.json`; first attempt/repeat at `resolution-005-v1/` / `-v2/` already match. Source rebuild takes about 114s and 2.10GB whole-producer peak RSS in one Mac observation; this is not runtime/Vercel memory. Changing `--step` recomputes the graph and needs a separately versioned evaluation; 0.025° has not been measured.

Existing accepted artifact checks, with no producer/network requests:

```sh
node --import tsx scripts/verify-coarse-resolution.ts data/coarse-quality/resolution-005-v2/grid.json data/coarse-quality/resolution-005-v2/build.json
node --import tsx scripts/compare-coarse-resolution.ts data/coarse-quality/resolution-005-v2/grid.json
node --expose-gc --import tsx scripts/verify-coarse-memory.ts data/coarse-quality/resolution-005-v2/grid.json --anchor-inputs
node scripts/finalize-coarse-grid-v6.mjs data/coarse-quality/resolution-005-v2/grid.json data/coarse-quality/grid-v6-repeat-new.json
```

The finalizer accepts the pinned qualified hash, changes only version and refuses an existing output. All 35 reference costs and all 42 candidate/active API counts match their saved outputs; comparisons include every regression/unreached case and distinguish cell counts from accuracy. The old fixed-v4 candidate verifier is not a cross-resolution comparator. Full memory sweeps use 405,384 inputs; repeat them only for affected storage/runtime changes, not docs alone. Current reports live under ignored `data/coarse-quality/resolution-evaluation-v1/`; raw proof archives remain local and checksum-bound in the build report.

To regenerate a **new** review page (precomputed validation cases only; no app/API/source/DB requests):

```sh
node --import tsx scripts/preview-coarse-resolution.ts data/coarse-quality/resolution-005-v2/grid.json data/coarse-quality/resolution-preview-new
python3 -B -m http.server 4176 --bind 127.0.0.1 --directory data/coarse-quality/resolution-preview-new
```

The current existing server instead serves `data/coarse-quality/resolution-evaluation-v1/`; its URL is **http://127.0.0.1:4176/preview-v2/**. Rediscover the listener before starting another server; never kill an unrelated owner. Maps share a camera and expose inland/rural/coastal/mountain 6/10/12h cases. The template/scripts copy installed MapLibre assets, with no dependency installation; online basemap requests remain separate from routing.

An isolated package probe still accepts any candidate/fresh directory through `prepare-coarse-package-probe.mjs`; it now copies active v8 source/wording, changes only the copied import/engine label and never edits the real app. Use it for a new runtime experiment, not to rerun completed package evidence. `npm run check:coarse:vercel` defaults to active v8. Preserve old v1–v6 data and every failed/original output.

## Census road states v7

Historical v7 comparison artifact `src/server/data/coarse-grid-v7.json`: **79,584,626 bytes / SHA `988d1ef988e0ca587b60cb3ee4d688eed37629bdb62f344d7f49e8f6f6349379`**. This comparison artifact is committed with v8 at `ee8809f`. Normal app/deployment now uses v8 below. No raw source, Python, DB, new dependency or env variable is required at runtime. [Complete evidence](evidence/coarse-connections-2026-10-23/README.md).

The completed source runs are `data/coarse-quality/road-layer-v1/` and `road-layer-v1-repeat/`, each containing `grid.json`, `build.json` and `links.json.gz`. Candidate SHA **`d2f220d90d3d27caaf6d19aab63e2fb0365ea3f29a06398be3ff365b921c3c73`**, 79,584,632 bytes; proof SHA **`fc71016fd7fbbcba10bc0a512499133c0d199027a1cb5d4dd6e02873111049f5`**, 10,226,099 bytes. Both repeat byte for byte. Evaluation/memory/paths/finalization/preview are under `data/coarse-quality/road-layer-evaluation-v1/`; candidate package probe under `road-layer-v1/package-probe/`.

Only if intentionally rebuilding, use Python 3.11+, bundled pinned v6, all 49 cached Census ZIPs/locks and manifest, three NE files and the pinned PyShp wheel described above. The default recipe requires v6's exact hash and reuses pure source helpers without running old producers. The v8 recipe below supplies an explicit base path/hash pair. It refuses existing output directories:

```sh
python3 -B scripts/build-coarse-road-layer.py \
  --source-manifest data/coarse-sources/tiger-2026/national-v1/sources.json \
  --tool-lock docs/evidence/coarse-source-2026-10-22/tool.json \
  --output data/coarse-quality/road-layer-replay-new
```

Expected: 135,128 Census states, 159,189 new links, same candidate/proof hashes. Existing completed passes take about 70s locally. No completed producer needs rerunning for runtime/docs validation. Recovery checks below read existing artifacts and call no routing provider, DB or source service; run only affected checks after changes:

```sh
node --import tsx scripts/verify-coarse-road-layer.ts data/coarse-quality/road-layer-v1/grid.json data/coarse-quality/road-layer-v1/build.json
node --import tsx scripts/compare-coarse-resolution.ts data/coarse-quality/road-layer-v1/grid.json --baseline-v6
node --import tsx scripts/inspect-coarse-access.ts data/coarse-quality/road-layer-v1/grid.json docs/evidence/coarse-connections-2026-10-23/comparison.json
node --expose-gc --import tsx scripts/verify-coarse-memory.ts data/coarse-quality/road-layer-v1/grid.json --anchor-inputs
node scripts/finalize-coarse-grid-v7.mjs data/coarse-quality/road-layer-v1/grid.json data/coarse-quality/grid-v7-repeat-new.json
```

Expected: all new link/transfer proofs and preserved v6 fields pass; 42 cases lose no v6 cells; all 35 baseline costs match sealed v6 evidence, 21 improve/14 unchanged/zero regress and every destination is reached/shaded. Original/broader mean absolute reference differences 14.712→11.579 / 23.615→17.211 min. These are development comparisons, not national accuracy. State IDs are base cell indices or `width * height + cell` for Census; path/attachment diagnostics retain these IDs. Contour arrivals use the minimum across both states. Full source validation remains; no growing decoded/query cache.

Finalization accepts only the qualified candidate hash, changes only version and refuses overwrite. Existing active/repeat bytes match; no producer or sweep is needed to recheck documentation. Default `routing:verify:coarse` and hosted verifier now require v8 counts/version. Both builds and local handler remain the normal app release checks.

For a fresh offline paired review directory:

```sh
node --import tsx scripts/preview-coarse-resolution.ts data/coarse-quality/road-layer-v1/grid.json data/coarse-quality/road-layer-preview-new --baseline-v6
python3 -B -m http.server 4177 --bind 127.0.0.1 --directory data/coarse-quality/road-layer-preview-new
```

The existing server instead serves `data/coarse-quality/road-layer-evaluation-v1/` at **http://127.0.0.1:4177/preview/**. Rediscover listeners before starting/stopping one. Twelve inland/rural/coastal/mountain cases at 6/10/12h share a camera, resolution and speeds; basemap requests are separate. Some full-page browser captures rendered only part of WebGL canvases; use a normal viewport capture and inspect it. Initial captures are preserved under ignored evaluation outputs. Main app remains `http://127.0.0.1:3000/` with v8, source notices and normal history/replay. Full DB write tests need not repeat for this unchanged persistence layer.

## Finer-resolution v8

Normal app/deployment needs only bundled `src/server/data/coarse-grid-v8.json`: **61,208,381 bytes / SHA `2beb2fb6d9af6e07f37c5ba53acdeca2da1334c31a5fadd1371efd5453134910`**. V7/v8 artifacts are committed at `ee8809f`; preserve them when publishing the current UX/planning changes. No new env, dependency, migration, raw source or Python is required at runtime. [Complete v8 evidence](evidence/coarse-finer-2026-10-23/README.md).

Completed ignored source directories: `resolution-0025-base-v1/` / `resolution-0025-base-v1-repeat/` and `resolution-0025-road-v1/` / `resolution-0025-road-v1-repeat/`, all under `data/coarse-quality/`. Each has grid/build/compressed link proofs. Evaluation/packed/repeat/finalization/profile/preview and intermediate package probes are in `resolution-0025-evaluation-v1/`; final qualified package is `package-probe-direct-arrays/`. Preserve all intermediate failures/marginal runs.

Only for an intentional source rebuild, reuse the Python 3.11+/pinned NE/49 Census ZIP/manifest/PyShp prerequisites above. Fresh output paths refuse overwrite:

```sh
python3 -B scripts/build-coarse-resolution.py --step 0.025 \
  --source-manifest data/coarse-sources/tiger-2026/national-v1/sources.json \
  --tool-lock docs/evidence/coarse-source-2026-10-22/tool.json \
  --output data/coarse-quality/resolution-0025-base-new
python3 -B scripts/build-coarse-road-layer.py \
  --base data/coarse-quality/resolution-0025-base-new/grid.json \
  --base-sha256 01ab7afcbf69a7a074984864ba4aacf3395bbd3225b472d4099f20b42f223e56 \
  --source-manifest data/coarse-sources/tiger-2026/national-v1/sources.json \
  --tool-lock docs/evidence/coarse-source-2026-10-22/tool.json \
  --output data/coarse-quality/resolution-0025-road-new
node scripts/pack-coarse-grid.mjs data/coarse-quality/resolution-0025-road-new/grid.json data/coarse-quality/grid-0025-packed-new.json
```

Expected base: **134,107,947 bytes / SHA `01ab7afcbf69a7a074984864ba4aacf3395bbd3225b472d4099f20b42f223e56`**, 2,454,400 cells / 378,515 links. Road-state model: **179,924,201 bytes / SHA `3dfdb35c180be2e998c65ea57d56c686117bda1431891093b24cc1819d4576f6`**, 317,586 Census states / 346,821 layer links. Packed: **61,208,393 bytes / SHA `f5dd46f223fc4a6d601235adc4c59cb8a31326aa416c6fe0da522e34a14dbb5a`** using the recorded Node/zlib version. All independent outputs/proofs match. Base source pass is ~142s / 2.57GB native peak RSS on this Mac; this is offline producer scope, not runtime/Vercel memory.

Existing artifacts can be checked without any producer/network/provider/DB requests; run only affected checks after changes:

```sh
node --import tsx scripts/verify-coarse-resolution.ts data/coarse-quality/resolution-0025-base-v1/grid.json data/coarse-quality/resolution-0025-base-v1/build.json
node --import tsx scripts/verify-coarse-road-layer.ts data/coarse-quality/resolution-0025-road-v1/grid.json data/coarse-quality/resolution-0025-road-v1/build.json
node --import tsx scripts/compare-coarse-resolution.ts data/coarse-quality/resolution-0025-evaluation-v1/grid-packed.json --baseline-v7
node --import tsx scripts/inspect-coarse-access.ts data/coarse-quality/resolution-0025-evaluation-v1/grid-packed.json docs/evidence/coarse-finer-2026-10-23/comparison.json
node --expose-gc --import tsx scripts/verify-coarse-memory.ts data/coarse-quality/resolution-0025-evaluation-v1/grid-packed.json --anchor-inputs
node scripts/finalize-coarse-grid-v8.mjs data/coarse-quality/resolution-0025-evaluation-v1/grid-packed.json data/coarse-quality/grid-v8-repeat-new.json
```

Expect full source/shore/transfer checks, 42 horizon-monotonic software cases and all 35 exact preserved v7 baseline costs; 29 improve/six regress (worst +3.180 min), every destination reached/shaded. Cross-resolution cell counts are not accuracy scores. The memory command performs 952,758 inputs: final retained decoded storage 158.04MB; declared fixed-load heap allowance 4MiB, post-load query growth limits unchanged at 2MiB heap/64KiB buffers. Earlier 2MiB fixed-load failure and all marginal startup runs remain preserved. No growing source-visit/query cache. Finalization changes only version and refuses overwrite. Completed producers and sweeps are unnecessary for documentation checks.

The loader recognizes `gzip:` prefixes only on binary-array fields, uses built-in zlib with a 256MB per-field inflate bound, and retains all full geometry/visit checks. Aligned native word views avoid copying/converting dense arrays; the fallback reads little-endian words explicitly. A fixed 0.01° geography index with compact band views/flat ring list preserves exact checks. No new package or runtime environment variable is needed.

Fresh review page (public precomputed cases; no routing references):

```sh
node --import tsx scripts/preview-coarse-resolution.ts data/coarse-quality/resolution-0025-evaluation-v1/grid-packed.json data/coarse-quality/resolution-0025-preview-new --baseline-v7
python3 -B -m http.server 4178 --bind 127.0.0.1 --directory data/coarse-quality/resolution-0025-preview-new
```

The existing server serves `resolution-0025-evaluation-v1/` at **http://127.0.0.1:4178/preview/**. Rediscover listeners before starting/stopping one; never stop an unrelated owner. Normal viewport screenshots render WebGL reliably here. Main app is `http://127.0.0.1:3000/`, with v8 and visible 0.025° / 1.8–2.8km notices. [Publication/hosted verification](next-steps.md#1-publish-and-verify-latest-v8).

## Regenerate the coarse grid

The historical v5 recipe below is preserved; normal development/deployment uses **v8** above. Historical v5 reproduction uses the included v5 artifact and requires no producer or raw data. To intentionally reproduce v5, first recover national-v2 using the preceding source recipe, then finalize notices into an unused output path:

```sh
node scripts/finalize-coarse-grid-v5.mjs \
  data/coarse-quality/census-national-v2/grid.json \
  data/coarse-quality/grid-v5-repeat-new.json
```

Expected: **39,977,082 bytes**, SHA-256 `b5a53b44fa42073e22575203d4848c7c6185e8eebd4688b504cefa04ff441cd4`. The finalizer requires the national-v2 input hash, changes only five version/notice fields and refuses an existing output. Do not overwrite any bundled or local evidence artifact as a health check. A source/geometry change requires a separately versioned recipe/run. The preserved v5 file remains included in Git/Vercel and excluded from Biome alongside earlier artifacts; v8 is the active import.

The commands below regenerate **preserved v4 only**; `npm run data:coarse` still names its historical builder, not current v8. This is optional for normal development/deployment: prepared v4 JSON is included in source. Use Python 3.11+ standard library, unchanged bundled v2/v3 artifacts and pinned public-domain Natural Earth v5.1.2 roads. The cached raw inputs already exist here; do not download them again. A fresh offline-builder setup needs only roads for v4 (older v1/v2 builders also use countries/lakes):

```sh
mkdir -p data/coarse-sources/natural-earth-v5.1.2
curl --fail --location https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_roads.geojson --output data/coarse-sources/natural-earth-v5.1.2/roads.geojson
npm run data:coarse
```

The v4 builder verifies pinned v3, v2 and roads hashes before writing `src/server/data/coarse-grid-v4.json`. Expected: **7,995,142 bytes**, SHA-256 `6905fa38d198f6c89201fb731db484a1b7ff911078648c005165b5ba7be654f3`, 26,946 visits / 142,029 points. To check repeatability without replacing the active file, use an unused output path:

```sh
python3 -B scripts/build-coarse-grid-v4.py --output data/coarse-quality/grid-v4-repeat-new.json
```

All v3 graph/mask/anchor/shore bytes and speeds remain unchanged; visits are taken only from roads owning the pre-existing v2 anchors. Do not attach new v3 shore land representatives to unrelated source roads. V4 refuses v1/v2/v3 output names. Earlier builders/artifacts/evidence remain preserved. Raw inputs are ignored and runtime requires none of them. The existing cache holds all three original sources (68.8 MB). [Model and provenance](coarse-estimator.md#v4-charged-road-attachment).

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

`check:vercel` is the retained Valhalla/provider check: it requires that selected graph service, invokes the generated handler locally and saves `vercel-verification.json` in its data directory. For the default coarse model, use `npm run check:coarse:vercel` instead; no routing service is required. Neither check deploys anything. The compact coarse artifact is bundled server-side, while large research graphs and environment files are excluded. Only the optional connected model requires a reachable provider. Default coarse v8 is committed at `ee8809f`; one public live configuration read confirms v8/min60, while the min30 slider update is local. Full hosted revision/behavior proof remains pending after its publication; actual connected-provider cloud verification remains open.
