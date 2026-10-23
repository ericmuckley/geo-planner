# Geo Planner documentation

For a new coding agent or disconnected session, read [AGENTS.md](../AGENTS.md), then [the resume guide](agent-handoff.md). V5 is active locally with nationwide Census + Natural Earth data; production remains independently verified v4 at `637746c`. All later runtime/data/diagnostic/evidence/doc work is uncommitted. The new v5 artifact belongs in Git/Vercel; raw inputs, ignored candidates/probes, detailed research graphs and secrets remain local-only.

## Current documents

| Document | Purpose |
| --- | --- |
| [Agent handoff](agent-handoff.md) | Recovery checks, graph/data locations, restart commands and resume prompt |
| [Implementation status](implementation-status.md) | Current capabilities, limits, code map and validation |
| [Local development](local-development.md) | App setup and the separate experimental/provider APIs |
| [Next steps](next-steps.md) | Verify actual v5 deployment, then diagnose remaining coarse-model errors; detailed research is parked |
| [Coarse estimator](coarse-estimator.md) | Implemented nationwide grid model, assumptions, sources and local Vercel evidence |
| [Six-hour preflight](six-hour-preflight.md) | Unclipped planning, source gaps and the current resource screen |
| [Two-hour regional baseline](two-hour-region.md) | Current graph's exact recipes, provenance, measurements and evidence |
| [Progress](progress.md) | Plain-language summary |
| [Initial project plan](initial-project-plan.md) | Long-term vision and semantics; current decisions above take precedence |
| [US service setup](us-routing-service.md) | Selected hosted main-page provider and recorded limits |
| [Retained Valhalla recipe](regional-routing.md) | Separate local Valhalla build/service reference |

**October 22 milestone:** nationwide v5 is active locally, with a reproducible **39,977,082-byte** model and **43,779,085-byte** local Vercel function. It adds 36,742 Census road links while preserving v4 anchors, geography and original roads. Fixed geography indexing retains every validation check and reduces first local packaged computation from 22.2 seconds to 2.46–2.47 seconds in three fresh processes. All 35 saved costs/paths and 42 national counts match the accepted candidate, with seven improvements/no regressions versus v4. Three complete memory sweeps retain bounded storage. 51 server tests, fifteen geometry fixtures, checks/typechecks, both builds, local handler and arbitrary inland/rural/coastal browser flows/history pass. Source credit and modified-data notices are visible. [V5 evidence](evidence/coarse-v5-2026-10-22/README.md), [national preparation](evidence/coarse-national-2026-10-22/README.md), [model](coarse-estimator.md). These measurements do not qualify national driving accuracy, cloud cold starts or peak memory. [Production proof](evidence/coarse-hosted-2026-10-22/README.md) remains v4; actual v5 deployment verification is next.

The preserved local experiment defaults to 120 minutes; five reference sources reach no detected cuts within two hours. It remains regional/static, and six-to-twelve-hour queries still clip. The optional hosted model remains capped at 60 minutes. The detailed six-hour preflight is complete; its storage calibration reproduces all eight qualified payloads at 2.415/2.416 GiB. [Final evidence](evidence/source-outgoing-2026-10-19/README.md) is complete; its partial-source expansion screen remains held at 9.290 GiB with margin against 4 GiB. No calibration job is running. These limits do not apply to the separate coarse grid.

## History and evidence

- [Archive](archive/README.md): older experiments, superseded plans, memory work and handoff snapshots.
- [Evidence](evidence/): measured outputs, logs, source excerpts and screenshots at their original paths.

There are twelve current top-level documents including this index. Four small forwarding pages preserve links from checksum-bound historical evidence; their reports live in the archive. Start new agents with the current documents, and consult archived reports only for the relevant model/proof history. Update these current pages when state changes; preserve dated measurements and sealed evidence.
