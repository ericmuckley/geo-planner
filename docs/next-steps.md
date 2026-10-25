# Next steps for coding agents

Updated October 25, 2026. Read [AGENTS.md](../AGENTS.md), [handoff](agent-handoff.md), [status](implementation-status.md) and [local development](local-development.md).

## Current baseline

Local **v9 is qualified/active, uncommitted and not deployed**. [Frozen policy, all 83 comparisons and qualification](evidence/coarse-path-features-2026-10-24/README.md). It uses generic NE-connector 55/secondary 85/major 105 costs on unchanged 0.025° geometry. Overall ORS MAE 34.612→29.257 min; frontier false 17→11/missed 5→2. 59 improve/24 regress; frontier median and older Valhalla means worsen. All planned gates pass, not a nationwide or fresh-holdout guarantee. Earlier 95/85 and 100/82 artifacts remain rejected under unchanged plans. V8/slider are last user-reported hosted; baseline commit `37ff14b` contains earlier tools/results. Floating-map UI edits remain separate and byte-preserved.

Geometry diagnosis, one prospective candidate, independent source repeat, accuracy/path/source/land checks, memory/package/software/HTTP/browser qualification and version-only v9 activation are complete. Do not rerun completed producers or sweeps as readiness checks. All 48/6/29 budgets are consumed; no new routing-provider request/retry/probe/key check is authorized. No env/DB/schema/dependency change is needed.

<a id="1-publish-and-verify-latest-v8"></a>
<a id="1-publish-and-verify-the-time-slider"></a>
<a id="1-authorize-and-acquire-the-frozen-reference-set"></a>
<a id="1-prototype-generic-road-class-timing-calibration"></a>
<a id="2-preserve-reproducible-offline-reference-access"></a>
<a id="1-implement-and-test-the-matched-reference-control"></a>
<a id="2-obtain-the-separate-six-request-budget-then-acquire"></a>
<a id="1-obtain-the-separate-six-request-budget-then-acquire"></a>
<a id="2-interpret-the-matched-results-and-select-a-generic-correction"></a>
<a id="1-prepare-the-remaining-same-provider-benchmark-offline"></a>
<a id="1-obtain-the-separate-29-request-budget-then-acquire"></a>
<a id="2-interpret-the-consistent-provider-development-benchmark"></a>
<a id="1-specify-one-generic-timing-cost-revision-offline"></a>
<a id="2-produce-and-evaluate-the-one-planned-revision-then-qualify-only-if-it-passes"></a>
<a id="current-ui-follow-up-ready-for-review"></a>
<a id="completed-v8-hosted-slider-and-first-frontier-references"></a>
<a id="completed-class-timing-candidate-rejected"></a>
<a id="completed-matched-reference-runner-tested"></a>
<a id="completed-six-matched-route-references-acquired"></a>
<a id="completed-remaining-29-planrunner-tested-offline"></a>
<a id="completed-all-83-same-provider-references-paired"></a>
<a id="completed-damped-10082-experiment-rejected"></a>
<a id="1-diagnose-generic-features-beyond-class-and-expressway"></a>
<a id="2-evaluate-only-the-next-evidence-backed-planned-revision"></a>
<a id="deferred-scope"></a>

## 1. Review, commit and deploy the qualified local changes

Review v9 activation, its new 61.23 MB runtime JSON, npm verification targets, source tests and measured evidence alongside the separate floating UI. Preserve older artifacts, failed attempts and sealed producers; do not commit ignored sources or credentials. Git is read-only in the agent workspace, and no commit/push/deployment has been performed. Source packaging includes only the imported runtime version. [Recovery/commands](local-development.md#connector-timing-v9).

Safe checks after a new code change:

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

**Pass:** normal/strict typechecks,56 server/43 Python fixtures and 42 API cell counts pass; generated Vercel handler reports `coarse-road-grid-v9` / `natural-earth-census-2026-grid-v9`, min 30/max 720, first local compute<=5s and function<=70MB, with no outbound routing fetch, client dataset/secret/raw input/env leakage, and missing-DB history fallback. These checks are already completed for this milestone; docs-only changes need link/diff/binding checks, not another build/producer/sweep.

## 2. Verify the hosted v9 deployment

After the user reports the deployment Ready, use the actual deployment URL. Read-only app verifier:

```sh
node --import tsx scripts/verify-coarse-deployment-v9.ts https://geo-planner-orcin.vercel.app > /tmp/coarse-v9-hosted.json
```

It makes 15 app requests, zero provider requests/history writes, and expects the configured production DB's anonymous history to be empty. `--database-free` is only for a deliberately unconfigured local preview. Never weaken version/count assertions to accept old production. Public responses identify model versions, not Git SHA.

**Pass:** v9 metadata/min 30/max 720, saved 6/10/12h counts, repeat/overlap smoke, input errors, disabled experiment and fresh no-cookie history all pass. Browser reload/default 120/min 30/release/visible loading/latest-result/newv 9 metadata/contours work. Inspect only public validation fixtures; unchanged persistence needs no new cloud writes/full DB suite. Preserve any deployment mismatch before later success. Update current docs with the actual outcome and distinguish HTTP round trip, server search/contour timing and cold-start uncertainty.

## 3. Select the next structural accuracy improvement

After hosted verification, review remaining divergent paths, source omissions and within-cell road merging using the saved full ledger. Grid spacing remains 0.025°; another timing tweak cannot promise visually finer boundaries. Favor one maintainable generic topology/geometry change with a measurable product benefit over a numerical sweep. Freeze hypothesis, scope and all per-set/horizon/tail/individual/classification/physical/runtime/package gates before production. Keep all 83 development cases,24 current regressions, frontier-median/Valhalla sensitivities and unsupported-origin limits visible.

**Pass:** one concrete bounded proposal, exact inputs and acceptance criteria before a new producer; no city/coordinate/region/fixture exceptions, no retroactive failed-gate changes. A genuinely fresh reference test requires a separately approved bounded acquisition plan; saved 83 are development data. No more provider/source acquisition is authorized now.

## Deferred scope

Further resolution increases until explicitly planned, traffic/turns/terrain/access, precise borders/coasts, caching, accounts/sharing/import, history cleanup/rate limits, PostGIS and advanced routing research remain deferred. Detailed regional six-hour expansion remains held: partial-source forecast 9.290 GiB versus 4 GiB; exact calibrated payloads 2.415/2.416 GiB. [Preserved six-hour report](six-hour-preflight.md), [two-hour baseline](two-hour-region.md). Unchanged persistence does not need full DB integration reruns.
