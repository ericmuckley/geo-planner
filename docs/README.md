# Geo Planner documentation

For a new coding agent or a disconnected session, read [AGENTS.md](../AGENTS.md), then [the resume guide](agent-handoff.md). The coarse estimator, cloud history and evidence are now committed at `0ffd6c8`; the user reports the hosted Vercel version works. The v2/v3 corrections and new evidence are uncommitted. The compact dataset is included in source; detailed research datasets and keys remain local-only.

## Current documents

| Document | Purpose |
| --- | --- |
| [Agent handoff](agent-handoff.md) | Recovery checks, graph/data locations, restart commands and resume prompt |
| [Implementation status](implementation-status.md) | Current capabilities, limits, code map and validation |
| [Local development](local-development.md) | App setup and the separate experimental/provider APIs |
| [Next steps](next-steps.md) | Assess local access/missing roads and verify hosted v3; detailed optimization is parked |
| [Coarse estimator](coarse-estimator.md) | Implemented nationwide grid model, assumptions, sources and local Vercel evidence |
| [Six-hour preflight](six-hour-preflight.md) | Unclipped planning, source gaps and the current resource screen |
| [Two-hour regional baseline](two-hour-region.md) | Current graph's exact recipes, provenance, measurements and evidence |
| [Progress](progress.md) | Plain-language summary |
| [Initial project plan](initial-project-plan.md) | Long-term vision and semantics; current decisions above take precedence |
| [US service setup](us-routing-service.md) | Selected hosted main-page provider and recorded limits |
| [Retained Valhalla recipe](regional-routing.md) | Separate local Valhalla build/service reference |

**Coarse MVP, October 22:** the main page now computes filled 1–12-hour estimates using a bundled road-informed grid, with six-/ten-/twelve-hour presets. Local Vercel-handler execution passes without a database, local worker or routing service. The user reports the hosted app works; independent hosted verification remains pending. The new local v2 correction reduces mean cell-arrival difference across eleven regional reference routes from 42.4m to 20.3m and fixes Calexico’s road-supported display cell. National accuracy and independent hosted verification remain open. Cloud PostgreSQL saved history is implemented, its reviewed additive migration is applied, and live persistence/isolation/concurrency checks pass. History is private to each browser with local fallback. The v1-to-v2 24-route/twelve-origin validation improves 18/23 paired finite point cases but finds five regressions and one unreached shore destination. V3 now restores the missing shore destination through generic geography-checked links and retained-road access. It preserves all eleven earlier costs; two common regional cases improve and none regress against v2. The next priority is local-access/missing-road assessment and hosted v3 verification; see [v3 findings](coarse-estimator.md#v3-general-shore-connectivity). Detailed-engine memory work and regional expansion are parked. See [the model report](coarse-estimator.md) and [next steps](next-steps.md).

The preserved local experiment defaults to 120 minutes; five reference sources reach no detected cuts within two hours. It remains regional/static, and six-to-twelve-hour queries still clip. The optional hosted model remains capped at 60 minutes. The detailed six-hour preflight is complete; its storage calibration reproduces all eight qualified payloads at 2.415/2.416 GiB. [Final evidence](evidence/source-outgoing-2026-10-19/README.md) is complete; its partial-source expansion screen remains held at 9.290 GiB with margin against 4 GiB. No calibration job is running. These limits do not apply to the separate coarse grid.

## History and evidence

- [Archive](archive/README.md): older experiments, superseded plans, memory work and handoff snapshots.
- [Evidence](evidence/): measured outputs, logs, source excerpts and screenshots at their original paths.

There are twelve current top-level documents including this index. Four small forwarding pages preserve links from checksum-bound historical evidence; their reports live in the archive. Start new agents with the current documents, and consult archived reports only for the relevant model/proof history. Update these current pages when state changes; preserve dated measurements and sealed evidence.
