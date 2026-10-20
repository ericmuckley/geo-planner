# Six-hour coverage preflight

Completed October 19, 2026. **Decision: hold the larger build.** The [qualified two-hour app](two-hour-region.md) remains available. This is an offline source/resource screening experiment; hosted routing quota is untouched.

## Saved plan and source scope

`data/coverage-pilot/six-hour-plan-v1/plan.json` binds the qualified graph, complete cut inventory and versioned planner. At 21,600,000 ms it accounts for 805 cut nodes / 1,173 history states and all five sources, with 3,138 reached origin/cut pairs (628 unique nodes). The unrounded envelope is `[-124.90341300736169,26.003207371030513,-108.2661702622383,39.82196671819786]`; outward rounding gives **`[-125,26,-108.2,39.9]`**. No cached-parent clipping is applied.

The 160 km/h continuation model assumes unchanged interior prefixes; restored roads/restrictions can change those. This rectangle includes ocean and unreachable corners. It is a planning heuristic, not minimal acquisition geography or a coverage certificate.

A pinned offline merge passed at `data/source-pilot/six-hour-cached-v1/`. It uses the full cached October 14 Southern California, Mexico and Arizona PBFs, rather than the previously clipped parent. No road-data download is needed for this screening phase. Northern California, Nevada, Utah, New Mexico and the Colorado corner of the enclosing rectangle are absent. Official source metadata is saved in `data/coverage-pilot/six-hour-catalog-v2/`. Approximate geographic probes expose each missing region; current polygons cannot prove a dated extract's completeness. The first catalog attempt is preserved at `six-hour-catalog-v1` (Python CA-store errors); the retry uses the system CA bundle with TLS verification enabled.

## Source assessment

The official October 14 listings show these missing-source options. No new PBF has been downloaded, so their file headers/checksums remain unverified. Approximate interior probes are source-footprint checks, not reachable destinations.

| Additional source | Listed bytes |
| --- | ---: |
| Northern California | 654,038,117 |
| Nevada | 123,823,096 |
| Utah | 170,097,345 |
| New Mexico | 136,533,076 |
| Colorado | 384,780,419 |
| **Five-extract total** | **1,469,272,053** |
| Alternative: US West | 3,417,392,464 |

Primary listings: [Northern California](https://download.geofabrik.de/north-america/us/california/norcal.html), [Nevada](https://download.geofabrik.de/north-america/us/nevada.html), [Utah](https://download.geofabrik.de/north-america/us/utah.html), [New Mexico](https://download.geofabrik.de/north-america/us/new-mexico.html), [Colorado](https://download.geofabrik.de/north-america/us/colorado.html), [US West](https://download.geofabrik.de/north-america/us-west.html). The smaller option reuses existing SoCal/Arizona/Mexico inputs. Keep Mexico in either option. Boundaries and duplicate object versions would still need validation after acquisition.

## Commands

Run from the repository root. Completed outputs refuse overwrite; inspect live processes and reports first. Fresh names for the merge/preparation do **not** automatically rebind dependent input defaults; inspect/version the recipes when changing inputs.

```sh
python3 -B routing/six_hour_preflight.py
SSL_CERT_FILE=/etc/ssl/cert.pem python3 -B routing/six_hour_sources.py --output data/coverage-pilot/six-hour-catalog-v2
node routing/six-hour-source.mjs
node routing/six-hour-prepare.mjs
```

The first command writes only a plan; the second collects small public metadata files. The third merges cached roads. The fourth runs the unchanged calibrated selector/reference completion and disk-backed census against the full six-hour rectangle, **using partial sources only**. It cannot admit a six-hour graph. All Docker work retains two CPUs / 4 GiB / no swap / no network / read-only inputs. Every later phase must also fit with 25% admission margin.

## Provenance and tools

| Cached road snapshot | Bytes | SHA-256 |
| --- | ---: | --- |
| socal-261014.osm.pbf | 671540119 | `4a0cc652b702142cadb77088f68564545628f7650b378847ec969e0d0a8f9a52` |
| mexico-261014.osm.pbf | 646916392 | `a0a4d8e8411fa3960ec56d4790ed5d45e9407acc396dcee05e49decf5255f81d` |
| arizona-261014.osm.pbf | 303543535 | `d008fac4857d0b520f0ab461bea57063d664f802473720385a359a952c825552` |

The cached-source merge binds the original source URLs/bytes/SHA-256 values from `routing/manifest.json` and `routing/two_hour_source_v2.py`, checks all three PBF replication headers against **2026-10-14T20:21:12Z**, and verifies ordered, single-version merged objects. Its 1,633,792,035-byte output has SHA-256 `8ae2225114df16ec5d8e91ab012eb6f8811322374aba48df9c4a62cfaacdd2ea`. Complete references can give a PBF a much wider object-coordinate bbox than its nominal footprint; that is not coverage.

The source tooling image is `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`; the sparse reader image is `sha256:025ebba8267c0aad21bc4cb52b40c4726b65a13a1ebe66b8642df5495261ddd5` (Pyosmium 4.3.1). Existing calibration artifacts and the pinned wheel lock must already exist; this is a same-workspace recipe, not a qualified clean-machine bootstrap. The graph remains our `exploratory-static-car-v3` static/native engine with `member-scoped-geometry-v1`; using a retained Valhalla tools image for Osmium does not build a new Valhalla graph. Source attribution: OpenStreetMap contributors, ODbL 1.0; extracts by Geofabrik. No October 16 admin supplements are added to this road-only screening input.

Supplemental publisher-checksum observations are preserved in `data/coverage-pilot/six-hour-checksums-v1/report.json`: Mexico matches its published MD5; several other requests timed out. Cached input SHA-256/header verification passed independently. Do not claim unavailable publisher checks passed or treat unacquired candidate bytes as locally verified snapshots.

## Measurements and decision

The completed partial-source census is at `data/coverage-pilot/six-hour-cached-v1/report.json`. The preparation uses four reference batches, passes `osmium check-refs --check-relations`, and preserves original OSM IDs. Counts below are measured source/census values, **not a newly built graph**.

| Measured partial-source value | Result |
| --- | ---: |
| Prepared nodes / ways / relations | 15,819,514 / 2,733,016 / 66,029 |
| Eligible directed road segments | 22,913,385 |
| Conservative road-state interval | 22,434,613–22,913,385 |
| History-state ceiling | 22,938,366 |
| Candidate via-way rules / proper-prefix ceiling | 11,099 / 24,981 |
| Prepared XML | 3,050,367,471 bytes |
| Source merge: complete wall / cgroup peak | 110.75 s / 1.864 GiB |
| Preparation plus census: complete wall / cgroup peak | 717.64 s / 3.175 GiB |

XML SHA-256: `5cde64f2c9ee4e79080b4726a7cc82a81d44f0f9cb9f229c72a4846732cc1451`. SQLite and selected-ID hashes are in the report. Both complete phases show zero pressure/OOM/kill/swap. The preparation peak with 25% margin is 3.969 GiB, close to the 4 GiB limit; do not infer extra capacity from a low final worker RSS. Cgroup totals include descendants/file cache; periodic composition samples can miss brief peaks. Host/VM paging is unmeasured.

The maximum corresponding source/restriction/road/history growth ratio is **2.8191×**, against the qualified two-hour census and actual built counts. Applying it to complete measured Linux phases gives:

| Phase | Forecast peak, GiB |
| --- | ---: |
| Build | 7.520 |
| Exact rebuild | 7.480 |
| Independent qualification | 7.432 |
| Source-linked cut audit | 6.209 |
| Preparation | 3.175, measured |

The largest sequential phase plus 25% margin is **9.400 GiB**, versus the unchanged **4 GiB** cap. The measured source merge is below that maximum. **Resource screen: fail; complete-source admission: hold.** No six-hour graph was attempted, no default changed and no missing-region road PBF was downloaded. This partial-source forecast is a screening heuristic, not measured graph RAM, a rigorous lower bound, a guaranteed full-region requirement or permission to raise the cap. Complete missing-source demand and future macOS native/browser resource use remain unmeasured.

This Mac has **16 GiB physical RAM**; Docker reports **7.654 GiB VM RAM**, with each batch capped separately at two CPUs / 4 GiB / zero container swap. Approximately **175.43 GiB disk remained free** after this preflight. New merged/prepared outputs occupy about 7.73 GiB including retained batches/SQLite. A proportional forecast of retained graph/qualification/native, rebuild and cut outputs plus those measured inputs is **36.91 GiB with 25% disk margin**. It fits free disk even when conservatively counting the already-created inputs again. Disk uses a sum of retained phase outputs; RAM uses the maximum sequential phase. This is only a partial-source artifact estimate, excludes existing caches/images/historical data from new additions, and does not reserve space or bound a full missing-source six-hour workflow or failed retries. See `resource-analysis.json` in the evidence.

No routing timings were remeasured: these wall times measure offline merge/preparation/census, not HTTP or isolated search. Existing local worker/app health checks still identify the qualified two-hour graph. No new browser routing claim is made because serving code/data did not change. Border queues/documents/current eligibility, source completeness and all-origin accuracy remain unverified.

## Evidence and next task

[Saved evidence](evidence/six-hour-preflight-2026-10-19/README.md) includes source headers/pins, official listings/current footprints, checksum observations, exact commands, census/admission reports, resource analysis and validation logs. Large ignored data remain local; producer scripts and evidence have separate checksum indexes. Never overwrite a completed output, sealed producer or failed-attempt evidence.

Safe evidence verification, without recomputing the census:

```sh
python3 -B - <<'PYTHON'
import hashlib, json
from pathlib import Path
folder = Path('docs/evidence/six-hour-preflight-2026-10-19')
for filename, root in [('evidence-sha256.json', folder), ('recipe-sha256.json', Path('.'))]:
    records = json.loads((folder / filename).read_text())
    for name, expected in records.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
    print(filename, len(records), 'files match')
PYTHON
```

The collection command was `python3 -B data/coverage-pilot/six-hour-validation-v1/collect-evidence.py`; it refuses overwrite. Its saved copy is in the evidence's `validation/` directory. Resource analysis was `python3 -B data/coverage-pilot/six-hour-validation-v1/analyze-resources.py`. The source/census commands above are completed producers, not health checks.

Validation passes: **20 adapter/server tests**, **205 routing tests run (196 pass, nine existing skips)**, `npm run check`, `npm run typecheck`, and `npm run build`. Biome retains the existing database non-null-assertion warning. The first npm-test launch was blocked at tsx's sandbox pipe before tests ran; the permitted retry passed. Previous 87 evidence / 187 recipe bindings remain intact. Documentation links/anchors and `git diff --check` are checked at handoff. A Vercel-target build was not repeated for this offline-recipe-only change; its earlier qualified result remains historical.

The bounded owner profile and first storage calibration build are now complete; see [the memory follow-up below](#memory-follow-up). The original preflight measurements/forecast above remain the sealed result of that named recipe. Exact repeat and a revised admission calculation are still pending, so the larger-build hold remains in force.

Keep the two-hour app available. Missing-source acquisition and a complete census remain necessary even if memory improves; the partial screen can never admit a full six-hour graph. Preserve all required directions, history states, Mexico and Otay uncertainties. Full six-hour coverage still requires an independent exact rebuild, native/cut proofs, zero detected cuts for the five sources and live API/browser qualification. See [the ordered queue](next-steps.md). Caching, national anchors, deployment and analytical layers remain deferred.

## Memory follow-up

The bounded diagnostic `node routing/base-memory-profile.mjs` completed at `data/resource-pilot/two-hour-base-owners-v1/`: the final base identity matches, with 8,131,472 roads and 17,655,210 base transitions. Its 175.96 s / 2.400 GiB diagnostic includes source validation, parsing and owner introspection, but omits road-key retention, repeated fallback builds, barrier preparation, maneuver construction, exports and qualification. Never substitute that peak for a complete-phase admission measurement.

The owner census finds about **392 MiB** in the outgoing dictionary plus node keys/ordinals, alongside decoded inputs, road arrays and base adjacency. Array/container allocations are measured; shallow reference sums can count shared objects and do not exhaustively decompose RSS. A focused follow-up replaces the temporary map with numeric offsets indexed by the existing sorted source-node IDs. Road-reference order stays unchanged; generic/unordered/string paths retain the frozen fallback.

The first complete calibration build, `node routing/source-outgoing-region.mjs`, **passed** at `data/compact-pilot/source-outgoing-v1/`. All eight qualified graph/audit/source/CSR payloads are byte-identical, with the same graph identity, model and coverage. Complete worker wall time was **1,494.59 s** and cgroup peak **2,592,776,192 bytes (2.415 GiB)**, or **3.018 GiB with 25% margin**. Pressure/OOM/kill/swap are zero. The previous complete build peak was 2.668 GiB: about **9.5% lower** in this single calibration. Parsing now reaches the peak; later base/history/export stages stay below it. These offline build times are not routing/search timings or production latency statistics.

Seven focused unit cases and 17 fresh scoped OSM fixtures pass, with **416 full / 1,248 bounded / 320 partial** independent cost comparisons. Latest checks record **20 server/adapter passes; 212 routing cases (203 pass, nine existing skips); check/typecheck/regular build pass**, with the existing database warning. No Vercel-target build or new browser routing verification was performed for this offline change. Serving graph/app are unchanged and ready, with zero routing-provider calls.

**Stopping point: first build complete; exact repeat not started; no calibration job running.** The follow-up is not yet accepted. [First-build handoff evidence](evidence/source-outgoing-build-2026-10-19/README.md) preserves profile/build reports, manifests, fixtures, producer hashes, checks and health. The first build snapshots 149 producer files. `storage-fixtures.json` is supplemental proof, bound separately from the eight payloads; the prepared result helper is not in that build snapshot and must be bound by its own hash.

After the handoff's read-only recovery/owner checks, the next command is:

```sh
node routing/source-outgoing-region.mjs --stage rebuild
```

It creates `data/compact-pilot/source-outgoing-v1-rebuild`; do not rerun the completed first build or profile. Preserve two CPUs / 4 GiB / no swap / no network / read-only inputs. A fresh output name alone does not rebind hardcoded source-run dependencies. Expect roughly 25 minutes for the repeat, with resource and exact-byte checks over the complete phase.

Only after that passes:

```sh
python3 -B routing/source_outgoing_result.py
# Review result.json, then collect the final evidence:
python3 -B data/resource-pilot/source-outgoing-validation-v1/collect-evidence.py
```

The prepared result helper is syntax-checked but **has not run end to end**. It will verify both builds and supplemental fixtures, bind existing independent/native/cut proofs on identical payloads and recompute the partial-source screen using measured affected phases and retained unaffected-phase peaks. Those regional searches are not rerun or remeasured. Its output is `data/resource-pilot/source-outgoing-validation-v1/result.json`. The prepared, unexecuted collector requires that result and writes `docs/evidence/source-outgoing-2026-10-19/`; it refuses overwrite. Keep the current partial evidence separate and immutable. Fix unexpected verifier failures transparently and record any helper revision; never alter sealed producer/output bytes to satisfy a check.

No revised optimized forecast has been accepted. The original **9.40 GiB** partial-source forecast remains the recorded screen, and complete-source admission is still held. No larger source acquisition, graph promotion, new coverage, deployment or hosted routing call occurred. See [next steps](next-steps.md) for acceptance and deferred work.
