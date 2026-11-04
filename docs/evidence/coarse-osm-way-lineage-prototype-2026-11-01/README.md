# Metadata-preserving way-lineage geometry prototype

November 1, 2026. **Complete, independently audited and closed.** The [national topology census](../coarse-osm-topology-census-2026-11-01/README.md) identified overconservative interior anchors. This prototype now verifies the replacement on actual captured road geometry: full source-way/relation metadata remains traceable offline, while membership of a way in a relation alone stops creating interior routing anchors. Explicit relation nodes, tagged nodes, selected-degree junctions, source-way ends and original window/outside-area anchors remain.

**All41original major-road native-distance pairs across21areas remain unchanged**, including8endpoints now inside contracted edges. No pairs are replaced and the graph is independent of validation-pair selection. Every143,560selected native point remains representable, with89,888internal aliases; independent source-derived prefix/suffix costs and full geometry preserve access without coordinate joins. These are native geometric queries, not the83ORS accuracy cases or an ordinary-car/timing model. The app remains deployed v9; work is local/uncommitted.

## Measured captured-data result

| Fixed major-road profile | Prior prototype | Way-lineage prototype |
| --- | ---: | ---: |
| Selected source ways / primitive edges |28,995 /148,961|28,995 /148,961|
| Selected native nodes |143,560|143,560|
| Routing anchors |62,520|53,672|
| Contracted edges |67,921|59,073|
| Routing arrays raw /gzip bytes |2,380,348 /1,729,690|2,061,820 /1,503,180|
| Full geometry raw /gzip bytes |2,287,696 /1,519,620|2,216,912 /1,503,280|
| Full geometry occurrences |216,882|208,034|
| Native connected components |41|41|

Every source-way ID/ordered reference-range partition and full native geometry survives. Paid native-point aliases live in offline provenance; their bytes are **not** a proposed Vercel runtime. Car access, direction, turns, cost policy, whole-country artifact, package/retained-app memory and request latency remain unqualified.

The separately measured whole-file [topology diagnostic](../coarse-osm-topology-census-2026-11-01/raw-audit-v1/audit.json) counts5,731,903anchors/6,674,747edges under the lineage rule. An f64-meter layout would need228,976,768routing bytes. A hypotheticalu16-cost layout would need148,879,804bytes, leaving only13,358,742bytes of the162,238,546-byte decoded-app budget before turn/overflow/snapping/geography/runtime overhead. **No time encoding, directed-car state graph or Vercel fit is admitted by this arithmetic.** It counts the entire acquired publisher file, not an exact continental subset; regional ratios are not extrapolated.

## Qualification, execution and independent verification

[Controls recipe](plan-controls-v1.json)/[single-use command](freeze-controls-v1.json), SHA`40cd5163f688c5dcc29522c7862506b2f87af57803b94df4ee79afe7406e5255`:12actual Linux tests/no skips and independent [tiny binary proof](tiny-artifacts-v1.json) pass. Fixtures compare all native-point distances with a separate Floyd oracle and cover closed/parallel/repeated/zero edges, distinct coincident IDs, 63-bit IDs, tagged/relation-node/way-end/window boundaries, source drift/caps and graph independence from query selection. [Admission](controls-admission-v1.json). Host0.717431s; controls34files/26,165logical bytes/conservative1,511,424; worker/client0/absent.

[Actual recipe](plan-run-v1.json)/[single-use command](freeze-run-v1.json), SHA`633806d5d8e4a8e9a2cd1735f5b512aec4140f0206327ea88d3f6f9d8298268d`, is USED at ignored `data/coarse-quality/us-osm-lineage-run-v1/`. Reads only the existing477,852,579-byte capture and unchanged old prototype report. Input1,368,072records/1,123,919nodes/239,253ways/4,900relations and all21area memberships remain intact. No countryPBF/fine/native-helper/Census/provider/applicationDB read. All3new producer/helper/test scripts are now immutable.

Actual2GiB/zero swap/1CPU/64MiBtmp/128MiBfile/256MiBowned. Host47.203545s/protected binding+validation+contraction+serialization+geometric checks46.379871s; these are neither ETA search nor HTTP timings. Kernel peak844,062,720bytes, zero memory.max/OOM/kill events.33closed files/13,712,064logical bytes/conservative15,151,104;13,667,792metered binary bytes stay ignored. Worker/client0 and independently absent. ReportSHA`9c9b2330d7d05e0bad9917c2f2501a43629696282a1545fefd10e924f31ccf7e`; artifact rosterSHA`14893fac0b6212b25c3318ed948824a1df87b45a58e48861d216a2ed8b281aec`.

[Separate audit plan](audit-plan-v1.json)/[freeze](audit-freeze-v1.json), SHA`819ee4fd65895413546d6575870bf549f65dd816f239faeb005324c73a2320c8`, passed against the sealed read-only independent captureSQLite plus serialized output. It checks every148,961primitive edge/59,073contracted edge/53,672anchor/208,034geometry occurrence/89,888internal alias and28,995source-way metadata partitions. Independent linked adjacency versus serializedCSR, full source geometry/paid aliases and an augmented virtual-point Dijkstra reproduce all41original pairs, including8internal endpoints;231,293independent settles. No producer/PBF/fine/provider/applicationDB execution. Two independent virtual-query chain/cycle/zero/disconnected fixture tests pass.

Independent audit6.507384s includes SQLite/artifact hashes, source metadata/geometry and serialized queries; host7.441851s includes bindings/lifecycle.2GiBzero swap/1CPU/64MiBtmp, peak488,185,856bytes, zero memory.max/OOM/kill events. Audit10files/16,991logical bytes/conservative1,183,744; worker/client0/absent. [Stored audit](raw-audit-v1/audit.json).

The first closer incorrectly required`artifacts.json`for an audit-only root. [Original closure stop](closure-stop-audit-v1.json) is preserved; no partial mirror or analysis rerun occurred. Separately versioned`close_v2.py`closes the unchanged successful audit. Every old source/recipe/helper/result and failed byte remains intact.

## Recovery and next work

Safe portable default proof reads repository code and small mirrors/stored independent results, with no ignored assets, native/Docker execution, large producer replay or provider/DB request:

```sh
python3 -B docs/evidence/coarse-osm-way-lineage-prototype-2026-11-01/verify_audit_v1.py
python3 -B docs/evidence/coarse-osm-topology-census-2026-11-01/verify_audit_v1.py
```

Never replay used producer/closer/audit commands or reuse old PIDs. Source, cached runtime/compiler, sealed SQLite and all binary/gzip/alias payloads are ignored/local-only and absent from a fresh clone. Rediscover owners from root`owner.json`if diagnosing a future job; all jobs in these completed stages are independently absent.64.5GBprior reserve includes all old assets/failures/censuses and stays within original4GiBzero swap/2CPU/four-hour/64GiBoverall; every new allocation must be added.

[Next implementation scope](next-cost-prototype-scope-v1.json): qualify a generic static-car/direction/access/turn/cost policy and compact time encoding on captured data, then freeze a bounded typed national builder. Existing parked generic car-policy helpers/fixtures can inform the reference; do not restart the detailed engine. No new executable country command or timing-model switch exists yet. Original83/35accuracy/physical/source/package/startup/API/visual gates remain; all48/6/29reference budgets remain consumed. App/env/DB/npm/Vercel configuration is unchanged.

The user selected road-only for the first nationwide timing model; vehicle ferries are deferred as non-core. All original reference/accuracy gates remain.

Final repository verification: npmcheck197files/typecheck/regular build all pass after implementation; both latest portable audit proofs and60-page/1,522-relative-link/anchor/diff checks pass. No app source/package/env change, new provider/applicationDB call, deployment, Vercel-target build or large source/audit replay for documentation.

## Subsequent road-only cost qualification

The [road-only car prototype and source audit](../coarse-osm-car-prototype-2026-11-01/README.md) now complete the previously proposed captured-data cost/encoding task. Vehicle ferries are deferred by the user. All 82 directional checks retain the original 41 geometric pairs and their reversals, including 14 unreachable results. This preceding geometry evidence and its frozen records remain unchanged; [current next steps](../../next-steps.md) govern further work.
