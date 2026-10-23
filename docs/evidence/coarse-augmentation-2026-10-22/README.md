# Offline Census augmentation pilot — October 22, 2026

This is a generic **offline candidate**, using the cached California partition to test the [source decision](../coarse-source-2026-10-22/README.md). Production and the app's active import remain v4. No routing/reference request, download, DB operation, env change or deployment occurred. No place/coordinate/region rule was added to query code.

## Candidate and physical model

`data/coarse-quality/census-augmentation-pilot-v1/grid.json` is ignored/local-only: **7,788,709 bytes**, SHA-256 `aca0fe8f62e463f3dee1ac64c2c3f993d1424ad9ca1c06715aa11cec3ad4e1f5`. The independent repeat at `data/coarse-quality/census-augmentation-pilot-v1-repeat/grid.json` is byte-identical. A fresh clone needs the pinned source ZIP/wheel and the offline builder; it does not contain this candidate. Source/tool locks and hashes are in [build.json](build.json); acquisition is documented in [local development](../../local-development.md#offline-road-source-pilot).

The adapter accepts repeated source-lock arguments, reads Polyline multipart sections independently, checks geographic NAD83/classes/counts and verifies source/tool hashes. California is an input partition, never a runtime region branch. Existing assumptions map S1100 to 105 km/h and S1200 to 80 km/h everywhere. These are not measured or calibrated speeds.

The candidate preserves v4 land/traversal/display masks, canonical positions, shore connections, legacy access, class assumptions and every existing road cost (or a cheaper added alternative). Each Census edge pays the original source arc at its class speed **plus both straight transfers to the unchanged anchors at 25 km/h**. Both transfers must be continuous land within the same country component, with no input-water tolerance. An explicit road arc can cross water; an invented transfer cannot. Source-only unsupported cells are skipped. This conservative fixed-anchor method can repeatedly charge transfers along a continuous road; it is still a coarse approximation, not a connector-aware road network.

The accepted additions are 1,004 new undirected link slots and eight improved existing slots. The builder rejects 229 edge visits for failed land transfers and eight for untraversable endpoints; these are visits, not unique slots. Every changed link retains source ID/partition/part and physical cost components in [build.json](build.json). The runtime decoder independently rejects supplemental visits whose transfer crosses water/country boundaries.

## Compact geometry and local resources

Little-endian base64 arrays store cell IDs, class speeds, point ranges, anchor indices and Int16 offset pairs. Packing is **lossless relative to the existing 1e-5-degree quantized visits**, not to original survey coordinates. All 26,946 v4 owner visits decode exactly, including bends, anchors and cumulative distances. Supplemental visits keep every distinct quantized bend, not a simplified chord; 2,212 visits contain 346,989 points, at most 1,851 in one visit.

| Geometry | Naive JSON bytes | Packed JSON bytes |
| --- | ---: | ---: |
| Existing v4 visits | 3,321,035 | 1,224,653 |
| Retained supplemental visits | 4,478,778 | 1,889,057 |

The entire augmented candidate is 206,433 bytes smaller than active v4's 7,995,142 bytes. This is one partition, **not a national size forecast**. Existing quantization moves an individual vertex by at most approximately 0.79 m; accumulated supplemental visit arc changes sum to +1.633 km, absolute sum 1.966 km, maximum absolute change 17.689 m per retained visit. These are measured quantization changes, not travel-time accuracy bounds. NAD83 is treated as approximate geographic degrees, without a survey-grade datum transformation.

Dense geometry exposed repeated polygon scans during attachment. Sorting candidates by charged time and checking land until the first valid one preserves the minimum and stable ties. [Before](physical-before-optimization.json) / [after](physical-checks.json), at the same 65 systematically sampled source inputs: median 92.223 → 1.116 ms; maximum 890.280 → 6.313 ms. Both complete 35-case comparison JSON outputs are identical across this optimization; v4 costs also match preserved evidence exactly. These are local sequential observations, not cloud percentiles or capacity claims.

The current decoder still expands all points to JavaScript objects. [Fresh-process retained-memory measurements](memory-candidate.json), with explicit GC and already-parsed inputs, show about 48.8 MB additional decoded heap versus about 19.7 MB for [v4](memory-v4.json). Whole-process peak RSS and decode timings are recorded separately; they include Node/tool/input effects and are not an isolated decoder peak or Vercel measurement. Reduce this expansion before nationwide scaling; compact disk bytes alone are insufficient.

## Saved comparisons against v4

[Comparison](comparison.json) checks **all 35 v4 baseline point costs against the preserved v4 report before evaluation**. Both sets retain every point as finite/reached/shaded. Common-finite denominators are unchanged.

| Development set | Cases | Mean absolute reference difference, v4 → pilot | Changes |
| --- | ---: | ---: | --- |
| Original San Diego | 11 | 22.181 → 21.944 min | One improves, ten unchanged |
| Broader regional | 24 | 34.234 → 31.204 min | Six improve, eighteen unchanged |

No sample regresses. These development sets guided the source assessment; they are not fresh holdouts or nationwide/long-horizon validation. Reference times are static modeled outputs, not observed driving truth.

[All 35 reconstructed paths](path-diagnostics.json) match the candidate point costs and component sums. Salton City–Bombay Beach falls 140.761 → 113.617 min versus a 61.268 min reference; its destination access falls 37.766 → 4.080 min, while 31.797 min of intercell local travel remains. San Diego–Big Bear falls only 194.170 → 191.560 min versus 150.413 min; intercell local travel is still 34.632 min. Palm Springs–Idyllwild stays 95.530 min versus 53.245 min, with access still 18.993 + 15.223 min. Closer source geometry alone does not fix the fixed-anchor/one-visit model or validate driving accuracy.

## Reproduction and verification

Run from the repository root, after restoring the [cached inputs](../../local-development.md#offline-road-source-pilot). Choose a **new** output name; the builder refuses overwrites and production-data paths:

```sh
mkdir -p data/coarse-quality/census-augmentation-replay-new
python3 -B scripts/build-coarse-augmentation.py \
  --source-lock docs/evidence/coarse-source-2026-10-22/source.json \
  --tool-lock docs/evidence/coarse-source-2026-10-22/tool.json \
  --output data/coarse-quality/census-augmentation-replay-new/grid.json \
  > data/coarse-quality/census-augmentation-replay-new/build.json
node --import tsx scripts/verify-coarse-augmentation.ts \
  data/coarse-quality/census-augmentation-replay-new/grid.json \
  data/coarse-quality/census-augmentation-replay-new/build.json
node --import tsx scripts/compare-coarse-candidate.ts \
  data/coarse-quality/census-augmentation-replay-new/grid.json
node --expose-gc --import tsx docs/evidence/coarse-augmentation-2026-10-22/measure-decoding.mjs \
  data/coarse-quality/census-augmentation-replay-new/grid.json
```

Fresh checks: **48 server tests, twelve geometry fixtures, 42 national active-v4 smoke cases, Biome (146 files), app/diagnostic typechecks, ordinary/Vercel builds and local generated-handler checks pass**. Tests cover lossless packed decoding, malformed arrays/ranges, bend/transfer costs, multipart isolation, narrow channels, separate islands and explicit road crossings. Structural checks cover every changed candidate edge, every unchanged v4 visit and 65 systematic supplemental inputs. No live DB suite was rerun because persistence is unchanged.

The local active-v4 generated handler is **13,451,510 bytes / 27 files**, with zero outbound fetches, no public dataset/secrets/raw inputs, disabled detailed research and DB-free history fallback. This does not deploy the candidate or measure cloud behavior. Hosted v4's earlier [verification](../coarse-hosted-2026-10-22/README.md) remains scoped to that deployed commit; no new browser/production check was needed.

The standard `npm test` launcher hit this sandbox's IPC restriction before running tests; [blocked output](blocked-test-runner.log) is preserved. The documented equivalent `node --import tsx --test src/server/*.test.ts` passes all 48. The first diagnostic typecheck invocation needed TypeScript 6's `--ignoreConfig`; the corrected strict check passes. No tool installation was needed.

[Provenance](provenance.json) records current source hashes as observations, not freezes on normal product code. [Checksums](sha256.json) seal this evidence only. Keep the original and failed evidence; write a new versioned run for future candidates. Next bound decoded geometry storage, then evaluate a nationwide augmentation using all 48 states plus DC with generic seam/dedup rules and source notices before activation. Do not trade the conservative paid transfers for free road switches or a blanket speed increase.
