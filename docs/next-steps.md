# Next steps for coding agents

Updated October 22, 2026. Read [AGENTS.md](../AGENTS.md), [the handoff](agent-handoff.md), [current status](implementation-status.md) and [local development](local-development.md).

## Current direction

Keep a simple fullstack Vercel app estimating coarse 1–12-hour isochrones from arbitrary contiguous-US land origins. Every production rule must be generic: named routes/coordinates are validation only. Preserve coarse warnings and distinguish display resolution from accuracy. Detailed regional graph expansion and memory research remain parked.

The user visually accepted the deployed v3 baseline. Repository commit `887ab50` contains v3, cloud history and prior evidence. **V4 is implemented and verified locally, but uncommitted and not deployed.** It adds charged access along retained source-road visits while preserving every v3 graph/mask/anchor/shore field and existing speeds. All 35 saved point comparisons remain reached/shaded: 31 improve, four stay unchanged, none regress. [V4 model](coarse-estimator.md#v4-charged-road-attachment), [evidence](evidence/coarse-v4-2026-10-22/README.md).

Cloud PostgreSQL history and its initial additive migration are implemented. Preserve ignored `.env`/`.env.local`, routing settings, all four coarse artifacts, original/failed evidence and parked detailed-engine assets. No new env variable, DB migration or routing service is required for v4.

## 1. Ship and inspect v4

The current verification already passes: **45 server tests, eight geometry tests, 42 national smoke cases, Biome, app/diagnostic typechecks, ordinary/Vercel builds and generated-handler packaging checks**. Browser San Diego 6h/New York 12h show v4 contours and warnings. Do not repeat completed producers or spend hosted routing quota for routine recovery.

Safe offline comparison:

```sh
npm run routing:compare:coarse:candidate
```

Expected: original eleven common-finite point cases have mean absolute reference difference **31.3810m v3 → 22.1808m v4**, eleven improve. Broader **24/24** common-finite cases have **38.8860m → 34.2337m**, twenty improve, four unchanged, none regress. Both models reach/shade every destination. The broader denominator now includes the shore trip v3 restored; it is not the older 23-case mean. Both sets guide development and are not fresh holdouts or nationwide accuracy evidence.

For cost/path diagnosis with the cached pinned roads, without any network request:

```sh
node --import tsx scripts/inspect-coarse-access.ts src/server/data/coarse-grid-v4.json docs/evidence/coarse-v4-2026-10-22/comparison.json
```

All 35 point costs and path sums must reconstruct. With no arguments, that script preserves the older v3 diagnostic. The older `routing:compare:coarse:regional` still replays fixed v1/v2 results (23/24 finite); it does not evaluate active v4.

Review the complete uncommitted access/v4 change, commit the compact artifact with its code/evidence, and use the existing Vercel project/deployment workflow. Inspect available Vercel project context before requesting its URL again. No deployment was performed in this v4 session; a fresh clone of `887ab50` still runs v3.

Acceptance on a v4 deployment: GET `/api/estimate` ready with `coarse-road-grid-v4`; arbitrary inland/rural/coastal 6/10/12h queries produce filled approximate results; unsupported origins/budgets fail clearly; new history saves/restores and retains browser isolation; map controls/export work; no routing-service requests. Do not enable `/api/experiment`. Record the deployed revision and observation scope. Cloud cold/warm latency, concurrency and peak memory are not established by local handler execution or process snapshots.

## 2. Prioritize compact road-source completeness

The access refinement is complete. Source omissions remain the largest measured gaps: Big Bear/Bombay Beach have no source road within approximately 30.0/22.5 km, forcing long assumed 25 km/h travel. Palm Springs has a source road nearby but it is not its cell's canonical-owner visit; this scoped correction only changes Palm Springs–Idyllwild from 96.4m to 95.5m. [Access diagnosis](evidence/coarse-access-2026-10-22/README.md) and [v4 path components](evidence/coarse-v4-2026-10-22/path-diagnostics.json) separate these limits.

Next choose a more complete **nationwide compact road source/augmentation** behind the same API. Start with a bounded source/size/connectivity assessment; reuse cached inputs for an offline extraction pilot where useful. A regional pilot tests a generic method, never a place-specific production exception or a nationwide accuracy claim. Do not restart the detailed turn-aware regional graph, grow its extract, build a nationwide detailed network, or download large inputs merely as a health check. Compare countrywide availability/licensing/update paths and projected compact bundle cost before choosing new acquisition. More general within-cell road transfers are an alternative to assess if source completeness alone cannot address access.

Acceptance: identify a concrete source/representation and the smallest generic implementation slice, with evidence separating source coverage, topology/transfer and speed assumptions. Preserve the arbitrary-input contract, server-only compact deployment and no-runtime-service design. Do not fix benchmarks with free transfers, hand-selected links or a blanket speed increase. New independent references require explicit authorization for quota-bearing calls.

For any subsequent runtime/data change, run relevant tests, check/typechecks, both saved comparisons, 42 national smoke cases, ordinary/Vercel builds and generated-handler packaging checks. Test positive physical costs, water/island separation, explicit bridges, failed attachments and unchanged prior artifacts/evidence. Database integration checks are needed only if persistence code changes: `npm run db:verify` and `npm run db:verify -- --vercel` write/remove one temporary owner in the configured cloud DB, and are not read-only health checks.

## Deferred scope

National/long-horizon accuracy validation, finer grids, exact coastline clipping, terrain/access/traffic/turn rules, border eligibility, caching, accounts/sharing/import, inactive-history cleanup, public-write rate limits, PostGIS, POIs/public lands/elevation and advanced routing algorithms remain deferred until chosen. Each anonymous browser has twenty saved summaries, without a global owner cap. Keep estimates useful while refining the measured limitations.

## Preserved detailed-engine baseline

The outgoing-index calibration is complete: both builds reproduce eight qualified payloads at 2.415/2.416 GiB, with proof binding/checks passing. The revised partial-source six-hour screen remains 9.290 GiB with margin versus 4 GiB: hold. The qualification owner/lifetime diagnostic never started and is parked. [Final evidence](evidence/source-outgoing-2026-10-19/README.md), [six-hour report](six-hour-preflight.md) and [two-hour baseline](two-hour-region.md) retain the original measurements/recipes. Do not rerun completed producers as health checks.
