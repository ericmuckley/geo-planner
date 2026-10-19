# Regional expansion and Vercel verification

Measured October 16, 2026. The app remains one fullstack TanStack Start application. The user subsequently selected [free external US routing](us-routing-service.md), with worldwide expansion deferred. The openrouteservice adapter is connected and [real hosted US smoke checks succeed](hosted-routing-verification.md). No paid plan or cloud deployment was performed.

## Current regional baseline

The default profile is `routing/profiles/california-baja-v2.json`, graph ID `california-baja-roads20261014-admin20261016-v2`, stored in ignored `data/valhalla-v2/`. It inherits the pinned engine and road sources from `routing/manifest.json`. The engine is Valhalla `3.9.1-7fd2228e5`, revision `7fd2228e5863b442bc1ac8d25eece6415dd91bff`, using the same digest-pinned ARM64 container as [v1](routing-baseline-verification.md).

The requested rectangle is `[-119.8,30.8,-114.5,35.5]`. Southern California and Mexico road inputs share OSM timestamp `2026-10-14T20:21:12Z`; their source URLs, sizes and SHA-256 checksums remain in the base manifest. This rectangle includes Los Angeles, Bakersfield and northern Baja, but **does not establish road coverage in Arizona or Nevada**. Complete ways can extend beyond the cut; paths leaving and re-entering it can still be lost. Bounds reject unsupported origins, not incomplete journeys.

The earlier missing US/California administrative polygons are repaired using complete OSM relations 148838 and 165475, retrieved October 16. Their exact sizes, relation versions and SHA-256 checksums are in the profile. Mexico relation 114686 and its members come from the October 14 PBF. `osmium check-refs -r` found no missing references in the two supplements; the built admin DB contains US, California (`CA`, parent US), and Mexico. A real San Diego `/locate` reports US/CA. This fixes the missing polygons; it does not independently prove correct costs at every border edge.

**Preserve the downloaded source snapshots.** Dated Geofabrik files may expire. OSM `/relation/.../full` URLs are mutable: downloads verify the recorded checksum and deliberately fail if content changes. These URLs alone cannot recreate the frozen supplements later; archive the verified files or publish an immutable copy before promising long-term reproducibility. Roads and supplementary administrative members also have different acquisition dates.

## Resources and observations

Same Apple M4/16 GiB host and Docker VM as v1; two build workers, build cap 2 CPUs/4 GiB, service cap 2 CPUs/2 GiB. Reserve at least 10 GiB free for this profile; preserve extra room when keeping previous builds. Disk checks are a guard, not a complete capacity estimator.

| Measurement | California/Baja v2 | Malta v1 |
| --- | --- | --- |
| Preparation + build wall time | 335.85 seconds | 4.79 seconds |
| Maximum child-process RSS | 3,914,976 KiB | 567,600 KiB |
| Graph tiles | 360 | 13 |
| Graph archive | 922,142,720 bytes | 13,178,880 bytes |
| Road input download | 1,318,456,511 bytes shared with v1 | 8,933,324 bytes |

RSS is GNU time's largest child-process measurement, not total Docker/VM peak memory. The v2 build logged four possible duplicate level-2 edges and missing admin-access entries for other countries. No timezone, elevation or traffic data was provisioned.

Six sequential app requests per budget retained one initial sample and five subsequent samples. No caches were flushed. Engine HTTP round trip includes request/response transport, graph work, contour construction and serialization; it is **not isolated graph-search time**.

| San Diego budget | First HTTP round trip | Subsequent median (n=5) | Upstream bytes |
| --- | --- | --- | --- |
| 15 min | 750.3 ms | 343.8 ms | 59,977 |
| 30 min | 580.7 ms | 461.3 ms | 81,664 |
| 60 min | 750.1 ms | 637.4 ms | 137,128 |
| 120 min | 3,417.7 ms | 2,344.8 ms | 399,187 |

All budgets returned polygons and no engine warnings. The default input snapped to `32.715695,-117.161085`, about 1.5 m away. Los Angeles (60 min), Bakersfield (30 min), and Ensenada (60 min) also returned real adapter contours. The default 60-minute San Diego query was exercised again through the browser with the v2 service and readiness badge.

Ten sampled destinations still include an unresolved disagreement: Rosarito's default route takes 66.20 modeled minutes, but its endpoint lies in the 60-minute polygon. Tijuana takes 32.44 minutes; Ensenada 109.67. A coarse 0.025° nesting scan found zero misses for 15→30 and 30→60, and four of 762 sampled 60-minute members missing from 120 minutes. No engine warning is a completeness guarantee. Live border queues, eligibility and lane restrictions are not modeled.

An exploratory v1 request for all four contours together had zero coarse 60→120 misses. The pinned engine selects a grid resolution using its maximum requested budget, so grid changes plausibly contribute. This is evidence to investigate, not a resolution: the searched budget also changed, and no exact graph-label comparison was made. The app continues to request one contour and retains `coverageVerified: false`.

Fourth Avenue way 5987900 has source OSM `oneway=yes`; `/locate` at `32.7167,-117.1611` reports car access on the forward edge and none on the reverse edge. This is a concrete import/access check, not validation of every turn restriction. A prohibited-turn case and disconnected-origin behavior remain to be qualified.

## Reuse outside North America

`routing/profiles/malta-v1.json` uses the entire dated Malta extract without a second rectangular cut. Its SHA-256 is `996bd058510cf562dd9b4ac7aad45d880a9f89f4a83ec49e9d626588d0b22f79`, with the same October 14 timestamp and pinned engine. Malta's admin code MT is present. Valletta origin `35.8989,14.5146` returned real 15/30/60-minute contours through a separate local app instance. Sampled routes: Mdina 14.55 min, Marsaxlokk 13.50, Mellieha 25.26. Coarse nesting checks found no misses; all engine warnings were empty. These few checks are not an independent coverage/correctness proof. External ferry destinations and actual schedules are absent.

To select this profile without altering existing data or environment files:

```bash
export VALHALLA_MANIFEST=routing/profiles/malta-v1.json
export VALHALLA_DATA_DIR=data/valhalla-malta
npm run routing:download
npm run routing:build
npm run routing:up
npm run dev:routing
# Separate terminal with the same two exports:
npm run routing:verify
```

Compose runs one selected graph at port 8002. Stop the app before switching profiles and restart it with the matching environment. Unset both exports to return to California/Baja. Regional graphs are separate qualification fixtures: do not merge independently built tiles or union their polygons to claim continuous worldwide routing.

## Vercel feasibility

`npm run build:vercel` produces a Node.js fullstack server function and static assets. `npm run check:vercel` invokes that generated handler locally for real readiness and default 60-minute requests, verifies graph/engine identity, and checks that graph archives, PBFs and environment files are absent from the function. `.vercelignore` also excludes local datasets and environment files from source upload. This verifies packaging and local handler behavior; actual Vercel deployment, credentials and cloud networking are untested. A deployed app cannot call this Mac's `localhost:8002`.

Vercel currently documents a standard 250 MB Node function bundle, eligible 5 GB large-function beta, and plan-dependent memory/time limits. Native routing should be measured against the actual chosen plan; it is not universally ruled out by the old bundle limit. [Official limits](https://vercel.com/docs/functions/limitations).

A separate local experiment used official Node bindings `@valhallajs/valhallajs@3.7.0` with a local HTTP road-tile server. Its 60-minute result equaled the same binding's local-file result; the first call fetched 32 tiles totaling **278,966,808 bytes**, with no extra downloads on the next call. Call durations were about 1.14 and 1.00 seconds while other local work was active. These are feasibility observations, not a benchmark. The native revision differs from the 3.9.1 graph builder, and Linux, WAN, worldwide data, missing required tiles and concurrent Vercel instances were not tested. The package is not an application dependency. Reproduction harness: `routing/experiments/native-tiles.mjs`.

## Evidence and next task

Selected responses, build provenance, raw timing summaries and browser evidence are retained under [evidence/routing-expansion-2026-10-16/](evidence/routing-expansion-2026-10-16/). Complete local responses/build logs remain in ignored `data/valhalla-v2/` and `data/valhalla-malta/`; the original v1 data remains intact. The agent preserved existing environment values; the user later added the hosted provider/key to `.env.local`. Nothing was committed.

All 14 adapter tests, `npm run check`, `npm run typecheck`, `npm run build`, and the Vercel-target build/local handler check pass. Check retains one existing database non-null assertion warning; builds retain MapLibre chunk-size/upstream directive warnings.

**Updated priority:** [brainstorm and qualify a self-built 10–12-hour routing path](long-range-routing-brainstorm.md) before Vercel rollout. Hosted routes remain a short-range comparison, with independent qualification pending as described in [hosted findings](hosted-routing-verification.md). Revisit self-hosting at usage/payment limits. Preserve unresolved regional findings; do not present local engine checks or mocked provider tests as hosted verification. PostGIS, elevation, road-distance semantics, caching and advanced search remain deferred.

Final production-preview command: `npm run preview:routing -- --port 4174` (the existing 4173 preview was left intact). Verification containers on ports 8003/8004 and the temporary Malta app were removed/stopped; the selected v2 service remains on loopback port 8002. The local 4174 preview was subsequently stopped when switching the main app to hosted production preview on port 3000. The final hosted missing-key preview used port 4175 and was stopped after evidence capture. Development reloads cleared intermediate displayed runs during file edits; final contour evidence comes from production preview.
