# Terminal-fragment prototype — October 26, 2026

**Implemented and synthetically verified; the real cached-data experiment has not run.** Eighteen tests pass on host and network-disabled Linux. The prototype permits cuts at a connected path's ends while retaining original endpoint connector requirements for every interior join. This completes the preceding [implementation/synthetic scope](../coarse-chain-role-scope-2026-10-26/next-fragment-plan.json).

The [exact execution recipe](execution-plan.json), SHA `509e98e071d67659698a550e6672766bad5e820a4f8d82c20688199669913fdd`, binds 32 inputs and 22 worker files after tests and before any new cached-data geometry/enumeration. [Frozen rules](rules.json), [synthetic readiness](readiness.json). No production or source-feasibility claim follows from synthetic fixtures.

## Geometry and uncertainty

[Prototype and worker](../../../scripts/coarse_timing_fragments.py) retain saved full nodes unchanged and add start-cut, end-cut and both-cut variants. Cuts use first/last own-aligned Census sample projections onto the original publisher polyline. Fractions use normalized cumulative haversine polyline length, without interpreting publisher interior-connector semantics. Raw IDs, fractions, points, sample indices, weights and source/scope/metadata bindings remain available.

Interior joins require identical nonnull original connector IDs, the existing 25 m distance and unchanged progress comparisons. A cut endpoint has no connector ID, so it cannot become an interior join. Interior nodes must remain saved full nodes; a path cannot reuse the same source row through another variant. No proximity-only join or first/best alternative selection.

Projection requires the existing 25 m distance and 15° undirected tangent. Distinct equally near along positions, loops, backwards progress, interior plateaus and insufficient progress remain unresolved. Adjacent pieces sharing the same vertex may tie at that one along position. Multiple samples clamped to the same **original raw endpoint** are allowed; that sampling edge case was exposed and fixed in synthetic development before the recipe freeze. It does not permit tied interior positions.

New clipped intervals must remain inside the original window, including every intervening original vertex. Nonempty level rules, unsupported roles, invalid geometry and endpoint-identity restrictions remain. All access/speed parser results and conditional/directional scopes stay unchanged. A geometric candidate can still have unusable or unknown speed/access metadata.

The search retains all distinct qualifying minimal variant paths under 80% original weighted-sample union support, 64 rows/path and 4,096 expanded states/arc. Different intervals or paths may describe the same physical road; candidate counts are not physical-road multiplicity or uniqueness. Empty cache and caps remain explicit. The prototype never admits physical identity, car access, usable-speed coverage or source completeness.

## Validation

[Eighteen fixtures](../../../scripts/coarse_timing_fragments_test.py) cover:

- Overhanging endpoints, connected segmentation, reversal and collinear vertex insertion.
- Shared-vertex duplicates, original-endpoint clamping, interior ties and retraced loops.
- Invalid/displaced joins, parallel alternatives and crossing tangents.
- Level/role/connector exclusions, unchanged scoped speed/access results and window boundaries/interior excursions.
- Weighted partial support, minimal paths, no repeated source row, length/state caps and empty cache.
- End-to-end immutable controls and rejection of altered fractions, projections, weights, original statuses and access claims.

The synthetic end-to-end fixture contains **two arc records / 112 original weighted source km**, including an empty-cache record. One populated record gains an uncapped clipped path while its original endpoint-chain candidates remain empty. This is a constructed test assertion, not a retained-data measurement. Original input bytes and every original JSON field remain equal. Old node/chain producers raise if the new pipeline calls them.

[Independent audit](../../../scripts/coarse_timing_fragments_audit.py) reconstructs projections, intervals, window checks, all-pairs joins and iterative enumeration. It checks every proper contiguous subchain, original weighted unions, candidate metadata, all original control fields and the fixed decision. Sealed WKB/parser/sample/tangent/hash primitives are shared explicitly; this is no independent physical road/access review.

Host and Linux each pass all eighteen tests; actual Linux cgroup/network guards pass. Biome checks 197 files; app typecheck and ordinary build pass. [Host](unit-tests.txt), [Linux](linux-tests.txt), [checks](checks.json).

The initial synthetic Docker command omitted `--init`. The watchdog guard refused PID 1 before tests or geometry started. [That failure log](linux-preflight-rejection.txt) is preserved. The corrected command uses `--init`, the cached image with `--pull=never`, network=none, 1 GiB/zero swap, read-only code/root, 64 MiB tmp and a 120-second synthetic-test watchdog. Both synthetic containers use `--rm` and mount only scripts; no real road data, workspace environment or credentials are mounted. The future real recipe separately retains the one-hour worker watchdog, 128 MiB output and 64 MiB tmp. No real-run latency, output size or peak-memory result exists yet.

## Next execution and fixed decision

Run the frozen experiment **once** at new ignored `data/coarse-quality/overture-timing-fragments-v1/`, which is absent at this checkpoint. Preserve all original 55,120 IDs, 2,469 arc/window controls, 85,629 weights, 85/105 source classes, 21 incomplete windows, 82 old candidates/32 old candidate-bearing outcomes, fourteen old positives, zero old caps and 2.827 baseline provisional eligible km. All original chain fields remain nested immutable controls.

**Support the hypothesis iff at least one populated-cache arc with zero original endpoint-chain candidates and no original cap gains a new uncapped path containing a terminal cut. Otherwise reject it without retuning.** This tests existence under sampled geometric rules, even when other aligned rows remain unresolved. It cannot establish unique/drivable matches, usable-speed coverage, ETA accuracy or the original source-feasibility gates.

Read-only readiness first:

```sh
python3 -B docs/evidence/coarse-timing-fragments-2026-10-26/verify.py
python3 -B docs/evidence/coarse-timing-fragments-2026-10-26/verify.py --local-assets
```

Future producer command, **not executed in this checkpoint**:

```sh
python3 -B scripts/coarse_timing_fragments.py data/coarse-quality/overture-timing-fragments-v1 509e98e071d67659698a550e6672766bad5e820a4f8d82c20688199669913fdd
```

If it fails or caps, preserve all evidence and stop; do not overwrite, retry with relaxed rules/resources, acquire more data or rerun old producers. Record the independent audit and frozen hypothesis outcome before making one next-input decision. All 21 windows remain incomplete regardless of geometry results.

This work remains local/uncommitted. Deployed v9/grid/UI/env/DB/npm, consumed 48/6/29 provider budgets and all earlier failures/results remain unchanged. Zero source/tool/provider requests, new real geometry enumerations, routing/ETA queries or deployments. [Recovery and commands](../../local-development.md#terminal-fragment-prototype), [ordered task](../../next-steps.md).
