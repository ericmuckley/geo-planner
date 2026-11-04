# Geo Planner documentation

For a new agent or disconnected session, read [AGENTS.md](../AGENTS.md), then [the resume guide](agent-handoff.md). Updated November 3, 2026. The current repository baseline is user commit`77d7818`; it includes the prior offline work and disk-selection drafts. The newer qualification/capture/census/lineage/car-policy code and evidence remain local/uncommitted. Large source/index/bank/archive/runtime assets and secrets remain ignored and absent from a fresh clone.

**V9 is committed at `648c731` (commit message `v8`), user-reported deployed and verified.** The agent's 15 production API checks also pass for `coarse-road-grid-v9`, min 30/max 720 and the saved 6/10/12 h counts. No provider call or history write was needed. Public model metadata does not expose deployed Git SHA; hosted browser verification is user-reported. [Hosted result and latest preflight](evidence/coarse-backbone-preflight-2026-10-25/README.md).

**Current work:** the finer national road engine remains **rejected for app integration**:same80-route mean error33.73min versus v9’s30.00, with3 unavailable routes. The user chose to keep every accuracy gate. The raw water-data stage is now complete:all101.74million requested coordinates are independently exact;2,439,095 water features/2,648,285 rings preserve source edges, roles, coordinates and holes.72 invalid standalone ways/522 excluded relations remain explicit. All245 saved input/reference points are outside accepted water, including the old unsupported shoreline input. Known excluded-feature bounds overlap12 other points;one source-incomplete relation cannot be fully located. These are source observations, not proof of land or repaired routes. The908.22MB geometry is offline-only. Next qualify compact geography storage, then one generic mask policy and all original routing/accuracy/app gates. Production stays v9; app/env/DB/dependencies/deployment unchanged, new code/evidence local/uncommitted. [Results and recovery](evidence/coarse-osm-car-capacity-2026-11-01/README.md).


## Current documents

| Document | Purpose |
| --- | --- |
| [Agent handoff](agent-handoff.md) | Recovery checks, graph/data locations, restart commands and resume prompt |
| [Implementation status](implementation-status.md) | Current capabilities, limits, code map and validation |
| [Local development](local-development.md) | App setup and the separate experimental/provider APIs |
| [Next steps](next-steps.md) | Fit the national road graph into a deployable app |
| [Native car construction](evidence/coarse-osm-car-capacity-2026-11-01/README.md) | National costs/storage, rejected finer candidate, path diagnosis and conservative turn proposal |
| [Road-only car prototype](evidence/coarse-osm-car-prototype-2026-11-01/README.md) | Frozen costs/direction/access/turns, compact binary and independent source audit |
| [Way-lineage geometry prototype](evidence/coarse-osm-way-lineage-prototype-2026-11-01/README.md) | Complete metadata/geometry/internal-point proof preceding car-cost qualification |
| [Exact topology census](evidence/coarse-osm-topology-census-2026-11-01/README.md) | Complete national incidences/anchors/array bounds and independent derived audit |
| [National footprint census](evidence/coarse-osm-national-footprint-2026-11-01/README.md) | Complete country counts, full-source guards and format bounds |
| [Direct OSM prototype](evidence/coarse-osm-backbone-prototype-2026-10-31/README.md) | Complete native-ID geometry/contraction/footprint proof; next national screen scope |
| [National execution/diagnostic evidence](evidence/coarse-osm-country-exec-2026-10-30/README.md) | Preserved guard stop/diagnostic,170-test correction and passed national census/probe |
| [Countrywide helper result](evidence/coarse-osm-country-helper-2026-10-30/README.md) | 103 actual Linux controls; source/byte/index/lookup core proof, no national execution |
| [Countrywide screen plan](evidence/coarse-osm-country-screen-plan-2026-10-29/README.md) | Fixed eight-shard design, resource arithmetic and qualification gates; no national run yet |
| [Road-batch prototype](evidence/coarse-osm-way-batch-2026-10-30/README.md) | 206 helper/7controller controls; passed full source/batch/coordinate measurement |
| [Typed-ID lookup work](evidence/coarse-osm-lookup-2026-10-30/README.md) | Six Linux controls; fixed replay passes with19.6%lower lookup time and identical results |
| [Extraction prototype scope](evidence/coarse-osm-extraction-2026-10-30/README.md) | Complete capture/audits, matching/topology feasibility results and proposed architecture choice |
| [Coarse estimator](coarse-estimator.md) | Implemented nationwide grid model, assumptions, sources and local Vercel evidence |
| [Six-hour preflight](six-hour-preflight.md) | Unclipped planning, source gaps and the current resource screen |
| [Two-hour regional baseline](two-hour-region.md) | Current graph's exact recipes, provenance, measurements and evidence |
| [Progress](progress.md) | Plain-language summary |
| [Initial project plan](initial-project-plan.md) | Long-term vision and semantics; current decisions above take precedence |
| [US service setup](us-routing-service.md) | Selected hosted main-page provider and recorded limits |
| [Retained Valhalla recipe](regional-routing.md) | Separate local Valhalla build/service reference |

**October 23 follow-up:** v8 halves cell width again to 0.025°, retaining v7's paid Census road states. All 35 saved queries are reached/shaded: 29 improve, six regress at most 3.18 min. Mean differences **11.579→10.288 / 17.211→12.011 min** on reused development sets, not national accuracy proof. Source/proof/packed repeats match; lossless storage reduces 179.92 MB to 61.21 MB, producing a 65.02 MB local Vercel function. Three fresh first computations take 3.59–3.66 s after config; retained decoded storage is 158.04 MB and bounded across 952,758 inputs. 56 server tests, nineteen Python fixtures, 42 API cases, checks/typechecks, both builds and handler/browser fixture checks pass. [V8 evidence/maps](evidence/coarse-finer-2026-10-23/README.md), [v7 road continuity](evidence/coarse-connections-2026-10-23/README.md), [v6 finer-grid evidence](evidence/coarse-resolution-2026-10-23/README.md), [next steps](next-steps.md). The hosted slider follow-up verifies the deployed v8 contract; v9 above is the latest deployed model.

**Current UX/planning:** [slider verification](evidence/time-slider-2026-10-23/checks.json) covers native pointer/keyboard updates, loading, latest-result behavior, 30-minute acceptance, builds and local packaging. The optional compute button remains for coordinate edits/retry; connected models retain provider limits. [Frozen 48-query frontier plan](evidence/coarse-holdout-plan-2026-10-23/README.md) spans eight public origins and 6/10/12h inside/outside probes. The new bounded helper and offline replay pass eleven synthetic tests; all 48 planned cases retain failures/skips and snap-quality flags. The subsequent approved run used exactly 48 requests with no retries/paid upgrade; all pair. Its mean absolute difference grows from 33.98 minutes at 6h to 78.77 at 12h. Road edges dominate reconstructed costs; the separate 105→95 / 80→85 km/h prototype has now failed both regional gates and is rejected. The now-observed 48 cases become development data, not a fresh holdout for that prototype. [New evidence](evidence/coarse-frontier-reference-2026-10-23/README.md), [next steps](next-steps.md).

The preserved local experiment defaults to 120 minutes; five reference sources reach no detected cuts within two hours. It remains regional/static, and six-to-twelve-hour queries still clip. The optional hosted model remains capped at 60 minutes. The detailed six-hour preflight is complete; its storage calibration reproduces all eight qualified payloads at 2.415/2.416 GiB. [Final evidence](evidence/source-outgoing-2026-10-19/README.md) is complete; its partial-source expansion screen remains held at 9.290 GiB with margin against 4 GiB. No calibration job is running. These limits do not apply to the separate coarse grid.

## History and evidence

- [Countrywide helper core qualified](evidence/coarse-osm-country-helper-2026-10-30/README.md):103 target tests/no skips; 500 synthetic fields/300 coordinate rows, exact census and guarded two-pass probe. National execution/remaining telemetry held.

- [Fixed real-sample screen passes](evidence/coarse-osm-sample-run-2026-10-29/README.md):64k nodes protected median1.112207→0.023119s,48.108× faster; all67k prefix/mixed fields and65k coordinate rows exact, lookup bits/index contents agree. Shared-host/small-sample scope only; no national/model admission.

- [Fixed-sample preparation complete](evidence/coarse-osm-sample-plan-2026-10-27/README.md):74 Linux controls, same index/source guards on both sides, bounded IO/proof/fast/lookup scopes and exact next command. Rejected-record counter defect corrected in V2 with V1 preserved. The subsequent actual sample run is recorded above; this preparation remains sealed unchanged.

- [Native metadata/projector success](evidence/coarse-osm-projector-2026-10-27/README.md):62 Linux tests, exact fields/coordinates/independent output;9000 synthetic nodes in3 blocks without Python node projections. No real-sample speed, national or map-accuracy qualification.

- [Native delta V2 success](evidence/coarse-osm-delta-v2-2026-10-27/README.md):46 Linux controls,20k synthetic index43.5%smaller/exact coordinates/output; full-shard per-batch authentication fixes V1 cache defect. This preceding index milestone does not qualify metadata validation or real benchmarks; the subsequent projector result is above.

- [Native delta V1 stop](evidence/coarse-osm-delta-2026-10-27/README.md):compiled codec passes43/44 Linux controls; unchanged timestamp cannot establish cache integrity. Frozen stop/code/raw bytes preserved.

- [Native build/ABI success](evidence/coarse-osm-native-build-2026-10-27/README.md):52requests/567MB; all25 layers/216 source files verified, GCC14.2.1 compiles1.93MB C ABI library; tiny target PBF and42 Linux controls pass. No native importer/sample/national run.

- [Native metadata V2 success](evidence/coarse-osm-native-lock-v2-2026-10-27/README.md):8requests/246KB, exact image/config/platform/source identities,27 host/Linux controls and offline replay pass; no layers/archives/compiler acquired. Subsequent bounded acquisition/tiny ABI qualification is above.

- [Native metadata V1 stop](evidence/coarse-osm-native-lock-2026-10-27/README.md):19 host/Linux controls pass; two requests/6.9KB stop on signed config-CDN redirect. Verified manifest subsequently reused by V2 above; no layers/archives/complete tool lock in V1. Raw signed URLs stay ignored, public records redacted.

- [Native capability review and design](evidence/coarse-osm-native-design-2026-10-27/README.md): no checked compiler/build tools in the cached runtime; native helper/guard mapping and conditional block/delta storage specified. No source/sample scan; subsequent completed metadata V2 and preserved V1 stop are above.

- [Compact two-pass prototype](evidence/coarse-osm-stream-2026-10-27/README.md):49%less prefix node-index time/41%less bytes; exact records/coordinates, synthetic independent audit and27 Linux controls pass. National time/storage held; subsequent native design review is above.

- [National inventory / importer decision](evidence/coarse-osm-inventory-2026-10-27/README.md): normal native EOF at1.606b nodes/162.7m ways/1.62m relations, fixed mixed samples equivalent; four-pass strategy rejected. V1/V2 cap stops preserved; subsequent compact prototype is above.

- [Node-index profile and portable-control correction](evidence/coarse-osm-import-profile-2026-10-27/README.md):64,000 real nodes, median2.589→1.790 s /1.446× throughput, exact record/index equivalence and18 host/Linux controls. Node-only profile result; subsequent inventory above rejects the existing full-import strategy.

- [Full V3 source / native deadline stop](evidence/coarse-osm-data-v3-run-2026-10-27/README.md):12.23GB source/checksums/date/format verified; first pass stops at321million nodes, no EOF/normalized records; cleanup/closed-file proof pass. Offline import performance is next.

- [National V2 stop /V3 monitor correction](evidence/coarse-osm-data-run-2026-10-26/README.md): HTTP200/33MiB prefix, host monitor race reproduced, header/date match, no native extraction;11 host/Linux regressions and corrected read-only preflight pass.

- [Frozen national-input recipe](evidence/coarse-osm-data-freeze-2026-10-26/README.md): tested one-GET launcher, actual safe 4 GiB resource controls, qualified tiny native wrapper and read-only preflight; no source acquired during that preparation, before the subsequently stopped run above.

- [Actual native tool proof](evidence/coarse-osm-tools-v2-run-2026-10-26/README.md): one runtime-package GET, preserved extraction refusal, separately frozen offline correction; actual imports/PBF/four-pass extraction/audit/negative checks pass. The subsequent data recipe is frozen above.

- [Cached runtime investigation / exact Expat package proposal](evidence/coarse-osm-runtime-v2-2026-10-26/README.md): cached library rejected for glibc mismatch; output-aware preflight has six host/Linux tests; official index pins one unacquired 83,528-byte package.

- [Locked tool setup / native ABI stop](evidence/coarse-osm-tools-run-2026-10-26/README.md): six exact wheel GETs/offline installation complete; missing Expat library stops native import before any PBF fixture. Saved bytes/versions/resources/cleanup reconcile; runtime correction next.

- [Completed v3 dependency lock](evidence/coarse-osm-tool-lock-v3-run-2026-10-26/README.md): six exact packages/2,387,936 planned wheel bytes, lock/accounting/resource/cleanup reconciliation pass before the subsequent native ABI stop above.
- [Metadata v2 stop / v3 correction](evidence/coarse-osm-tool-lock-run-2026-10-26/README.md): second catalogue exceeds original per-response cap; saved Requests seed reused by separately frozen four-GET correction, six host/Linux tests pass before the subsequently completed v3 run above.
- [Offline OSM controls](evidence/coarse-osm-offline-controls-2026-10-26/README.md): 39 host/Linux tests, safe Linux/SQLite guards and frozen five-GET metadata recipe before its stopped attempt; no PBF/decoder qualification.
- [Proposed offline US-input revision](evidence/coarse-osm-offline-plan-2026-10-26/README.md): explicit dated source/new publisher state, 12 GiB network/64 GiB working/4 GiB memory/four-hour proposal and capacity; no larger acquisition.
- [Bulk/native OSM review](evidence/coarse-osm-bulk-review-2026-10-26/README.md): two whole-file approaches do not fit the original pilot budget; the subsequent offline proposal above addresses rescoping; no bulk download.
- [Stopped native OSM capture](evidence/coarse-osm-pilot-run-2026-10-26/README.md): first status GET returns 502/534 bytes; no data POST, independent stopped audit/cleanup pass; no retry.
- [Native OSM capture controls](evidence/coarse-osm-pilot-2026-10-26/README.md): 28 host/Linux fixtures, hard resource proofs and exact executable freeze before the stopped run above.
- [Bounded OSM input design](evidence/coarse-input-redesign-2026-10-26/README.md): two primary-documented approaches reviewed, one finite 21-window/42-attempt snapshot design selected before the subsequent implementation; no data acquired.
- [Cached terminal-fragment result](evidence/coarse-timing-fragments-run-2026-10-26/README.md): fixed hypothesis passes on 96 records; sparse parser-usable attributes and incomplete source still prevent timing-model admission.
- [Terminal-fragment prototype](evidence/coarse-timing-fragments-2026-10-26/README.md): eighteen host/Linux fixtures and exact freeze before the subsequently completed real run.
- [Declared-role reporting](evidence/coarse-chain-role-scope-2026-10-26/README.md): fixed hypothesis rejected; 0/32 newly exhaustive, all original fields preserved, reporting branch closed.
- [Chain-exclusion audit](evidence/coarse-chain-exclusions-2026-10-26/README.md): 3,334 incidences/995 retained identities; no uniform-zero level shortcut, all original candidate outcomes remain unresolved.
- [Bounded endpoint chains](evidence/coarse-timing-chains-2026-10-26/README.md): fixed existential hypothesis passes on 14 formerly absent arcs; all 32 candidate-bearing records stay unresolved, no speed/model admission.
- [Geometry/scope compatibility](evidence/coarse-timing-compatibility-2026-10-26/README.md): 163 single-ID absences have >=80% combined geometric support; scopes and 0.522% eligible-speed baseline stay unchanged.
- [Offline timing-cache analysis](evidence/coarse-timing-cache-2026-10-25/README.md): all 55,120 IDs/2,469 Census records reconcile; 2.827 provisional matched km and no further acquisition under the current recipe.
- [Capped importer and stopped pilot](evidence/coarse-timing-pilot-2026-10-25/README.md): 22 host/Linux tests, kernel limits, 55,120 retained rows; source timeout with every window incomplete and no retry.
- [Timing-input design](evidence/coarse-timing-design-2026-10-25/README.md): cached-schema inventory and concrete 512 MiB/21-window Overture data-feasibility proposal; no new model or road data.
- [Distance budget](evidence/coarse-distance-budget-2026-10-25/README.md): exact source/connector lengths and justified endpoint bounds show all eight misses have shorter recorded modeled distances.
- [Timing/exposure join](evidence/coarse-timing-exposure-2026-10-25/README.md): reconciles all 83/35 records; existing class/partial-corridor features do not select a timing rule.
- [Fixed-policy path control](evidence/coarse-road-time-control-2026-10-25/README.md): separates direct source pricing from route-choice effects, with all 83/35 cases retained.
- [Archive](archive/README.md): older experiments, superseded plans, memory work and handoff snapshots.
- [Evidence](evidence/): measured outputs, logs, source excerpts and screenshots at their original paths.

There are twelve current top-level documents including this index. Four small forwarding pages preserve links from checksum-bound historical evidence; their reports live in the archive. Start new agents with the current documents, and consult archived reports only for the relevant model/proof history. Update these current pages when state changes; preserve dated measurements and sealed evidence.
