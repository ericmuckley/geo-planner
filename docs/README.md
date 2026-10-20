# Geo Planner documentation

For a new coding agent or a disconnected session, read [AGENTS.md](../AGENTS.md), then [the resume guide](agent-handoff.md). Current code includes uncommitted/untracked work; large datasets and keys are local-only. Resume in this workspace rather than assuming a fresh clone contains the running baseline.

## Current documents

| Document | Purpose |
| --- | --- |
| [Agent handoff](agent-handoff.md) | Recovery checks, graph/data locations, restart commands and resume prompt |
| [Implementation status](implementation-status.md) | Current capabilities, limits, code map and validation |
| [Local development](local-development.md) | App setup and the separate experimental/provider APIs |
| [Next steps](next-steps.md) | Finish the memory calibration/rebuild, then complete-source six-hour qualification |
| [Six-hour preflight](six-hour-preflight.md) | Unclipped planning, source gaps and the current resource screen |
| [Two-hour regional baseline](two-hour-region.md) | Current graph's exact recipes, provenance, measurements and evidence |
| [Progress](progress.md) | Plain-language summary |
| [Initial project plan](initial-project-plan.md) | Long-term vision and semantics; current decisions above take precedence |
| [US service setup](us-routing-service.md) | Selected hosted main-page provider and recorded limits |
| [Retained Valhalla recipe](regional-routing.md) | Separate local Valhalla build/service reference |

The local experiment defaults to 120 minutes; five reference sources reach no detected cuts within two hours. It remains regional/static, and six-to-twelve-hour queries still clip. The hosted main page remains capped at 60 minutes. The six-hour preflight is complete and the larger graph remains held at the 4 GiB memory gate. The first storage calibration reproduces all eight qualified payloads and reduces complete build peak from 2.668 to 2.415 GiB. Its exact repeat and revised resource screen are pending. Start with the handoff; no calibration job is running at this checkpoint.

## History and evidence

- [Archive](archive/README.md): older experiments, superseded plans, memory work and handoff snapshots.
- [Evidence](evidence/): measured outputs, logs, source excerpts and screenshots at their original paths.

There are eleven current top-level documents including this index. Four small forwarding pages preserve links from checksum-bound historical evidence; their reports live in the archive. Start new agents with the current documents, and consult archived reports only for the relevant model/proof history. Update these current pages when state changes; preserve dated measurements and sealed evidence.
