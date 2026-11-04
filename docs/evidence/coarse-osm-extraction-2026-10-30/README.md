# Complete road extraction and bounded national capture

Updated October 31, 2026. **Latest: complete acquired-file capture, metadata inventory, continuous matcher V2 and independent saved-output audits passed. The data-enrichment strategy still misses its feasibility gate: only 21.650% raw geometric/numeric corridor opportunity before source/car/physical review.** All original 2,469 Census records/85,629 weighted midpoints/21 areas remain. V9 is unchanged; the next step needs a data-architecture choice. [Latest result and decision](#latest-completed-results-and-road-model-decision), [resume guide](../../agent-handoff.md), [next steps](../../next-steps.md). Earlier named stages retain their original scope.

**Earlier checkpoint:**

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


## Disk-backed selection qualification

New primary/audit SQLite spools stream raw fields and output with fixed8MiBcache/1.25GiBpage cap each. Selection supports2Munique/4Mwindow occurrences,512MiBraw/state,1GiBoutput/8MiBselected row. Source copy/canonical4MiB/frame8MiB remain. Native source ABI6changes exactly the selected-count guard and ABI constant; typed64-bit Python buffer avoids a giant argument tuple. Every geometry/reference/metadata/semantic/EOF/independence guard remains.

[V14recipe](qualification-plan-v14.json)/[freeze](qualification-freeze-v14.json) compiled the helper and passed71Linux tests, then its separately persisted four-pass reference stopped before source reads on `SQLite index arithmetic`. This was a qualification-fixture configuration error. Failed files/code/recipe remain immutable; [closed53files/3,366,421bytes](qualification-closed-v14.json), conservative5,070,848, workers absent.

[V15recipe](qualification-plan-v15.json)/[freeze](qualification-freeze-v15.json), SHA`79289164e7c5a1ae7936543062fa8d05184d87e15ab640a6e09e0f36b34fa5b9`, corrects only the tiny reference index page/cache settings and reuses the compiled library. **71actual Linux tests/no skips pass**, including250,001SQLite raw nodes/500,002memberships, all caps/ABI/transactions/page-full/configuration/tamper/ownership controls, exact tiny independent output and zero-highway fine-file verification. [Result](qualification-raw/v15/controls/result.json).

Persisted tiny output is1470bytes/SHA`dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c`,4objects/8memberships/18native visits; both primary/audit DBs sealed/closed and independently checked. All3fine input files unchanged, no copied fine index, two581byte banks. [Tiny proof](qualification-raw/v15/controls/tiny-proof.json).

The separate native proof projects **2,000,000selected nodes**, IDs`9223372036852775808..9223372036854775807`, and compares every raw field and coordinate to an independent deterministic synthetic source formula. Complete native EOF/count/semantic/metadata/witness/field receipts pass. All full fields are saved in an ignored gzip archive; the saved proof independently checks every archived row and complete semantic seal without native/PBF decoding. [Boundary proof](qualification-raw/v15/controls/native-boundary-proof.json). This is synthetic boundary correctness, not national capture or accuracy.

Host36.332697seconds including bindings/tests/proofs/cleanup; kernel137,768,960bytes/no OOM/swap. Closed40files/16,298,408bytes, conservative18,726,912; worker/client0/independently absent. [Closed](qualification-closed-v15.json), [cleanup](cleanup-audit-v15.json). Large archive/PBF/library remain ignored; small records mirrored. Library`data/coarse-quality/us-osm-country-controls-v14/build/country-screen.so`,2,004,888bytes/SHA`eaf28ec03eb32da954fedb68b300caa62a89cf29f28a158a94a39829c18b3600`. All11V14producers plus3V15producers/recipes are USED/immutable; no national source/fine/bank mount/read.

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_qualification_v15.py
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_qualification_v15.py --local-assets
```

Controller: [controls recipe](disk-capture-plan-controls-v1.json)/[freeze](disk-capture-freeze-controls-v1.json),16actual Linux tests/no skips and complete tiny capture/reference/resource/lifecycle pass. [Closed28files/213,827bytes](disk-capture-closed-controls-v1.json), conservative1,609,728; host1.697620seconds including bindings/cleanup, worker/client0/absent. [Safe proof](verify_disk_capture_controls_v1.py). It reserves all58,226,331,751prior retained bytes,64MiBqualification(actual23,797,760),64MiBmetadata and256MiBtmp. Owned10,090,491,801; worst writable9,996,902,206. Every bank write size/hash must match the accepted bank receipt. National [recipe](disk-capture-plan-run-v1.json)/[freeze](disk-capture-freeze-run-v1.json), SHA`2942796a1920a862a2e524160247a0506dd143a2aff8111cdcaf754f2869d1be`, is USED/running at`data/coarse-quality/us-osm-disk-capture-run-v1/`. Rediscover its actual owner; no duplicate/replay/resume. Require complete two-pass capture/output/independent audit/resource/lifecycle before admission. No global budget/source/window/model change. App check197/typecheck/build pass. Latest base commit is`77d7818`(user commit); this resumed qualification/controller work remains local/uncommitted.


### Saved publisher metadata and host containment diagnostic

A separately frozen public-metadata attempt [V1](polygon-metadata-plan-v1.json) stopped on the host Python certificate trust error before a response body; [original failure/closure](polygon-metadata-closed-v1.json) is preserved. [V2](polygon-metadata-plan-v2.json) uses system curl with certificate verification enabled/user configuration disabled. Four successful metadata GETs return27,759body bytes in2.129823seconds; no PBF/source-road/routing-provider request. [Result](polygon-metadata-raw/v2/result.json), [transport](polygon-metadata-raw/v2/transport.json), [closed16files/35,604bytes](polygon-metadata-closed-v2.json). Both used producers/recipes remain immutable; no CA/environment/dependency changes.

The archived US polygon file is from repository commit`9e71ba22cb4a7b7b1c4228031e2afdfc514d6b6e`, dated2025-07-31T12:51:53Z, before the acquired source's2026-10-25state. The bounded later-history query returned no file changes in its checked interval. Archived repository polygon SHA`69e21474d28b074d198ca504a516ddeafc75e6a2f483e9a6dc2169d7801f4ee6`; current deployed polygon SHA`5b36ffe960cba918b5b33bd998bca090ce4279828590dab382d097d4a3b7a2f3`. Bytes/vertices differ, as can happen with the publisher's documented effective-boundary processing; the cause of these particular differences is not independently established.

[Host diagnostic recipe](polygon-review-plan-v1.json), SHA`f3b5f2b92530aa92817f30697f37d82d065018bed55027cfa9755d29200cc2ed`, pins those two small files and the original21windows. Seven host controls cover exact edges, holes, nonconvex cuts, disjoint/oriented rings, bounded numeric input and failure cases. **All21window rectangles lie strictly inside both saved polygons**, with no boundary intersection. Archived/current files each have two outer rings/no holes,438/428vertices. [Measured result](polygon-review-raw/v1/result.json), [closed3files/16,416bytes](polygon-review-closed-v1.json). The independent saved proof uses a separate ray/parametric clipping implementation and verifies all42window checks. Small polygon bytes are mirrored for fresh-clone proof; API/raw headers remain ignored. Polygon data: ©OpenStreetMap contributors; publisher Geofabrik. [Publisher source/history](https://github.com/geofabrik/polygons_download.geofabrik.de).

This is host diagnostic evidence, not Linux/native/timing admission, OGC topology validation, proof of the effective deployed boundary on the source date, or proof about omitted long road segments. Source/publisher/model admission flags stayfalse. The metadata/review work overlapped the running national capture; elapsed scopes are shared-host processing, not isolated throughput or graph-search measurements.

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_polygon_review_v1.py
PYTHONPATH=scripts python3 -B -m unittest coarse_osm_polygon_review_v1_test
```


### Earlier web-only publisher review

The official [polygon-history repository](https://github.com/geofabrik/polygons_download.geofabrik.de) and its [README](https://github.com/geofabrik/polygons_download.geofabrik.de/blob/master/README.md), [contribution guidance](https://github.com/geofabrik/polygons_download.geofabrik.de/blob/master/CONTRIBUTING.md) and [current deployed US polygon](https://download.geofabrik.de/north-america/us.poly) were read before the separately frozen metadata snapshot. Repository/deployed polygons may differ after effective-boundary processing; current URLs alone do not bind the acquired2026-10-25PBF. At that checkpoint no local checksum-bound polygon snapshot or containment test existed. The later saved snapshot/diagnostic above supersedes that preparation state, with source/model admission still false.

Earlier closure/reader preparation: the unexecuted V2closer was prepared to preserve large SQLite sidecars without duplicate evidence copies; the actual completed closure now uses it. The facts reader's selected-row cap became8MiB and missing/empty highway failed explicitly;11host controls passed before the subsequent actual Linux qualification. All source/provider/model semantics remained unreviewed.


## National disk-backed capture passed and closed

[Used recipe](disk-capture-plan-run-v1.json), SHA`2942796a1920a862a2e524160247a0506dd143a2aff8111cdcaf754f2869d1be`, completed at`data/coarse-quality/us-osm-disk-capture-run-v1/`. Two normal-EOF passes each have1,606,229,364nodes/162,688,797ways/1,624,265relations and GPF1seal`209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16`. Total3,541,084,852visits. [Controller result](disk-capture-raw/run-v1/result.json), [complete extraction result](disk-capture-raw/run-v1/extraction-result.json), [all21window ledger](disk-capture-raw/run-v1/window-ledger.json).

| Measured scope | Result |
| --- | --- |
| Normalized output |477,852,579bytes/SHA`efc36dc058b198711cc2666a751c9fd60b52d37902efbb22e1cba8b5f30f91f4` |
| Records/occurrences |1,368,072/1,368,072 |
| Types |1,123,919nodes;239,253ways;4,900relations |
| Rebuilt cell banks |938,364,831bytes each/14parts; byte-identical to accepted census |
| Primary/audit SQLite files |357,265,408/336,826,368bytes; sealed/integrity checked/closed |
| Canonical raw bytes per independent store |229,630,917 |
| Live batch conservative heap peak |35,654,012bytes, below128MiB |
| Full highway delivery per pass |52,053,199ways/509,547,029references |
| Certified-outside ways / fine references per pass |51,813,944 /1,530,046 |

The legacy`examinedHighwayReferences`receipt is508,093,741because the bounded-probe trace skips1,148ways with>1024refs. Complete mode queues those ways before that branch; the full delivered509,547,029references include them. These scopes differ; no reference is trimmed to match an old counter or an example.

Each fresh readonly fine view compares all1,606,229,364source node rows and completes one whole-file verification,43,472,344,176payload bytes/pass. [Fine revalidation](disk-capture-raw/run-v1/fine-revalidation.json). No duplicate fine index/deletion/repair; prior failed admissions remain unchanged. Fine lookup authenticates2,260,508,334,182shard bytes/pass. Hash/format2492.398656/2556.247047s and block decode328.023635/338.784789s are measured separately; these are not physical disk-byte or graph-search metrics.

Native loops5651.571356/5947.101867s include callbacks/lookup/storage; framing99.647079/110.575269s and post-source hashes11.011113/10.392395s are separate. Complete protected extraction11942.319828s includes framing, callbacks, fresh fine validation, bank writes, independent materialization, output audit and close. Host11993.307143s includes bindings/cleanup (~3h20m). Shared-host offline processing under the frozen four-hour limit; no query/Vercel runtime forecast.

Actual4GiB/zero swap/twoCPU/original21windows/64GiBretained envelope remains. Kernel peak4GiB includes page cache/reclaim(max3507426),oom0/oom_kill0. Worker/client0/not OOM/owned removal/separate absence pass. [Metrics](disk-capture-raw/run-v1/metrics-end.json), [cleanup](disk-capture-cleanup-run-v1.json). [Closed249files/3,049,088,532bytes](disk-capture-closed-run-v1.json), conservative3,089,563,648. Used`close_osm_disk_capture_v2.py`is immutable.31large bank/SQLite/output assets remain ignored; small records/directories mirrored. Every old source/failed SQLite/index/prefix/attempt is preserved.

Default and local saved proofs pass. Local hashes only new derived files, verifies both readonly SQLite tables/key sets/memberships/raw bytes/integrity and independently reconstructs every output raw field/geometry seal/order/window ledger. No old fine/PBF/native execution. It already passed; do not repeat the~3GBscan just for docs.

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_disk_capture_run_v1.py
# Optional closed-derived-asset recheck only:
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_disk_capture_run_v1.py --local-assets
```

This qualifies complete acquired-file capture for the validation dataset. Source/publisher adequacy, usable driving limits, matching/physical/accuracy/package/API/model gates remainfalse/unadmitted. Generic routing rules and deployed v9 are unchanged. No routing-provider call, DB write or app deployment.


## Facts reader Linux controls passed

[Recipe](attribute-controls-plan-v1.json), SHA`7f0f99f0b109a1ebb132496e5cb1d7e2b0dcb9a1f47c445ea8f4b276106c9e7e`, was used after the national worker closed.15host preparation tests(11reader+4controller), then11actual Linux tests/no skips and full tiny facts preservation pass. [Host preparation](attribute-host-controls-v1.json), [result](attribute-controls-raw/v1/result.json), [facts](attribute-controls-raw/v1/facts.json). Source raw/ordered geometry/metadata, numeric mph/kmh, private access, conditional scopes and barriers remain intact. Car permission staysunreviewed/usableForTiming=False; this adapter has read no national records.

Actual512MiB/zero swap/oneCPU/32MiBtmp+file limits/network none/readonly/no capabilities. Peak48,295,936bytes/no OOM; protected0.058038s, host0.702448s. [Closed12files/13,163bytes](attribute-controls-closed-v1.json), conservative1,208,320; worker/client0/independently absent. Four facts/controller files and used recipes are immutable.

The original saved V1verifier compared Decimal-rounded88.51392to the binary product`55*1.609344`(88.51392000000001), failing by one ULP. [Original verifier/failure receipt](attribute-verifier-stop-v1.json) is preserved. New V2uses the exact Decimal unit conversion and passes; no source/parser/producer/data/policy change.

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_attribute_controls_v2.py
```

## Raw metadata inventory controls passed; target controller finished

New three producers implement a bounded typed node/canonical-byte arena, exact source-field/geometry-seal validation, raw speed/unit/scope/access/direction/role counts and spherical clipped-length metrics. Overlapping windows are unioned for aggregate length. All records/areas remain included; permissions/usable limits/matching/source adequacy/costs stay unreviewed/false.

[Controls recipe](attribute-inventory-plan-controls-v1.json), SHA`4892fd1fe53b154b2727431421d5accd1e99b84aeaa53f05bf333f20d0aaf0cf`, passes8actual Linux tests/no skips and tiny4record/2window positive inventory. [Closed12files/23,734bytes](attribute-inventory-closed-controls-v1.json), conservative1,216,512; peak22,913,024bytes/no OOM, worker/client0/absent. [Safe proof](verify_attribute_inventory_controls_v1.py). All used producers/recipes immutable.

[Actual recipe](attribute-inventory-plan-run-v1.json), SHA`a406a2202962e8e20fcbfa20768534b4b5a507d30c715a2d5517cca91a7843db`, was USED at`data/coarse-quality/us-osm-attribute-inventory-run-v1/`. The controller now reports exit0 in36.439003seconds. Target inventory has not yet been closed/independently verified or interpreted in this checkpoint.512MiB/zero swap/oneCPU/32MiBtmp/file limits/network none/readonly input;300sworker/360shost,256MiBnode arena/2Mrecords/4Moccurrences/4Mrefs/1GiBinput/8MiBrow caps. It reads qualified captured JSONL only, not PBF/old fine/native helper/provider/DB. Close once with`close_osm_attribute_inventory_v1.py run`, then independently verify saved raw statistics. Never equate raw tag presence/clipped source length with usable limits or matched-route coverage.

A documentation write-target error during this update was caught by relative-link checks. This unsealed report was restored from its Git baseline plus recorded update blocks and saved measurement records; no frozen recipe, producer, raw/closed record or data asset was changed.


## Captured metadata inventory passed and independently audited

The [run recipe](attribute-inventory-plan-run-v1.json), SHA`a406a2202962e8e20fcbfa20768534b4b5a507d30c715a2d5517cca91a7843db`, is USED/passed/closed. All1,368,072records/21areas,1,530,030ordered way references, raw node/way seals and geometry dependencies pass. [Saved inventory](attribute-inventory-raw/run-v1/inventory.json), SHA`bbf6ab5238a8e63af7c3399132eeac2355d3750d4ec07837f99091322af76f09`. No source/permission/matching/model gate is promoted.

| Raw numeric tag presence | Captured clipped km | Numeric base-tag length | Numeric without additional speed scopes |
| --- | ---: | ---: | ---: |
| Every captured highway role |27,228.499|11.921%|11.121%|
| Supported road roles, including service roads/links |18,801.017|17.189%|16.031%|
| Motorway |644.530|91.717%|65.402%|
| Primary |746.156|64.789%|63.266%|
| Secondary |1,009.746|47.834%|47.455%|
| Residential |6,580.490|11.398%|11.387%|
| Service |7,296.537|3.725%|3.722%|

20,602of239,253ways have a plain numeric base tag;19,610also have no additional speed scopes. Supported roles account for141,734ways;20,474numeric/19,482unscoped.28,556captured nodes have a barrier tag. Counts retain every original area, unknown role/unit and scope/access/direction case. Tags are source limits, not measured driving speeds or reviewed car permissions. These source-polyline lengths are **not** the original clipped Census-km denominator; these percentages cannot establish success or failure of the>=50%unique plausible usable-limit Census-km gate. Geographic variation is descriptive of the original validation areas, not nationwide coverage.

Host36.439003seconds, protected35.649053seconds (input checks/stream/geometry/inventory/output; not graph search). Actual512MiB memory/zero swap/oneCPU/32MiBtmp/file limits/network none/readonly input. Kernel peak536,870,912bytes includes page cache;974memory.max events with0OOM/0OOM kills. No PBF/fine/native-helper/provider/DB reads. [Closed11files/50,152bytes](attribute-inventory-closed-run-v1.json), conservative allocation1,228,800; client/worker0 and independently absent. All used producers/recipes/closer are immutable. Retain the original capture3,089,563,648bytes plus this result in later budgets.

[Current safe proof](verify_attribute_inventory_run_v2.py) passes in default mode and with`--local-assets`. Optional mode independently streams the477MBcaptured JSONL, reconstructs every tag count and every area/role length using separate slab clipping/haversine calculations and typed node coordinate arrays, and checks the exact input hash. It does not call the inventory producer or read source PBF/old fine/native/Docker. Full input geometry dependency seals were also checked by the bounded producer and earlier independent capture proof. Do not repeat the local scan merely for documentation. V1default proof passed but optional byte accounting used UTF-8characters instead of sealed canonical ASCII escaping (10bytes); [failure](attribute-inventory-verifier-stop-v1.json) and V1remain preserved. V2fixes that verifier convention only; measured producer/data unchanged.

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_attribute_inventory_run_v2.py
# Optional closed derived-input audit, already passed:
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_attribute_inventory_run_v2.py --local-assets
```

Next diagnostic: compare raw numeric-tag geometry opportunity with **all2,469original Census arc/window records**, keeping their saved weights/classes/areas. A generous geometric union can test whether enough potential exists before implementing full semantic/connected matching. It cannot establish car permission, unique matches, source adequacy or usable speed coverage. Freeze exact inputs/25m/15degree/midpoint rules/caps/implementation before actual access, qualify synthetic controls first, and preserve failures rather than selecting easier roads or dropping areas.


## Census geometry opportunity passed; full matching remains

The [frozen actual recipe](speed-opportunity-plan-run-v1.json), SHA `63ce0dc1c1d0b97aded04027b8367f71700d5aa11a50944cabf1005a85def8ce`, is USED/passed/closed. Ten actual Linux synthetic controls and a complete split-way positive fixture passed first ([controls closure](speed-opportunity-closed-controls-v1.json)). The actual diagnostic retains every original **2,469 arc/window record, 2,078.237959868 Census km, 85,629 weighted midpoints, 21 areas and 85/105 source class**. All 1,368,072 captured records and 1,530,030 way references were read with unchanged input hash. It clips captured segments to their original windows and preserves the frozen <=25 m distance/midpoint spacing and <=15 degree undirected tangent rules.

| Captured geometry category | Aligned Census km | Aligned sample weight | Whole-arc opportunity at >=80% union |
| --- | ---: | ---: | ---: |
| Any captured highway | 2,073.235 | 99.759% | 99.852% |
| Any maxspeed-family tag, including symbolic/scoped/annotation | 1,682.135 | 80.940% | 78.746% |
| Plain numeric base maxspeed | 1,678.197 | 80.751% | 78.386% |
| Numeric base without additional speed scopes | 1,383.084 | 66.551% | 62.351% |

[All results and area/class breakdowns](speed-opportunity-raw/run-v1/opportunity.json), SHA `e6d4c2c8817b84e19f01eb3fbc2644fd2dc4ec3a9bbf6d1738d0bdbf1ce599bc`. Whole-arc opportunity deliberately counts the entire source arc when its geometric union reaches 80%; it is an optimistic category bound under this sampling rule, not observed matched/usable km. The 17.189% raw supported-road-polyline statistic and 80.751% Census-weighted statistic use different denominators. The data therefore supports continuing with native matching; the earlier sparse overall tag presence does not demonstrate a failed Census feasibility screen.

These unions can mix separate, disconnected or competing ways and ignore access, direction, grade, conflicting limits and road identity. They prove neither a unique plausible connected match nor a usable car limit. Source-date publisher adequacy and all original matching/physical/model gates remain false. No original 50% usable-limit/matching gate is admitted, and no nationwide accuracy claim follows from these validation areas.

Host **31.236569 s**, protected **30.244511 s** (bindings/streamed node coordinates/segment/sample unions/output, not graph search or app latency). Actual 512 MiB/zero swap/one CPU/32 MiB tmp/file/network none/read-only inputs; kernel peak 536,870,912 bytes includes cache/reclaim, 81 memory.max events, 0 OOM/0 OOM kills. 3,658,273 bin visits/942,969 final comparisons stayed below frozen caps. [Closed 13 files/1,476,811 bytes](speed-opportunity-closed-run-v1.json), conservative allocation 2,674,688; worker/client zero and independently absent. All four used producers, recipes and closed records are immutable. Source PBF/fine/native/provider/DB reads: zero.

[Current saved proof](verify_speed_opportunity_v2.py) passes in default and optional original-small-span modes. It independently reconciles every arc/window/class summary, sample mask weight and original denominator. V1 default proof passed; its optional exact-float comparison failed on 10 sourceKm sums by roundoff. [Preserved failure](speed-opportunity-verifier-stop-v1.json); V2 uses the existing 1e-9 km reconciliation tolerance for that comparison, changing no data/producer.

A [separate full-mask audit](speed-opportunity-independent-geometry-v1.json) independently streamed the derived input, used separate slab clipping, dot/cos tangent, projection/atan2 distance, numeric classification and a different bin size, and reconstructed **every one of the 85,629 four-category midpoint masks exactly**. Hash `0ac85754d605b4c0bdcb86da86a02c0680fc16a47b2811e1126915095746d001`; 2,289,677 bin visits/2,166,262 comparisons, 6.439517 s host audit. This verifies the saved geometric statistic, not road identity. Default proof reads the small audit/mirrors only; do not repeat the derived-input scan for docs.

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_speed_opportunity_v2.py --stage run
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_speed_geometry_v1.py
# Optional original920KBsaved Census span audit, already passed:
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_speed_opportunity_v2.py --stage run --local-assets
```

Next: a native OSM geometry adapter and bounded endpoint-connected/terminal-fragment matcher, using every captured alternative and unchanged source weights. OSM ways must split at shared native node identities; no coordinate-only joins, invented connectors or Overture attribute conversion. Keep raw speed/access/direction/structure context and unresolved alternatives visible. Qualify synthetic matching/ambiguity/junction/resource controls before any new exact actual run; native applicability/source adequacy and independent deterministic match review still precede feasibility/model admission.


## Native connected matcher controls passed; actual recipe frozen

Fifteen host and actual Linux tests/no skips pass, including a separate reference fragment/search implementation. Native ways split at shared node IDs; coincident coordinates without matching IDs do not connect. Parallel/grade/unknown-role alternatives, node metadata/geometry drift, missing nodes, barriers, raw private/conditional/oneway tags, overhanging terminals, reversal, every input/index/projection/search cap and original denominator are retained/tested. Native tags remain outside the Overture attribute parser and all car/timing/physical/source/model flags remain false.

[Controls closure](native-match-closed-controls-v1.json):17files/25,911bytes, conservative1,294,336; host0.702697s/protected0.026336s/peak24,793,088/no OOM/worker0/absent. [Safe proof](verify_native_match_controls_v1.py). All four new producers and used recipes are immutable. [Actual recipe](native-match-plan-run-v1.json), SHA `251fda35d24c5de9433584fe4132170ba9e06f5fd218250201d084e451259ca9`, is frozen for one later execution at `data/coarse-quality/us-osm-native-match-run-v1/`. No actual result at this checkpoint. Read-only derived JSONL/original Census spans only,1GiB/zero swap/oneCPU/1800sworker/1860shost/64MiBtmp/128MiBfile/512MiBowned. One full captured geometry-seal/node traversal plus21rebound window traversals; no sourcePBF/fine/native/provider/DB. Emit every original Census record and capped/unknown alternative, per-window native-part bindings, all area/class summaries and deterministic50record review selection. No usable-match or accuracy admission. Never replay an existing root.


## Native matcher V1 completed; conservative geometry bottleneck measured

[Actual recipe](native-match-plan-run-v1.json), SHA `251fda35d24c5de9433584fe4132170ba9e06f5fd218250201d084e451259ca9`, is USED/passed as a diagnostic/closed. Every original 2,469 arc/window record, 2,078.237959868 Census km and 85,629 midpoint weight is preserved; no search/projection cap fired. [Report](native-match-raw/run-v1/report.json), SHA `fac07762233a9c99ad6a8646c9636d0320af93cbd3326fad6dc99143b4db182f`.

| Acquired-file geometry outcome | Records | Original Census km |
| --- | ---: | ---: |
| Unresolved aligned alternatives | 2,162 | 1,865.739 |
| Multiple geometric paths | 151 | 98.363 |
| Single geometric path | 155 | 114.135 |
| No path under these rules | 1 | 0.000364 |

Single paths whose parts all have unscoped numeric base limits support **56.929704 km / 2.7393%** of the original denominator. This is an unqualified geometric/numeric opportunity, not usable car coverage. It is below the original 50% gate even before native semantic/source/physical checks. No feasibility/model admission follows. It does not establish poor OSM geometry or prove that another generic matcher cannot work: the separate 80.751% numeric union statistic remains valid under its own scope.

Host **163.470526 s**, protected **162.488227 s**, including complete input seals/ordered node geometry and 21 rebound derived-input window traversals, adaptation/sampling/fragment enumeration/output; not graph search/app latency. Actual 1 GiB/zero swap/one CPU/64 MiB tmp/128 MiB file/512 MiB owned bounds, network none/read-only inputs. Kernel peak 1,073,741,824 bytes includes page cache; 977 memory.max events, 0 OOM/0 OOM kills. [Closed 76 files/31,043,244 bytes](native-match-closed-run-v1.json), conservative allocation 33,492,992; worker/client zero and independently absent. Files over 1 MiB remain ignored; all small records are mirrored. All used producers/recipes/closer/evidence immutable.

[Independent saved audit](native-match-independent-audit-v1.json) passed: all 24,946 aligned native-part bindings reconstructed from the separate sealed read-only audit SQLite (including full raw tags/field/ordered node/geometry/record seals), every 3,980 saved candidate variant mask/weight/true node-ID join, all area/class/arc weights and the exact deterministic 50-record review selection. Audit 6.735768 s. Shared qualified numeric-unit parser is explicit. This is not independent exhaustive geometric enumeration or physical road review. The audit reads derived SQLite/output/small Census spans, never original PBF/fine/native/provider/application DB. Source adequacy, access/direction/grade/restriction applicability, physical identities and usable timing remain unqualified. Safe default proof uses saved small records/audit only:

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_native_match_run_v1.py
# Optional closed derived-output/SQLite audit, already passed:
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_native_match_run_v1.py --local-assets
```

The same fixed saved-output audit diagnoses 34,615 unrepresented part occurrences (parts can repeat across source arcs). **19,728 are at most 25 m long**. Reasons include 23,090 unsupported-role occurrences, 5,116 insufficient-projection-progress, 4,158 no-eligible-variant and 2,052 projection-tangent mismatch. Insufficient progress affects 1,702 arcs / 1,489.876 original km; unsupported roles affect 1,248 / 1,061.738 km. Reason exposures overlap and are not an additive partition. Numeric results and all original failed/unknown cases remain unchanged.

Next hypothesis: map native geometry to continuous progress along the unchanged Census source polyline, allowing short and zero-midpoint native junction connectors to retain true node-ID connectivity. Keep the **same original positive midpoint weights and 25 m/15 degree/80% criteria**; extra geometry probes carry no Census weight. Enumerate geometry for all roles and report unsupported-role candidate paths separately, without assuming car permission. Preserve rejected/uncertain alternatives, finite projection/index/search budgets and independent reference controls. This is a new generic prototype, not a source-coverage waiver or permission to reinterpret the V1 result. Synthetic qualification and a separate exact freeze must precede any new real-data run; no national/source PBF replay or production model change.


## Continuous-progress controls passed; actual experiment frozen

[Controls](continuous-match-closed-controls-v1.json):16actual Linux tests/no skips, independent straight-source graph oracle and a persisted genuine zero-original-midpoint connector pass; unchanged45positive samples/7source km/full support. Reversed parts, real node-ID joins, missing joins, all-role parallel competitors, rejected side branches, access/scopes, source progress ties/incident tangents, distances, terminals and every new/search cap are tested. Host0.709508s/protected0.030000s/peak24,412,160bytes/no OOM/worker absent;18files/29,471bytes/conservative1,306,624. [Safe proof](verify_continuous_match_controls_v1.py).

[Actual recipe](continuous-match-plan-run-v1.json), SHA `91538f9f64af5766d734c2ddf393497f045119b467a767bcecec319b20401d42`, is frozen for one later execution at `data/coarse-quality/us-osm-continuous-match-run-v1/`. No actual result at this checkpoint. All four new producers/used recipes immutable. Reuses native V1qualified raw/geometry/node/part adapter. Original2469Census records/85629positive midpoint weights/21areas/classes and25m/15degree/80%rules remain. Additional native-curve geometry probes carry no Census weight; continuous source progress allows short/zero-midpoint native ID connectors. All roles remain geometric competitors. Rejected aligned alternatives remain visible; uniqueness is conditional on the new corridor/window/progress/terminal eligibility rules, which is a different policy from V1's automatic unresolved-alternative block. All source/car/physical/usable/model gates remain false. New actual experiment still needs terminal closure, independent audit and deterministic review; no production change.

1GiB/zero swap/oneCPU/1800sworker/1860shost/64MiBtmp/128MiBfile/512MiBowned;61.7GBprior retained reserve+new owned/tmp fits64GiB. Reads only derived captured JSONL/original small Census spans, no PBF/fine/native/provider/appDB. Exact hypothesis, rejection/tie/probe/search semantics, caps and cap-sentinel accounting are in the recipe. Preserve all results/failures without post-result tuning.


## Continuous V1 memory stop preserved; V2 controller qualified

The1GiB [V1actual run](continuous-match-plan-run-v1.json) stopped after71.438720host seconds: worker/client137, DockerOOMKilledtrue. Complete node/field/geometry-seal traversal and4area reports/partial119fifth-area records remain. No complete report/result or terminal kernel peak was produced; do not infer all-area coverage or graph-search time. [Closed23files/75,606,743bytes](continuous-match-closed-run-v1.json), conservative80,056,320; worker independently absent. [Safe stop proof](verify_continuous_match_run_v1.py) passes default and optional derived partial-file hashes. All V1helpers/code/recipes/failed evidence immutable.

V2changes only controller memory/retention:2GiB hardRAM/zero swap within original4GiBoverall, and retain aggregate scalars after writing full detailed output. Same used V1matching algorithm, inputs, criteria, weights, probes and cases.19actual Linux tests/no skips pass, including3new aggregate-equivalence/bounded-retention/capped-outcome checks. Persisted fixture report is byte-identicalV1SHA `3d1b41c57c74fa1bea57d1377d62bc92ab25f77962bd9e233ee889faef1ee1fe`. [Controls closure](continuous-match-closed-controls-v2.json):18files/30,899bytes/conservative1,306,624; host0.718479s/protected0.035103s/peak24,571,904/noOOM/worker absent. [Safe proof](verify_continuous_match_controls_v2.py).

[ActualV2recipe](continuous-match-plan-run-v2.json), SHA `54573c32c46f359cbe0ffcb56b0228394c7ef09f081f12f98e6bedfc1a0c4b91`, is frozen for one execution at `data/coarse-quality/us-osm-continuous-match-run-v2/`. No actualV2result at this checkpoint. Require identical output for4completed V1areas and exact119record fifth-area prefix, with independent audit after closure.2GiB/zero swap/oneCPU/1800sworker/1860shost/64MiBtmp/128MiBfile/512MiBowned;61.8GBprior retained reserve includes failed80,056,320bytes, total stays below64GiB. No PBF/fine/native/provider/appDB. Matching/source/car/physical/usable/model caveats remain unchanged.


## Latest completed results and road-model decision

Continuous **controller V2 completed all 21 areas**, all 2,469 original records/85,629 positive midpoint weights/2,078.237959868 Census km. [Full report](continuous-match-raw/run-v2/report.json), SHA `bdc784b7fc6000228c592b1a5240686a8ba6214c567fa7ff2f29fabe6a85e25b`: 610 single geometric paths, 1,259 multiple paths, 594 no-path records and 6 explicit search caps. Conditional single-path unscoped numeric opportunity **263.253121 km / 12.6671%**. The new continuous policy has stricter whole-curve corridor/progress eligibility and retains rejected alternatives; this percentage is not an apples-to-apples accuracy improvement over V1 or a usable/physical/source admission.

Host **205.168694 s**, protected **204.200463 s** including binding/seals/22 derived-input traversals/adaptation/probes/connected enumeration/output, not routing-engine search or app HTTP time. Actual 2 GiB/zero swap/one CPU/64 MiB tmp/128 MiB file/512 MiB owned limits. Kernel peak **1,180,360,704 bytes**, 0 memory.max events/0 OOM/0 OOM kills. [Closed 76 files/374,960,483 bytes](continuous-match-closed-run-v2.json), conservative allocation **384,417,792**; worker/client zero and independently absent. The 1 GiB V1 failure remains preserved.

[Independent V2 audit](continuous-match-independent-audit-v2.json) passes every original weight/class/area, 24,946 raw native-part/node/geometry/lineage bindings, 7,475 saved candidate variant masks/weights/true node-ID joins and exact deterministic 50-record review selection. It also proves **byte equality of all four completed V1 area files and the 119-record fifth-area prefix: 71,853,104 bytes across five files**. Audit 11.837365 s, using only closed derived outputs/sealed audit SQLite/original small Census spans. Source/car/physical/usable/model flags remain false; the packet has not been promoted to independent physical-road approval.

The subsequent [frozen saved-candidate topology diagnostic](corridor-family-plan-v1.json), SHA `d4b59ed2673695f1c386e036289e20b1ccccad80a780892bcf0a24936c11b59c`, changes no matches. Eight Linux controls/no skips pass before classification. It asks whether alternative saved paths are overlapping subpaths of the same connected, acyclic native-node corridor with no branching. True branches/cycles/disconnected alternatives remain ambiguous. Every original case/class/weight and rejected-geometry context stays visible.

| Saved candidate-union topology | Records | Original Census km |
| --- | ---: | ---: |
| One unbranched native corridor | 983 | 876.856 |
| Multiple disconnected corridors | 701 | 284.008 |
| Branch or cycle | 185 | 263.068 |
| No saved candidate | 594 | 637.473 |
| Original search capped | 6 | 16.833 |

[Topology result](corridor-family-raw-v2/report.json): unbranched corridors whose parts all have supported road roles and unscoped numeric base limits support **449.928265 km / 21.6495%** of original Census weight. Raw access/direction/grade/physical/source applicability is still unreviewed; even this optimistic figure is below the original **50% usable-limit/matching** target. It does not establish that no better matcher exists or that OSM itself lacks useful information. The 80.751% raw numeric overlap remains a different, nonconnected statistic.

Topology analysis **2.148415 s after input bindings**, including 8 tests/read/classification/output, not graph search or total launch time. Actual 1 GiB/zero swap/two CPU/64 MiB tmp/network none/read-only derived inputs; kernel peak **455,303,168 bytes**, 0 OOM/0 kills. [Closed 31 files/1,777,562 bytes](corridor-family-closed-v2.json), conservative allocation **3,604,480**; worker zero and independently absent. A closer V1 full-stat comparison stopped while reading; [failure](corridor-family-closure-stop-v1.json)/used closer/partial mirror remain. V2 uses the established content-change stat key excluding access time; analysis/data unchanged. Prepared code copies are ignored at `data/coarse-quality/us-osm-corridor-families-prep-v1/code/`.

[Independent topology audit](corridor-family-independent-audit-v1.json) reconstructs all **2,860 candidate components** via a separate disjoint-set/degree implementation, plus every original identity/weight/class/area/mask and summary, in 1.939406 s. It does not infer car permission, physical uniqueness, publisher adequacy or nationwide accuracy. All stages are closed. Safe proofs (optional derived scans already passed; do not repeat just for docs):

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_continuous_match_run_v2.py
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_corridor_families_v1.py
```

**Decision needed:** continue cross-dataset Census enrichment research, or prototype a compact native OSM road backbone. [Concrete proposal and preserved gates](next-road-model-decision-v1.json). Recommended: a bounded **direct-OSM graph prototype** using the existing complete 21-area capture, true native node identities and degree-two contraction, first measuring topology/geometry/footprint. This could remove cross-dataset matching as a prerequisite; it is not a proven accuracy, national-footprint or Vercel-fit result. Keep the existing Vercel/TanStack app/PostgreSQL history and deployed v9; no new service or live routing DB is proposed. Native semantic policy still precedes ETA evaluation. A separate national count/footprint/input freeze follows only if the small prototype is promising; no new country PBF pass is included now.

Choosing this direction supersedes the current Census-enrichment workstream and its strategy-specific 50% matching screen, so user guidance is required before that material change. All old failures/results, generic arbitrary-location rules, 83/35 accuracy/physical/source/path checks, <=70 MB function, decoded <=162,238,546 bytes, first packaged estimate <=5 s and software/API/visual gates remain. Alternative: diagnose the preserved no-path/disconnected/branch/cap cases and specify one further generic matcher hypothesis; payoff is uncertain. No further producer, model switch, source replay, provider/paid/DB request, commit, push or deployment follows from this proposal.
