# Geo Planner documentation

For a new agent or disconnected session, read [AGENTS.md](../AGENTS.md), then [the resume guide](agent-handoff.md). Updated October 25, 2026. V8 and slider were committed through `9b3e83b`, user-reported deployed; reference tools/results are committed at `37ff14b`. The floating-map UI and subsequent accuracy work are local/uncommitted. Raw sources, research datasets and secrets remain ignored.

**V9 is qualified and active locally, uncommitted and not deployed.** It retains the 0.025° grid and changes generic travel costs: Natural Earth artificial connections use 55 km/h, secondary roads 85, major roads 105, Census connections/local travel 25. All rules apply everywhere; locations occur only in validation. Across 83 saved ORS development routes, mean absolute difference falls **34.612→29.257 min**; frontier missed reachable **5→2**,  false reachable **17→11**. All prospective gates pass. [Decision, complete ledger and limits](evidence/coarse-path-features-2026-10-24/README.md).

Gains are uneven: 59 routes improve/24 regress, frontier median worsens 37.254→40.561 min, and the older Valhalla sensitivity means worsen. This is an observed development comparison, not nationwide/area accuracy or a fresh holdout. Cell spacing is unchanged. Both earlier timing candidates remain rejected under their original frozen decisions. No new provider call, download, DB write, env/schema/dependency change, commit or deployment occurred. All 48/6/29 reference budgets are consumed.

## Current documents

| Document | Purpose |
| --- | --- |
| [Agent handoff](agent-handoff.md) | Recovery checks, graph/data locations, restart commands and resume prompt |
| [Implementation status](implementation-status.md) | Current capabilities, limits, code map and validation |
| [Local development](local-development.md) | App setup and the separate experimental/provider APIs |
| [Next steps](next-steps.md) | Review/commit/deploy qualified local v9, then verify hosted behavior |
| [Coarse estimator](coarse-estimator.md) | Implemented nationwide grid model, assumptions, sources and local Vercel evidence |
| [Six-hour preflight](six-hour-preflight.md) | Unclipped planning, source gaps and the current resource screen |
| [Two-hour regional baseline](two-hour-region.md) | Current graph's exact recipes, provenance, measurements and evidence |
| [Progress](progress.md) | Plain-language summary |
| [Initial project plan](initial-project-plan.md) | Long-term vision and semantics; current decisions above take precedence |
| [US service setup](us-routing-service.md) | Selected hosted main-page provider and recorded limits |
| [Retained Valhalla recipe](regional-routing.md) | Separate local Valhalla build/service reference |

**October 23 follow-up:** v8 halves cell width again to 0.025°, retaining v7's paid Census road states. All 35 saved queries are reached/shaded: 29 improve, six regress at most 3.18 min. Mean differences **11.579→10.288 / 17.211→12.011 min** on reused development sets, not national accuracy proof. Source/proof/packed repeats match; lossless storage reduces 179.92 MB to 61.21 MB, producing a 65.02 MB local Vercel function. Three fresh first computations take 3.59–3.66 s after config; retained decoded storage is 158.04 MB and bounded across 952,758 inputs. 56 server tests, nineteen Python fixtures, 42 API cases, checks/typechecks, both builds and handler/browser fixture checks pass. [V8 evidence/maps](evidence/coarse-finer-2026-10-23/README.md), [v7 road continuity](evidence/coarse-connections-2026-10-23/README.md), [v6 finer-grid evidence](evidence/coarse-resolution-2026-10-23/README.md), [next steps](next-steps.md). The hosted slider follow-up verifies the deployed v8 contract; v9 above is the latest local model.

**Current UX/planning:** [slider verification](evidence/time-slider-2026-10-23/checks.json) covers native pointer/keyboard updates, loading, latest-result behavior, 30-minute acceptance, builds and local packaging. The optional compute button remains for coordinate edits/retry; connected models retain provider limits. [Frozen 48-query frontier plan](evidence/coarse-holdout-plan-2026-10-23/README.md) spans eight public origins and 6/10/12h inside/outside probes. The new bounded helper and offline replay pass eleven synthetic tests; all 48 planned cases retain failures/skips and snap-quality flags. The subsequent approved run used exactly 48 requests with no retries/paid upgrade; all pair. Its mean absolute difference grows from 33.98 minutes at 6h to 78.77 at 12h. Road edges dominate reconstructed costs; the separate 105→95 / 80→85 km/h prototype has now failed both regional gates and is rejected. The now-observed 48 cases become development data, not a fresh holdout for that prototype. [New evidence](evidence/coarse-frontier-reference-2026-10-23/README.md), [next steps](next-steps.md).

The preserved local experiment defaults to 120 minutes; five reference sources reach no detected cuts within two hours. It remains regional/static, and six-to-twelve-hour queries still clip. The optional hosted model remains capped at 60 minutes. The detailed six-hour preflight is complete; its storage calibration reproduces all eight qualified payloads at 2.415/2.416 GiB. [Final evidence](evidence/source-outgoing-2026-10-19/README.md) is complete; its partial-source expansion screen remains held at 9.290 GiB with margin against 4 GiB. No calibration job is running. These limits do not apply to the separate coarse grid.

## History and evidence

- [Archive](archive/README.md): older experiments, superseded plans, memory work and handoff snapshots.
- [Evidence](evidence/): measured outputs, logs, source excerpts and screenshots at their original paths.

There are twelve current top-level documents including this index. Four small forwarding pages preserve links from checksum-bound historical evidence; their reports live in the archive. Start new agents with the current documents, and consult archived reports only for the relevant model/proof history. Update these current pages when state changes; preserve dated measurements and sealed evidence.
