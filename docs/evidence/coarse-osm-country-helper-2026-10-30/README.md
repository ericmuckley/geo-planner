# Countrywide summary/probe helper: synthetic qualification

October 30, 2026. **All 103 pinned target Linux tests pass, with zero skips.** The new C++ summary helper and Python index probe preserve the tested metadata, field, coordinate, source-integrity and failure behavior. This completes the core helper qualification, not the national feasibility test. No existing national file or saved real road sample was mounted, read, hashed or decoded. Deployed v9 and its map remain unchanged; new code/evidence/docs are local/uncommitted.

The [preceding plan](../coarse-osm-country-screen-plan-2026-10-29/README.md) calls for two guarded national reads while retaining only eight fixed index portions. Four new, now sealed producers implement the summary/probe core and a synthetic qualification runner:

- `scripts/coarse_osm_country_screen_v1.cpp`: continuous native validation, GPF1 sealing, encoded-node roundtrip, bounded highway selector and typed source witnesses.
- `scripts/coarse_osm_country_screen_v1.py`: bounded bridge, exact would-be index census, fixed source-ordinal probe, rolling source rebuild, lookup instrumentation and independent reference-codec audit.
- `scripts/coarse_osm_country_screen_v1_test.py`: 29 new/ported tests; actual target execution is required for 24 of them.
- `scripts/run_osm_country_screen_v1.py`: frozen offline build/qualification lifecycle. It implements `--qualify` only; a national execution wrapper/freeze is still needed.

The old 16 MiB/two-million-object projector, source, failed 8.78 GB index, compiler assets and all earlier used producers/recipes are unchanged. C++ guard/parser logic is versioned from the sealed predecessor because it cannot be refactored in place. Frozen Python framing/field oracles and the delta codec/V2 shard checks are reused read-only.

## What passes

The actual corpus is 74 retained regressions plus 29 country-helper controls. Host execution passes 56 and skips 47 target-only cases; the actual target runs all 103 with no skips. `npm run check` checks 197 files; typecheck and ordinary build pass. Existing chunk-size/directive build warnings remain. No dependency, env, database, app or Vercel configuration changes.

The new compiled helper is 2,002,760 bytes, SHA `0b3d2d9e609350252fb9850a2342215c6fae3172b03b76fc65350b55c66b9a53`. Pinned GCC14.2.1/libosmium2.23.1/protozero1.8.2 compile/load in the cached Python3.13.5/glibc2.34/zlib1.2.11 target. ELF is AArch64/little-endian, required exports load, static C++ runtime and allowed dynamic dependencies pass. The unchanged delta source is linked into the new artifact. [Exact ABI](abi.json), [qualification freeze](qualification-freeze.json).

Controls cover:

- Full fields and semantic seals against the frozen Python reference, Unicode/duplicate tags, calendar/epoch0/state/visibility/type/order/version/XY checks, exact cap fallback, invalid discarded metadata and references, rejected/cap+1 receipts, callback refusal/lifetime/reentry and malformed frames.
- Checked u64 operations across `2**31`, `2**32` and overflow, explicit ABI array lengths, fixed priority/stratum vectors, 65,536-object checkpoints, signed63 ID gaps and every source block's original ID/XY roundtrip.
- Exact byte census against a fully written tiny reference; nonadjacent source-shard remapping, partial final blocks/shards, complete rolling comparison and refusal to delete a corrupt/unowned primary.
- Source-built coordinate witnesses, missing-ID stops, fixed highway top-128 selection/exclusions, 70-block cache pressure, order/duplicates, warm whole-shard authentication, unchanged-mtime drift, IO/file/index/catalog/namespace/allocation limits and unavailable metrics.
- Hard watchdog kills during a blocked native callback, a native syscall without callbacks, framing and posthash; normal/error EOF and exact owned cleanup remain distinct.

The new summary mode emits no ordinary Python node/way/relation projections. It still validates and seals every object. It sends bounded semantic batches and encoded node blocks, at most 128 selected highway traces, exact ambiguous-node fallback frames and typed witness batches. Native canonical sizes for node floats remain **bounds**, with exact Python checks at ambiguous limits; they are not exact all-node JSON totals.

## Persistent independent positive proof

The generated synthetic source has 300 nodes and 200 highway ways, 1,202 PBF bytes. Full-field proof preserves all 500 records, semantic SHA `b98149892668d7880e9c4d7443f56d81dbd1a16a33f0a0c62699c78d269200f8`. Two complete guarded passes consume 1,000 returned source receipts, retain the same index/trace, and source-capture all 300 coordinate rows. The frozen Python decoder independently verifies all 300 ID/XY rows and binary64 coordinate bits. ID/XY row SHA `a9e7075c1b33d8301cdf4682e02e7c4a4922549304cb4eeaef16ffffa5e2d8a5`.

The fixed priority chooses 128 of 200 eligible ways, preserving 256 reference occurrences. Local/spread/way-reference cohorts each have cold-application/warm/repeat results. Warm hits still authenticate the full 2,891-byte shard; first access also validates its format. Persistent positive proof is one tiny shard; the separate passing controls exercise nonadjacent remapping and more than 64 cached blocks. Neither is a national lookup or speed benchmark.

The default auditor independently recomputes all raw-field seals, selected-way priorities, full tiny index/census bytes, all source-witness and lookup bits/order/duplicates, and resource/lifecycle bindings from saved bytes. It executes no native helper or PBF decoder.

## Actual limits and measurement scopes

One exact used recipe SHA `b61b64f5405a0528333f543b0f99efecd7e8412aab05a2ae9eb91ebf42d2c4b8` binds 284 host inputs/265 worker files/80 code or proposal mounts, 103 test IDs and the saved compiler/header content seals. No image pull, install or network request. Both build/control worker and clients exit0, not OOM; exact owned removal and a separate exact-ID inspect show both workers absent. Rediscover ownership for future work.

Actual isolation: network none, read-only root/inputs, 4 GiB RAM/zero swap, two CPUs, 64 PIDs, 256 MiB tmp, 64 MiB files, 1 GiB work including tmp, 300 s workers/570 s shared work/600 s host. Compiler alone gets narrowly scoped SYS_CHROOT, cleared before exec. Qualification uses smaller 32 MiB probe-index, 64 MiB authenticated lookup IO and two-million lookup-codec-row allowances. The larger countrywide proposals are not activated.

Cgroup `memory.peak` is 426,672,128 bytes for build and 95,068,160 for controls, with zero OOM events. These are container/cgroup peaks, including cache and descendants, not host, VM, cloud or national peaks. Host16.939385 s includes binding/asset hashes, compiler/startup, tests, positive proofs and cleanup; the unit runner's3.169 s and synthetic pipeline's0.382423 s are separate scopes. None is national import or graph-search time.

[Scope notes](scope-notes.json) preserve important accounting limits. Returned parent C++ receipts total86,867, plus separately recorded positive encoder/reference views. Killed children have unreturned bounded receipts; retained Python/reference scopes are separate. A conservative static corpus bound, including those reserves, is1,080,422<2million, not an exact measurement. Raw `sourceOrSavedSampleReads=0` refers to pre-existing real inputs: synthetic fixtures were read. Positive result storage snapshots precede the result-file write, so they are scoped subtotals rather than whole-worker allocated peaks. Complete pre/post source guard bytes are also only a subtotal; decoder/index/audit/lookup/process/physical IO remain distinct.

Closed ignored root `data/coarse-quality/us-osm-country-controls-v1/`: 54 files/3,519,966 bytes. All 53 non-library files/1,517,206 bytes are mirrored unchanged, including synthetic XML/PBF, fields, index/witness bytes and raw logs. The library stays ignored. Primary probe payload rotation was performed only after source rebuild/equality; final primary catalogs are retained while the complete replacement payload is in pass B. [Closed roster](closed-output.json), [verification](verification.json).

## Remaining work before a national run

The core component passes its declared synthetic corpus. The runner currently qualifies it only. Next implement a separate versioned whole-source execution wrapper, with admission records and exact resource/input/output bindings. Close remaining per-type timestamp/tag-size summary telemetry, full pass timing/close scopes, final storage-margin decisions and phase/aggregate counters before freezing that wrapper. Do not edit these now-used V1 producers.

No new source read is needed to implement or synthetically qualify that closure. Reuse the existing national identity/count records. Only a separately frozen, unused recipe may later activate the proposed larger source/pass/index/lookup bounds. No national maximum ID, whole-source metadata/EOF, full index allocation, mixed throughput, national lookup distribution, full road dependencies/21-window extraction, publisher/attributes/matching/physical route, accuracy, package/API/visual or model gate is admitted here. The old real-node48× result remains under its own scope; it is not a national forecast.

Vercel continues to serve the compact TypeScript model. Raw OSM/native/compiler tools remain offline. Cloud `DATABASE_URL`, all local config and consumed provider budgets are unchanged; no provider/DB/history write, commit, push or deployment.

## Safe recovery

From the repository root:

```sh
python3 -B docs/evidence/coarse-osm-country-helper-2026-10-30/verify.py
python3 -B docs/evidence/coarse-osm-country-helper-2026-10-30/verify.py --local-assets
```

Default is standard-library/read-only saved proof; local mode additionally hashes ignored closed outputs, pinned tools and compiler/header content, without native execution, PBF decoding or national-file reads. Do not replay the used qualification command as a health check. The exact command is retained in the freeze/recipe and original output; the existing owned root must remain closed. [Ordered next task](../../next-steps.md).
