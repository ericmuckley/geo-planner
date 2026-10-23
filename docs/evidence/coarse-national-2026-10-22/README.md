# Nationwide Census augmentation — October 22, 2026

**The nationwide offline candidate is built and checked; v4 remains active.** All 48 contiguous states plus DC use the same source release/classes, fixed v4 anchors, physical costs and geography rules. There are no named-route, coordinate or query-region exceptions. This completes the [source pilot](../coarse-source-2026-10-22/README.md) and [bounded-storage](../coarse-memory-2026-10-22/README.md) scaling step. Initialization latency still needs improvement before activation.

## Sources, recipe and artifact

The [Census 2026 release](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) and [primary/secondary-road catalog](https://www2.census.gov/geo/tiger/TIGER2026/PRISECROADS/) supply the offline inputs. [Captured catalog](catalog.html), [49 source locks](sources.json), [acquisition](acquisition.json) and [offline verification](source-verification-final.json) record **289,239,748 bytes**. The cached California file was reused; 48 missing files downloaded 276,518,840 bytes. Subsequent verification downloads nothing. FIPS selection excludes Alaska, Hawaii and territories during data preparation only. The downloader checks existing locks, preserves cached bytes, and checks a pinned manifest before installing a fresh download. Interrupted/unexpected downloads are not silently substituted.

The accepted local-only artifact is `data/coarse-quality/census-national-v2/grid.json`: **39,976,621 bytes**, SHA-256 `119a463d0a876bc83761efb235e1a8a7d9f9105c990b720c9751699c7076b95d`. The independent repeat at `data/coarse-quality/census-national-v2-repeat/grid.json` is byte-identical. [Build](build.json), [repeat](repeat-build.json), [resources](build-resources.json) and [provenance](provenance.json) record inputs and production. All source/tool/candidate/probe directories are ignored/local-only; a fresh clone needs the recovery commands below. Active v1–v4 artifacts and the earlier pilot remain unchanged. The legacy pilot command still reproduces its original hash; exact dedup is enabled by the national-manifest recipe or explicit `--deduplicate`.

49 partitions contain 261,861 records, 261,862 parts and **27,774,778 source points**. The adapter verifies NAD83/Polyline/class/counts and keeps multipart boundaries separate. Exact geometry plus class, independent of direction/source ID, removes 38,470 duplicate parts, including 168 found across partitions. It does not merge nearby/distinct bends or classes. Partition links union through shared canonical grid cells with paid transfers; unrelated line parts do not acquire invented connecting geometry. Synthetic seam/class/bend tests cover these rules.

## Physical model and preserved rejection

The candidate retains every v4 anchor, land/traversal/display mask, shore/access path, class assumption and original road alternative. Census S1100/S1200 use globally assumed 105/80 km/h speeds. Each accepted edge pays the source arc plus both continuous-land transfers to canonical anchors at 25 km/h. It adds **36,742** link slots and lowers 73 existing costs. Failed transfers reject 3,773 edge visits; untraversable endpoints reject 39. These are visits, not unique slots. One supplemental visit per cell still limits access and repeated canonical transfers can remain slow. Grade/turn/access/traffic topology is unmodeled.

The first national version reproduced exactly but failed the strict source-arc/chord bound on fourteen retained links: maximum shortfall about **10.868 mm**, from linear interpolation of geodesic samples. [Diagnosis and original records](failed-v1/arc-failure-diagnosis.json), [failure](failed-v1/physical-check-failure.txt) and [rejected summary](failed-v1/build-summary.json) are preserved; raw original/repeat artifacts/reports remain local under `census-national-v1*`. No tolerance was widened. V2 universally bounds interpolated source arcs by their endpoint geodesic distance while retaining source bends. Across all candidate edge visits, 126 corrections add 0.486 m total; **no rounded encoded edge cost changes** versus v1. V2 passes every changed-edge physical/transfer/key check. The earlier `time -l` wrapper could not query `kern.clockrate`; v2 uses Python child-resource capture instead, without a capped/cloud resource claim.

## Geometry, national smoke and saved comparisons

51,159 supplemental visits retain **6,220,841** quantized points (maximum 1,851 per visit). Their naive JSON size is 80,806,588 bytes; packed size is 34,064,677 bytes. All 26,946 original owner visits decode exactly. Packing preserves bends at the existing 1e-5-degree resolution; per-vertex displacement is at most about 0.79 m, with retained supplemental arc changes totaling +23.157 km / 31.715 km absolute / 33.229 m maximum per visit. These describe quantization, not accuracy. NAD83 is used as approximate geographic degrees without a survey-grade transformation.

[42 national smoke cases](national-smoke.json) pass 6/10/12h budget monotonicity, connected-sample, geometry-size and no-lost-v4-count checks. Thirty-nine cases reach more cells; the three Nantucket cases remain isolated. Counts do not prove actual road access, all-origin completeness or national travel-time accuracy. Samples are shared between active-API and offline checks in `scripts/coarse-smoke-cases.ts`, never imported by runtime routing.

[Saved comparisons](comparison.json) still check all 35 v4 baseline costs against preserved evidence. Both sets retain every case as finite/reached/shaded. Original point mean absolute reference difference is 22.181 → 21.944 min (one improves, ten unchanged); broader mean 34.234 → 31.204 min across all 24 cases (six improve, eighteen unchanged). None regress. All [35 path sums/components](path-diagnostics.json) reconstruct and match the pilot's paths. These development sets have no new nonregional driving references; national accuracy remains unvalidated. Big Bear/Palm Springs limitations remain.

## Runtime and Vercel observations

[Memory sweeps](memory-sweeps.json) measure **31,021,957 bytes** incremental retained decoded heap + buffers, with encoded input already parsed and retained. Three complete sweeps at validated on-land source anchors total **153,477 inputs**. After GC, heap growth is 114,152 / 115,840 / 116,016 bytes and buffer growth zero. Median local attachment times are 1.361 / 1.315 / 1.312 ms; maxima 69.501 / 9.974 / 13.080 ms. Rejected v1's [first-vertex sweeps](failed-v1/memory-sweeps.json), which include generalized-water points, are a separate stress population and also retain bounded memory. Do not compare their maxima as equivalent user-query latency. Whole-process peaks and transient allocation remain separate from retained storage and cloud budgets.

An isolated source/config copy uses this candidate solely for [local package/handler checks](package-probe.json). It copies no env files/credentials/raw sources and never switches the real app. The generated function is **43,779,753 bytes / 27 files**; coarse estimates, disabled detailed research, server-only data/secrets and no-DB fallback pass with **zero outbound calls**. [First local computation](vercel-handler.json) takes **22,201.6 ms**, then Denver/New York take 26.0/65.9 ms in that same process. The first computation includes dataset decoding/validation after the configuration request; it is not total process startup or proven Vercel cold latency. Standalone concurrent validation observations are also recorded and can be slower. No cloud deployment, peak-memory or load-capacity claim follows.

**Do not activate yet:** reduce initialization work while preserving full source/geometry/land validation and exact outputs. Candidate response attribution/source-release/warnings also still need the Census credit/derived-data notice before activation; the probe is a packaging experiment, not the final product copy. The [2026 citation guidance](https://www2.census.gov/geo/pdfs/maps-data/data/tiger/tgrshp2026/TGRSHP2026_TechDoc_Ch1.pdf) requests source credit and a conspicuous repackaging statement. This is an implementation follow-up, not a request for user approval or a reason to revisit the parked detailed engine.

## Checks and reproduction

**49 server tests, fifteen geometry fixtures, check (137 files), app/strict diagnostic typechecks, ordinary/Vercel builds and both active-v4/candidate handler checks pass.** Biome now excludes ignored `data/` so isolated source copies and frozen/local assets are not checked as application code. Current active-v4 counts and packaging remain unchanged. No routing/reference/service request, DB/env/dependency change, research build or deployment occurred; network use was public source/catalog/document reads only.

Restore pinned catalog/manifest on a fresh clone before acquisition (preserve any existing files), then use [local development commands](../../local-development.md#nationwide-census-candidate). Existing caches need only offline verification:

```sh
node scripts/acquire-coarse-census.mjs data/coarse-sources/tiger-2026/national-v1
node --import tsx scripts/verify-coarse-augmentation.ts \
  data/coarse-quality/census-national-v2/grid.json \
  docs/evidence/coarse-national-2026-10-22/build.json --anchor-inputs
node --import tsx scripts/compare-coarse-candidate.ts \
  data/coarse-quality/census-national-v2/grid.json
node --import tsx scripts/verify-coarse-national.ts \
  data/coarse-quality/census-national-v2/grid.json
node --expose-gc --import tsx scripts/verify-coarse-memory.ts \
  data/coarse-quality/census-national-v2/grid.json --anchor-inputs
```

Full sweeps can take several minutes locally. Do not rerun them for documentation alone. [Checksums](sha256.json) seal this evidence; source hashes observe code versions rather than freezing normal product code. Preserve original/failed attempts and write new measured results to a separately versioned run.
