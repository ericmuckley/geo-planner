# Proposal: precomputed anchors for US reachability

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

October 16, 2026. **Status: larger design proposed; a small [offline coordinate-matrix pilot](offline-anchor-pilot.md) is implemented. A [separate small state-graph reference](state-routing-reference.md) now qualifies directed bounds under an explicit static model. No nationwide computations or cache have been built.** The user suggested computing approximately 10,000 points along the interstate network to ground initial estimates and benchmark refinement. This extends the [long-range brainstorm](long-range-routing-brainstorm.md); the required 10–12-hour capability remains unimplemented.

## Use the points for three distinct jobs

| Role | Data to retain | How it helps |
| --- | --- | --- |
| Access/backbone anchors | Directed travel costs between anchors, local attachments and consistent road states | Cheap long-distance estimates and feasible paths |
| Global landmarks | Selected travel-cost fields or conservative region summaries | Bound travel costs and identify uncertainty needing refinement |
| Reference cases | Independently computed answers for a separate set of origins/destinations | Detect correctness errors and measure refinement quality |

These roles need not use the same number of points. A candidate design uses thousands of access anchors and a much smaller experimentally chosen set of detailed landmarks. Interstate points are useful seeds; important junctions, graph-region exits and gaps in coverage should influence selection.

The foundations are established: [transit-node routing](https://turing.iem.thm.de/routeplanning/hwy/transit.pdf) precomputes access connections and travel-cost tables for long-distance routing, with handling for local queries. [ALT landmark research](https://www.microsoft.com/en-us/research/wp-content/uploads/2005/01/soda05.pdf) derives directed shortest-path bounds from precomputed landmark distances. Neither technique alone is our complete isochrone/rendering pipeline, and arbitrary interstate samples do not automatically satisfy their correctness conditions.

## Anchor data can support conservative refinement

Derivation for a fixed nonnegative driving-time model: let s be an origin state, a an anchor state, v a target road state and d(x,y) the minimum modeled travel time. Direction and turn history must compose correctly at each state.

```text
Upper bound: d(s,v) ≤ d(s,a) + d(a,v)
Lower bound: d(s,v) ≥ d(a,v) − d(a,s)
Lower bound: d(s,v) ≥ d(s,a) − d(v,a)
```

Combine valid lower bounds with a maximum (including zero), and upper bounds with a minimum. For budget T, an upper bound ≤ T certifies reachability; a lower bound > T certifies non-reachability. Refine unresolved states. Only use defined bounds: infinity minus infinity is not valid arithmetic. A feasible route cost can provide an upper bound; it cannot be substituted for an exact distance in the lower-bound formulas without another proof. Record whether stored values are exact costs or certified bounds.

Equivalently, for graph-state reachability R:

```text
R(a, T − d(s,a)) ⊆ R(s,T) ⊆ R(a, T + d(a,s))
```

This applies to matching road states under the same graph/cost model, not directly to generalized filled polygons. A coordinate may snap to several permitted starting states: apply the argument per state and combine their reachable sets correctly. Reaching a coordinate must not reset heading or turn restrictions. Ordinary coordinate-to-coordinate API costs cannot be assumed to provide composable state costs.

The outer bound can require anchor data beyond the user's maximum budget. A field truncated at 12 hours cannot establish an outer bound at 12 hours plus an attachment cost. Preserve the computed horizon; distinguish **unreachable** from **not searched far enough**. An attachment-dependent margin or explicit unresolved status is required. Quantized lower/upper bounds need conservative rounding and a recorded time unit.

## What 10,000 points would cost

Arithmetic estimates below assume uncompressed four-byte cost entries. They exclude IDs, access lists, geometry, indexes, working memory and build intermediates. Actual US graph-state count and compression are not measured.

| Representation | Raw cost storage |
| --- | --- |
| Full ordered 10,000 × 10,000 anchor table | 400,000,000 bytes ≈ 400 MB / 381 MiB |
| One row of that table | 40,000 bytes |
| Full ordered table for 20,000 directed states | 1.6 GB |
| 10,000 fields to/from each 1 million road states | 80 GB per million states |

The full ordered matrix already includes both a→b and b→a. Ten thousand physical locations may require more than ten thousand states to preserve directions/turns; doubling states quadruples matrix storage. The dense matrix is a useful upper-level asset to evaluate, not a complete cost field for every road.

Proposed storage experiment: small immutable row/block files, a manifest and selected coarse landmark summaries, with detail loaded on demand. A query could fetch a few relevant rows instead of the entire matrix, but access-pattern and storage-request costs need measurement. Measure lossless compression before choosing precision reductions. Cached polygon previews may help display; numeric cost/bound data is needed for principled refinement and different thresholds.

## Selection and benchmark design

Seed at interstate interchanges and important long-distance connections, then evaluate gaps using **driving time to/from anchors**, not just map distance. Include divided-road directions, major non-interstate highways, rural/coastal/mountain roads and separate Alaska/Hawaii components. US coverage must retain the chosen Canada/Mexico crossing policy. A shortest permitted path may avoid the interstate network entirely; a feasible path through sampled anchors is an upper bound until complete access coverage or another proof establishes exactness.

Reserve independent evaluation origins away from the chosen anchors, including urban streets, remote roads, source offsets, prohibited turns and disconnected components. Tune anchor placement on development cases, then evaluate on the reserved cases. Reference answers must come from an independent exact search using the same imported graph and weights; testing cached estimates against those same estimates is circular. Maintain both graph-membership and separate geographic-rendering error measurements.

Measure 2/6/10/12-hour queries only where the graph supports their coverage. Report false positives/negatives, unresolved-state fraction, bound width, states searched, bytes fetched, peak memory, cold/warm latency and preprocessing/storage costs. Anchor-to-anchor point-routing speed alone does not establish whole-contour performance.

## Precomputation and cache lifecycle

**User constraint: the experiment must not depend on public routing API quotas.** The current interactive app is configured for hosted openrouteservice and spends a provider request when computing/replaying a contour. That is separate from the proposed offline anchor batch. The [initial batch runner](offline-anchor-pilot.md) uses our downloaded graph in a network-disabled container, verifies required graph/PBF/config artifacts before native work, and checkpoints rows for resumption. It cannot call/fall back to a public provider. Its coordinate-to-coordinate costs are not yet the composable exact state costs needed for the bounds above. Run the computational phase without network access where practical, as the existing graph-build container already does.

Data acquisition is a bulk snapshot step, not a per-anchor request. The repository already contains checksum-verified Southern California/Mexico OSM source files totaling 1,318,456,511 bytes in ignored `data/valhalla/sources/`, and a completed California/northern-Baja graph in `data/valhalla-v2/` (922,142,720-byte archive). Those files support bounded pilots; a national road graph and 10k-anchor dataset have not been provisioned. Broader coverage needs a separate download/disk/RAM assessment before acquisition. All computations in an offline batch must refer to the same graph/model snapshot. Periodic source refreshes are explicit acquisition/build jobs.

Use our offline engine and fixed source snapshot. Build rows in resumable batches, retaining timings and checksums. A one-to-many computation can populate a row; 100 million matrix entries do not require 100 million separate API calls. Choose the actual batched routing method after pilot measurements. The connected public free API does not supply the required 12-hour reference capability.

Reuse the repository's provenance pattern: graph/source identity, metric/profile version, coverage and border policy, directed anchor IDs, snapping offsets/states, algorithm revision, time unit/precision, horizon, build settings and artifact hashes. Keep large generated files in ignored data storage, with immutable published versions when ready. Treat a changed graph or metric as a new index version initially; effects of a changed road can propagate beyond its local tile.

Separate this durable precomputed index from a bounded opportunistic query cache. Exact query-cache identity includes the graph/model, direction, snapped states/offsets, budget/horizon and output quality. Coordinate bucketing requires an explicit approximation/error policy. Never mix fields from different graphs or silently treat missing files as disconnected roads.

## Proposed pilot

1. Initial state/turn/bound qualification is complete on a restricted real downtown graph, with independent Bellman–Ford search and adversarial tests. See [reference evidence](state-routing-reference.md). The [cell-summary comparison](cell-routing-experiment.md) checks safe grouping/selective reads, with no exact-query speedup; the [compact native baseline](native-routing-baseline.md) is qualified on that same graph. A separate [v2 model](maneuver-routing-model.md) qualifies prohibited via-way history and partial destinations, retaining unsupported-rule closures. The [regional capacity probe](regional-routing-capacity.md) now measures 387,236 states; qualify barrier access and reduce importer memory before expanding anchor counts. Import realism remains incomplete.
2. The first 256-target samples showed substantial runtime/memory costs; the initial complete storage/resume smoke test uses 32 anchors. Qualify the method before roughly 256, then 1,000 anchors and a national 10,000-point build. Use existing regional data for structural/short-budget tests; assess broader source/disk/RAM capacity before claiming complete 12-hour coverage.
3. Compare an anchor table plus selected landmark/region summaries with the uncached reference. Record preparation cost, raw/compressed bytes and how much uncertain work remains for held-out origins.
4. Scale anchor count or improve placement only when the measured reduction in refinement work justifies build/storage/I/O cost. Start national computation after the graph/model, coverage and resource budget are concrete.

Recommendation: **make the 10k points a candidate reusable backbone, pair them with a smaller set of landmark fields, and maintain a separate independent benchmark.** This is compatible with offline preparation and one Vercel app serving/using versioned assets; actual server/browser query feasibility still needs evidence. It does not yet provide a self-hosted 12-hour engine.
