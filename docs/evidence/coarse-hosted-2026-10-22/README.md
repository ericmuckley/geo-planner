# Hosted v4 verification — October 22, 2026

[Production](https://geo-planner-orcin.vercel.app) serves **`coarse-road-grid-v4`**. The existing Vercel project overview shows Ready / main / commit **`637746c04c12fe46e7b64222b1a3ff7a30bcd86a`**. [Deployment identity](deployment.json) records the observed overview and deployment URLs. The user had already committed/deployed it; this agent did not push, promote, change hosting settings or redeploy.

[The live API check](api.json) makes 15 requests: configuration, five representative 6/10/12h estimates, one repeat, two overlapping estimates, four invalid requests, disabled research API and fresh-client history. All pass. San Diego, Denver, New York, rural Utah and Key West return filled validated contours with cell counts matching the saved v4 national checks. Responses retain no-store, approximation warnings, v4 identity and `coverageVerified: false`. Malformed JSON returns 400; unsupported budgets/geography return 422; `/api/experiment` returns 503. No-cookie history is configured and empty. No history write, cookie inspection or routing-provider endpoint is used by the verifier. One successful GET configuration probe preceded this run.

Observed HTTP round trips for the eight computations range **119.9–725.4 ms**, including this machine's network/body delivery. San Diego's first observed call is 725.4 ms and its repeat 176.1 ms; actual cold/warm invocation state is unknown. The two overlapping calls succeed at 183.5/297.1 ms, without establishing load capacity. Returned server search/contour timings have separate scopes. Cloud peak memory, percentiles and actual deployed bundle bytes were not measured; prior 13.45 MB packaging is a local build result.

[Browser evidence](browser.json) and [screenshot](browser-san-diego-6h.png) confirm a 2,162-cell six-hour contour, Cloud saved, restoration of the same public test after reload, replay, visibility toggle and zoom controls. Export is enabled but was not used to collect pre-existing history. Normal public test computations use automatic saving; no bulk old-history backup occurs. Fresh no-cookie HTTP history is empty; the prior broader owner-isolation/concurrency DB tests were not repeated. The only observed console errors are the pre-existing wallet extension's `window.ethereum` error.

```sh
node --import tsx scripts/verify-coarse-deployment.ts https://geo-planner-orcin.vercel.app
```

This spends app function requests, **zero hosted routing quota**, and no verifier history writes. Do not run it automatically as a documentation check. The first sandbox network probe failed DNS resolution; authorized normal network access succeeded. Biome (145 files), strict verifier typecheck and [ordinary build](build.log) pass. Application code/data, database schema and env settings are unchanged. Prior v4 tests/build/evidence retain their original scope and bytes. Adjacent manifests bind this new observation.
