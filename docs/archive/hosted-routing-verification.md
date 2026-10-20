# Hosted US routing verification

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

October 16, 2026. Following the user's decision to focus on the US and use a free external service, openrouteservice is connected through the existing TanStack Start server route. The user supplied the key in ignored `.env.local`; it was never included in logs, committed files or browser responses. No paid plan or cloud deployment was created.

## Reproduction

With `ROUTING_PROVIDER=openrouteservice` and `ORS_API_KEY` configured server-side:

```bash
npm run dev
# Separate terminal; spends five contour requests:
npm run routing:verify:hosted
```

For the built production preview, use `npm run build` then `node --env-file=.env.local node_modules/vite/bin/vite.js preview --port 3000` after stopping the development server. Keep 60 minutes and the default San Diego origin, then Compute. This preview command loads existing values into the process without editing the file. Vercel uses its project environment variables instead of this local file. The local Valhalla preview was verified separately on 4174 and then stopped; its measurements are distinct from hosted results. The v2 routing service/data remain available as a fallback.

The smoke command calls the app for San Diego/Los Angeles/New York/Anchorage/Honolulu and saves validated results under ignored `data/hosted-routing/verification/`. `GEO_PLANNER_URL` can select another running app or future Vercel preview. It stops on the first failure and makes no retries. Page-load configuration calls spend no contour quota.

## Real observations

All five smoke queries returned a valid polygon. Each is **one sequential observation**, not a median, percentile, cold/warm comparison or graph-search benchmark. HTTP round trip includes WAN transport, provider work, contour construction and serialization, plus body read.

| Origin | Driving budget | Engine HTTP round trip | Whole app request | Upstream bytes |
| --- | --- | --- | --- | --- |
| San Diego | 60 min | 12,531.9 ms | 12,571.1 ms | 121,575 |
| Los Angeles | 30 min | 4,819.2 ms | 4,839.9 ms | 48,018 |
| New York | 60 min | 11,925.7 ms | 11,987.1 ms | 89,356 |
| Anchorage | 30 min | 768.7 ms | 784.1 ms | 47,665 |
| Honolulu | 30 min | 469.7 ms | 484.8 ms | 26,305 |

All five responses reported openrouteservice **9.10.0**, engine build date `2026-08-13T11:53:14Z`, graph date `2026-09-21T10:31:27Z`, and OSM date `2026-09-13T23:59:59Z`. These are provider-reported dates, not a checksum-pinned rebuildable graph. Full engine revision, source PBF checksum and graph-build settings were not supplied by the hosted response. The provider may update the graph between runs. Local Valhalla uses different data/costs and is not an equivalent performance comparison.

The first real browser default query completed with engine HTTP round trip 11,860.4 ms, browser request/validation 11,947.8 ms, server decode/validation 10.8 ms, and source-to-map-idle 727.9 ms. The teal contour, provider/profile, reported engine/graph date, attribution and result license appeared correctly. The final production query verified “Routing connected” and a persistent contour: engine HTTP round trip 12,171.3 ms, browser request/validation 12,220.2 ms, decode/validation 16.4 ms and source-to-map-idle 725.1 ms. This additional observation is not a benchmark distribution. Saved histories still distinguish old local graph IDs from hosted dates.

The selected free Standard plan currently allows **500 contours/day, 20/minute**, with a **60-minute driving cap**. The smoke run and two browser queries use seven contour requests total. No quota was deliberately exhausted: HTTP 429/access failures and no-retry behavior are tested with synthetic responses. Hosted queries above 60 minutes are rejected before calling the provider. [Current plan](https://account.heigit.org/info/plans), [range limits](https://openrouteservice.org/restrictions/).

## Limits and next task

These checks establish working service/API/browser integration at five public US locations. They do not prove nationwide road coverage, optimal travel times, snapping accuracy, every turn/access restriction, monotonic contours or route/polygon agreement. The hosted API's polygon center was not promoted to a claimed snapped point; no orange snapped marker is invented. The San Diego contour visibly extends into Mexico, so US focus is not a US-only clipping or border-avoidance rule. No live border waits are modeled by the app.

Requests use the provider's `driving-car` defaults, outbound start locations, time in seconds and smoothing 0. Generalization/denoise/speed-source settings from Valhalla are not relabeled as hosted settings. Returned polygons remain approximate and metadata retains `coverageVerified: false`. The 30-second adapter timeout bounded these requests; it is not a cancellation guarantee for provider work.

Tests: all 14 cases, `npm run check`, `npm run typecheck`, `npm run build`, and `npm run build:vercel` pass. Lint retains one pre-existing database non-null assertion warning. The generated Vercel handler was exercised locally against Valhalla and contains no graph/environment files; **actual Vercel cloud deployment remains untested**. The hosted production preview uses the Node build locally.

Evidence: [real normalized responses, raw measurements and screenshots](../evidence/hosted-routing-2026-10-16). The source/license requirements are in [service setup](../us-routing-service.md); the local graph provenance remains in [regional reproduction](../regional-routing.md).

**Updated priority:** research a self-built 10–12-hour routing path before Vercel rollout; see [brainstorm and experiment gates](long-range-routing-brainstorm.md). Hosted queries remain a short-range operational baseline. Later, verify a Vercel preview and inspect sampled hosted routes/snapping and border behavior at 15/30/60 minutes. Revisit self-hosting when quotas, payment requirements or longer budgets become an actual constraint. Worldwide expansion, PostGIS, elevation, road-distance semantics, caching and advanced routing research remain deferred.
