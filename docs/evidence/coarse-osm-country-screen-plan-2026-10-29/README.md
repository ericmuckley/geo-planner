# Countrywide feasibility screen: bounded plan

October 29, 2026. **Planning is complete; implementation and execution are pending.** The next task is a versioned native summary helper and synthetic qualification. No national file was read, decoded or rehashed for this plan; no compiler, container, index producer, provider or database was used. The app and deployed v9 are unchanged. Everything added here is local/uncommitted.

The proposed test reads the saved national source twice, validates every object, and computes the bytes a complete lossless node index would need. It writes only eight fixed portions of that index. That separates the national ID/metadata/byte question from the cost of allocating a full index, while providing a bounded test of wider-ranging lookups and actual highway references. It does not extract roads for the app or qualify national routing accuracy.

## Why this test

[The measured sample](../coarse-osm-sample-run-2026-10-29/README.md) processes 64,000 nodes in a protected median 0.023119 s versus 1.112207 s (48.108×). Fields, coordinates and indices agree. That removes the demonstrated per-node Python bottleneck on that prefix. The timing includes framing and pre/post hashes; proof and lookup are separate. Mixed full-field checks are not a mixed fast-processing benchmark, and the first-ID lookup is cache-local. Shared-host overlap and uncontrolled OS cache remain limitations of that measurement. None of its speed, maximum IDs or bytes/row are national forecasts.

The [complete count inventory](../coarse-osm-inventory-2026-10-27/README.md) saw 1,606,229,364 nodes, 162,688,797 ways and 1,624,265 relations at normal decoder EOF. Its count loop took 1,260.770 s. It did not validate all metadata or establish maximum IDs/unique order. The old full import stopped after 14,340 s; its untrusted 8,783,028,224-byte index stays preserved. Neither experiment may be resumed or replayed.

## Fixed phases and retained evidence

The detailed prospective contract is [screen-plan.json](screen-plan.json), with a [guard map](guard-map.json), [existing bindings](bindings.json) and [reproducible arithmetic](resource-arithmetic.json). This is a design, **not an executable frozen recipe**.

1. **Preflight:** bind the saved source, candidate code/artifact, actual target controls, cached runtime/compiler/headers and new exclusive output. Verify current capacity and real isolation. Do not run other producers or asset proofs concurrently. Source: `data/coarse-quality/us-osm-input-v3/download/http/001.bin`, 12,229,320,016 bytes, SHA `1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff`, state `2026-10-25T21:21:21Z`. Use this saved file; no acquisition.
2. **Pass A:** full framing/decompression/prehash/MD5/state checks, continuous native metadata/order/ID validation of all three types, GPF1 semantic seal, exact encoded-byte census and normal EOF, then full posthash/stable-file checks. Roundtrip every node block through the frozen C codec against original source ID/XY arrays. Retain only eight complete source-ordinal shards, global directory/catalog, summary and bounded way trace.
3. **Pass B:** rebuild from the same source with all guards again. Match global summaries/seals and independently source-build the eight retained shards. Compare and authenticate each primary shard before removing its exact owned predecessor. Capture query ID/XY witnesses directly from this source pass. Final count/source/metadata/EOF/census/trace/witness equality is mandatory. Two passes through the same validator prove rebuild consistency; they are not an independent national metadata oracle.
4. **Lookup and close:** after both passes succeed, run the fixed cohorts below through the unchanged V2 full-shard authentication policy. Compare every coordinate bit, order and duplicate to the pass-B source witnesses. Independently decode the retained probe with the frozen Python reference codec, audit arithmetic/receipts, close allocation/time/IO/memory evidence, record exit/OOM, remove only the owned worker and independently prove its absence. No model promotion.

All 1,770,542,426 objects/pass must validate before filtering. Received failures and the first cap+1 sentinel count; decoder-unknown objects stay unknown. The new helper must use checked 64-bit counters, including the 3,541,084,852 accepted objects across both passes, bytes, references and codec work. State and ID order never reset inside a pass. Native EOF alone cannot override a framing, posthash or output failure.

The existing 16 MiB profile-input and two-million-object helper caps stay unchanged. New versioned C++/Python/runner/test files must support a summary mode that validates/seals all ways and relations without ordinary Python object dictionaries or JSON. Preserve exact canonical fallback, callback errors, source guards and independent controls. Semantic batches remain bounded; do not remove metadata or hashing to improve timing. Checkpoints change only in the new helper to every 65,536 objects plus final; a separate hard watchdog covers blocked callbacks and source IO.

## The eight-shard probe

The full node census has 392,146 blocks and 766 shards at the frozen 4,096 rows/block and 512 blocks/shard. Retain source shards **0, 109, 218, 327, 437, 546, 655, 765**, using `floor(k * (766 - 1) / 7)`. This selects 4,050 blocks/16,588,148 nodes without geographic rules. The last shard has 466 blocks/1,908,084 rows. Never replace these choices after seeing results.

Original block boundaries, payloads, IDs and XY stay exact. The mini-index renumbers its shard/directory entries and dependent header seals, with an explicit mapping to original ordinals. Each pass must produce identical mini-index files. At most eight retained shards plus one replacement coexist. No other national shard is written. The global directory/catalog describe the would-be whole index and are separate from the mini-index.

The way trace retains up to 128 highway ways with 2–1,024 references, all IDs within the eight shards' numeric ranges. The fixed SplitMix64 priority/seed and tie order are in the plan and arithmetic code. Validate all ways first. Numeric range membership is only eligibility: every selected reference must later have exactly one source witness. Fewer than 64 eligible ways or a missing dependency stops this subgate as insufficient/failure, without top-ups. Record exclusions and reference/member/canonical/fallback processing costs for all objects, including those discarded.

Three fixed cohorts each run cold-application, warm and repeat:

| Cohort | Query rule | Purpose |
| --- | --- | --- |
| Local | First 1,024 IDs reversed, then 128 duplicates | Compare with the original cache-local test |
| Spread | First ID of all 4,050 retained blocks, round-robin across shards, then 128 duplicates | Exercise eight ID ranges and exceed the 64-block cache |
| Highway references | Fixed selected ways in priority order, references in original order, at most 131,072 occurrences | Measure real range-eligible road references, with duplicates |

Use batches of at most 65,536 IDs. Clear application cache and format-validation state only before each cohort. Authenticate each whole queried shard every batch, including warm cache hits; first access also validates the full format. No OS page-cache flush or OS-cold claim. The source-witness union is at most 136,146 IDs (2,178,336 typed row bytes). Lookup coverage remains a selected ID/way probe, not a representative national routing distribution. Full road dependency extraction stays separate.

## Proposed limits, not measured performance

| Resource | Proposed hard bound / reservation |
| --- | --- |
| Execution | 4 GiB RAM, zero swap, 2 CPUs, 64 PIDs; network none, no added capabilities, read-only root/inputs |
| Owned writable space including tmp | 1 GiB; arithmetic reservation 796,123,776 bytes; tmp 256 MiB |
| Files | 64 MiB each; at most 1,024 file/directory entries |
| Probe index | 384 MiB aggregate each; 4 MiB per directory/catalog; maximum shard 35,679,872 bytes |
| Global summaries | 16 MiB directory + 4 MiB catalog per pass; directory needs 12,548,800 bytes |
| Time | 3,000 s each protected source pass; lookup 300 s; other worker work 600 s; worker 7,200 s; host 7,800 s |
| Source hash / cleanup | Host binding-hash cap 240 s; cleanup 60 s; remaining host margin covers startup/administration |
| Lookup IO | At most 4 GiB authenticated-shard reads; conservative fixed-cohort bound 3,282,548,224 bytes |
| Lookup native codec | At most 256 million decoded rows/100,000 calls; each decode remains at most 4,096 rows |
| All preserved assets + proposed work | Reservation 39,885,283,431 bytes inside the existing 64 GiB envelope; fresh capacity checks required |

The exact frozen payload maximum is 69,623 bytes, so `128 + 512 * (64 + 69623) = 35,679,872` bytes/shard. The older design's 35,684,480-byte shard expression was a conservative bound. Its original 32 MiB small-experiment index cap is insufficient for a worst-case full shard; this new proposal explicitly separates a 384 MiB aggregate probe budget and 64 MiB file limit. It changes no used recipe or producer.

The 1 GiB owned-work proposal covers nine worst-case shards, both mini-index sidecar pairs, both global directory/catalog pairs, traces/witnesses/logs/receipts, scratch and tmp, plus explicit 4 KiB rounding/8 KiB namespace reserves per entry and a further reserve. Retained-source/failed-index/runtime/build/small-output reservations carry forward; the latest 36 MB sample is within the earlier 1 GiB small-output reservation. These are conservative accounting allowances, not a current host-allocation measurement. Never delete prior assets to make capacity pass. Future execution must measure logical/allocated peaks, namespace and writable/tmp usage, and stop if the required accounting is unavailable.

Memory reservations sum to 1,344 MiB before the remaining 4 GiB headroom: queues/decompression 512, Python/runtime 256, writer/snapshot copies 256, native semantic/metadata frames 128, trace/witness selection 64, directories/catalog/cache 64 and logs/metrics 64. They are not proven peaks. Use an explicit libosmium `Pool(2, 2)`, input/output queue sizes 2, and retain metadata. The selected saved headers bind those options. Measure actual cgroup current/peak/events, CPU/process IO, and OOM; process `ru_maxrss` is insufficient.

The time ceilings are administrative stop limits, not predictions. The count-only 1,260.770 s result justifies a bounded larger screen after the sample gain; all metadata/mixed/semantic/roundtrip costs remain unknown. Two 3,000 s passes plus 300 s lookup and 600 s other work total 6,900 s, below the worker limit. The host limit leaves 600 s beyond that worker limit for binding hashes, startup and cleanup. Do not multiply the 48× sample gain into an admitted runtime forecast.

Two full preframing/prehash and posthash pairs read exactly **48,917,280,064 source guard bytes** if complete. That excludes host binding hashes, native decoder reads, index/output/audit/lookup IO and kernel physical IO. Record those scopes separately. Type spans/checkpoints include shared decoding/sealing work; do not call a way/relation span pure parsing time. Reference audit reads the probe once per shard and streams bounded block decoding; do not repeatedly call per-block V2 snapshots and mislabel that extra IO as lookup cost.

## Acceptance and held gates

The planning task passes with the sealed proposal, reproducible arithmetic, guard mapping, prior proof and current-document updates. There is **no national execution admission** in this report.

Future synthetic qualification must prove full-field/GPF1/reference equivalence, discarded metadata validation, exact fallback/cap+1 counters, 64-bit rollover rejection, source/EOF/callback failures, summary suppression, census vs fully written tiny reference, nonadjacent remapping/partial final blocks, fixed selection/witness bits, >64-block cache behavior, same-mtime drift detection, bounded resource enforcement and exact ownership/cleanup. Actual target Linux controls must have no native skips. Freeze candidate code/artifact and bounded controls before qualification; freeze the larger execution recipe only after qualification passes. [The detailed controls and proposed command contract](screen-plan.json) distinguish unavailable future commands from safe commands that work today.

Future screen success requires both guarded whole EOFs, exact recorded counts, matching summaries/metadata/seals/indices/trace/witnesses, the minimum trace coverage, all fixed lookup results and all resource/time/exit/OOM/cleanup checks. Separately apply 1.5× margins plus filesystem reserves to exact whole-index logical bytes and retained working assets against the 24 GiB/index and 64 GiB total envelopes. Also report the conservative monotone-ID varint bound using the **measured** national maximum ID. Allocation of a national index is still unmeasured even when those arithmetic screens pass. A completed scan with a failed storage/resource/trace subgate is not an overall pass.

The positive signed63 format domain stays intact. The old illustrative `2**40-1` ID assumption conditionally fits; the full signed63 storage bound does not. The new arithmetic includes namespace reserves absent from the earlier conditional example, so its figures are deliberately distinct. No real maximum ID is asserted here.

No full national index, 21-window extraction, publisher boundary, usable speed/access dataset, matcher, physical route, new policy, 83 ORS/35 Valhalla accuracy, packaging/startup/API/visual gate or model switch is admitted. V9 arbitrary-origin routing rules, app, env, cloud PostgreSQL, npm and Vercel stay unchanged. Native tools and raw OSM stay offline; Vercel continues serving the compact TypeScript model. No provider budget is spent.

## Safe recovery and next action

From the repository root, standard library only:

```sh
python3 -B docs/evidence/coarse-osm-country-screen-plan-2026-10-29/resource_arithmetic.py
python3 -B docs/evidence/coarse-osm-country-screen-plan-2026-10-29/verify.py
python3 -B docs/evidence/coarse-osm-country-screen-plan-2026-10-29/verify.py --local-headers
```

The default proof checks the plan/bindings/arithmetic and prior sealed sample chain without Docker, native execution, PBF decoding or national-source reads. The optional flag hashes only three saved libosmium headers. It does not prove all ignored assets are present; use the preceding sample proof's `--local-assets` separately when needed, outside future timing. Do not rerun completed producers for recovery.

**Next:** implement the four new versioned files, close the synthetic controls and actual target build/ABI qualification, run applicable code checks, and record their independent proof. No national source mount or decoding in that next task. Only then prepare a separate exact, unused execution freeze for one future screen. The existing sample recipe stays USED; preserve every source, failed index, signed record and prior measurement.
