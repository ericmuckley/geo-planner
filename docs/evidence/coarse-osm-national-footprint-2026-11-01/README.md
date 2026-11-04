# Native national footprint census

November 1, 2026. **Passed, independently checked and closed.** The approved [native geometry prototype](../coarse-osm-backbone-prototype-2026-10-31/README.md) now has actual whole-file class/reference counts. The deployed v9 app is unchanged; all new work is local/uncommitted.

The fixed major-road profile contains **4,227,238 ways / 48,163,649 references / 43,936,411 primitive edges**. Carrying the entire acquired file in the prototype's full-geometry runtime format would require **at least311,017,288 decoded bytes**, above the162,238,546-byte app budget even before JS/search/app overhead. This is a mathematical lower bound for that format, not regional extrapolation or a rejection of leaner representations. It counts the entire publisher file; it does not establish an exact continental-only subset or compressed function size.

The subsequent [exact topology census](../coarse-osm-topology-census-2026-11-01/README.md) and [actual way-lineage prototype](../coarse-osm-way-lineage-prototype-2026-11-01/README.md) are now complete. The active next task is a car-cost/encoding prototype, with full source geometry preserved offline. No native graph has been constructed nationwide and no ordinary-car/ETA/model/package/coverage gate is admitted.

## Measured counts

| Whole acquired file | Ways | Full references | Primitive edges |
| --- | ---: | ---: | ---: |
| All highway roles |52,053,199|509,547,029|457,493,830|
| Motorway/trunk/primary/secondary/tertiary and links |4,227,238|48,163,649|43,936,411|
| All ways including non-highways |162,688,797|1,867,096,915|1,704,408,118|

All111raw highway role values remain distinguishable, including unknown/empty values if present; profile exclusions are explicit. All1,148highway ways longer than1024references are included. The old508,093,741examined-reference probe counter is not the509,547,029delivered-reference denominator.

The source has48,142,518tagged nodes and480,196`type=restriction`relations. All relation member occurrences:1,201,443node /13,455,382way /30,832relation. Restriction member occurrences:424,719node /1,009,605way /4relation. Counts describe metadata context, not car applicability, resolved dependencies or legal travel.

## Guarded execution and closure

[Build](plan-build-v1.json)/[freeze](freeze-build-v1.json): cached compiler/header/runtime only, ABI7artifact2,005,904bytes/SHA`7d2ba9e6c9b6a583bf497acd1cfce6b74c7e0794d293c0efba5c83d91014dbb9`. Host13.999303s; kernel peak461,475,840bytes. [Controls](plan-controls-v1.json)/[freeze](freeze-controls-v1.json): all23targetLinux tests/no skips pass;0.420s test suite/1.971215s host/62,550,016-byte kernel peak. Independent fixture counters, original semantic seal, typed storage arithmetic, bindings and ownership pass. [Controls admission](controls-admission-v1.json).

[National recipe](plan-run-v1.json)/[exact single-use command](freeze-run-v1.json), SHA`1080fc05fc55e52df78b7cca4903f1269327f353e4d77c76cd29c24f0a2ee36f`, is USED at ignored `data/coarse-quality/us-osm-footprint-run-v1/`. Same cached12,229,320,016-byte source SHA`1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff`, MD5`c5abaec55e724255277f22fb97941e5a`, state2026-10-25T21:21:21Z. Full native EOF counts1,606,229,364nodes/162,688,797ways/1,624,265relations and all-field semantic SHA`209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16` match the original seals. Per-type metadata and every legacy compared counter agree. Continuous framing/header/raw SHA+MD5 and complete posthash guards pass. Guard reads24,458,640,032bytes exclude the decoder's own source IO; no extra host source hash.

Actual4GiB/zero swap/2CPU/networknone/read-only,256MiBtmp/64MiBfile/64MiBowned. Kernel peak4,294,967,296bytes includes file cache/reclaim;15,281memory.maxevents, zero OOM/kill, Docker reports no OOM. Host783.830444s; protected worker binding/scan/output781.945427s, including framing109.292907s/native validation+codec+summary661.902384s/posthash10.683792s. These are input-processing scopes, not routing/ETA/HTTP latency. App checks ran on the shared host during the census, so this is no quiet-host performance benchmark.

[Closed build](closed-build-v1.json):20files/3,365,676logical bytes/conservative4,640,768. [Controls](closed-controls-v1.json):15files/315,143bytes/conservative1,540,096. [Actual](closed-run-v1.json):13files/327,197bytes/conservative1,531,904. All three worker/client exits0 and workers independently absent. Actual receiptSHA`0bff10741a66a14b970825d359593998830e7e150b2babb26aec9f311aba2c82`; boundsSHA`1c2fc8c85b8763ff34f3c826dde2a72ca2c3f3673272c78c99000eb8f3dabdde`. Small records are mirrored here; native binary and cached tools/source remain ignored/local-only. Every used helper/controller/recipe/producer/result is immutable. Never replay a completed command/root.

## Interpretation and next implementation

[Count-based interpretation](interpretation-v1.json)/[binding](interpretation-binding-v1.json) preserves strict lower and conservative upper bounds. Each selected source way contributes at least one retained edge, giving routing+full-geometry lower bound`4*primitiveEdges+32*ways+28`for a nonempty graph. Major-road routing alone is bounded below by101,453,728bytes, so cardinalities do **not** decide whether a contracted routing-only format fits. No compressed-size or continental-subset forecast is treated as a measurement.

[Exact topology census design](topology-census-design-v1.json) uses native fixed occurrence chunks and sorted metadata streams. Its measured-count design arithmetic is1,775,576,920spool bytes including sorted relation copies; native source-node presence needs1,789,963,563bytes at the sealed max node ID. These are design allocations, not tested actual memory/time/IO. They leave room for implementation under the original4GiB/zero swap/2CPU/four-hour/64GiB envelope, with prior retained assets and every new allocation explicitly reserved. Preserve source identity and every old failure; no graph/coordinate dictionary/fine index, provider request, appDB write or deployment.

The subsequent standalone fixed-record topology sort/count kernel was implemented at `scripts/coarse_osm_topology_kernel_v1.cpp`/`.py`/`_test.py`. Its eight host-native controls pass, including100seeded independent graph/anchor/edge-partition cases, loop/parallel/repeated IDs, typed sort/multiset/order/truncation/cap and metadata checks. The temporary host library was not a Linux-qualified artifact at this historical checkpoint; subsequent actual Linux qualification/source execution and independent audit are recorded in the linked topology report. Do not replay them.

V1read-only proof of small mirrors and bound cached code/runtime files (no native execution/Docker/PBF/index/provider/applicationDB access). This older checker requires the ignored cached site/runtime bindings; portable current proofs are in the topology/lineage reports linked above:

```sh
python3 -B docs/evidence/coarse-osm-national-footprint-2026-11-01/verify_v1.py
```

Normal check197/typecheck/build pass for the completed census code. Full geometry, permissions, turns, cost policy, original83/35accuracy and physical/source/coverage/package/startup/API/visual gates remain separate.
