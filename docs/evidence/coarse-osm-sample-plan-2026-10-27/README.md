# Fixed saved-sample test: preparation complete

Started October27, closed October29,2026. **74 actual Linux synthetic tests pass/no skips** with the existing compiled C++ helper; host51 pass/23 native skips. The corrected sample adapter and exact real-sample recipe are frozen. **No saved road sample was decoded/re-encoded or benchmarked in this preparation.** V9/HEAD`648c731`/app/env/DB/npm/Vercel are unchanged; new work is local/uncommitted.

## Decision and preserved correction

V1 adds a fair paired profile: frozen Python metadata validator versus C++ metadata/block handoff, using the same deltaV2 index/codec/full queried-shard authentication. It separates source-framing/hash, validation/index/semantic/EOF, full-field proof and lookup costs, and adds a separate60s watchdog process that kills a worker even without Python callbacks.71 Linux controls pass. A post-control code review nevertheless finds a counter omission: V1 charges only validated Python consume callbacks, so a metadata-rejected object disappears from partial counts/global visits. **V1 is not admitted for real samples.** Its three source files, freeze, raw output and all passing tests remain unchanged. [Preserved scope](v2-correction.json).

V2 uses pending native/reference receipt counters, clamps each scan to the remaining aggregate budget, and charges receipts in `finally`, including rejected objects. Partial reports separate received counts from validated projections; a refused cap+1 receipt remains a counted failure sentinel. New actual regression proves V1's version0 node reports0counts/0budget, while V2 Python/C++ both report1received/1budget/EOFfalse. Aggregate cap1 reports2received including sentinel and stops on both paths. Valid source/fields/index/lookup/IO behavior stays equal.

Three frozen V1 producers: [adapter](../../../scripts/coarse_osm_sample_v1.py), [tests](../../../scripts/coarse_osm_sample_v1_test.py), [runner](../../../scripts/run_osm_sample_v1.py). Three separate V2 producers: [corrected adapter](../../../scripts/coarse_osm_sample_v2.py), [regressions](../../../scripts/coarse_osm_sample_v2_test.py), [runner](../../../scripts/run_osm_sample_v2.py). Do not edit/replay any used control producer. No recompilation or target-runtime changes; existing1,935,424-byte artifact SHA`9227bc577f3592f167d614329ecc25311c4f8505aa854d3121f9837073f75f26` is reused and actually loaded. [Parent native projector proof](../coarse-osm-projector-2026-10-27/README.md).

New controls cover seeded XY extrema/float bits/near-cap ASCII-BMP-nonBMP boundaries, unknown wire types/members/reserved/count bounds/copy charges, full-field oracle refusal/source binding, source-posthash/immutability, matching source-IO scopes/index contents/lookup bits, mixed synthetic encoding with unresolved references, exact failure counters and a real subprocess-watchdog kill. The62 retained controls keep source/framing/EOF/callback/independent selected geometry/membership/audit and V2 unchanged-metadata cache protections. No guard is waived because mixed real samples may lack referenced nodes.

## Frozen future procedure

[Specification](sample-spec.json), [actual V2 control admission](control-acceptance-v2.json), [sample recipe](sample-plan.json), [sample freeze](sample-freeze.json). Recipe SHA`7ef28e422a97604f43f19ba6960897b44260ec9fd81726fef5a439cd66a48723`;279host/261common-worker/two exact sample bindings. This recipe has not run.

Only saved377,536-byte64k-node prefix and3,304,488-byte first1000/type JSONL are admitted, with their original saved hashes/counts/canonical field hashes. No national source mount, resampling or new acquisition. Mixed encoding uses exact raw projected fields, preserved order, fixed publisher-state header/generator and saved Pyosmium version; its canonical round-trip must match the original JSONL hash. It remains re-encoded data, not original publisher PBF or dependency-complete roads.

The future run first makes independent Python/reference and C++ full-field proofs for both inputs. Every canonical field line, all index XY rows/binary64 bits, metadata/counts/normal EOF/source identity/new semantic seal must agree. Python/reference proof directories are named `prefix-reference-proof` and `mixed-reference-proof`; native directories use `-native-proof`. The spec's Python labels name these reference cases. Old canonical-JSON and new length-prefixed field seals retain separate meanings. All six fast pairs must have identical complete index manifests with those proofs.

Three paired Python/native prefix repetitions run in the frozen interleaved order. Both use identical V2 index/storage/checksum policy; C++ fast mode must have zero ordinary Python node projections. Acceptance uses median **protected total≤0.070s and strictly faster than Python**; this is a target, not a measured result. Protected total includes case entry/watchdog setup/index setup/full framing+SHA/MD5/features/state/precision, PBF open/decode/metadata/index/semantic/normal EOF/index.finish and full post-source SHA/stat check. Separate loop/framing/post-hash scopes remain explicit. Full-field/coordinate proof and lookup run separately and never masquerade as fast timing.

Queries are the first1024 source node IDs from the reference proof, reversed plus128 duplicates:1152 queries, repeated cold application-cache/warm/repeat. Both paths authenticate full queried shards on every batch. Cold means decoded cache/format state, **not OS filesystem cache**. Report exact query-bit hashes and authenticated shard bytes; this first-ID/cache-local screen is not national lookup behavior. Planned object receipts524,000 include both raw JSON and XML encoder views, all reference/native proof views and all fast pair views; limit2million. An invalid/cap+1 receipt stops qualification and remains reported. Unknown pre-object decoder failures are not invented counts.

No selected real-road extraction or national performance claim follows. The unchanged synthetic independent selected-output audit remains required and passing; mixed first-per-type data preserves missing references without trying to reconstruct unavailable geometry. National maxID/allocated storage/time/full21-window/speed-access/matcher/physical/83ORS35Valhalla accuracy/package/startup/API/visual/model gates remain held even if the fixed sample screen passes.

## Actual controls, ownership and recovery

Both control workers/client exit0/not OOM, exact owned removal and separate inspect absence pass. [Independent audit](cleanup-audit.json). Neither had real source/sample mounts, network, compiler, added capabilities or writable inputs. Actual4GiB zero swap/two CPUs/64PIDs/256MiB tmp/read-only root;64MiB files/32MiB index/1GiB writable+tmp;300s worker/600s host/570s work. Future cases additionally have a separate60s hard watchdog; any hard stop leaves partial evidence and requires final worker exit/OOM/cleanup inspection.

V1 control recipe SHA`5b8642f5f95d42d2719194f29ae1077b28223263c9c07401798ca899cceca3d4`,271host/257worker bindings;9356 new-projector object visits. V2 control recipe SHA`3920d4043126efe046697a6903d0b3c2f06d234948c847bad66919b218d2d5c7`,275host/260worker bindings;9363 new-projector visits. Legacy controls retain original separately bounded scopes. V1 host2.177734s/V2host4.505429s include binding hashes/startup/synthetic tests/cleanup, not import/graph-search time. No process/cgroup peak-memory measurement. App check197/typecheck/build pass for unchanged app source.

Ignored closed outputs: `data/coarse-quality/us-osm-sample-controls-v1/`12files/133,356bytes and `us-osm-sample-controls-v2/`12files/135,726bytes; all mirrored unchanged as `v1-raw/` and `v2-raw/`. Original code/recipe/output and the prefreeze refusal of an unnecessary inherited asset-proof mount remain preserved. No worker remains; rediscover future owners rather than reusing old PIDs/session IDs. Fresh clones lack these uncommitted files and ignored artifact/tool assets.

Safe proof, Python standard library/read-only, no Docker/native/PBF/network/compiler or producer replay:

```sh
python3 -B docs/evidence/coarse-osm-sample-plan-2026-10-27/verify.py
python3 -B docs/evidence/coarse-osm-sample-plan-2026-10-27/verify.py --local-assets
```

259 cumulative implementation producers/50 prior sealed runs. Default checks the sealed parent chain, every mirrored record, both freeze/code/ABI/control/lifecycle bindings and prospective sample recipe/admission. Local hashes ignored closed control outputs and reused artifact/tools; it does not decode real samples. No cloud/provider/DB/history write or configuration change.

## Exact next command

The following command is **frozen and not yet used**. It is the next task, not a readiness check. It requires Docker/cached runtime/site/Expat/compiled artifact, all bound local code and both existing saved samples. It refuses an existing output; do not retry/rename to bypass a failed run.

```sh
python3 -B scripts/run_osm_sample_v2.py docs/evidence/coarse-osm-sample-plan-2026-10-27/sample-plan.json 7ef28e422a97604f43f19ba6960897b44260ec9fd81726fef5a439cd66a48723 data/coarse-quality/us-osm-sample-v2
```

Outputs are under the exact new root's `sample/` worker directory. Preserve all partial/final files, actual error/normal exit/OOM and independently verified removal. First classify equivalence; any mismatch stops performance/national admission. If equivalent but slower/over70ms, preserve that failed screen without retuning/repeating. Only measured fixed-sample scope may pass; no source/global/full-import/model deployment is activated by this command. [Current next steps](../../next-steps.md).
