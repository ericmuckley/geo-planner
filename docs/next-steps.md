# Next steps for coding agents

Updated October 23, 2026. Read [AGENTS.md](../AGENTS.md), [handoff](agent-handoff.md), [status](implementation-status.md) and [local development](local-development.md).

## Completed: finer nationwide v6

**V6 is active locally at 0.05° (about 3.5–5.5 km cells); production is user-reported v5 at `08074fb`.** New runtime/data/tools/evidence/docs are uncommitted. [V6 evidence / visible comparisons](evidence/coarse-resolution-2026-10-23/README.md), [handoff](agent-handoff.md), [model](coarse-estimator.md). The new configurable builder rebuilds masks, anchors, roads, shores and visits from existing pinned inputs. It does not resize v5 labels or modify sealed historical producers.

Active artifact: 68,129,975 bytes / SHA `a1ba5ae3eb7419feb458641f00da1886802fc16ec11af86e3d61d42a3b8b3f99`, with exact source/repeat/version parity. All 35 saved cases remain reached/shaded: 26 improve, nine regress, worst +7.092 min. Original/broader mean absolute reference differences fall 33.0%/24.3%; these reused development sets are not national or long-horizon accuracy proof. All regressions/path components remain visible. No 0.025° candidate exists.

First local package computation meets the <5s engineering target in three fresh runs (3.06–3.12s); final active handler is 71,940,272 bytes/28 files with zero outbound calls. Retained decoded storage is 57.30MB; 405,384 inputs retain bounded memory. 51 server tests, nineteen geometry fixtures, full link/shore proofs, 42 active API cases, check/typechecks, both builds, local handler, twelve paired UI scenarios and main-app fixture cloud save/reload/replay pass. Cloud cold starts, peak memory/load capacity remain unmeasured. No new env variable, dependency or migration is required.

## 1. Publish and verify actual v6

Review the dirty tree and publish using the existing Git/Vercel project workflow. Include **`src/server/data/coarse-grid-v6.json`** and the new scripts/templates/evidence; preserve ignored raw sources, credentials and all v1–v5 artifacts. No commit/push/deployment occurred during local activation. Checks below already pass; repeat only after changes or an unresolved concern:

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

When the new deployment is Ready, identify its actual revision and deliberately run:

```sh
node --import tsx scripts/verify-coarse-deployment.ts https://geo-planner-orcin.vercel.app
```

**Pass:** deployed code includes v6; config reports `coarse-road-grid-v6` / `natural-earth-census-2026-grid-v6`, fifteen app HTTP checks match saved v6 counts/notices, invalid inputs fail, detailed research is disabled and fresh no-cookie history is empty/configured. Verify one arbitrary public 6/10/12h browser query, visible 0.05°/3.5–5.5km source notices and new fixture Cloud saved→reload→Replay/map controls. Inspect only fixture history; no private cookies/bulk export. Record deployed revision/URL and measured timings/screenshots in a new run. Updated verifier intentionally rejects old v5. First/repeat HTTP calls do not establish cold/warm state. Do not redeploy unchanged code merely for documentation or rerun full DB integration unless persistence changes.

## 2. Refine remaining generic access/transfer error

Use all [35 v6 comparisons](evidence/coarse-resolution-2026-10-23/comparison.json), [reconstructed paths](evidence/coarse-resolution-2026-10-23/path-diagnostics.json) and [nine regressions](evidence/coarse-resolution-2026-10-23/regressions.json). Several regressions add intercell overland travel; one canonical anchor and one supplemental road per cell remain plausible causes to test, not isolated causal error measurements. Choose a small universal correction from evidence before coding. Do not patch named routes/coordinates, raise all speeds or silently drop worse/unreached cases.

Existing offline review commands (no source downloads/providers):

```sh
node --import tsx scripts/compare-coarse-resolution.ts data/coarse-quality/resolution-005-v2/grid.json
node --import tsx scripts/inspect-coarse-access.ts \
  data/coarse-quality/resolution-005-v2/grid.json \
  docs/evidence/coarse-resolution-2026-10-23/comparison.json
```

The comparator deliberately baselines preserved v5 and accepts different dimensions/anchors. The older candidate comparator requires fixed v4 geometry and is unsuitable for cross-resolution comparisons. To compare a subsequent cost correction against v6, add an explicit new baseline/version without overwriting these records. Report all paired errors and every unreachable/unshaded outcome. Add meaningful synthetic fixtures for the chosen generic rule; preserve physical distance, full source/land/country/lake/shore validation and Vercel runtime independence. Recheck affected resource/package behavior, including the existing local <5s initialization target, when storage/runtime changes.

A 0.025° experiment is a possible later product step, after actual v6 feedback. Reuse the configurable builder into a fresh versioned directory and measure size/runtime rather than extrapolating; do not assume accuracy improves just because cells are smaller. [Exact producer/recovery commands](local-development.md#finer-resolution-v6). No completed producer or quota call is needed to validate documentation.

## Deferred scope

Fresh nonregional driving references need explicit quota authorization. Precise topology/traffic/turns/terrain/access, border eligibility, exact coastlines, caching, accounts/sharing/import, history cleanup/rate limits, PostGIS/spatial layers and advanced routing algorithms remain deferred. Overture remains a source alternative without a measured extraction footprint. Keep the useful coarse app working while refining measured gaps.

Detailed outgoing-index calibration is complete: both builds reproduce eight payloads at 2.415/2.416 GiB. Partial-source six-hour forecast remains 9.290 GiB with margin versus 4 GiB: hold. Memory profiling/graph expansion remain parked. [Evidence](evidence/source-outgoing-2026-10-19/README.md), [six-hour report](six-hour-preflight.md), [two-hour baseline](two-hour-region.md). Do not rerun completed producers as health checks.
