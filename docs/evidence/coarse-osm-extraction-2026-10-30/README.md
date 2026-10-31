# Complete road extraction and bounded national capture

October 30,2026. **Lossless format/prefix and new controller pass; national capacity census V2 passes and complete filtered capture stopped at its250kselected guard.** V9 remains unchanged. This is offline raw input preparation, with no measured map/accuracy improvement. [Prior typed lookup result](../coarse-osm-lookup-2026-10-30/README.md).

<a id="latest-national-result-and-safe-recovery"></a>

## Preserved full-extraction stop and safe recovery

The [V2national recipe](full-plan-run-v2.json), SHA`0c0765c20786bf5ed4a69df94722d705d3b43be399dd2d26be938ab9a18f5f28`, was used once. [Freeze](full-freeze-run-v2.json). It is **stopped/closed**, worker independently absent. Never replay/edit used producers/recipes or resume/repair/delete the stopped index. Root`data/coarse-quality/us-osm-full-extract-run-v2/` retains all766payloads; [closed roster](full-closed-run-v2.json) mirrors the32small records here. No full source EOF/output/independent second pass or raw-capture qualification.

The [operator stop request](operator-stop-request-v2.json) records an early engineering feasibility decision: the complete first node index was built, but the observed road throughput was impractical. Last checkpoint1,606,229,364nodes/123,727ways,0.0761%of162,688,797source ways. This is **not a measured wall/IO-cap failure or a proven whole-source runtime forecast**. [Stop](full-stop-v2.json), [independent absence](full-cleanup-run-v2.json). Host1346.536440seconds including source binding20.039778seconds and cleanup; no graph-search timing. Worker137/not OOM; no kernel peak was closed after the hard stop. Observed live Docker memory183MiB excludes cache and is not a cgroup peak.

Closed798files/14,503,551,785bytes; conservative physical allocation14,512,766,976bytes. Full first node index766shards/14,503,453,128logical bytes and catalog all match the earlier source-built census. This establishes physical first-index bytes, not complete extraction/trusted failed output. Old source/failedSQLite/V1partial/V2full bytes remain untouched. Safe [saved proof](verify_full_run_v2.py):

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_full_run_v2.py
```

Optional`--local-assets` hashes only closed derived files (14.5GB), never the source/native/Docker. Closure already hashed every payload. Do not repeat just to validate documentation.

The source is the saved 12,229,320,016 byte national PBF, unchanged SHA`1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff`. The plan pins all 1,770,542,426 source objects, complete semantic seal and 52,053,199 highway ways per pass. Every newly written shard/catalog must match the sealed source-built census. All 766 shards and the 14,503,453,128-byte full index were physically built in V2 before road lookup. Each write matched the frozen census. This is a completed first-index phase in an otherwise stopped attempt; no second pass/output qualification.

Limits:14400 seconds including setup/binding/cleanup,13800 worker/6900 each pass;4 GiB RAM/zero swap/two CPU/network none/read-only inputs;64 GiB retained work, including 38,811,541,607 reserved retained bytes and 256 MiB tmp;24 GiB/index,128 MiB output-file/64 MiB index-file,4096 names.4 TiB authenticated shard IO per pass and 48 billion aggregate codec rows/12 million calls are finite ceilings, not allocations or performance forecasts. Selected 250 k unique/500 k window occurrences,64 MiB serialized retention/256 MiB selection heap,128 MiB output/1 MiB records remain. Same 21 original validation windows. Old failed 8.78 GB SQLite index/source/probes/witnesses remain untouched.

Success requires two normal-EOF/count/metadata/semantic/source passes, every highway's full geometry including long/outside-probe references, physical full-index/guarded independent rebuild/rotation, independent window membership and full-field materialization, exact output audit, complete acquired-file-only window ledgers and resource/lifecycle closure. Missing geometry stops. Raw restrictions preserve roles/conditions/unresolved external refs; recursive relation dependency repair is not claimed. Publisher clipping/source suitability, source adapter/usable speed limits/matching, physical/accuracy/package/API/model admission remain separate.

## Qualified complete prototype

V6 ABI `0x50000` adds generic all-highway batches, selected node metadata and raw restriction delivery while preserving all-source metadata/typed-ID/order/UTF8/copy/canonical/semantic/coordinate/reference/member/hash/EOF guards.32768 ways is the ceiling implied by 65536 references and at least 2 refs/way;8 MiB batch bytes and 4 MiB source validation remain. Selected output 1 MiB is separate. Partial way batches flush before restrictions. Every highway's full geometry is looked up before separate primary/audit bounding-envelope and clipping predicates; both-endpoints-outside crossings/touches remain selected.

First [V6 freeze](qualification-freeze.json) passed 258/259 Linux tests and stopped on a harness assertion about the final lexically sorted object type, after reference byte equality passed. Failure preserved. The exact compiled library is 2,003,688 bytes/SHA`1084fc1b6e9b1a627b52180fd91df0b46e01a967fbd399c2bad672a4f675f48a`, at`data/coarse-quality/us-osm-country-controls-v6/build/country-screen.so`. [V7 freeze](qualification-freeze-v7.json) corrects only that test assertion;259 actual Linux/no skips and persistent complete two-pass/four-pass reference proof passed. The earlier mistyped CLI hash was rejected before output/worker/source activity and remains recorded in`rejected-cli-hash.json`.

[V8 freeze](qualification-freeze-v8.json) separates 128 MiB transient rows/keys/points heap from unchanged 64 MiB selected serialized retention. A valid 32768 way/65536 ref batch fits 8 MiB wire but exceeded the mistakenly reused old 64 MiB threshold. New control measures 78,079,432 conservative recursive heap bytes, zero selected records; shared objects can be counted repeatedly, so this is not RSS.260 actual Linux controls/no skips and persistent independent output pass. V8 closed 61 files/620,149 bytes; host 26.6443 seconds;0/not OOM/independently absent. All V6/V7/V8 producers/recipes/raw records are used/immutable.

The tiny full output is 1470 bytes/SHA`dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c`,4 unique/8 window occurrences/18 source visits versus 36 four-pass reference views. Full raw fields/access/conditions/unresolved restrictions match; all 4 index coordinates independently verified. These are synthetic results, not nationwide/source accuracy.

## Qualified full controller

[Controller freeze](full-freeze-controls-v1.json)/[recipe](full-plan-controls-v1.json), SHA`fcfd58177e3da75a6b92d910f8d668d599b34f0bee2b8e023f70b3c70384a599`, and all 4 new producers are USED/immutable.14 actual Linux controls/no skips and real tiny two-pass execution pass with the national 2×aggregate allowance configured and each native call clamped to one source's maximum. Actual visits remain 18. Source/census-bound physical writes, guarded removal/rebuild, all coordinates, exact independent output, negative guards and lifecycle pass. Closed 24 files/112,946 bytes; host 1.753324 seconds; protected tiny extraction 0.049506 seconds; cgroup peak 48,480,256 bytes/not OOM; worker independently absent. [Admission](full-admission-v1.json), [closed roster](full-closed-controls-v1.json), [independent absence](full-cleanup-controls-v1.json).

Safe checks verify saved evidence without Docker/native/national source reads or producer execution:

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_qualification_v8.py
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_full_controls_v1.py
```

These cover their named synthetic/controller stages; the stopped national proof above is separate. All prior closed source/batching/lookup evidence remains sealed and unchanged. Local scripts/evidence/docs are uncommitted; source/tools/binaries remain ignored and absent from a fresh clone. No new env variable, DB dependency, provider call, download, app/Vercel change or model switch.

## Preserved national V1 monitor stop and V2 correction

V1 stopped early because the concurrent host monitor used multiple metadata probes on a progress file that was atomically renamed. [Exact stop](full-stop-v1.json), [closed roster](full-closed-run-v1.json), [absence](full-cleanup-run-v1.json). Last checkpoint 6,291,456 nodes;3 partial source-census-matching shards/56,725,840 bytes; total 18 files/56,819,201 bytes. No EOF or complete index/output; all derived bytes remain untrusted/preserved. Host 122.411059 seconds; source binding 20.124292 seconds; worker killed 137/not OOM, independently absent. No source fault or routing change established.

V2 uses one`lstat` per host entry, tolerating only concurrently missing non-root paths; special/symlink/hardlink/type/physical-accounting guards remain. Worker index-write bounds and all extraction/resource/selection rules are unchanged. New [qualification recipe](full-plan-controls-v2.json)/[freeze](full-freeze-controls-v2.json), SHA`cafc97545aa18c67422951e154443e84c4d2b1357f521099fec216d026c182bf`, passes 19 actual Linux tests/no skips, including exact old-failure reproduction and rename correction, plus complete tiny index/rebuild/independent output. Closed 24 files/116,482 bytes; host 1.663537 seconds; cgroup peak 48,074,752 bytes;0/not OOM/independently absent. [V2 admission](full-admission-v2.json), [roster](full-closed-controls-v2.json), [absence](full-cleanup-controls-v2.json). All new producers/recipes used/immutable.

Newest safe proof (also validates prior V1/prototype/stop evidence):

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_full_controls_v2.py
```

The V2national run was separately versioned with unchanged extraction/window/resource caps. It is now stopped/closed as recorded above; no successful national capture/output. Preserve all V1/V2bytes; do not restart either used output.

## Qualified native cell codec and filtered extraction

[V9freeze](qualification-freeze-v9.json)/[recipe](qualification-plan-v9.json), SHA`17a02f6fdf5bcd774c0b8532420a6096ece2927c9076c42f1d014addd73b308a`, are USED/passed/closed.276actual Linux controls/no skips include all7225cell classes,10,000arbitrary paths against both clippers and native full signed63-bit IDs/canonical runs/hash/ABI/missing-reference/cap/buffer cases. Closed80files/3,731,377bytes; host32.017263seconds; build/control kernel peaks455,823,360/296,607,744bytes; workers0/not OOM/independently absent. The83byte native block matches independent encoding,4source nodes and ordered/duplicate queries. [V9proof](verify_qualification_v9.py).

[V10freeze](qualification-freeze-v10.json)/[recipe](qualification-plan-v10.json), SHA`80948413cb67d51001dfc77a9a199a92f249efd069cc584140c638525cac11d2`, add immutable bank, separate native primary-table/audit-half-plane masks and complete filtered extraction. **304actual Linux controls/no skips pass.** The complete1470byte output matches the frozen four-pass reference exactly:4unique objects/8window occurrences/18source visits. All4road references resolve;2need fine coordinates and one outside way is certified rejected per pass. Tiny fine-shard bytes read remain454per pass; fewer queried references is not a national IO/speed measurement. Source metadata/access/conditions/raw unresolved restrictions remain unchanged. Fine-reader per-batch full-shard authentication/exact geometry is unchanged.

V10closed95files/3,792,620bytes; host33.827068seconds; build/control kernel peaks456,687,616/325,099,520bytes; workers0/not OOM/independently absent. Positive bank578bytes per pass,1block/4nodes; codec40rows/10calls and masks8refs/2calls across both passes. Bank snapshots are immutable in memory; on-disk changes cannot alter answers and fail mandatory close verification. Missing references fail before rejection, including outside roads. Primary-table corruption cannot suppress the independent audit. These are tiny semantic results; national size/RAM/time/capture remains unqualified.

Compiled V10library`data/coarse-quality/us-osm-country-controls-v10/build/country-screen.so`,2,004,312bytes/SHA`a84d4641026dbe250fd13f8e098082ac2ba7987bf54b9e63ff5d1126d94bee38`; country V6/delta/cell codec sources unchanged, new masks ABI`0x10000`. [Closed roster](qualification-closed-v10.json), [absence](cleanup-audit-v10.json), [safe independent proof](verify_qualification_v10.py). All used V9/V10producers/recipes/results are immutable.

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_qualification_v10.py
```

No native/Docker/national source/index reads in this saved proof; it also verifies prior stages and stopped attempts.

## Preceding read-only qualification and reporter correction

[V11freeze](qualification-freeze-v11.json)/[recipe](qualification-plan-v11.json), SHA`e1f3c6f123d20a961b4c2c56340a20834b9195f41244d7608348b00b01023d70`, are USED/stopped/closed at`data/coarse-quality/us-osm-country-controls-v11/`. Inspect owner/controls/results before acting; never replay/edit used files. Exact V10library reused,All38targeted tests/no skips and persistent tiny four-pass output/input preservation passed; final reporter then stopped on an int/list variable collision. V12corrects only that wrapper and passes; see latest proof above. No national source/stopped index mounted/read. All4new producers are immutable.

The adapter compares every fresh source-built node block with expected-census-bound fine bytes, native decode/ID/coordinate/order checks, whole-shard/header/table/source equality and before/after/end hashes. It writes/removes/repairs nothing. **Node comparison alone cannot qualify source EOF**; a new caller must still prove complete native source/count/semantic and independent output. This qualification uses tiny generated inputs, never the stopped national index. Future use remains a new admission, with old failed evidence unchanged.

<a id="next-bounded-measurement"></a>

## Preceding capacity proposal

This proposal preceded the V12correction, V1bank-cap stop and V2lossless continuation below. It called for a separate national cell-bank capacity census, not full road capture. Two complete summary/source passes/read-only fine block verification/independent compact bank rebuild plus fixed source-derived membership/coordinate witnesses must reconcile. Prospective bank<=2GiB, one resident snapshot at a time,4GiB zero swap/four-hour/64GiB retained work remain. No capacity/speed forecast from tiny results.

Original retained reservation38,811,541,607plus new stopped full-run conservative14,512,766,976=53,324,308,583bytes; after256MiB tmp, new owned work<=15,126,732,697bytes. Do not allocate another full fine index under old arithmetic. Keep all original21windows/selected-output/source/boundary/attributes/matching/physical/accuracy/package/API/model gates. Complete filtered capture needs its own later unused freeze if capacity gates pass. No download/provider/DB/app/env/Vercel change.

## Actual national bank-capacity stop

The [national census recipe](cell-census-plan-run-v1.json), SHA`4111e7509a348b3ac47c7d93d048378b504f6b97030514187cd624eb9aa9bca5`, is USED/stopped/closed at`data/coarse-quality/us-osm-cell-census-run-v1/`. [Freeze](cell-census-freeze-run-v1.json), [actual stop](cell-census-stop-v1.json), [closed roster](cell-census-closed-run-v1.json), [independent absence](cell-census-cleanup-run-v1.json). Never replay/edit/resume it.

Formal`Cell bank projected logical cap`stop after1,577,373,696recognized/1,577,373,695accepted node receipts,98.2035%of1,606,229,364nodes. These partial counters include rejected/cap+1. No source EOF/way/relation scan/second pass/complete bank or readonly national input qualification.31flushed parts retain2,080,277,463bytes; the unflushed buffer is not on disk.60closed files/2,080,605,918bytes, conservative allocation2,082,320,384bytes. Host776.984551seconds including binding/cleanup; worker final sample748.775074seconds. Kernel peak4GiB with reclaim;oom0/oom_kill0, worker/client2/not OOM/independently absent. This is a logical bank limit failure, not an OOM or completed-source measurement.

Fine view compared385,101blocks/1,577,373,696nodes,752shards; payload reads28,474,117,675bytes, zero whole-file verification rounds. It cannot admit the stopped fine input. Source/full fine/oldSQLite/old prefix files remain unchanged. Original source/attribute/matching/accuracy/model gates stay held.

The preceding V12read-only correction passed38Linux tests/no skips and exact tiny output/input preservation; V11reporter int/list collision is preserved. [V12proof](verify_qualification_v12.py). The new capacity controller passed11Linux controls and two complete tiny source/bank/fine/witness passes,18objects and identical578byte banks, source-derived cells/order/duplicates exact;30closed files/106,565bytes, worker absent. [Controller proof](verify_cell_census_controls_v1.py).

Safe newest proof:

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_cell_census_stop_v1.py
```

Optional`--local-assets` hashes closed prefix only, never PBF/native/Docker; parts were already hashed at closure. Do not repeat for documentation.

## Next lossless format revision

V1stores repeated ID gaps separately. New separately versioned encoding should store equal-gap runs and choose canonical raw gaps when runs are not smaller, preserving exact IDs/cells/order. No lossy geometry, handpicked region, changed windows or raised2GiB cap. Qualify native/reference codec/bank/filter/readonly output equivalence and all malformed/hash/ABI/budget/drift/missing-reference cases before another national attempt. Prefix recompression is prefix-only evidence, not national capacity or accuracy.

Retained reservation is now55,406,628,967bytes after adding the closed prefix; new owned work after256MiB tmp<=13,044,412,313bytes under64GiB. Global4GiB zero swap/four-hour remain. Source input reuse still needs new complete source EOF/count/semantic/source-block/catalog/hash proof; original failures stay unchanged/unqualified. No app/env/DB/provider/download/deploy/model change.


## Lossless ID-gap format V13 qualified

[Recipe](qualification-plan-v13.json), SHA`e3c3f12d84f0bb0eea3629da292dd6187cf587925eb420c110ca53939ccc2237`, and all used producers are immutable. **65 actual Linux checks/no skips pass.** V2 represents repeated positive ID gaps as runs only when strictly smaller than raw gaps; raw wins ties. IDs, cells, metadata, query order/duplicates and all prior integrity/independent audit rules remain exact. Complete filtered and readonly output stays1470bytes/SHA`dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c`; tiny bank581bytes vs preceding578 (small header overhead). No national size/speed inference from this fixture.

Native legacy conversion checks every V1ID/cell, emits canonical V2 and re-decodes/compares every row inside C; the wrapper additionally authenticates metadata and endpoint queries. [Safe proof](verify_qualification_v13.py) independently constructs the86byte tiny V2 block and composes preserved prior evidence without native/Docker/PBF/prefix reads.

[Closed roster](qualification-closed-v13.json):108files/3,796,019bytes; host18.679201seconds including bindings/build/tests/cleanup; build/control cgroup peaks456,495,104/252,387,328bytes. Both workers0/not OOM/independently absent. [Artifact receipt](qualification-raw/v13/build/result.json):2,004,888bytes/SHA`e82ccc44579ded7e7a6fcae5cdd3a6267250f3f3e00968195e45e567f1c0138e`, ignored at`data/coarse-quality/us-osm-country-controls-v13/build/country-screen.so`. No national source/fine/stopped prefix was mounted/read. Next is a separately frozen measurement on the31old parts, before new complete national capacity qualification under unchanged limits.


## Preserved-prefix lossless measurement passed

[Recipe](prefix-plan-run-v2.json), SHA`5f69fbf52a9d0ec879402c318ce27c7b0e43b848790e9a8e5ed0a56ff46eaee7`, is USED/passed/closed. All31stored V1parts authenticate against the original failed-run roster; all373,002blocks/1,527,816,192stored IDs/cells pass native conversion/full-row roundtrip, strict cross-part order, canonical/hash and unchanged cell-run-byte checks. **2,080,277,463→914,994,196bytes (56.0158%smaller)**. Stored nodes differ from the interrupted run's larger receipt count because its pending buffer was never flushed. No converted bank saved, no PBF/fine index read, no inputs changed. Prefix-only size evidence, not full-source capacity/speed/accuracy.

Conversion36.321070seconds; host37.390202seconds including bindings/startup/cleanup;746,004native calls/3,055,632,384charged rows; cgroup peak2,123,542,528bytes includes file cache, no OOM. [Closed](prefix-closed-run-v2.json):42files/151,097bytes, conservative allocation1,703,936bytes; worker/client0 and independently absent. Per-part summaries/converted ordered-byte hashes are retained in[prefix raw](prefix-raw/run-v2/result.json). Old ignored2.08GBparts unchanged.

First controller stopped before conversion on a missing monitor import mount; [V1closed](prefix-closed-controls-v1.json) failure preserved. V2launcher reuses immutable V1worker and corrects recipe closure/output:8actual Linux checks/no skips plus exact tiny83→86byte conversion; worker absent. [Controller proof](verify_prefix_controls_v2.py), [prefix proof](verify_prefix_run_v2.py) read saved records only, never native/Docker/PBF/ignored parts.

## National capacity census V2 passed

[Controller freeze](cell-census-freeze-controls-v2.json) is USED/passed/closed:11actual Linux checks/no skips, two complete tiny source/fine/bank/witness passes,18objects/identical581byte banks and exact source-derived cells/order/duplicates.30closed files/142,822bytes, worker0/not OOM/independently absent. [Safe controller proof](verify_cell_census_controls_v2.py) composes the prefix and V13qualifications.

[National recipe](cell-census-plan-run-v2.json), SHA`562122a0a5181f5716904a3859bd855f9f708098c565772669e3a15ce627f1fe`, [freeze](cell-census-freeze-run-v2.json), was USED for the completed census at`data/coarse-quality/us-osm-cell-census-run-v2/`. Rediscover actual owner/driver/container from owned records; never replay/resume. Same2GiB bank/4GiB RAM/four-hour/64GiB total/original21windows; new retained reservation55,406,628,967bytes includes old prefix. No duplicate fine index. Every fresh source block, whole source EOF/count/semantic, source-derived coordinate witness, fine/catalog/hash and byte-identical second bank must pass, then independent resource/lifecycle/proof closure. Prefix savings waive no gate. Complete filtered road capture remains a separately frozen next stage after capacity admission; source adequacy/speed/access/matching/physical/accuracy/package/API/model gates remain held.


The following success-only closure commands have now executed and passed. This is a historical command record; never replay the closer:

```sh
python3 -B scripts/close_osm_cell_census_v2.py
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_cell_census_run_v2.py
```

Run only after successful driver/worker result and owned cleanup. The closer hashes new derived parts once, preserves them ignored, mirrors small records/directories and independently checks current owned-container absence. The saved proof then checks both complete source receipts, all fine comparison totals, full directory/catalog/part bindings, source-coordinate witnesses, identical bank rebuilds and resource/lifecycle closure without native/PBF/ignored-part reads. Failure requires separately preserved stop evidence; do not force success closure.


## Complete filtered capture controller qualified

[Controls recipe](filtered-capture-plan-controls-v1.json), SHA`2ffecc1bc31f47bb1e17dcc9b09354012f568523f76642e092cc07efdea5e95b`, [freeze](filtered-capture-freeze-controls-v1.json), is USED/passed/closed.13actual Linux checks/no skips plus complete tiny filtered extraction/read-only fine revalidation/four-pass output pass. Output1470bytes/4unique objects/8occurrences/18source visits; two581byte banks, every4coarse refs resolve/2fine refs per pass, unchanged raw metadata/restrictions. No fine index copies/deletion. [Closed](filtered-capture-closed-controls-v1.json):26files/159,072bytes; worker0/not OOM/independently absent. [Safe proof](verify_filtered_capture_controls_v1.py). This tiny qualification overlaps the running national census; no isolated/national performance claim.

New controller keeps all55,406,628,967prior retained bytes and reserves both census banks at their2GiBceilings plus64MiBmetadata, total59,768,705,127. Owned8,682,336,153after256MiBtmp under64GiB. Read-only fine input avoids another14.5GBindex; only new cell banks/output/records may be written, all retained. Same4GiB/zero-swap/twoCPU/four-hour and original21windows/selected/output caps. Prospective new whole-road cell lookup budget1e12rows/100mcalls; fine lookup4TiB/pass/48brows/12mcalls unchanged; mask1.1brefs/1mcalls. Administrative ceilings, not measured execution. Used controller/resource/test files immutable. National capture is not yet frozen/started; completed census proof remains mandatory.


Pass A has completed:1,770,542,426source objects at normal EOF, original counts/semantic/source seals, every392,146node block/766fine shards plus whole-file verification, and1532source-coordinate witnesses pass. Bank938,364,831bytes; protected pass817.461429seconds. This was the live first-pass checkpoint; both passes and final capacity proof now pass as recorded below. These live records stay in the owned root until final closure.


## Complete national capacity result

V2census is USED/passed/closed. [Closed roster](cell-census-closed-run-v2.json):82files/1,877,239,685bytes, conservative allocation1,879,212,032;28large bank parts retained ignored, small records/directories mirrored. [Independent absence](cell-census-cleanup-run-v2.json), [safe proof](verify_cell_census_run_v2.py). The closer and proof executed/passed and are now immutable.

Two full1,770,542,426object source traversals pass normal EOF/count/metadata/semantic/source identities; all1,606,229,364nodes/392,146blocks/766fine shards freshly compare to read-only fine bytes per pass, followed by whole-file checks43,472,344,176payload bytes/pass. Each1532source-coordinate witnesses/query order/duplicates match the independent cell oracle. Both complete14part banks are byte-identical at938,364,831bytes under the unchanged2GiBcap. No road capture/source suitability/accuracy admission follows from this capacity result. Old failed evidence and all input bytes are unchanged.

Protected passes817.461429/819.942328seconds; host1683.695520seconds including bindings/startup/cleanup, not graph search. Kernel peak4GiB includes page cache/reclaim;104452max events,oom0/oom_kill0; worker/client0/not OOM/independently absent. Cell codec12,862,383,752charged rows/3,140,232calls; fine codec3,212,458,728rows/784,292calls. Source/native/framing/posthash/lookup scopes remain separate in raw receipts. No source/provider/download/app/DB/env/Vercel/model change.

## Preserved filtered road capture attempt

[National capture recipe](filtered-capture-plan-run-v1.json), SHA`8a2e7321dbef9faeda6c49660196cdb04c35e6204b5f7b248c866873604c3ed4`, [freeze](filtered-capture-freeze-run-v1.json), is USED/running at`data/coarse-quality/us-osm-filtered-capture-run-v1/`. Rediscover current owner/driver/container, never replay/resume or edit used code. Passed capacity proof and13Linux/tiny capture controls precede this freeze. Original source/windows/selected-output bounds, same4GiB/zero swap/twoCPU/four-hour/64GiB retained total and2GiBbank cap. Fine input remains read-only, no duplicate14.5GBindex.

Requires two complete source passes, every highway's full geometry/reference lookup, independent primary/audit window membership/materialization, raw metadata/restriction retention, output/window ledger, source-linked readonly fine validation and resource/lifecycle/proof closure. Complete source/publisher adequacy, adapter/usable-limit/matching/physical/accuracy/package/API/model gates remain later. No active app change.


## Attribute adapter preparation (unfrozen)

New`coarse_osm_attributes_v1.py`/tests pass9host synthetic checks. The draft preserves full raw way records/field seals, ordered node geometry and full dependency seals, all native tags/units/scopes/direction/access/structure and barrier-node references. It parses only plain positive finite ASCII numeric values in documented km/h or mph, without statutory/class defaults. Symbolic, unsupported and conditional/directional/lane/vehicle scopes remain visible. Every result keeps car permission unreviewed and usableForTiming=False. No Overture schema conversion, driving-time model, usable-limit/matching result or real captured-data inventory. These files remain unfrozen drafts; native target qualification and policy/inventory freeze remain later.

The source defines numeric values as km/h unless a unit is supplied; special values and scoped forms have separate meanings. [OSM maxspeed documentation](https://wiki.openstreetmap.org/wiki/Key:maxspeed). Access restrictions use transport-mode and scoped tags; the draft reports them without resolving legal permission. [OSM access documentation](https://wiki.openstreetmap.org/wiki/Key:access). One-way values are retained in source-way orientation with no direction flattening. [OSM oneway documentation](https://wiki.openstreetmap.org/wiki/Key:oneway). Documentation reviewed October30,2026 through the web tool; no routing quota or national-source acquisition. Complete capture and source adequacy still precede any real-data feasibility conclusion.


## Publisher-boundary review preparation

Documentation reviewed October30,2026, with no polygon/OSM data acquisition. Geofabrik describes hierarchical polygon clipping, completion of selected crossing ways/multipolygons, downloadable clip polygons, and possible later changes to clip bounds. Public metadata omits contributor user/uid/changeset fields; this is a publisher property rather than an importer repair. [Publisher technical details](https://download.geofabrik.de/technical.html).

Osmium documents complete-way selection through nodes inside the extraction region, followed by those ways' referenced nodes; relations need separate completion rules. [Primary extraction manual](https://docs.osmcode.org/osmium/latest/osmium-extract.html#strategies). **Inference:** a segment can cross a validation window while both endpoints lie outside the publisher polygon, so polygon containment alone cannot establish absence of outside-file competitors. This does not show any road is missing from the saved file. Exact source-snapshot clip identity, all21window decisions and competitor uncertainty remain unqualified; do not substitute current documentation for proof of the2026-10-25snapshot or waive original gates.


## Selected-element cap stop closed

[Used recipe](filtered-capture-plan-run-v1.json) SHA`8a2e7321dbef9faeda6c49660196cdb04c35e6204b5f7b248c866873604c3ed4` stopped at`Selected unique element cap`during primary selection. [Stop](filtered-capture-stop-v1.json), [closed roster](filtered-capture-closed-run-v1.json), [absence](filtered-capture-cleanup-run-v1.json), [safe proof](verify_filtered_capture_stop_v1.py). Source recognized1,606,229,364nodes/11,201,886ways; accepted ways11,201,885. Delivered batches10,736,397highways/170,361,375refs include the rejected/cap+1scope. No EOF/relations/second pass/normalized output/capture/source-suitability/model admission. Not an OOM or measured wall/IO limit failure. No worker remains; never replay/resume/edit used outputs.

Host1845.746947seconds including binding/cleanup; worker1816.602107seconds. Kernel peak4GiB/cache reclaim,333558max events,oom0/oom_kill0; worker/client2/not OOM/independently absent. Closed62files/938,722,550bytes, conservative allocation940,490,752.14ignored bank parts still match accepted census hashes; this does not promote the stopped stage. Process rchar420,079,682,208includes multiple IO scopes, not authenticated fine IO or graph-search time. Source/fine/old failures unchanged. Unexecuted success-only closer/proof drafts were withdrawn; actual stop closer/proof executed/passed and are immutable.

Next is separately versioned disk-backed primary/audit selected data and a native2Mselected-ID bridge. Same4GiB/zero swap/twoCPU/four-hour/64GiB global budget, original21windows and every source/geometry/independence/matching/model gate. New proposed2Munique/4Moccurrences,512MiBraw/state,1GiBnormalized output/8MiBselected row; source-copy/canonical4MiB/frame8MiB unchanged. Proposed SQLite files<=1.25GiB/cache8MiB each, OS file cap2GiB; new bank writes must match exact938,364,831byte accepted capacity output. Actual retained58,226,331,751 plus64MiBmetadata/256MiBtmp leaves10,157,600,665owned bytes. Worst-case2DBs2.5GiB +2journals4GiB +two banks1,876,729,662 +1GiBoutput +64MiBmetadata =9,996,902,206, below owned by160,698,459. Qualify arithmetic/SQLite/native beyond-old-cap and exact tiny output/tamper/ownership/lifecycle before any new national freeze. No request for a larger global budget or changed source/window/model scope.
