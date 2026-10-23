# Next steps for coding agents

Updated October 23, 2026. Read [AGENTS.md](../AGENTS.md), [handoff](agent-handoff.md), [status](implementation-status.md) and [local development](local-development.md).

## Completed: finer v8 with road continuity

**V8 is active locally at 0.025° (about 1.8–2.8 km cells). V7/v8 changes are uncommitted; HEAD/user-reported verified production remain v6 at `ffd7fec`.** V8 rebuilds 2,454,400 cells, retaining generic paid Census road states. Lossless arrays reduce the raw 179.92 MB model to a 61.21 MB artifact; local Vercel function is 65.02 MB. Independent source/proof/packed/finalization repeats match. Three fresh packaged first computations take 3.59–3.66s after config. No new env, dependency, migration or routing key is needed. [Evidence/maps](evidence/coarse-finer-2026-10-23/README.md), [recovery](local-development.md#finer-resolution-v8).

All 35 saved development trips remain reached/shaded: **29 improve, six regress**, worst +3.180 min. Mean absolute differences **11.579→10.288 / 17.211→12.011 min**. All paths/regressions remain visible. These reused regional references do not prove national or 6–12h frontier accuracy. The 0.025° experiment is complete; do not rebuild it as a health check.

## 1. Publish and verify latest v8

Review/publish through the existing user-managed Git/Vercel workflow. Include **both `src/server/data/coarse-grid-v7.json` and `coarse-grid-v8.json`** plus accumulated code/tools/tests/evidence/docs. Preserve all old bundled artifacts, ignored sources and secrets. V7 publication is superseded by the latest v8; no agent commit/push/deployment occurred. These checks already pass; repeat only for changes/unresolved concerns:

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

**Pass:** revision includes v8; config reports `coarse-road-grid-v8` / `natural-earth-census-2026-grid-v8`; fifteen HTTP checks match saved v8 counts/notices, invalid inputs fail, detailed research is disabled and fresh no-cookie history is configured/empty. Verify arbitrary public 6/10/12h browser queries with **0.025° / 1.8–2.8 km** notices and a new fixture Cloud saved→reload→Replay/map controls. Inspect only fixture history; no private cookies or bulk export. Record actual revision/URL and measured timing scopes/screenshots in a new run. Old v6/v7 intentionally fail the updated version assertion. First/repeat HTTP requests are not proven cold/warm. Do not redeploy unchanged code for documentation or rerun full DB integration when persistence is unchanged.

## 2. Plan independent national and long-horizon validation

The app now has finer cells and lower aggregate error on its reused development cases. Before more fitting or resolution increases, design a **fixed nonregional holdout plan** covering arbitrary public inland/rural/coastal/mountain/border origins and 6/10/12h frontiers. Selected places belong only to validation, never routing rules. Read all [35 comparisons](evidence/coarse-finer-2026-10-23/comparison.json), [six regressions](evidence/coarse-finer-2026-10-23/regressions.json) and [paths](evidence/coarse-finer-2026-10-23/paths.json).

**Acceptance before reference acquisition:** seal the query set/model identities and scoring rules, including origin/destination access, finite/unreachable outcomes and inside/outside frontier tests. Verify the chosen provider/reference's actual supported geography/horizon/route limits and current terms using primary sources; state exact request count/cost cap and retain raw requests/responses. Fresh reference quota needs explicit user authorization; prepare a concrete reviewable plan first. No provider/key fallback, repeated public demo use, DB migration or detailed regional graph expansion is needed to plan it. Existing regional references remain development data, not holdouts.

For offline inspection of current results (no producer/network/quota):

```sh
node --import tsx scripts/compare-coarse-resolution.ts data/coarse-quality/resolution-0025-evaluation-v1/grid-packed.json --baseline-v7
node --import tsx scripts/inspect-coarse-access.ts data/coarse-quality/resolution-0025-evaluation-v1/grid-packed.json docs/evidence/coarse-finer-2026-10-23/comparison.json
```

Expect all 35 v7 baseline costs to match exactly, 29 improvements/six regressions and every saved destination reached/shaded. Do not silently drop worse or unreachable results. No new generic routing correction is selected yet. Keep v8 deployable, preserve physical/source/land checks, and retain every old/failed result in a new versioned run when changing semantics.

## Deferred scope

Further resolution increases, precise topology/traffic/turns/terrain/access, border eligibility, exact coastlines, caching, accounts/sharing/import, history cleanup/rate limits, PostGIS/spatial layers and advanced routing research remain deferred. Overture remains an alternative without measured extraction footprint.

Detailed outgoing-index calibration is complete: eight payloads reproduce at 2.415/2.416 GiB. Partial-source six-hour forecast remains 9.290 GiB with margin versus 4 GiB: hold. Profiling/expansion stay parked. [Evidence](evidence/source-outgoing-2026-10-19/README.md), [six-hour report](six-hour-preflight.md), [two-hour baseline](two-hour-region.md). Do not rerun completed producers as health checks.
