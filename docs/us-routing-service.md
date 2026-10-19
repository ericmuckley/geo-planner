# US routing: start with a free external service

Decision, October 16, 2026: focus on the US, keep one fullstack TanStack Start app on Vercel, and use a free external routing service first. Revisit self-hosting when usage limits or payment requirements become a problem. Worldwide expansion is deferred. The original 10–12-hour driving requirement is still unmet; the user now wants to [brainstorm building that capability ourselves](long-range-routing-brainstorm.md) before Vercel rollout. This free endpoint is the short-range baseline.

**Selected integration: openrouteservice's free Standard plan.** Its current account page lists 500 isochrone requests/day and 20/minute. Hosted driving contours stop at **60 minutes**, so the default query fits; 120-minute and 10–12-hour hosted driving queries do not. The provider maintains its road graph; this app does not need to ship or build a US graph. [Current plans](https://account.heigit.org/info/plans), [range restrictions](https://openrouteservice.org/restrictions/).

| Service checked | Free-plan fit for this app |
| --- | --- |
| openrouteservice | 60-minute driving supported; 500 contours/day, 20/minute. Selected. |
| Geoapify | Free driving contours stop at 15 minutes, so the default query would need a paid plan. [Pricing](https://www.geoapify.com/pricing/). |
| Mapbox | Supports 60 minutes, but its isochrone API requires a Mapbox map/library. The app currently uses MapLibre. [API requirements](https://docs.mapbox.com/api/navigation/isochrone/). |

Limits were checked October 16; verify the account dashboard before relying on them. A free routing plan does not guarantee zero Vercel hosting cost. Quota errors stop the request; the app never upgrades, retries automatically, or switches to a paid service.

## Connect your free key

1. Create a [HeiGIT account](https://account.heigit.org/) and obtain its free Standard API key. Account creation and accepting the provider's terms are user steps.
2. Add these values to the existing ignored `.env.local`, preserving other settings:

   ```dotenv
   ROUTING_PROVIDER=openrouteservice
   ORS_API_KEY=your-key
   ```

3. Restart with `npm run dev`. Docker and `VALHALLA_URL` are unnecessary for this provider. The key stays on the server; never use a `VITE_` prefix or paste it into chat/Git.
4. Compute the default 60-minute San Diego query. For Vercel, set the same two server environment variables in the project settings and redeploy the single app. No extra app/server deployment is needed.

The backend uses `https://api.heigit.org/openrouteservice/v2/isochrones/driving-car` with the key in an Authorization header. The old `api.openrouteservice.org` hostname is deprecated. [Provider migration announcement](https://ask.openrouteservice.org/t/deprecating-api-openrouteservice-org-in-favour-of-api-heigit-org/7912).

Page load reports **key configured**, not **service healthy**, and uses no contour quota. A successful validated hosted query changes the badge to **Routing connected**; this records that successful request, not continuous monitoring. Computing or replaying a query spends one contour request. The UI remains click-to-compute. A provider HTTP 429 is surfaced as a quota error; HTTP 401/403 reports key/permission/daily-quota checks. There is no durable shared quota counter yet.

## Semantics and verification

Requests use `driving-car`, outbound `location_type=start`, a time range in seconds, and `smoothing=0`. Other routing costs use provider defaults. These differ from Valhalla; saved runs identify the engine and must not be compared as if their graphs/costs were identical. Returned engine version, graph date, OSM date and build date are retained when available; absent provenance stays unrecorded. No isolated graph-search timing is claimed. [Isochrone API documentation](https://giscience.github.io/openrouteservice/api-reference/endpoints/isochrones/).

The US is our product focus, not a polygon filter: cross-border travel may appear near Canada/Mexico. Smoke queries succeeded in San Diego, Los Angeles, New York, Anchorage and Honolulu. Nationwide completeness, border behavior and provider snapping remain unverified. The adapter does not invent a snapped-origin marker from the provider's polygon center. Filled contours remain approximate, with `coverageVerified: false`.

Required attribution and the result license are shown with hosted results and retained in exported metadata: © openrouteservice by HeiGIT | Data from OpenStreetMap; CC-BY-SA 4.0. The provider prohibits transmitting personal data; current public-location smoke queries send coordinates without account/user identifiers. Review the intended use before sending personal locations. [Provider terms](https://account.heigit.org/info/tos).

**Status:** the user configured the key, and all five US smoke queries succeeded through the real provider. The default 60-minute San Diego contour also rendered in the browser with attribution and reported provenance. See [measured hosted verification](hosted-routing-verification.md). Actual Vercel cloud deployment and independent routing correctness remain unverified. To repeat the five-query smoke run with the configured app:

```bash
npm run routing:verify:hosted
```

This spends five contour requests: San Diego/Los Angeles/New York/Anchorage/Honolulu. It saves validated results and measurements in ignored `data/hosted-routing/verification/`, stops on the first failure, and does not retry. Set `GEO_PLANNER_URL` to a running preview URL to check that same fullstack deployment. Add sampled provider directions, inspected snapping and near-border checks before claiming correctness.

To use the preserved regional baseline explicitly: `npm run routing:up` then `npm run dev:routing`. That command selects Valhalla by default and leaves `.env.local` unchanged. See [regional reproduction](regional-routing.md). Keep the graph/source snapshots; no further graph expansion is currently needed.
