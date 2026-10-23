# Bounded coarse geometry decoding — October 22, 2026

The existing [offline augmentation candidate](../coarse-augmentation-2026-10-22/README.md) now uses lazy packed geometry. **V4 remains active** and no artifact, road cost, speed, source or query geography changed. No new data acquisition, reference/provider request, DB/env/dependency change, detailed build or deployment occurred. The candidate and source/tool caches remain ignored/local-only; runtime support/tests/docs are uncommitted at HEAD `637746c`.

## Implementation and exactness

`src/server/coarse-data.server.ts` retains base64-decoded packed buffers and a fixed-size Uint32 cell index. Every visit is validated during load using the same anchor, bend, class, duplicate-point and continuous-land transfer checks. `get(cell)` materializes only that visit, including exact coordinates and cumulative distances, with **no cache**. Iteration yields one visit at a time. Repeated reads cannot mutate stored geometry or accumulate point objects. Legacy JSON visits keep their existing Map behavior, so active v4 still uses its original data path.

`RoadVisits` in `src/server/coarse-grid.ts` describes only the required size/get/iteration operations. The physical verification now compares visits one at a time rather than depending on the storage container's shape. [All 35 saved comparisons](comparison.json) and [complete reconstructed paths](path-diagnostics.json) are JSON-identical to the earlier candidate, with every v4 baseline cost checked against preserved v4 evidence. All 26,946 owner visits decode exactly; all changed links and supplemental transfer costs pass [physical checks](physical-checks.json). All 42 active-v4 national cell counts match the prior run. The original candidate remains **7,788,709 bytes / SHA-256 `aca0fe8f62e463f3dee1ac64c2c3f993d1424ad9ca1c06715aa11cec3ad4e1f5`**; no producer or rebuild was needed.

## Local memory and query observations

Measurements use fresh Node processes, explicit GC and already-parsed encoded input retained. Incremental decoded storage includes both heap and ArrayBuffer changes; this does not count the encoded input/parser/bundle/tool footprint as decoded geometry.

| Candidate decoder | Retained heap delta | Retained ArrayBuffer delta | Sum |
| --- | ---: | ---: | ---: |
| [Earlier eager decoder](../coarse-augmentation-2026-10-22/memory-candidate.json) | 48,834,552 B | 3,076,192 B | 51,910,744 B |
| [Lazy decoder](memory-candidate.json) | 246,136 B | 6,636,314 B | 6,882,450 B |

This observed incremental storage falls approximately **86.7%**, from 51.91 MB to 6.88 MB. Buffers increase because packed coordinates/indexes replace point objects; reporting heap alone would hide that cost. [Unchanged legacy v4](memory-v4.json) retains approximately 19.68 MB additional heap plus 3.07 MB buffers. Decode validation still examines every point: one fresh candidate observation is 946.5 ms, not a claimed cold-start improvement. Whole-process RSS/peak values are recorded separately and include Node/tool/input/query effects; none is a Vercel or isolated decoder peak measurement. Nationwide sizes remain unknown.

[Three complete sweeps](memory-sweeps.json) cover all 2,212 supplemental visits each time, totaling **6,636 query inputs** and 346,989 source points per sweep. After GC, retained heap growth relative to the decoded state is 125,736 / 127,136 / 127,936 bytes, with zero added buffers. The verifier rejects eager decoded heap growth over 2 MiB on load, or query retention over 2 MiB heap / 64 KiB buffers after each sweep. These allowances detect accidental object retention in this local fixture; they are not a production memory budget.

All-cell attachment medians are 1.288 / 1.273 / 1.281 ms, maxima 313.748 / 313.593 / 322.585 ms. Dense coastal/failed-access cases cost more than the earlier **65-input** sample (current median 1.420 ms / max 7.587 ms). The sample populations differ; do not compare their maxima as a regression or treat these as cloud percentiles. Temporary allocations and geography scans still affect process peaks/query time; the change bounds **retained** decoded geometry, not all runtime memory or CPU.

## Reproduction and checks

The ignored candidate already exists locally. Fresh clones can restore it through [the source locks and offline builder](../../local-development.md#offline-augmentation-candidate). To check current code without rebuilding or network use:

```sh
node --expose-gc --import tsx scripts/verify-coarse-memory.ts \
  data/coarse-quality/census-augmentation-pilot-v1/grid.json
node --import tsx scripts/verify-coarse-augmentation.ts \
  data/coarse-quality/census-augmentation-pilot-v1/grid.json \
  docs/evidence/coarse-augmentation-2026-10-22/build.json
node --import tsx scripts/compare-coarse-candidate.ts \
  data/coarse-quality/census-augmentation-pilot-v1/grid.json
node --expose-gc --import tsx docs/evidence/coarse-augmentation-2026-10-22/measure-decoding.mjs \
  data/coarse-quality/census-augmentation-pilot-v1/grid.json
```

**49 server tests, twelve Python geometry fixtures, 42 national smoke cases, Biome (147 files), app/strict diagnostic typechecks and ordinary/Vercel builds pass.** Expanded malformed-visit tests exercise both encodings; tests preserve every v4 visit and check independent reads/missing cells. The no-cache sweep above separately checks retained growth across all supplemental locations. Local active-v4 Vercel handler: **13,452,189 bytes / 27 files**, zero outbound calls, no client dataset/secrets/raw inputs, detailed research disabled and no-DB history fallback. No live DB suite, new hosted verification or browser check was needed for this server-only representation change.

[Provenance](provenance.json) observes current source hashes, not freezes on normal product code. [Checksums](sha256.json) preserve this measured run; older evidence and failed attempts stay unchanged. Next process all contiguous-US Census partitions through a generic acquisition/seam/dedup pipeline, measure actual nationwide sizes/resources and evaluate before activation. This storage change preserves the pilot's remaining large route errors; it does not validate nationwide driving accuracy.
