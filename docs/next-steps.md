# Next steps for coding agents

Updated October 22, 2026. Read [AGENTS.md](../AGENTS.md), [handoff](agent-handoff.md), [status](implementation-status.md) and [local development](local-development.md).

## Current baseline — v5 ready locally

**Nationwide v5 is active locally; production remains verified v4 at `637746c`.** All subsequent runtime/data/tools/tests/evidence/docs are uncommitted. The active 39,977,082-byte v5 artifact must accompany publication; raw sources/candidates/probes remain ignored/local-only. [V5 evidence](evidence/coarse-v5-2026-10-22/README.md), [source preparation](evidence/coarse-national-2026-10-22/README.md), [existing hosted v4](evidence/coarse-hosted-2026-10-22/README.md).

The same rules support arbitrary contiguous-US land inputs at 60–720 whole minutes. Census roads add 36,742 links and lower 73 costs while retaining original roads/anchors/geography. Source notices are finalized and visible. Generic fixed geography indexing retains all validation, reducing first local packaged computation from 22.2 seconds to **2.46–2.47 seconds in three fresh processes**. Full sweeps over 153,477 inputs retain bounded memory (32.44 MB incremental decoded storage; no query cache). These are local observations, not cloud cold-start/peak-memory qualification.

51 server tests, fifteen geometry fixtures, check/typechecks, both builds and generated Vercel handler pass. All 35 costs/path components and 42 national counts match accepted national-v2 exactly. Seven saved cases improve versus v4, 28 unchanged, none regress. Local browser inland 6h/rural 10h/coastal 12h, notices and new fixture cloud save/reload/replay pass. No new env variable, migration, dependency or routing quota is needed. National driving accuracy remains unvalidated; detailed research stays parked.

## 1. Publish and verify the actual v5 deployment

Review the existing dirty tree, include the new v5 artifact and publish through the existing Git/Vercel project workflow. Do not reset/clean local work or commit secrets/raw sources. No commit/push/deploy was performed during local activation. Before publication, these are the relevant checks (already passed for the current implementation; repeat only after changes or an unresolved concern):

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

After the new deployment is Ready, identify its actual revision/model and deliberately run:

```sh
node --import tsx scripts/verify-coarse-deployment.ts https://geo-planner-orcin.vercel.app
```

**Pass:** actual deployed revision includes v5; config reports `coarse-road-grid-v5` / `natural-earth-census-2026-grid-v5`; fifteen HTTP checks pass with v5 saved cell counts, source notice, validation errors, disabled research and empty no-cookie history. Browser shows an arbitrary public 6/10/12h query, visible Census modified-data notice, a newly created fixture Cloud saved → reload → Replay and working map controls. Use only new fixture history; no private cookies/bulk export. Record revision/URL, response timing scopes and screenshot in a new measured run. Fail version/count mismatches explicitly. Updated verifier intentionally rejects old hosted v4. Do not call connected routing or acquire new references. Do not rerun the full live DB write suite unless persistence changes.

HTTP first/repeat calls do not establish cold/warm state; cloud memory/load remains unmeasured. No source acquisition/producer, DB/env/configuration change or detailed-engine run is required. [Exact setup/recovery](local-development.md#nationwide-census-candidate).

## 2. Diagnose the next generic accuracy correction

Use the saved [v5 comparisons](evidence/coarse-v5-2026-10-22/comparison.json) and [path components](evidence/coarse-v5-2026-10-22/path-diagnostics.json) to rank remaining reference differences and their endpoint/local/road contributions. Reuse existing references; do not spend quota. The current one-supplemental-visit/fixed-anchor model and repeated 25 km/h transfers remain plausible limitations, not established causes of every error. Choose a small universal correction from measured evidence before coding; no named-region/query exceptions or blanket speed increase.

Offline inspection can deliberately rerun these read-only commands when needed (cached Natural Earth roads are needed only for the path diagnostic):

```sh
node --import tsx scripts/compare-coarse-candidate.ts src/server/data/coarse-grid-v5.json
node --import tsx scripts/inspect-coarse-access.ts \
  src/server/data/coarse-grid-v5.json \
  docs/evidence/coarse-v5-2026-10-22/comparison.json
```

**Acceptance for an ensuing implementation:** preserve existing source/evidence artifacts, physical distance charges, country/lake/shore checks, arbitrary-query behavior and runtime deployment independence. Add meaningful synthetic tests for the chosen general rule; compare every saved cost/path and national count explicitly. Recheck package/initialization/retained storage only when affected. Use a new artifact/recipe if graph geometry/costs change; keep original results distinguishable from interpretation. The existing development sets do not establish national accuracy, so report their limits.

## Deferred scope

Fresh nonregional driving references need explicit quota authorization. Precise topology/traffic/turns/terrain/access, border eligibility, finer grids/exact coastlines, caching, accounts/sharing/import, history cleanup/rate limits, PostGIS/spatial layers and advanced routing algorithms remain deferred. Overture remains a source alternative without a measured extraction footprint. Keep the useful coarse app working while refining measured gaps.

Detailed outgoing-index calibration is complete: both builds reproduce eight payloads at 2.415/2.416 GiB. Partial-source six-hour forecast remains 9.290 GiB with margin versus 4 GiB: hold. Memory profiling/graph expansion remain parked. [Evidence](evidence/source-outgoing-2026-10-19/README.md), [six-hour report](six-hour-preflight.md), [two-hour baseline](two-hour-region.md). Do not rerun completed producers as health checks.
