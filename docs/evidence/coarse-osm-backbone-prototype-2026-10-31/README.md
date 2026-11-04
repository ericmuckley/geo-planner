# Direct OSM backbone prototype

October 31, 2026. **The bounded prototype completed and passed its independent audit.** It builds geometry directly from native OSM node IDs, removing the Census-matching dependency for this experiment. All original 21 validation areas and the complete captured input are accounted for. [Selected user decision](decision.json), [outcome](outcome-v1.json), [next national-screen design scope](next-national-screen-scope-v1.json). Deployed v9 is unchanged; all new work is local/uncommitted.

## Measured topology and footprint

| Measurement | All captured highways | Fixed major-road subset |
| --- | ---: | ---: |
| Selected source ways | 239,253 | 28,995 |
| Selected native nodes | 1,123,919 | 143,560 |
| Primitive edges | 1,290,777 | 148,961 |
| Contracted vertices | 484,166 | 62,520 |
| Contracted edges | 651,024 | 67,921 |
| Edge reduction | 49.56% | 54.40% |
| Routing arrays, raw bytes | 21,434,572 | 2,380,348 |
| Routing arrays, gzip bytes | 14,321,763 | 1,729,690 |
| Full geometry arrays, raw bytes | 19,362,656 | 2,287,696 |
| Full geometry arrays, gzip bytes | 11,249,066 | 1,519,620 |
| Routing plus full geometry, gzip | 25,570,829 | **3,249,310** |

Major-road roles were fixed before actual access: motorway/trunk/primary/secondary/tertiary and their links. Every other role stays in the all-highway graph/source denominators. This is a geometric backbone experiment; selecting a role does not establish car permission. No city/coordinate/region-specific routing behavior is present.

Contraction stays within each original way. It preserves that way's endpoints, degree!=2 junctions **within each selected profile**, every tagged node, relation-member nodes/all nodes of relation-member ways, boundary-crossing segment endpoints and every outside-area node. It preserves parallel edges, loops, zero-length edges, exact original geometry, native IDs and source-edge partition/length. No joins are created from nearby coordinates. Original ordered-way/field/geometry seals are checked before construction; metadata remains traceable to the unchanged complete capture.

The complete capture is 477,852,579 bytes, SHA `efc36dc058b198711cc2666a751c9fd60b52d37902efbb22e1cba8b5f30f91f4`, with 1,368,072 records: 1,123,919 nodes, 239,253 ways, 4,900 relations. Three captured-data traversals perform qualified native metadata/geometry sealing, degree/tag/relation/coverage analysis, then contraction. No country PBF/fine index/native helper/Census dataset/provider/application DB is read by the producer. Raw metadata/provenance and source limitations remain in the [qualified capture](../coarse-osm-extraction-2026-10-30/README.md#latest-completed-results-and-road-model-decision).

## Verification and limits

Fifteen host and actual Linux controls/no skips pass: independent raw-versus-contracted all-pairs geometric oracle, junction/way/tag/relation/boundary/outside cases, closed loops/parallel/zero edges, coincident coordinates with different IDs, unknown role profiles, input/field/geometry/snapshot drift, every input/edge/geometry/query/heap/deadline cap, and binary/gzip roundtrip. The independently decoded tiny graph has two primitive edges contracted to one, with all three geometry nodes retained. [Controls recipe](backbone-plan-controls-v1.json), [closed 49 files/31,769 bytes](backbone-closed-controls-v1.json), conservative allocation 1,744,896. Host 0.705224 s/protected 0.035896 s, peak 24,948,736 bytes/no OOM; worker/client zero and independently absent. [Safe controls proof](verify_controls_v1.py).

The [actual recipe](backbone-plan-run-v1.json), SHA `2a2e6384c5cd388e48a39d02971e66fd4b8e75231d8b54d03a604416711726f1`, is USED/passed/closed. Root `data/coarse-quality/us-osm-backbone-run-v1/`; [full report](backbone-raw/run-v1/report.json), SHA `f90efccb069b6be8f3e348fd72686d80b56a844a37d0824d32420313317685eb`. [Artifact roster](backbone-raw/run-v1/artifacts.json). All four new helper/test/controller/closer files and used recipes/results are immutable; never replay the roots.

Host **54.908808 s**, protected **53.919933 s**, covering input bindings/seals/analysis/contraction/binary generation/gzip/native-meter validation queries/output. These are offline processing scopes, not ETA graph-search or app HTTP times. Actual 2 GiB/zero swap/one CPU/64 MiB tmp/128 MiB file/256 MiB owned, network none/read-only input. Kernel peak **1,025,335,296 bytes**, zero memory.max events/zero OOM/zero OOM kills. [Closed 48 files/113,260,775 bytes](backbone-closed-run-v1.json), conservative allocation **114,888,704**; worker/client zero and independently absent. Binary/gzip/provenance artifacts remain ignored; small metadata is mirrored. A fresh clone has the code and saved proof but lacks large cached source/runtime/graph/SQLite assets.

The producer checks up to two source-ranked native-anchor pairs per area/profile, without substitutions. All 21 areas have at least one pair for both profiles: **42 all-highway pairs (41 reachable/one unreachable) and 41 major-road pairs (all reachable)**. Reachability and geometric-meter distance agree before/after contraction. These 83 native-length comparisons are **separate from the saved 83 ORS accuracy references**; no provider call occurred. Captured graph components (1,007 all-highway/41 major) remain identical through contraction and describe the captured regional graphs, not country connectivity.

[Independent actual audit](independent-audit-v1.json), **15.909115 s**, reconstructs source nodes/ways/memberships/relations from the separate sealed read-only acquired-file audit SQLite. It verifies every primitive-edge partition, all 718,945 contracted edges, 546,686 anchors, 2,158,683 geometry occurrences, protected metadata/coverage context, exact serialized CSR against an independent linked-adjacency representation, profile/role/area accounting, gzip bytes and independently ranked/raw/contracted distance comparisons. Its separate Dijkstra settles 1,600,204 native vertices across the checks. It calls no producer or PBF/fine/native/provider/application DB. Default proof reads small saved records/audit only; optional derived graph/SQLite audit already passed and should not be repeated for docs:

```sh
python3 -B docs/evidence/coarse-osm-backbone-prototype-2026-10-31/verify_controls_v1.py
python3 -B docs/evidence/coarse-osm-backbone-prototype-2026-10-31/verify_run_v1.py
# Optional only when local derived artifacts need rechecking:
python3 -B docs/evidence/coarse-osm-backbone-prototype-2026-10-31/verify_run_v1.py --local-assets
```

All graph metrics here are **undirected geometry only**. Ordinary-car access/direction/turn costs, ETA/traffic accuracy, nationwide coverage, countrywide decoded memory/package size and first Vercel estimate/startup remain unqualified. Array payload bytes exclude app code, route-search heap/cache/decoder overhead and source metadata. Gzip files are a lossless offline measurement, not a measured Vercel function. Twenty-one areas cannot establish national size or accuracy. Normal check197/typecheck/build pass; no app/UI/env/DB/npm dependency/deployment change.

## Next step

The prototype is advantageous enough to investigate a native national backbone: it preserves selected source topology directly and avoids failed cross-dataset alignment. [Next bounded design scope](next-national-screen-scope-v1.json): prepare/qualify a new metadata-only national by-role/profile/reference census using the cached country source. Measure actual national cardinalities and conservative storage/work bounds before allocating any national graph. This is a design/implementation task, not an executable country recipe; no country pass has been performed or enabled by the completed prototype.

Count the whole acquired publisher file and preserve every original source EOF/typed/semantic/raw hash/state guard. Role counts alone do not establish exact continental-only inclusion or unique junction/anchor counts. Large raw upper bounds do not prove a contracted graph cannot fit; if needed, prepare a separate exact topology census. Do not extrapolate regional compression ratios, drop cases/roles post-result or start national graph construction before measured capacity supports it. Keep the overall 4 GiB/zero swap/four-hour/64 GiB envelope, reserve at least 62.6 GB prior work, and freeze exact new code/input/resource limits after synthetic qualification.

V9 stays live. A separate native direction/access/car-cost policy freeze precedes ETA evaluation; every original application accuracy/physical/source/path/package/startup/API/visual gate remains. No new routing-provider quota, paid service or application DB request is proposed.
