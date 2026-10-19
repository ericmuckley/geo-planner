# Regional routing baseline

## Current default: California and northern Baja v2

Use `routing/profiles/california-baja-v2.json` with ignored `data/valhalla-v2/`. It shares the original pinned engine/road snapshots, expands the requested rectangle to `[-119.8,30.8,-114.5,35.5]`, and repairs complete US/California administrative relations. Read [current measurements and limitations](routing-expansion-verification.md), including the requirement to retain frozen administrative source files. The user has chosen [free external US routing](us-routing-service.md); these local graphs are retained as a fallback. Worldwide expansion is deferred.

Requirements remain Node 22.12+, npm, Docker Compose v2, curl and at least 10 GiB free disk for this profile. Build cap: 2 CPUs/4 GiB; service cap: 2 CPUs/2 GiB. The measured largest build child used 3.73 GiB RSS. Use a larger data directory/reservation when retaining multiple graphs; do not attempt a planet build with this regional capacity estimate.

```bash
# From the repository root, with Docker Desktop running:
npm run routing:download
npm run routing:build > data/valhalla-v2/build.log 2>&1
npm run routing:up
npm run dev:routing
# Separate terminal while the app runs on port 3000:
npm run routing:verify > data/valhalla-v2/verification-report.json
```

`routing:download` creates the directory used by the log redirection. `dev:routing` reads generated `data/valhalla-v2/app.env`; existing `.env.local` remains unchanged. Process values override the generated environment. Readiness now checks service status/capability/engine version; coverage bounds reject outside origins but cannot detect truncated contours. The time cap remains 120 minutes for this local graph, not a worldwide product limit.

Builds refuse to overwrite a completed graph. For another build, set both `VALHALLA_MANIFEST` and a **new** `VALHALLA_DATA_DIR`; source cache defaults to `data/valhalla/sources/` and is shared read-only during builds. Use these same values for build/up/app/verify. The Malta example is in the expansion report. The single Compose service selects one graph at port 8002; stop/restart the app when switching. `routing:down` retains all files.

## Historical San Diego–Tijuana v1 recipe

The remainder documents the original v1 graph and its missing US admin polygons. These findings are historical; the active v2's remaining correctness gaps are in the expansion report. To reproduce v1 explicitly, use these values in **each** terminal before the commands below:

```bash
export VALHALLA_MANIFEST=routing/manifest.json
export VALHALLA_DATA_DIR=data/valhalla
```

The local baseline uses a checksum-verified OSM snapshot and a digest-pinned official Valhalla image. Large inputs, graph files, build logs, and repeatable verification outputs live in ignored `data/valhalla/`. This is a driving-time baseline; the basemap is a separate online dataset.

### Reproduce v1

Requirements: Node 22.12+ and npm, Docker with Compose v2, `curl`, an internet connection for initial downloads/images, and a WebGL browser. The tested host is an Apple M4, 10 CPU cores, 16 GiB RAM; Docker has 10 CPUs and 7.65 GiB RAM available. The build container is capped at 2 CPUs / 4 GiB; the service at 2 CPUs / 2 GiB. Reserve **10 GiB free disk** for sources, merged/clipped PBFs, intermediate graph files, tiles, and images. These are capacity recommendations, not measured minimum requirements.

From the repository root:

```bash
# Start Docker Desktop first (macOS: open -a Docker).
docker info
npm install
npm run routing:download
npm run routing:build > data/valhalla/build.log 2>&1
npm run routing:up
curl --fail http://127.0.0.1:8002/status
npm run dev:routing
```

In another terminal, with the app on `http://localhost:3000`:

```bash
npm run routing:verify > data/valhalla/verification-report.json
```

Open the app, keep the default origin `32.7157, -117.1611` and 60 minutes, and click **Compute contour**. Check the contour, orange snapped-location marker, coverage label, engine warnings, and measurements. Toggle the contour and inspect the border area. `routing:verify` uses the app adapter for 15/30/60/120-minute contours and Valhalla directly for sampled route diagnostics; raw responses and a summary go to `data/valhalla/verification/`. It checks engine/graph labels against the manifest and fails on HTTP, schema, or route failures. Route/contour disagreements and nesting diagnostics are reported for review, not hidden by an assertion.

`npm run dev:routing` reads generated, nonsecret `data/valhalla/app.env` into the process. Existing `.env.local` values are preserved on disk. Process environment values take precedence; this command deliberately selects the local baseline's routing values. Ordinary `npm run dev` retains the existing environment behavior. Do not point a Vercel deployment at its own localhost expecting this graph to exist there.

```bash
# Stop the local service; data is retained.
npm run routing:down
# Start the existing graph without downloading or rebuilding it.
npm run routing:up
```

The build refuses to overwrite a completed graph. For a clean rebuild, select a new `VALHALLA_DATA_DIR` (for example `data/valhalla-v1-rebuild`) and rerun download/build/up. Keep the shared `data/valhalla/sources/` cache in place to avoid downloading again. A failed build has no `build-complete.json`; correct the error and rerun build. Preserve failure logs before rerunning because build measurements/logs are overwritten. Never run two builds against the same data directory. The final recipe was also verified with an [isolated second build](routing-baseline-verification.md) while preserving the active graph.

### V1 pinned inputs and settings

[`routing/manifest.json`](../routing/manifest.json) records the engine image index digest, full Git revision, source URLs, sizes, MD5 and SHA-256, requested bbox, and build concurrency. The multiarchitecture index pins both Linux ARM64 and AMD64; only ARM64 was exercised. The tools Dockerfile adds `osmium-tool=1.16.0-1build1` and GNU `time=1.9-0.2build1`; apt's transitive dependencies can change. Archive the local tools image if bitwise toolchain preservation is required. Tile output is not claimed byte-identical across platforms/build times.

Both Geofabrik sources have PBF replication timestamp **2026-10-14T20:21:12Z**. Their combined download is **1,318,456,511 bytes** (1.23 GiB). Dated URLs and checksums are intentional: a missing historical extract must fail, never silently fall back to `latest`. Retain the source files because the provider may expire daily snapshots. OSM attribution: © OpenStreetMap contributors, [ODbL 1.0](https://www.openstreetmap.org/copyright); regional extracts by Geofabrik.

The recipe merges the two sorted snapshots before clipping, so shared border objects are deduplicated. `osmium extract --strategy=complete_ways` retains entire ways touching the rectangle **west −118.5, south 31.5, east −115.5, north 34**. Ways can extend beyond the requested rectangle; this is not an exact rectangular coverage guarantee. Full-source admin relations build `admin.sqlite` before the road graph. **The sources still lack members of the US and California relations: the builder skips those polygons. Mexico's country polygon is present.** Country overrides are enabled in configuration but cannot be assumed to apply correctly on the US side. Repair admin coverage before making border-cost or strict routing-correctness claims. The recipe then runs the standard graph pipeline (hierarchy, shortcuts, restrictions, validation) and packages `tiles.tar`. Driveways and the engine's default driving/bicycle/pedestrian graph data are retained; the app exposes only auto routing.

The engine-generated full configuration is retained as `data/valhalla/valhalla.json`. The explicit changes are tile/admin/timezone paths, two build workers, use of the admin DB/country overrides, and a 120-minute isochrone cap. No timezone DB, elevation, transit feed, predicted-speed profile, or live traffic is provisioned. No date/time is requested. Generated defaults from the pinned engine determine the remaining settings. `build-complete.json` retains the manifest and artifact sizes/checksums; `build-resources.txt` records GNU time wall duration and maximum child-process RSS for preparation and graph build. This RSS is not total Docker/VM peak memory.

### V1 meaning and coverage limits

The adapter requests outbound `auto`, `speed_types=[freeflow, constrained]`, polygons, locations, 100 m generalization, and denoise 0. Those speed sources do not imply imported live/historical traffic: this graph uses OSM/engine-default static speeds. The pinned auto implementation uses road-class/density/preferences and transition penalties, not pure shortest elapsed time. Default country-crossing cost is **600 seconds**, maneuver penalty 5 seconds, gate cost 30 seconds plus a 300-second preference penalty, ferry boarding cost 300 seconds, and service-road preference penalty 75 seconds. Route and isochrone algorithms can differ even with the same profile. These results are not an independent proof of minimum-time graph reachability.

Mexico is included deliberately. The graph covers the Tijuana, Rosarito, Ensenada, and San Ysidro/Otay areas. Border access comes from OSM and the engine profile, with the incomplete US admin caveat above. The profile's default ten-minute crossing cost is **not measured border wait time**; whether it is applied at the correct edges needs revalidation after the admin repair. It does not capture live queues, immigration eligibility, inspections, crossing hours, or lane/program restrictions. Reverse routes need separate checks because access and direction differ.

North/east/south cuts can truncate longer journeys and paths that leave and re-enter the region. Even a contour that does not visibly touch a cut is not a completeness proof. The app continues to return `coverageVerified: false`; there is no automatic boundary detector. Filled polygons can cross water, restricted land, disconnected roads, and unroutable locations. Generalization, contour-grid resolution, and small retained components further limit geographic membership accuracy. Keep 120 minutes as an exploratory diagnostic, and do not raise the cap for this graph.

See [baseline verification](routing-baseline-verification.md) for measured resource use, routes, timings, browser evidence, and the next recommended task.

Primary references: [official Valhalla container recipe](https://github.com/valhalla/valhalla/blob/7fd2228e5863b442bc1ac8d25eece6415dd91bff/docker/README.md), [graph pipeline](https://valhalla.github.io/valhalla/contributing/architecture/mjolnir/), [isochrone API](https://valhalla.github.io/valhalla/api/isochrone/), [Osmium extraction](https://docs.osmcode.org/osmium/latest/osmium-extract.html), [Southern California source](https://download.geofabrik.de/north-america/us/california/socal.html), [Mexico source](https://download.geofabrik.de/north-america/mexico.html), [pinned auto costs](https://github.com/valhalla/valhalla/blob/7fd2228e5863b442bc1ac8d25eece6415dd91bff/src/sif/autocost.cc), [pinned transition defaults](https://github.com/valhalla/valhalla/blob/7fd2228e5863b442bc1ac8d25eece6415dd91bff/src/sif/dynamiccost.cc).
