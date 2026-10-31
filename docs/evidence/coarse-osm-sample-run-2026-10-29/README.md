# Fixed real-sample screen passes

October29,2026 local time; worker ran October30 at03:36UTC. **64,000 saved real nodes take median0.023119s versus1.112207s on the Python path:48.108× faster** in the frozen protected scope. The≤0.070s gate passes. All full fields, coordinate bits, index contents and paired lookup outputs agree. This qualifies the fixed node-prefix screen and re-encoded mixed-field equivalence, not countrywide extraction or map accuracy. V9/HEAD`648c731`/app/env/DB/npm/Vercel remain unchanged; work is local/uncommitted.

## Measured result

One exact execution of [the frozen preparation](../coarse-osm-sample-plan-2026-10-27/README.md), recipe SHA`7ef28e422a97604f43f19ba6960897b44260ec9fd81726fef5a439cd66a48723`. Same C++ artifact and V2 index/codec/full queried-shard integrity on both sides; no recompilation, data acquisition or national-source mount.

| Median over three paired prefix runs | Python | C++ block path |
| --- | ---: | ---: |
| Protected total,64k nodes |1.112207s|0.023119s|
| Decode/validate/index/seal/EOF+index.finish |1.107987s|0.018463s|
| Source framing/prehash |3.246ms|3.253ms|
| Full post-source hash/stat |0.392ms|0.389ms|
| Index size |579,134bytes|579,134bytes|
|1152 queries, cold application cache |14.825ms|14.585ms|
|1152 queries, warm cache |3.493ms|3.325ms|

Protected total includes case/watchdog/index setup, full framing/decompression/SHA/MD5/features/precision/state, PBF open/decode/metadata/index/semantic/normal EOF/index.finish, full post-source SHA/stat and output-file close. The separately measured loop excludes preceding framing/setup and posthash. Full-field/coordinate proof, lookup and watchdog teardown follow fast timing. Both formats preserve equivalent validation/output semantics; canonical-JSON hashes and the new binary field seal keep distinct names.

Native fast cases produce16 encoded blocks and **zero ordinary Python node-projection frames**. All six indices have identical complete manifest SHA`bd20cfb3ae4f031e80906caaed195312d927b5e8c2e3abdaa3e5b1e17131bf54`. A first-ID/cache-local query screen does not establish national random lookup behavior. Each query batch still authenticates full shards: cold application state reads1,156,352 shard bytes, warm/repeat578,176. Catalog/decoder/other IO is outside that named shard subtotal.755,072 guard bytes per prefix case are377,536 framing/prehash plus377,536 posthash, not an all-IO count. Lookup is broadly similar; the large gain is node validation/index handoff.

**Measurement limits:** the read-only parent local-asset proof was still running when the sample driver launched; exact overlap with timed cases was not measured. OS filesystem cache is uncontrolled. These are this shared-host run, not dedicated/cold-filesystem/cloud/national timings; no rerun or retuning was used. The preserved raw host timer name mentions controls, but this sample worker verifies prior74-test admission instead of rerunning that suite. The raw resource phase `controls` is a reused guard-helper label; actual recipe phase is `sample`. [Exact timing and IO interpretation](timing-scope.json).

## Independent field, coordinate and source proof

Saved377,536-byte prefix SHA`8c27122ee2321a320cf33c1f8c678fdd3041fee16621984380e768d4746d38b8` yields64,000nodes. Full Python/native raw-field files are byte-identical:9,071,329bytes/SHA`e845926261ab0fc4d7c1d8a904e08bbde01fd9e063b582d6537fc4cdd0a957b7`. The separately reconstructed `geo-planner-projected-fields-v1` semantic seal is`010895083c7843ac4f26b635e21e361bc585cbdf726d61e770c6659781083a95`. All64,000index signedXY32 rows and binary64 coordinate bits agree with the independent source projection. Source hashes/header/features/state/precision/calendar/order/copy/ref/member/byte/quota/normal EOF and post-source checks remain intact.

Saved first1000/type JSONL SHA`fd45e8844f790da058c708689548ee477382826d202ff06968d91db5ee1aee95` is re-encoded once without repairing references.3000JSON receipts+3000XML/native encoder views produce327,670-byte PBF SHA`26818b8f3e6ed5bc748e852110bfb647a7b7a73744f3a0232976843aa257ee84`, fixed publisher-state header/generator. Both projections reproduce the exact original3,304,488-byte raw-field file, preserving every way reference/relation member, including unresolved references. Semantic seal`529101b3926908ad51ce21f9a62dc0695e8aa8d0629d8b398543469d5644a140`; all1000node coordinate rows agree. This is re-encoded data, not original publisher PBF or dependency-complete roads.

Mixed **full-field proof** protected time0.179109→0.136052s includes Python projection/comparison/files; it is not a mixed fast/extraction speed result. Prefix full-field proof1.391122→0.659867s likewise stays separate from fast23ms processing. Prior synthetic selected-output/geometry/window membership/independent audit and adversarial controls remain qualified under their recorded74-test preparation; this run does not make a complete real-road extraction claim.

Actual524,000object receipts match the freeze:128,000prefix proof views+6000mixed proof views+6000encoding/JSON views+384,000paired prefix views. All cases reach normal EOF for their small input, never whole national-source EOF. Three native protected times0.023119/0.023217/0.022597s pass the exact median target and are faster than all three paired Python cases; no parameter sweep, source resampling or post-result threshold change. [Decision and held gates](decision.json).

## Resources, lifecycle and closed evidence

Worker/client0/not OOM; exact owned cleanup and a separate inspect confirm removal. [Independent audit](cleanup-audit.json). No worker remains; rediscover future owners. Actual4GiB zero swap/two CPUs/64PIDs/256MiB tmp/read-only root+inputs/network none/no added capabilities,64MiB files/32MiB indices/1GiB writable+tmp/60s hard cases/300s worker/600s host. Host7.747449s includes binding hashes/startup/re-encoding/all proof/case/lookup work/cleanup, not graph search or national import. No memory-peak measurement; hard resource enforcement is observed.

Closed ignored `data/coarse-quality/us-osm-sample-v2/`:75files/36,423,557bytes.39JSON/log/reference-index/coordinate records totaling1,921,786bytes are mirrored unchanged. Identical reference/native full-field files have separately named lossless gzip snapshots866,238+490,379bytes, with compressed and original byte/SHA bindings. Original XML/PBF, all indices and all measurements remain unchanged under the ignored root. [Exact closed roster](closed-output.json). The recovery proof independently compares every field/semantic seal/all65,000coordinate rows and query order/duplicates using the pure Python codec, never C++/PBF/producer execution.259 cumulative implementation producers/51 prior sealed runs; no old code/evidence changed.

Safe standard-library/read-only proof:

```sh
python3 -B docs/evidence/coarse-osm-sample-run-2026-10-29/verify.py
python3 -B docs/evidence/coarse-osm-sample-run-2026-10-29/verify.py --local-assets
```

Default checks mirrored records/lossless field snapshots/source+ABI+recipe bindings, independent fields/coordinate bits/index/lookup arithmetic, frozen performance gates and actual isolation/lifecycle. Local also hashes all closed ignored files and saved original inputs/tools through the parent chain. Existing74Linux controls and check197/typecheck/build remain bound to unchanged code; no app-code/test/build/DB replay was needed for this evidence-only closure.

The following command was used once, for provenance only; **do not replay** it as a health check:

```sh
python3 -B scripts/run_osm_sample_v2.py docs/evidence/coarse-osm-sample-plan-2026-10-27/sample-plan.json 7ef28e422a97604f43f19ba6960897b44260ec9fd81726fef5a439cd66a48723 data/coarse-quality/us-osm-sample-v2
```

## Next decision

The node path clears its small-sample throughput gate. Next specify one versioned, bounded countrywide feasibility/ID-range/storage and mixed-work/lookup screen before another national extraction. Reuse the saved national source/build tools, preserve source SHA/framing/global metadata/order/EOF/counter/canonical/callback/audit guards, and bind actual resource/byte/time/lookup scopes before execution. Current16MiB profile input and2million-per-call native bounds stay unchanged; a larger helper or budget requires new versioned implementation/controls/freeze, never bypassing these limits.

National maximum ID/global guard validity/allocated index footprint/mixed-work and nonlocal lookup cost remain unknown. Do not extrapolate the prefix's compression/ID maximum/48× gain to all1.606billion nodes/162.7million ways or call this a complete road dataset. No national/full-import/21-window/speed-access/matcher/physical/83ORS35Valhalla accuracy/package/startup/API/visual/model/Vercel admission. Provider budgets remain consumed, no DB/history/provider calls. [Current ordered next task](../../next-steps.md).
