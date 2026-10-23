# Next steps for coding agents

Updated October 23, 2026. Read [AGENTS.md](../AGENTS.md), [handoff](agent-handoff.md), [status](implementation-status.md) and [local development](local-development.md).

## Completed: finer v8 with road continuity

**V8 is committed at `ee8809f` (message `v7`), including both data artifacts. The time-slider/API-range change and frozen-reference preparation tool are local/uncommitted.** V8 rebuilds 2,454,400 cells, retaining generic paid Census road states. Lossless arrays reduce the raw 179.92 MB model to a 61.21 MB artifact; local Vercel function is 65.02 MB. Independent source/proof/packed/finalization repeats match. Three fresh packaged first computations take 3.59–3.66s after config. No new env, dependency, migration or routing key is needed. [Evidence/maps](evidence/coarse-finer-2026-10-23/README.md), [recovery](local-development.md#finer-resolution-v8).

All 35 saved development trips remain reached/shaded: **29 improve, six regress**, worst +3.180 min. Mean absolute differences **11.579→10.288 / 17.211→12.011 min**. All paths/regressions remain visible. These reused regional references do not prove national or 6–12h frontier accuracy. The 0.025° experiment is complete; do not rebuild it as a health check.

<a id="1-publish-and-verify-latest-v8"></a>

## 1. Publish and verify the time slider

The local main page now uses **one 30-minute–12-hour slider, default two hours**, with automatic release/key computation and loading feedback. The optional compute button remains for coordinate edits/retry. API min30 is implemented and tested; source data/weights/env/schema are unchanged. A single public live configuration GET confirms v8 with the previous min60, not its Git revision or full behavior. [Observation](evidence/time-slider-2026-10-23/production-config-before-slider.json), [UX checks](evidence/time-slider-2026-10-23/checks.json).

Review/publish the current small UX/tooling/doc changes through the existing user-managed workflow. V7/v8 artifacts are already committed; preserve all source/failed/secret assets. No agent commit/push/deployment occurred. These checks already pass; repeat only for changes/unresolved concerns:

```sh
npm run check
npm run typecheck
node --import tsx --test src/server/*.test.ts
npm run test:coarse-data
npm run routing:verify:coarse
npm run build
npm run build:vercel
npm run check:coarse:vercel
```

When Ready, identify the actual deployed revision, then deliberately run:

```sh
node --import tsx scripts/verify-coarse-deployment.ts https://geo-planner-orcin.vercel.app
```

**Pass:** revision includes v8; config reports `coarse-road-grid-v8` / `natural-earth-census-2026-grid-v8`; fifteen HTTP checks match saved v8 counts/notices, invalid inputs fail, detailed research is disabled and fresh no-cookie history is configured/empty. Verify arbitrary public 6/10/12h browser queries with **0.025° / 1.8–2.8 km** notices; verify slider default120/min30/max720, pointer/key automatic updates, loading/latest-request behavior, and a new fixture Cloud saved→reload→Replay/map controls. Inspect only fixture history; no private cookies or bulk export. Record actual revision/URL and measured timing scopes/screenshots in a new run. Old v6/v7 fail the version assertion; pre-slider v8 intentionally fails the updated min30 assertion. First/repeat HTTP requests are not proven cold/warm. Do not redeploy unchanged code for documentation or rerun full DB integration when persistence is unchanged.

## 2. Implement bounded reference capture/replay

A [fixed 48-query frontier plan](evidence/coarse-holdout-plan-2026-10-23/README.md) is now prepared and sealed, before any new reference result. It uses eight public non-Southern-California origins, 6/10/12h and inside/outside pairs. Two offline preparations match byte for byte. [Exact requests](evidence/coarse-holdout-plan-2026-10-23/plan.json), [preparer](../scripts/prepare-coarse-holdout.ts). This is a model-conditioned boundary check, not a random national sample or area accuracy qualification. The existing 35 regional references remain development data.

Next build/review a capture/replay helper around the sealed plan: hard cap **48 POST Directions requests**, fixed new HeiGIT endpoint, at least 6.5s between requests, 45s timeout, zero retries/fallback/paid upgrades and stop on 401/403/429. Reuse existing server-only `ORS_API_KEY` without printing it. Preserve exact requests, bounded raw responses, UTC timings, nonsecret quota/engine metadata and every failure in a fresh append-only run. Do not modify the sealed queries or add an auth/status probe to the budget. Fixture-only synthetic transport tests must prove the cap, stop/retry behavior, safe secret handling and offline replay before any live call.

**Before acquisition:** obtain explicit user authorization for the exact 48-request / zero-paid-spend budget. No authorization or provider call has occurred. Provider limits, current endpoint and public terms were checked in primary sources and linked from the plan. Retain all original cases, ambiguous boundary/snap-quality flags and paired-finite denominators under the predeclared scoring protocol. No source/graph producer, fresh key, DB migration or runtime routing exception is required. No generic accuracy correction has been selected yet.

## 3. Migrate the optional connected adapter's API host

Provider research found [the announced retirement](https://ask.openrouteservice.org/t/deprecating-api-openrouteservice-org-in-favour-of-api-heigit-org/7912) of `api.openrouteservice.org` for November 2–6, 2026. The new prefix is `https://api.heigit.org/openrouteservice/v2/`, with the same existing keys. The sealed reference plan already uses the new host. The main app's optional connected adapter is unchanged; make a focused URL/mock-test update before relying on it after retirement. Keep its 60-minute cap, server-only key, no retries/fallback and no automatic live provider check. The default coarse estimator remains independent of that service.

## Deferred scope

Further resolution increases, precise topology/traffic/turns/terrain/access, border eligibility, exact coastlines, caching, accounts/sharing/import, history cleanup/rate limits, PostGIS/spatial layers and advanced routing research remain deferred. Overture remains an alternative without measured extraction footprint.

Detailed outgoing-index calibration is complete: eight payloads reproduce at 2.415/2.416 GiB. Partial-source six-hour forecast remains 9.290 GiB with margin versus 4 GiB: hold. Profiling/expansion stay parked. [Evidence](evidence/source-outgoing-2026-10-19/README.md), [six-hour report](six-hour-preflight.md), [two-hour baseline](two-hour-region.md). Do not rerun completed producers as health checks.
