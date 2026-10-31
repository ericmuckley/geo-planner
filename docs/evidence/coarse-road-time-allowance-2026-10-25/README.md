# Source-road time allowance — October 25, 2026

**The fixed 10% allowance improves mean error but is rejected under six frozen gates.** The policy was frozen before changed costs/query results. It is a round engineering hypothesis on observed development data, not a measured correction, optimized factor, traffic estimate or national accuracy claim. [Policy](policy.json), [preparation recipe](preparation-plan.json), [single evaluation recipe](execution-plan.json). Active v9 and all prior sealed records remain unchanged; work is local/uncommitted at HEAD `648c731`.

The [saved-path audit](../coarse-backbone-path-audit-2026-10-25/README.md) finds systematically different provider durations despite similar median lengths/corridors. It motivates testing a timing component without another geometry/access change and does not establish a causal factor. The first backbone candidate and older timing failures remain rejected under their original gates.

## Exact cost change and controls

- Full Census source arc: original minutes +0.10×(original source km/class speed×60). Its original distributed rounding residue stays fixed; no source speed tag, position, component or adjacency changes.
- Selected coarse base-road link: original source-road hours×1.10 plus unchanged artificial connector hours, rounded upward to0.1 s. The original selected source alternative is fixed; artificial NE/Census connectors still use55/25 km/h. Mixed aggregate link cost is not scaled.
- Partial Census input/output/same-arc access uses the repriced full-arc cumulative fraction and unchanged chord lower bound. NE partial access lazily reads visits at original speed/1.10, preserving geometry/anchors/cumulative/transfer distance; local access stays25 km/h. No visit-result cache or duplicated persistent arrays.

The [versioned cost module](../../../src/server/backbone-cost.ts) leaves the sealed routing, geometry, decoder and geography code unchanged. Its independent endpoint replay enumerates accepted saved endpoints without a label/queue search. Controls reproduce **1,234,223 source-arc costs, 378,515 selected base-link prices and 166 recorded endpoint-state costs** before changed costs are written. All 123,116 road visits decode from unchanged payloads; the lazy wrapper changes only their source-road-time interpretation. [Control report](preparation.txt). Only graph `arcMinutes` and kept-base `roadDeciseconds` gzip payloads change; the other 27 payloads are exact.

[Independent Python audit](independent-cost-audit.json) checks every new source/base cost and original rounding, same coverage/zero masks, descriptor parity and 166 endpoint records against the saved paths. Maximum arc-time arithmetic difference is8.882e-16 min. The new binary is **61,907,611 bytes**, SHA `f099563d48f5b7f31fc12768deeca9cfe388adbbae54a29f952f65974a896af3`. This is an artifact size, not a measured generated function package. Preparation 2,294 ms and observed RSS781,615,104 bytes are offline producer scopes, not app/cloud measurements.

Eight synthetic cost/partial-access/control/water/same-arc tests, 194-file Biome, app/strict runner typechecks and ordinary build pass. [Development notes](development-notes.json) preserve an initial test typecheck correction before full-data work; no numeric policy or result was changed. There is no source producer rerun, new reference/provider/env/key/DB input, schema/dependency/config change, commit, push or deployment.

## Evaluation scope

The one 83 ORS/35 Valhalla comparison completes all 21 origins with the same 900-minute diagnostic cap. [Full comparison](comparison.json), [independent arithmetic](analysis.json), [captured paths](paths.json.gz), [decision](report.json).

| Gate or metric | Active v9 | Allowance candidate |
| --- | --- | --- |
| Overall mean absolute ORS error | 29.257 min | **24.482 min**, 16.32% lower |
| Frontier mean absolute error | 44.629 min | **37.285 min** |
| Original /regional means | 7.223 /8.613 min | **6.352 /7.188 min** |
| False reachable /missed | 11 /2 | **5 /8** |
| 12-hour frontier misses | 1 | **4**, maximum 1 |
| Worst added error, frontier /older | — | **66.578 /7.584 min**, maxima 20 /5 |
| Older Valhalla means, original /regional | 14.896 /13.389 min | **12.420 /11.100 min** |

Fifteen gates pass and **six fail**: horizon p90, worst frontier/older regressions, definite frontier errors, total frontier misses and 12-hour misses. Six-/ten-hour p90 errors rise 54.603→58.730 /70.048→81.533 min. Total definite frontier errors stay 13 versus the required maximum 12. All 83 cases remain finite, all 166 component sums reconcile and all 35 older destinations stay shaded. Fifty absolute errors improve/33 regress. Every point time is no faster than the unbuffered backbone, confirming the intended monotone cost intervention.

The independent Python audit reproduces every gate; the raw versioned runner has no inherited scalar error fields. Initial commentary counted seven failures; this decision and independent audit correctly record six. Neither the mean gain nor provider sensitivity overrides a necessary failure. No other factor was tried and no gate changed.

Origin preparation plus Dijkstra ranges 2.622–22.816 s on the 900-minute diagnostics; binary/module load, display arrival and polygon tracing are separate. Full packaged-query, physical/API/retention/visual/cloud admission stops after accuracy failure; no candidate Vercel build/deployment. The first candidate and all old timing failures remain preserved.

The frozen execution recipe's inherited routing design SHA binds the earlier geometry/access semantics; this separately frozen cost policy supersedes only its unchanged-cost assumption. Benchmark timing includes origin preparation and Dijkstra, with display-arrival work separate. No contour/package/cloud qualification or active switch is implied. Necessary failure stops this candidate without another factor or changed gate. [Exact commands](../../local-development.md#source-road-time-allowance).

## Recovery and next action

Ignored `data/coarse-quality/road-time-allowance-v1/` preserves the artifact/manifest/control, and `road-time-allowance-comparison-v1/` the complete rejected run. Copies of reports/control/paths are here. A fresh clone at HEAD lacks this uncommitted work and ignored assets. Do not rerun completed producers/comparisons for readiness.

```sh
python3 -B docs/evidence/coarse-road-time-allowance-2026-10-25/verify.py
python3 -B docs/evidence/coarse-road-time-allowance-2026-10-25/verify.py --local-assets
```

Next implement the [held-state path counterfactual](next-diagnostic-plan.json): reprice captured unbuffered state/arc sequences at this same 1.10 policy, replay eligible endpoint attachments to their captured states, and compare direct cost shifts with actual new path choices. Keep all 83/35 cases and an explicit900-minute cap/gap ledger. This computes no Dijkstra/query or alternate factor. Freeze its exact tool/commands/bindings first. No case/region/horizon exceptions, source/provider/env/DB input or active switch. Every original gate remains required before any later activation.
