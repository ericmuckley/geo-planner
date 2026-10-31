# Native metadata/projector: synthetic qualification

October27,2026. **62 actual Linux tests pass with no skips**, including46 retained and16 new controls. Host46 pass/16 compiled-target skips. The new C++ metadata validator/projector and bounded encoded-node handoff preserve the recorded fields, exact coordinates and independently audited selected output. This is synthetic correctness evidence, not a real road-data speed or map-accuracy result. V9/HEAD`648c731`/app/env/DB/npm/Vercel are unchanged; work is local/uncommitted.

## Implementation and measured result

Five new frozen producers: [C++ helper](../../../scripts/coarse_osm_projector_v1.cpp), [Python bridge](../../../scripts/coarse_osm_projector_v1.py), [two-pass integration](../../../scripts/coarse_osm_projector_extract_v1.py), [controls](../../../scripts/coarse_osm_projector_v1_test.py), [runner](../../../scripts/run_osm_projector_v1.py). Original delta source and every prior failed/sealed record remain unchanged. [Parent V2 proof](../coarse-osm-delta-v2-2026-10-27/README.md).

C++ validates every node/way/relation before filtering, including discarded metadata, then passes4096-row-or-final lossless encoded node blocks without ordinary per-node Python dictionaries/JSON. Python still owns framing/features/source hashes, digest/file/catalog/cache/storage, selected materialization/audit and exact near-cap canonical fallback. No full C++ IO or national launcher. The9000-node synthetic control delivers3 blocks and zero Python node-projection frames, with independent semantic/coordinate agreement. This is a batching observation, not throughput evidence.

Full-field proof emits all raw projected fields. Fast mode emits ways/relations and caller-selected node IDs. Both bind all validated objects to the new `geo-planner-projected-fields-v1` length-prefixed semantic seal; it is deliberately distinct from old canonical-JSON hashes. Exact escaped string/integer/syntax lengths and safe32-byte finite-float bounds accept unambiguous records; near-cap nodes call the exact Python canonical-size fallback. Refusal/errors stop. Calendar/epoch0/UTF8/duplicate tags/copy/ref/member/XY/capminus1-cap-capplus1/quotas/callback-lifetime/reentry/truncation/framing/EOF/source-drift controls pass. See [frozen format/ABI](format-spec.json), [qualification and remaining scope](qualification.json), [actual test log](raw/controls/worker.log).

Saved564-byte synthetic PBF has4nodes/3ways/2relations. Proof9 projected objects and fast5/7 objects have identical full-field seal`04630ed15b3eb0925917fb1d4dcabb51991d3cfe65eee84bc5a76b7652b9ed81`. Independently source-built second-pass index/audit reject missing/extra primary nodes/roads/restrictions/window membership and unselected metadata drift. Selected canonical/geometry/window output remains1470bytes/SHA`dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c`; two-pass18 vs four-pass36 object visits. Raw/field/coordinate/output equality is also checked offline by the Python proof, without native/PBF execution.

GCC14.2.1/libosmium2.23.1/protozero1.8.2 produce1,935,424-byte AArch64 `.so`, SHA`9227bc577f3592f167d614329ecc25311c4f8505aa854d3121f9837073f75f26`. Frozen delta codec is linked unchanged. Target load succeeds in the cached Python3.13.5/glibc2.34/zlib1.2.11 runtime, with zlib/m/pthread/c/loader only and no GLIBCXX dependency. [ELF/build receipt](raw/build/result.json). Compiler/header portable contents match the qualified original closure; original Linux metadata seal stays separate.

## Frozen execution and resource scope

[Freeze](freeze.json) predates compiled controls. Recipe SHA`43e4f0408efe3cb8308911f1b184db87a8cd322350f9051007ece526bc14bcea`,267host/254worker file bindings plus portable compiler/header receipts. Cached runtime/site/Expat only; no download/pull/install/network or source/sample mounts. Both actual workers use4GiB/zero swap/two CPUs/64PIDs/256MiB tmp/read-only root+inputs/64MiB files/1GiB writable+tmp;300s worker/600s host/570s work. Compiler alone gets SYS_CHROOT, cleared before scoped-env compiler execution under no-new-privileges; controls have no added capabilities.

Build/client0 and controls/client0, neither OOM. Owned cleanup and a separate exact-ID inspect prove both absent. [Independent cleanup](cleanup-audit.json). New projector visits9249 across tests/9276 including positive proof, below2million aggregate; legacy controls retain their separate bounded scopes. Process maxRSS59,932KiB is not cgroup/cloud/national peak. Host13.390140s includes input+compiler/header hashing, build, tests, synthetic proofs, startup and cleanup; it is not decode/import/search timing. Check197/typecheck/build pass.

The inherited `state.hashFramingBytesRead=0` is an unused legacy initialization, not an IO measurement. Per-scan receipts record564 framing bytes and source identity; post-scan SHA reads the full564 bytes again. Future performance must account for these separately, alongside proof, fast validation/index and lookup. Pending semantic batches on a failure do not constitute a complete-prefix seal; EOF stays false.

Closed ignored output `data/coarse-quality/us-osm-projector-v1/`:46files/3,159,367bytes.45small records/1,223,943bytes are mirrored unchanged under `raw/`; compiled `build/projector.so` stays ignored and checksum-bound. [Closed roster](closed-output.json). Every used producer is sealed: do not replay it as a health check or edit bound code to fix later results. Fresh clones lack ignored binary/tool assets and these uncommitted changes.

The following command was used once, for provenance only; **do not rerun**:

```sh
python3 -B scripts/run_osm_projector_v1.py docs/evidence/coarse-osm-projector-2026-10-27/execution-plan.json 43e4f0408efe3cb8308911f1b184db87a8cd322350f9051007ece526bc14bcea data/coarse-quality/us-osm-projector-v1
```

## Safe recovery and next action

Standard-library, read-only proof; no Docker/network/compiler/native/PBF execution or producer replay:

```sh
python3 -B docs/evidence/coarse-osm-projector-2026-10-27/verify.py
python3 -B docs/evidence/coarse-osm-projector-2026-10-27/verify.py --local-assets
```

Default verifies the sealed parent chain, all mirrored records, source/ABI/recipe/test/lifecycle bindings, full fields/coordinate bits/semantic seal and independently derived selected output. Local also hashes the closed ignored output, compiled binary and qualified compiler/header contents.253 cumulative implementation producers/49 prior sealed runs.

Next prepare a separately frozen fixed64k-prefix/re-encoded first1000-per-type equivalence and paired lookup/performance recipe. Bind source/code/artifact/guards/near-cap/callback/audit controls and exact IO/proof/fast timing scopes before execution. Do not read real samples or begin national scanning under this completed synthetic recipe. Necessary remaining guard gaps must be closed first. National maxID/storage/time, full21-window extraction, speed/access/matching, physical and83ORS/35Valhalla accuracy/package/startup/API/visual/model gates remain held. No extra provider/DB calls or live-map change. [Current ordered task](../../next-steps.md).
