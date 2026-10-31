# Bounded road-batch prototype and lookup measurement

October30,2026. **Prototype qualification passes206 actual Linux tests/no skips.** Controller V1 qualification stopped in a disk-space test harness before native scanning; preserved unchanged. A separate V2 qualification corrects only the mocked host disk and passes7target controls plus full200way/400coordinate fixture proof. The separately frozen national batching measurement passed and is closed. Deployed v9/app/model remain unchanged.

The [preceding national screen](../coarse-osm-country-exec-2026-10-30/README.md) passed both full-source metadata/census passes, fixed lookup cohorts, reference audit and resource/storage checks. It measured14,503,453,128logical national index bytes, but allocated only eight fixed source-ordinal portions. A full extraction still needs practical road-coordinate lookup behavior. The earlier per-way interface would authenticate large files separately for each road; this prototype groups eligible ways while preserving the frozen per-batch full-shard integrity policy.

New ABI0x40000 retains the complete V4 metadata/ID/order/copy/canonical/semantic/coordinate/reference/member/source/EOF guards and4MiB source/8MiB frame policy. A new callback emits ordered eligible highway ways in batches bounded by2048ways,65536references and8MiB. Selection uses exactly the prior fixed probe-source ranges and existing2–1024reference rule; all source objects are still validated/sealed. This is a validation-workload filter only, not a routing rule or national representativeness claim. No city, coordinate, region or outcome-selected exception.

[Qualification freeze](qualification-freeze.json):206 actual target Linux tests/no skips, retaining all170 prior controls and36new/ported V5 controls. Batch count/reference/byte boundaries, complete source-order/field/seal equivalence, actual PBF batch delivery, invalid unselected metadata, budget/callback stops, old-consumer ABI refusal and original guards pass. Persistent positive proof compares all200way fields against an independent500-object reference, then verifies all400reference coordinate bits/order/duplicates with the frozen authenticated reader.

Four new used/immutable producers: `coarse_osm_country_screen_v5.cpp`, bridge, tests and `run_osm_country_screen_v5.py`. The runner qualifies synthetic/decoded-fixture controls only; it does not run a national measurement. Artifact2,003,456bytes/SHA`9c81c86e3605738430b1c8f9f762bce71830740e5c46737485371ef8c0561166` at ignored `data/coarse-quality/us-osm-country-controls-v5/build/country-screen.so`. Both workers/client0/not OOM/independently absent.61closed files/3,618,659bytes;60non-library mirrors. Host25.472s covers input/compiler/build/tests/proofs/lifecycle, not source throughput. No national or saved PBF read; two captured decoded relation fixtures remain explicit. All original failures/source/index/tools remain preserved.

The separately versioned bounded measurement controller now uses the existing source and readonly probe: one full guarded native scan, all274,570previously counted eligible highway ways, bounded batched coordinate lookups, exact whole-source seal/count comparison and explicit IO/row/time/resource accounting. No full national-index allocation, road output,21-window extraction, attributes, model/accuracy/package/API/deploy admission follows. Preserve all used code/recipes; do not replay qualification.

## Controller qualification recovery

V1 controller/test/recipe are USED/stopped at`data/coarse-quality/us-osm-way-batch-controls-v1/`. Seven tests ran; the Docker-name test used the real256MiB temporary disk inside Linux and tripped the production2GiB free-space guard before its mocked create call. It failed in the harness, with no native source scan. Preserve the original evidence. V2 uses the same production limits and a mocked8GiB host disk in that test; seven host tests pass.

V2 qualification [freeze](controller-qualification-freeze-v2.json)/recipeSHA`80fbc842fb5c1f80ea48001fb9ff27e9e51c9e857a719d49927658a4cd6d4850` is USED/passed/closed at`data/coarse-quality/us-osm-way-batch-controls-v2/`. Inspect the owned output/actual owner before recovery; never replay either attempt. The qualification reads only the existing500-object synthetic PBF and its tiny readonly index, then checks all200ways/400coordinate references. The independent [controller proof](verify_controller.py) passes; both qualification workers are independently absent. V1 closed14files/109,588bytes; V2 closed18files/123,312bytes. V2 host1.524s includes bindings/tests/synthetic scan/lookup/audit/cleanup, not national performance.

The separately proposed national measurement uses one full-source scan and bounded selected road batches, writes typed reference/coordinate witnesses, and independently checks every returned coordinate bit with the frozen Python reference decoder. New administrative caps are explicit:3000s protected scan+lookup case/900s separate reference audit/4200s worker/4800s host;8million references/512batches;32GiB authenticated lookup IO and1.024billion decoded rows/250k calls **per** native-reader and independent-reader stage.4GiB zero-swap/twoCPU/1GiB owned+tmp/64MiB files/1024entries remain. IO/row limits are stop bounds, not forecasts or changes to the earlier passed4GiB-IO screen. No full index allocation or model/source suitability admission.

## Completed frozen measurement

[Exact measurement freeze](measurement-freeze-v2.json)/recipeSHA`55a558f4575682d70ff3df009b104e5119eb72194aa639fd9d2cbd7fdc72c175` is **USED, passed and closed** at`data/coarse-quality/us-osm-way-batch-run-v2/`. All four helper producers and both V2 controller/test files remain immutable. Same saved sourceSHA`1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff` and readonly fixed eight-shard probe from the sealed national run. No source/index producer replay, acquisition, provider or DB call; this is one newly frozen batch measurement, not a full index allocation.

Inspect the owned output's`owner.json`, actual exact process/container ownership, newest`progress-*.json`, ledger, source-and-lookup receipt, independent audit and final result/cleanup records. Rediscover ownership; do not trust an old PID/tool session. Never rerun, rename, top up, raise caps or overwrite an existing output. A stop remains evidence; choose only a separately versioned generic diagnosis afterward. App check/typecheck/build were run during host binding/startup; shared-host timing and uncontrolled OS cache remain explicit.

Required and passed: full native source counts/metadata/hash/semantic/normal EOF matching the prior corpus, exactly274,570eligible ways delivered in source order, bounded repeated/duplicate coordinate requests, every written coordinate occurrence independently checked against the frozen Python decoder, all IO/row/storage/time/resource gates, exit/OOM and independent exact owned absence. No broader routing/accuracy inference or full extraction admission from this fixed validation workload.

Safe completed proofs only, no Docker/native/national reads:

```sh
python3 -B docs/evidence/coarse-osm-way-batch-2026-10-30/verify_qualification.py
python3 -B docs/evidence/coarse-osm-way-batch-2026-10-30/verify_controller.py
```

## Closed measurement result

All1,770,542,426source objects reach normal native EOF with exact prior counts/metadata/typed IDs/order/source hash and complete semantic seal.135batches deliver all274,570eligible ways/2,135,008reference occurrences. Selected way-field canonical seal`85c1a4f165c600ed05ae194be1f46c618b9379e4808a59a09054f02486c7e6d0`; every ordered coordinate/duplicate is preserved, witness seal`258fd506bedb017097fc6f8bd03eaa1bd777ef88ef47bba7542988422eb5eb7a`.

Native reader points()32.626820s;9,460,848,817authenticated shard bytes,69,544,680decoded rows/16,979codec calls and17,709,705catalog bytes. Hash/format8.029045s and block-decode16.446030s are included, not additional end-to-end times. A separate independent Python reader checks every coordinate in71.742157s with the same9,460,848,817authenticated bytes/69,544,680rows/16,979calls. Each stays within its own32GiB/1.024billion-row/250k-call budget; combined authenticated probe IO18,921,697,634bytes excludes source reads and other IO.

Case716.023650s before source-and-lookup record close, protected through close by the3000s hard timer. Native606.622551s includes callback field parsing, coordinate queries and witness writes; framing100.434084/post-source hash8.950664s are separate. Independent audit seconds exclude its own result serialization. Host809.842328s includes source binding/worker/cleanup and excludes final host-summary serialization. These are selected probe workload timings with uncontrolled OS cache, not nationwide routing/graph-search forecasts.

Cgroup peak4GiB includes page cache/reclaim; oom/oom_kill0, Docker not OOM. Observed conservative worker output allocation54,128,640bytes (logical51,388,848/allocated51,761,152;161entries) excludes final metrics serialization/host journals. Closed164files/51,390,722bytes,135typed witness payloads remain ignored; other records mirrored unchanged. Process rchar55,867,299,010/wchar51,279,175/read_bytes0/write_bytes51,279,175 are kernel counters, not physical national-file byte accounting. Zero read_bytes does not mean zero IO. Worker/client0/owned removal/separate exact absence pass.

[Portable result proof](verify_measurement.py) verifies frozen source/batch/ledger/budgets/lifecycle receipts. `--local-assets` hashes ignored inputs/witnesses, decodes the probe once by shard and independently verifies every coordinate occurrence/duplicate/order against saved witness bits. Both proofs pass; no native/Docker/national PBF read. No second national road-field oracle or nationwide accuracy is claimed.

```sh
python3 -B docs/evidence/coarse-osm-way-batch-2026-10-30/verify_measurement.py
python3 -B docs/evidence/coarse-osm-way-batch-2026-10-30/verify_measurement.py --local-assets
```

Next: [one typed-ID lookup prototype and fixed saved-query replay](../coarse-osm-lookup-2026-10-30/README.md), avoiding another national source scan. App check197/typecheck/build pass. Deployed v9/data/env/Postgres/npm/Vercel remain unchanged; all original source/21-window/attributes/matching/physical/accuracy/model gates stay held pending their own evidence.
