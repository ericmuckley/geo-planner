# Geo Planner documentation

For a new coding agent or a disconnected session, read [AGENTS.md](../AGENTS.md), then [the resume guide](agent-handoff.md). V3, cloud history and prior evidence are committed at `887ab50`; the user accepted that deployment visually. The active v4 road attachment, access diagnostics/evidence and current-doc updates are uncommitted and not deployed. Compact datasets are included in source; detailed research datasets and keys remain local-only.

## Current documents

| Document | Purpose |
| --- | --- |
| [Agent handoff](agent-handoff.md) | Recovery checks, graph/data locations, restart commands and resume prompt |
| [Implementation status](implementation-status.md) | Current capabilities, limits, code map and validation |
| [Local development](local-development.md) | App setup and the separate experimental/provider APIs |
| [Next steps](next-steps.md) | Deploy v4, then assess compact road-source completeness; detailed optimization is parked |
| [Coarse estimator](coarse-estimator.md) | Implemented nationwide grid model, assumptions, sources and local Vercel evidence |
| [Six-hour preflight](six-hour-preflight.md) | Unclipped planning, source gaps and the current resource screen |
| [Two-hour regional baseline](two-hour-region.md) | Current graph's exact recipes, provenance, measurements and evidence |
| [Progress](progress.md) | Plain-language summary |
| [Initial project plan](initial-project-plan.md) | Long-term vision and semantics; current decisions above take precedence |
| [US service setup](us-routing-service.md) | Selected hosted main-page provider and recorded limits |
| [Retained Valhalla recipe](regional-routing.md) | Separate local Valhalla build/service reference |

**Coarse MVP, October 22:** the main page computes filled 1–12-hour estimates with 6/10/12h presets, optional private PostgreSQL history, local fallback and export. The user accepted the earlier deployed v3 baseline. Active local v4 adds charged source-road access while preserving the graph and shoreline correction. It improves 31 of 35 saved point comparisons, four unchanged and none regressed; all destinations remain reached. The 8.00 MB artifact and 13.45 MB generated Vercel function pass local checks with no outbound routing requests. National accuracy remains unvalidated; missing roads and access through other roads in a cell remain. Next deploy v4, then prioritize compact source completeness. [V4 model/evidence](coarse-estimator.md#v4-charged-road-attachment), [saved-history milestone](implementation-status.md#saved-history-verification), [next steps](next-steps.md). Detailed-engine expansion and memory work remain parked.

The preserved local experiment defaults to 120 minutes; five reference sources reach no detected cuts within two hours. It remains regional/static, and six-to-twelve-hour queries still clip. The optional hosted model remains capped at 60 minutes. The detailed six-hour preflight is complete; its storage calibration reproduces all eight qualified payloads at 2.415/2.416 GiB. [Final evidence](evidence/source-outgoing-2026-10-19/README.md) is complete; its partial-source expansion screen remains held at 9.290 GiB with margin against 4 GiB. No calibration job is running. These limits do not apply to the separate coarse grid.

## History and evidence

- [Archive](archive/README.md): older experiments, superseded plans, memory work and handoff snapshots.
- [Evidence](evidence/): measured outputs, logs, source excerpts and screenshots at their original paths.

There are twelve current top-level documents including this index. Four small forwarding pages preserve links from checksum-bound historical evidence; their reports live in the archive. Start new agents with the current documents, and consult archived reports only for the relevant model/proof history. Update these current pages when state changes; preserve dated measurements and sealed evidence.
