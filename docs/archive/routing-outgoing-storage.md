# Compact outgoing-road storage — October 18, 2026

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

Current coverage status: the [two-hour regional baseline](../two-hour-region.md) now qualifies and runs in the browser. Continue with its six-hour source/resource preflight; this report preserves the earlier storage experiment.

This experiment replaces temporary per-node Python lists with a compact numeric index during graph construction. It continues [the source XML memory work](routing-xml-streams.md), using cached data and no routing-provider quota. [The short progress summary](../progress.md) describes the remaining 10–12-hour goal; this experiment does not raise the hosted app's 60-minute cap.

## Change and preserved behavior

`outgoing_index.py` uses one node dictionary, a 32-bit offset array and a 32-bit road-reference array for exact ordered `Roads` inputs. The original validation loop counts outgoing roads instead of appending road-index objects. Counts become node ordinals in the same dictionary; there is no second full node map. A temporary cursor array fills reference slots in the original road order, then is released before routing transitions are built. Lookups return views of the appropriate reference range, preserving every per-node append order, including parallel geometry.

Only rows reached by the original validation iteration are indexed. This matters for incomplete compact arrays: Python sequence iteration can end on an `IndexError`, and the old builder can accept that prefix. The new version preserves the observed result/error rather than introducing a new completeness check. Delay/cost/duplicate/self-loop validation and error priority remain unchanged. Node/way IDs retain their original integer precision; only array positions are 32-bit.

Generic rows, subclasses, unordered compact inputs, explicit string-ID mode and inputs beyond the reference capacity retain the frozen list builder. Compact eligibility does not introduce a new validation error. `outgoing_input.py` and `outgoing_import.py` version only the builder/import bindings; their function bodies match the old producers. AST guards preserve the validation loop apart from its storage operation and the complete restriction/adjacency body. Turn history, costs, access/barrier policy, source XML streams/excerpts, graph identities and JSON/CSR/gzip encoders stay frozen.

Twelve focused tests compare graph/audit/order or exact error type/message with the frozen builder, including interleaved nodes, 4,096-way fanout, missing/empty lookups, generic/subclass/unordered/capacity fallbacks, large OSM IDs, direction truth values, duplicate geometry, truncated arrays, restriction/delay priority and blocked nodes. Fresh importer fixtures cover 17 cases in compact and string fallback modes, with 296 full/888 bounded independent fixture cost checks per mode. Each real-data worker also repeats the prior 11 control-point and 17 XML/source/uncertainty fixtures. Existing regional route/native qualification is reused on identical bytes, not rerun here.

## Reproduce

Requires cached qualified graphs and canonical `data/xml-pilot/xml-v1-*` baselines. These commands do not read credentials, download data or use networking:

```sh
npm run routing:outgoing -- --case downtown-v2
npm run routing:outgoing -- --case corridor-v3
npm run routing:outgoing -- --case wide-v3
npm run routing:outgoing -- --case hour-v3
python3 -B docs/evidence/routing-outgoing-2026-10-18/analyze.py
```

Outputs use ignored `data/outgoing-pilot/outgoing-v1-*`. Completed attempts refuse overwrite. Repeat with the same fresh `--series outgoing-repeat-01` on all four commands, smaller cases first. Equality references stay canonical `xml-v1-*`; the current hour case requires three same-code/mode smaller proofs. Changed code requires a new version/output identity. Preserve all prior attempts and producers.

The wrapper retains **two CPUs / 4 GiB / no swap / no network**, `--pull never`, read-only inputs/recipes/root filesystem and a 256 MiB temporary filesystem. Tools remain pinned to image `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`, Python 3.12.3/Linux arm64 and Valhalla tools revision `7fd2228e5863b442bc1ac8d25eece6415dd91bff`. The custom graph builder does not use Valhalla search. There are no new dependencies.

Workers verify frozen source/artifact/recipe bytes, save code snapshots and bind run identities to predecessor and original qualification manifests. The current case verifies original independent/native reports, comparison counts and kernel source/binary hashes before success. No larger graph is attempted.

## Measurements

All **24 artifacts** match across four frozen cases, including all seven current graph/audit/source/CSR/gzip files. Original independent/native qualification stays bound to those identical bytes. Every worker records **zero limit/OOM/kill events and zero swap**.

| Frozen case | Complete peak before → after (GiB) | Import before → after (s) | Complete before → after (s) |
| --- | --- | --- | --- |
| Downtown v2 | 0.050 → 0.049 | 1.97 → 1.76 | 2.42 → 2.18 |
| Corridor v3 | 0.238 → 0.217 | 40.28 → 41.44 | 47.60 → 48.79 |
| Wide v3 | 0.465 → 0.419 | 123.64 → 133.80 | 147.04 → 161.35 |
| Current hour v3 | 1.214 → 1.062 | 400.20 → 403.28 | 474.04 → 476.85 |

Current complete peak is **1,140,269,056 bytes / 1.062 GiB**, down **12.5%** from 1,303,441,408. With the 25% factor it is **1,425,336,320 bytes / 1.327 GiB**. Worker peak RSS falls **1,236,696 → 1,078,380 KiB** (**1.179 → 1.028 GiB**). Current import rises **0.8%**, complete runtime **0.6%**; the wider case's complete time rises about **9.7%**. These are individual observations, not a timing distribution or guaranteed performance improvement.

The largest current index has **1,567,609 nodes / 3,039,480 references**. Offset/reference payload is **18,428,360 bytes (17.57 MiB)**. Dictionary plus array containers total **102,314,680 bytes (97.57 MiB)**, versus 221,840,968 bytes (211.56 MiB) for the preceding dictionary/list containers. New node keys and ordinal integers add **48,509,384 / 43,893,052 shallow bytes**, respectively; do not compare only the array payload with the old whole index. The temporary cursor array is **6,270,516 shallow bytes (5.98 MiB)**. There is one full node map. All seven base builds record counted, offsets-ready, buffers-ready, filled and final-index checkpoints, followed by rules, arcs and release/hash checkpoints.

The full peak is first reported at `pass4:indexesReleased` (270.22 s); source evidence/export/verification add no higher peak. That checkpoint's anonymous/file samples are **929,693,696 / 40,648,704 bytes** after releasing the index; they are not the components of the earlier instantaneous peak. The parser's cumulative peak is **997,306,368 bytes** at 48.15 s. [Raw reports and peak histories](../evidence/routing-outgoing-2026-10-18/README.md) retain construction overlap and separate sampled anonymous/file accounting. The existing XML streams still read all four current source passes to EOF, close every handle and advise completed ranges without errors.

Validation passes: **174 host Python cases (165 pass, nine existing tool/platform skips)**; **83 scoped Linux cases, no skips**; **14 adapter tests**; `npm run check`, `npm run typecheck`, `npm run build` and the evidence analyzer. Existing database non-null assertion, MapLibre chunk-size and upstream TanStack directive warnings remain. All **194 pre-existing fingerprints and seven frozen new files** match. No environment values were inspected/changed and nothing was staged.

These are single local observations on Apple M4/16 GiB, with uncontrolled cache/host/VM conditions. Application checks and scoped regression tests overlap part of the corridor run; the hour run has no deliberately concurrent workload. Complete cgroup peaks include preflight, fixtures, parse, every base/history pass, evidence, export and verification reads. Checkpoints are cumulative peaks; periodic anonymous/file samples and RSS have different scopes and must not be summed. Host/VM paging is unmeasured. Shallow container/key/ordinal sizes exclude allocator overhead and are not isolated peak savings. The 25% factor describes current-workload headroom, not larger-build/query admission. These are preparation/verification timings, not graph-search, HTTP, contour, browser or Vercel timings.

The current graph remains `b50422b83537cecf12f1ecb4f7a3fa4e80df206726796b562135715f3737d048`: **3,034,771 roads / 3,036,124 states / 6,411,757 arcs / 1,160 via-way prohibitions**. Bounds remain `[-117.65,31.9,-116.0,33.6]`; model `exploratory-static-car-v3` retains 5,000 ms signal and 20,000 ms U-turn delays. Source XML remains **451,794,442 bytes**, SHA-256 `64462b578bd9b688290fa8777bbb2564ea40ed649c47d88146353c72097ab1a1`, from cached California/Mexico data dated `2026-10-14T20:21:12Z`. [Provenance/preparation](two-hour-coverage-preflight.md) is unchanged. The saved native report records 258,070,540 cost/membership comparisons plus two partial destinations from its original uncapped macOS run; those checks are reused on identical graph bytes.

Current priority update: [the visible local experiment](local-routing-experiment.md) now takes precedence over general resource optimization. The qualification-memory recommendation below is retained as historical context and applies only to a concrete coverage blocker.

## Remaining work

**Next: version and measure qualification/reload storage before another larger build.** The preserved current qualification report peaks at **1,733,201,920 bytes / 1.614 GiB**, above the latest graph-construction path. This is the previous qualified run, not a new qualification measurement here. It includes reload, five full fields, eight budgets, route witnesses, two partial sinks and final verification reads.

Start with phase measurements for road-ID lookup, snapping, full/bounded label lifetimes, field encoding and partial-destination diagnostics. The frozen qualifier builds a global road-ID dictionary that remains live after its small set of source-maneuver lookups; version a targeted lookup or shorter lifetime while preserving lookup/error behavior. Keep the independent algorithms, exact costs, summary semantics and qualification coverage unchanged. Explicitly measure temporary overlap and complete peaks rather than extrapolating from container sizes.

Require fresh fixture checks plus exact full-field/CSR bytes and functional summaries on the frozen current graph, retaining five-origin/eight-budget full/bounded comparisons, twelve city routes, both partial destinations and existing native/source/model bindings. Reuse old evidence only where byte identity justifies it; do not describe that reuse as fresh regional search. Keep the same cap and all old producers/attempts. Source gaps remain a separate gate.

Coverage stays unchanged: five selected origins have no potential cuts within 60 minutes; first cuts are **63m32s–77m34s**, and all selected two-hour cases reach cuts. This does not prove all-origin/source completeness or long-range contours. Northern Baja remains included. Otay ways `114198251`, `185333061` and `577149752` retain explicit source uncertainty; real queues, documents and current crossing eligibility remain unmodeled. The continuation envelope still exceeds cached eastern/southern geography, including missing Arizona/Nevada roads.

**Larger admission remains on hold** pending source coverage and complete preparation/build/qualification resources. The old 20.64 GiB estimate is a historical workflow forecast, not measured candidate graph/query RAM or a forecast for this version. Any later admitted graph needs its own identity, exact rebuild, independent full/bounded/partial/native qualification and every all-direction cut/history state at 120 minutes. US-wide acquisition, the 10k-anchor batch, long-range app contours, caching and Vercel rollout remain deferred.

Raw reports and exact validation commands are in [the evidence directory](../evidence/routing-outgoing-2026-10-18/README.md).
