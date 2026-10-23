# Geo Planner documentation

For a new agent or disconnected session, read [AGENTS.md](../AGENTS.md), then [the resume guide](agent-handoff.md). **V8 is active locally at 0.025° / about 1.8–2.8 km cells. V7/v8 are uncommitted; a fresh clone contains v6 at `ffd7fec`, user-reported verified live.** Include both new artifacts when publishing. Raw sources, ignored candidates/probes, detailed graphs and secrets remain local-only.

## Current documents

| Document | Purpose |
| --- | --- |
| [Agent handoff](agent-handoff.md) | Recovery checks, graph/data locations, restart commands and resume prompt |
| [Implementation status](implementation-status.md) | Current capabilities, limits, code map and validation |
| [Local development](local-development.md) | App setup and the separate experimental/provider APIs |
| [Next steps](next-steps.md) | Publish/verify v8, then plan independent long-horizon validation; detailed research is parked |
| [Coarse estimator](coarse-estimator.md) | Implemented nationwide grid model, assumptions, sources and local Vercel evidence |
| [Six-hour preflight](six-hour-preflight.md) | Unclipped planning, source gaps and the current resource screen |
| [Two-hour regional baseline](two-hour-region.md) | Current graph's exact recipes, provenance, measurements and evidence |
| [Progress](progress.md) | Plain-language summary |
| [Initial project plan](initial-project-plan.md) | Long-term vision and semantics; current decisions above take precedence |
| [US service setup](us-routing-service.md) | Selected hosted main-page provider and recorded limits |
| [Retained Valhalla recipe](regional-routing.md) | Separate local Valhalla build/service reference |

**October 23 follow-up:** v8 halves cell width again to 0.025°, retaining v7's paid Census road states. All 35 saved queries are reached/shaded: 29 improve, six regress at most 3.18 min. Mean differences **11.579→10.288 / 17.211→12.011 min** on reused development sets, not national accuracy proof. Source/proof/packed repeats match; lossless storage reduces 179.92 MB to 61.21 MB, producing a 65.02 MB local Vercel function. Three fresh first computations take 3.59–3.66s after config; retained decoded storage is 158.04 MB and bounded across 952,758 inputs. 56 server tests, nineteen Python fixtures, 42 API cases, checks/typechecks, both builds and handler/browser fixture checks pass. [V8 evidence/maps](evidence/coarse-finer-2026-10-23/README.md), [v7 road continuity](evidence/coarse-connections-2026-10-23/README.md), [v6 finer-grid evidence](evidence/coarse-resolution-2026-10-23/README.md), [next steps](next-steps.md). Actual v8 publication/verification is next.

The preserved local experiment defaults to 120 minutes; five reference sources reach no detected cuts within two hours. It remains regional/static, and six-to-twelve-hour queries still clip. The optional hosted model remains capped at 60 minutes. The detailed six-hour preflight is complete; its storage calibration reproduces all eight qualified payloads at 2.415/2.416 GiB. [Final evidence](evidence/source-outgoing-2026-10-19/README.md) is complete; its partial-source expansion screen remains held at 9.290 GiB with margin against 4 GiB. No calibration job is running. These limits do not apply to the separate coarse grid.

## History and evidence

- [Archive](archive/README.md): older experiments, superseded plans, memory work and handoff snapshots.
- [Evidence](evidence/): measured outputs, logs, source excerpts and screenshots at their original paths.

There are twelve current top-level documents including this index. Four small forwarding pages preserve links from checksum-bound historical evidence; their reports live in the archive. Start new agents with the current documents, and consult archived reports only for the relevant model/proof history. Update these current pages when state changes; preserve dated measurements and sealed evidence.
