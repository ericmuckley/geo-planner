# Compact two-pass prototype: faster sample, national import still held

October 27, 2026. The bounded prototype passes its frozen sample gates: median node-index loop **1.803566 → 0.914775 seconds**, **1.9716× throughput / 49.28% less time** against the previous optimized V4 validator. Index storage falls **1,748,992 → 1,024,256 bytes**, a **41.44% reduction**. Projected records and coordinate float bits match. **This is a sample result; deployed v9 and map accuracy are unchanged.**

The synthetic extractor now uses two passes and independently recomputes audit selection. Its output matches the frozen four-pass reference; deliberate primary omissions and output corruption are rejected. A real dependency-complete road extraction has not run. The fixed node-prefix forecasts still fail the original national time and storage screens, so no full import is admitted. [Decision and remaining blockers](design-decision.json).

## What was implemented and verified

Six new, separately versioned files preserve all old producers:

- [Compact index](../../../scripts/coarse_osm_compact_v1.py): ordered ID64/XY32 records in checksum-bound shards, exact coordinate conversion, bounded batched writes/lookups and independent rolling replacement. A replacement shard is generated from the second stream, compared and verified before its primary predecessor is removed. Failures preserve owned output; close never repairs or flushes a failed buffer.
- [Two-pass / fused native prototype](../../../scripts/coarse_osm_stream_v1.py): raw-object metadata/ordering/byte checks, fused native projection/validation and separately built audit geometry/membership. Pass two materializes raw objects and rebuilds its own coordinate shards. Primary IDs are materialization hints only; an independently recomputed exact key-set check rejects omissions/extras.
- [Correctness controls](../../../scripts/coarse_osm_stream_v1_test.py): reference output equivalence, outside-node/crossing-way/typed-ID/raw conditional/private tags/unresolved members, omitted ways/nodes/restrictions, extra nodes, membership/output/geometry tampering, source drift, malformed metadata, caps, deadlines, corrupt/truncated shards and lifecycle failures. Native controls compare 5,000 deterministic random coordinate pairs and a genuine tiny mixed PBF against the frozen projector. Unsupported precision and negative zero in raw fixture coordinates are explicitly rejected, never rounded into acceptance.
- [Profile](../../../scripts/profile_osm_stream_v1.py), [launcher](../../../scripts/run_osm_stream_v1.py) and [driver controls](../../../scripts/coarse_osm_stream_driver_v1_test.py): exact input/tool bindings, fresh output, fixed cases/gates, offline resource guards, partial-counter evidence and label/image-checked cleanup.

Combined controls: **host 26 pass / 1 native skip; Linux 27 pass / no skips**. The production launchers do not import these prototypes. Shared decoder/canonical/normalization primitives remain explicit; the audit has separate source-built coordinate storage, selection geometry, membership and output reconstruction. These controls are not an independent national source proof.

## Fixed sample measurements

| Item | Result |
| --- | --- |
| Original node-prefix input | First9 complete frames /377,536 bytes /64,000 nodes from the previously saved prefix |
| Plain paired loop times, V4 | 1.816906 /1.803566 /1.799650 s |
| Plain paired loop times, compact | 0.914775 /0.908695 /0.915847 s |
| Frozen gates | Speedup≥1.25× and sample index fraction≤0.75; both pass at1.9716× /0.585626 |
| Projected-record hashes | All eight prefix cases equal `e845926261ab0fc4d7c1d8a904e08bbde01fd9e063b582d6537fc4cdd0a957b7` |
| Index bytes | V4 SQLite1,748,992; compact payload+header+catalog1,024,256 |
| Full saved-index reconciliation | All64,000 rows in each compact index exactly match SQLite ID and coordinate float bits |
| Separate projection / fused-validation loops | 1.084429 /0.857291 s; individual loops, not paired speed claims |
| Separate lookup medians | V4 **1.236 ms**, compact **3.540 ms**; compact is slower |
| Lookup pattern | 1,152 queries: first1,024 node IDs reversed, then first128 again; one compact shard, no national lookup claim |
| Mixed-object equivalence | First1,000/type saved JSON records, re-encoded as PBF; both paths return the exact original3,000 records/hash |
| Counted native views | **521,000**:512,000 prefix callbacks,3,000 XML encoding views and6,000 re-encoded mixed callbacks; tiny synthetic controls separate |
| Worker / host before summaries | **10.867376 /11.955991 s** |
| Observed process max RSS | **115,724 KiB**, this Linux sample worker only; excludes host/kernel/full-import/cloud memory |
| Closed output | **45 files /13,120,016 bytes** |
| Worker/client/OOM/cleanup | Both exit0, not OOM; owned removal and separate exact-ID absence inspection pass |

The timed index loop includes projection, validation, canonical hashing, counters/checkpoints as applicable, writes and index finalization. Index construction happens before that loop; its footprint is counted. Lookup is timed separately after finalization and excluded from the speed gate. The fused native path avoids redundant canonical serialization and calendar parsing; raw JSON projection still occurs for every node. There is no instrumented/paired subtraction or whole-import timing claim. [Raw results](raw/result.json), [independent saved-byte audit](index-byte-audit.json), [closed roster](closed-output.json).

The mixed fixture is **re-encoded saved real records**, not original publisher PBF bytes or dependency-complete road geometry. Its two modes differ (V4 includes a small node index; fused validation does not), so their individual timings are not a speed comparison. Exact projection/hash equivalence is the criterion. Native EOF is for these bounded files only. No national source is mounted/read by the profile and no full-source framing/count/extraction is replayed.

## National decision and next design

The [completed inventory](../coarse-osm-inventory-2026-10-27/README.md) supplies1,606,229,364 nodes. Extrapolating the compact prefix loop to two node passes gives **12.75 hours before margin /25.51 hours at the fixed2× margin**, versus14,340 s original work time. This is **a forecast from an unrepresentative leading prefix, not a measured national duration**; remaining way/relation/audit/framing/setup/cleanup work is excluded. The node-only screen needs another **6.40×** improvement at that margin.

Storage also remains held: the exact16-byte node payload alone is25,699,669,824 bytes/index, or **38,549,504,736 bytes** at the retained1.5× margin, exceeding the old24 GiB/index screen before headers/catalogs. Rolling replacement avoids two full concurrent copies but does not shrink this per-index payload. Prototype defaults (32 MiB indexes,1 MiB catalogs) are sample bounds, not national defaults. No physical budget or full-import typed cap has been raised.

Next select a bulk/native processing path that avoids per-node Python object/JSON work while preserving all source guards and independent auditing, and specify a lossless block/delta-ID coordinate format with a conservative footprint bound. Review cached capabilities before assuming a compiler/API exists. Any changed validation contract needs an explicit versioned design; do not silently skip guards. Then freeze another bounded prototype screen. No new national scan or full-extraction recipe from this result. [Current ordered task](../../next-steps.md).

## Frozen recipe, resources and safe recovery

[Execution plan](execution-plan.json) SHA256 **`2b91e6547522e701ca0043e73fc4490932ae9c2687980a73ee0aa6db01475bd1`**,234 host/233 worker file bindings. [Command](commands.json) is **used historical provenance**, never a readiness check; [freeze](freeze.json) describes pre-execution state. Preserve all sealed files, raw outputs and stopped older attempts; no replay, resampling or post-result retuning.

Cached qualified image/site/runtime only; network none/no pull/no packages/no credentials, read-only inputs/root,4 GiB memory/zero swap/two CPUs/64 PIDs/256 MiB tmp,64 MiB file/32 MiB index/1 GiB owned writable+tmp. Case60 s/worker300 s/host600 s;200,000 objects/case/two million aggregate. Source/provider/DB/metadata/paid requests zero. App/grid/UI/env/Postgres/npm/Vercel and commits/deployment unchanged. [Actual guards and receipts](raw/resource-guards.json), [independent cleanup](cleanup-audit.json), [verification](verification.json).

Safe saved proof, no Docker/network/native or producer replay:

```sh
python3 -B docs/evidence/coarse-osm-stream-2026-10-27/verify.py
python3 -B docs/evidence/coarse-osm-stream-2026-10-27/verify.py --local-assets
```

The proof chains42 prior sealed runs and223 earlier producers, plus six new files. Local mode hashes the closed roster and compares compact/SQLite rows; the parent chain may hash prior national source assets but never decodes them. Small metadata are mirrored here; raw indexes/XML/re-encoded PBF stay ignored. All new code/evidence/docs are local and uncommitted, absent from a fresh clone at648c731 along with ignored assets. Check197/typecheck/build pass with existing build warnings.

All original21 windows/publisher/source/50% usable-limit/independent matching/physical/83ORS-35Valhalla accuracy/package/startup/API/visual/model gates remain held. No usable-road dataset, timing correction, graph or national accuracy improvement is qualified. [Handoff](../../agent-handoff.md).
