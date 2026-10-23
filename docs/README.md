# Geo Planner documentation

For a new coding agent or disconnected session, read [AGENTS.md](../AGENTS.md), then [the resume guide](agent-handoff.md). V6 is active locally at 0.05° (about 3.5–5.5 km cells), with a new independently rebuilt nationwide graph. It is uncommitted; a fresh clone and user-reported production remain v5 at `08074fb`. Raw inputs, ignored candidates/probes, detailed research graphs and secrets remain local-only. Include the v6 dataset when publishing.

## Current documents

| Document | Purpose |
| --- | --- |
| [Agent handoff](agent-handoff.md) | Recovery checks, graph/data locations, restart commands and resume prompt |
| [Implementation status](implementation-status.md) | Current capabilities, limits, code map and validation |
| [Local development](local-development.md) | App setup and the separate experimental/provider APIs |
| [Next steps](next-steps.md) | Publish/verify v6, then refine residual generic access/transfer errors; detailed research is parked |
| [Coarse estimator](coarse-estimator.md) | Implemented nationwide grid model, assumptions, sources and local Vercel evidence |
| [Six-hour preflight](six-hour-preflight.md) | Unclipped planning, source gaps and the current resource screen |
| [Two-hour regional baseline](two-hour-region.md) | Current graph's exact recipes, provenance, measurements and evidence |
| [Progress](progress.md) | Plain-language summary |
| [Initial project plan](initial-project-plan.md) | Long-term vision and semantics; current decisions above take precedence |
| [US service setup](us-routing-service.md) | Selected hosted main-page provider and recorded limits |
| [Retained Valhalla recipe](regional-routing.md) | Separate local Valhalla build/service reference |

**October 23 milestone:** v6 halves cell width from 0.1° to 0.05° by rebuilding masks, anchors, roads, shores and visits. The 68.13 MB artifact reproduces exactly; the final local Vercel function is 71.94 MB. Twenty-six of 35 saved estimates improve, nine worsen (worst +7.09 min), all remain reached/shaded. Regional mean absolute differences fall 33.0% / 24.3%; national accuracy remains unvalidated. A generic geometry-index refinement reduces first packaged computation to 3.06–3.12 seconds in three fresh processes, with bounded retention over 405,384 inputs. 51 server tests, nineteen geometry fixtures, 42 active API cases, checks/typechecks, both builds and local handler/browser/history checks pass. [V6 evidence and side-by-side maps](evidence/coarse-resolution-2026-10-23/README.md), [model](coarse-estimator.md), [next steps](next-steps.md). Production is user-reported v5; cloud v6 verification remains next.

The preserved local experiment defaults to 120 minutes; five reference sources reach no detected cuts within two hours. It remains regional/static, and six-to-twelve-hour queries still clip. The optional hosted model remains capped at 60 minutes. The detailed six-hour preflight is complete; its storage calibration reproduces all eight qualified payloads at 2.415/2.416 GiB. [Final evidence](evidence/source-outgoing-2026-10-19/README.md) is complete; its partial-source expansion screen remains held at 9.290 GiB with margin against 4 GiB. No calibration job is running. These limits do not apply to the separate coarse grid.

## History and evidence

- [Archive](archive/README.md): older experiments, superseded plans, memory work and handoff snapshots.
- [Evidence](evidence/): measured outputs, logs, source excerpts and screenshots at their original paths.

There are twelve current top-level documents including this index. Four small forwarding pages preserve links from checksum-bound historical evidence; their reports live in the archive. Start new agents with the current documents, and consult archived reports only for the relevant model/proof history. Update these current pages when state changes; preserve dated measurements and sealed evidence.
