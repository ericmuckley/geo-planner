# Typed node-ID lookup prototype and saved-query replay

October30,2026. **Six actual Linux controls/no skips and the400-coordinate native proof pass. The frozen replay passed and is closed.** No national source read, new index allocation or model change.

The [completed batching measurement](../coarse-osm-way-batch-2026-10-30/README.md) provides135immutable batches/2,135,008reference/coordinate witnesses plus the independently checked readonly eight-shard probe. Native lookup took32.627s, including per-batch full-shard authentication, format checks and decoding. The current Python search repeatedly unpacks directory entries during binary search. The new reader caches only checked block-end IDs in a typed array and uses standard-library C bisect for both directory and decoded-block searches. Snapshot/catalog/cache/format/whole-shard validation and coordinate arithmetic stay inherited unchanged.

The three qualified reader/test/replay-runner producers are USED/immutable. Six host controls pass: signed63edges/gaps/duplicates/bit equality, identical baseline IO/cache sequence across>64blocks, same-metadata warmed-shard drift, cached-key catalog drift, unchanged IO guard and the complete392,146-entry national catalog without shard allocation. The full typed search table is3,137,168bytes<4MiB; probe table32,400bytes. Those are search-key allocations, not full index/graph memory. No national PBF read or routing/provider call.

The qualified runner uses the already saved witnesses. Its exactly four frozen full ordered cases are:old/new/new/old, each with a fresh application cache and unchanged full-shard integrity. Require every saved coordinate bit/order/duplicate and identical IO/row/cache accounting. Proposed performance admission: mean new points() time<=90% of old mean, complete-case mean no worse, unchanged4GiB RAM/1GiB owned limits. No alternate factors, query top-up or post-result retuning. OS cache remains uncontrolled; results describe these saved development queries, not national routing performance.

No national source mount or full-source read is needed. Complete extraction, road semantics/attributes/50%usable-limit/matching/physical/accuracy/package/API/model gates remain separate.

## Qualified runner and completed replay recovery

Qualification [freeze](controls-freeze.json)/recipeSHA`f7e12676f24eeabf672b06110b030378cbef184ee44f23b9f131a45501b48fbd` is USED/passed/closed at`data/coarse-quality/us-osm-lookup-v3-controls/`. Six actual Linux tests/no skips and all400native-coordinate occurrences pass, with equal old/new IO/cache/row/call accounting.13closed files/112,622bytes mirrored unchanged. Worker/client0/not OOM/independently absent, host1.674s covers bindings/tests/tiny proofs/lifecycle. [Read-only qualification proof](verify_controls.py) passes. Parent's checksum-bound documentation-link count typo is corrected separately in [this scope note](parent-link-check-correction.json), leaving original evidence intact.

Replay [freeze](replay-freeze.json)/recipeSHA`e60b9b81e307f8241b38a1405e0864a4c71594101175f71d9a0fd209c7b8b1c6` is **USED, passed and closed** at`data/coarse-quality/us-osm-lookup-v3-run/`. All three producer files are immutable. Inspect owned`owner.json`, actual exact process/container ownership,`case-*.json`, final result/cleanup records. Never replay, rename, retune, change cases or overwrite existing output. The national PBF is not mounted/read; only saved witnesses, readonly probe, tiny fixture/catalogs, code and existing cached tools/artifact are inputs.

Caps: old/new/new/old,135batches/2,135,008refs each;180s complete protected case/900s worker/1200s host,80million decoded rows/20kcalls/12GiB authenticated shard IO each. Four cases imply at most320million rows/80kcalls/48GiB probe IO. Same4GiB zero-swap/twoCPU/read-only/no-network/no added capability/1GiB owned+tmp/64MiB files/1024entries. Required mean new points()<=90%old and complete-case mean no worse; coordinate bits/order/duplicates and all integrity/cache/row/call counters must agree. Startup, complete-case and points() times remain distinct; OS cache uncontrolled. App check197/typecheck/build pass before replay, with no concurrent producer/app check scheduled during timed cases.

```sh
python3 -B docs/evidence/coarse-osm-lookup-2026-10-30/verify_controls.py
```

No full index allocation, national road extraction, source suitability, model/accuracy/package/deploy admission follows from the replay alone. Continue from its measured result toward one bounded complete extraction design; keep all original gates and failures intact.

## Closed replay result

Both gates pass. points() old30.685445/30.854449s (mean30.769947) versus new24.515440/24.945945s (mean24.730693):19.627%lower on these fixed saved queries. Complete-case means31.564906→25.524386s, including setup through case-record close, excluding close-footer serialization. All8,540,032coordinate occurrences/order/duplicates agree with the independently verified saved witnesses. Per-case authenticated shard IO9,460,848,817bytes,69,544,680decoded rows/16,979calls, catalog IO/cache hits/misses/evictions are identical. Total probe IO37,843,395,268bytes and278,178,720decoded rows across four cases; no source PBF read. No national routing/cold-cloud or quiet-host extrapolation.

Worker/client0/not OOM/owned removal/separate exact absence pass. Host115.767673s includes bindings/startup/four cases/cleanup, excluding its own final summary serialization. Cgroup peak338,923,520bytes; oom/oom_kill0. Conservative observed output allocation1,363,968bytes, allocated192,512/logical148,833 at the final worker snapshot, excluding final metrics/host journals. Closed19files/150,688bytes mirrored unchanged. Kernel process rchar38,358,764,885/wchar4261/read_bytes0/write_bytes4261 are separate IO scopes; zero read_bytes does not mean zero input reads.

[Independent replay proof](verify_replay.py) passes default and local-input/reference-witness modes. No native execution, source producer, national PBF read or provider call is needed. Source/model/accuracy gates remain separate. All three producers/used recipes/raw records remain immutable. App check197/typecheck/build pass.

```sh
python3 -B docs/evidence/coarse-osm-lookup-2026-10-30/verify_replay.py
python3 -B docs/evidence/coarse-osm-lookup-2026-10-30/verify_replay.py --local-assets
```

Next: [one complete extraction prototype](../coarse-osm-extraction-2026-10-30/README.md), with generic all-highway batches, selected metadata and independent dependency-complete output/audit. No full national index allocation is admitted by this replay alone.
