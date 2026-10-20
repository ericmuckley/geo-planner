# Compact routing import and larger buffer

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

The subsequent [compact OSM input/no-swap experiment](compact-osm-input.md) reproduces all five graphs, including this buffer, with approximately 47% less worker memory. This page preserves the earlier graph-storage qualification and its original swap allowance.

October 17, 2026. This follows the [broader-buffer preflight](coverage-buffer-preflight.md). The experiment keeps the existing static v2/v3 routing semantics, frozen OSM inputs and **4 GiB/two-CPU cap**. It uses no provider requests, new downloads, credentials or application environment changes.

## Representation and equality gate

`routing/compact_import.py` is a versioned copy of the frozen streaming import control flow. It substitutes the storage/builders in `compact_storage.py`; previous recipes remain unchanged. Access exclusions, speeds, integer rounding, turn delays, via-way candidate/fallback logic and v3 barrier policy retain their existing rules.

Road numeric fields and endpoint coordinates use typed arrays. Road dictionaries/IDs are generated as temporary views when existing helpers need them. Adjacency uses offset/target/cost arrays, with no eagerly built reverse adjacency. Initial maneuver states have implicit road indices; only nonempty initial histories and additional history states need extra storage. The ordering of roads, states and transitions is preserved.

Canonical JSON identities/exports stream the large road/state/transition arrays through a small buffer, avoiding a complete encoded graph string. Ordinary metadata/audit lists still use normal JSON encoding; the buffer threshold is not a universal allocation bound. CSR is written from little-endian arrays without building separate Python integer lists and a second complete packed graph. Gzip compression still reads the small CSR file into memory; its buffers are included in measured export peaks. The compatibility JSON remains available and byte-identical on the frozen cases.

Decoded OSM node/way dictionaries, outgoing-road lookup lists and restriction-resolution lookups still scale with the extract. Coordinates are stored twice per directed road. This is a measured reduction in graph/output overhead, not constant-memory or national-ready preprocessing. The compact base graph deliberately exposes outbound adjacency only; an operation needing reverse fields must add and qualify that representation explicitly.

The gate checks downtown v2, corridor v2, corridor v3 and wider v3 against their original manifests. Every case checks all original artifact checksums first, then requires exact graph identity, graph JSON, audit and CSR bytes. Where present, gzip, prepared barrier XML, original barrier examples and uncertain-source XML must also match. Original oracle files are checksum-verified; these parity runs do not recompute their searches.

Synthetic checks additionally compare all-source costs with independent Bellman–Ford, prohibited maneuver replay, control-point permissions/closures, canonical Unicode/float/range encoding and streamed reload. Reload tests split tokens into seven-character blocks and reject malformed/trailing/duplicate graph data. `compact_load.py` reconstructs compact views one JSON array element at a time, then recomputes graph identities; verification no longer needs a full decoded graph JSON tree.

All four frozen cases pass exact parity:

| Case | States / arcs | Compact import | Complete worker peak | Observed container peak |
| --- | ---: | ---: | ---: | ---: |
| Downtown v2 | 20,332 / 39,171 | 1.29 s | 71,724 KiB | 85,454,848 bytes |
| Corridor v2 | 387,236 / 818,698 | 27.89 s | 557,312 KiB | 819,961,856 bytes |
| Corridor v3 | 387,236 / 819,241 | 34.87 s | 561,632 KiB | 966,373,376 bytes |
| Wider v3 | 926,900 / 1,957,330 | 107.31 s | 1,204,148 KiB | 2,134,364,160 bytes |

All four containers record zero OOM/kill/limit-hit counters. Corridor v2/v3 complete worker peaks fall approximately **46%** from the frozen streaming parity runs' 1,026,632/1,033,488 KiB. Imports slow from 17.81/26.30 s to 27.89/34.87 s. Wider v3's matched import checkpoint drops from 2,267,240 to 1,204,148 KiB (**47%**), while import slows from 71.49 to 107.31 s. Its older complete qualification peak was 2,361,520 KiB; the compact parity case does not rerun those old oracles. Cgroup comparisons also include different charged-cache histories and are observations, not isolated allocation measurements. This trades import CPU for memory while preserving output bytes; it is not a query-speed result.

## Reproduction

Docker must be running with the cached immutable tools image and all frozen inputs described in [local development](../local-development.md). Commands use `--pull never`, networking disabled, read-only recipe/input mounts and a fresh capped container per case:

```bash
npm run routing:compact -- --case downtown-v2
npm run routing:compact -- --case corridor-v2
npm run routing:compact -- --case corridor-v3
npm run routing:compact -- --case wide-v3
npm run routing:compact -- --case buffer-v3
npm run routing:compact:reload
npm run routing:compact:verify
```

Recorded defaults are ignored `data/compact-pilot/compact-v1-<case>/`. Existing run identities refuse overwrite, including failed attempts. Parity reproductions may use `--run-name fresh-name`; the buffer admission gate deliberately requires the four recorded default parity reports to match the current worker fingerprints. Changed code needs new versioned proof paths before reuse. The prepared buffer is read from `data/coverage-pilot/san-diego-tijuana-buffer-preflight-r2/car-roads.osm`; no extraction is repeated.

Run identities bind source/prior-manifest checksums, profile, image, Python worker fingerprints and parity reports. Recipe snapshots and cumulative resource checkpoints are written before expensive work. `progress.json` preserves the last completed import stage on failure. Preserve the run directory and terminal log if a process fails; the Docker wrapper removes the exited container.

`routing:compact:verify` requires the existing macOS `sandbox-exec`/C++17 compiler prerequisites. It denies network access, streams graph reload, rechecks JSON/CSR identity and then uses the unchanged native kernel for full/bounded labels, membership, traversal counts and partial destinations. Unlike build/reload, verification refreshes its own timing report and compiled output; preserve those before remeasurement or select another completed buffer with `--run-name`. Graph/source artifacts remain read-only. This path runs locally, not in Vercel.

`routing:compact:reload` independently reads the completed buffer exports under **1 GiB/two CPUs/network denial**, binding their checksums before reload. It writes a separate proof under ignored `data/compact-pilot/compact-v1-buffer-reload/`; use `--run-name fresh-name` to preserve prior attempts. The actual 605,560,826-byte graph JSON reloads, rehashes and reproduces the 44,834,976-byte CSR exactly. Observed worker maximum RSS is **357,580 KiB (349.2 MiB)**, cgroup peak **1,051,291,648 bytes**, with zero OOM/kill/limit-hit events. Reload plus identity verification takes **28.67 s**, whole worker 29.09 s, including input checksumming. This is a sequential local reload with reused caches, not a Vercel cold start or an isolated graph-search measurement. A geometry/metadata JSON reload should not be counted as native CSR startup.

## Interpretation and remaining work

The prepared larger export has **2,137,982 directed roads, 2,139,131 history states, 4,534,800 transitions and 974 via-way prohibitions**. Its road count lies inside the preflight's measured interval; its states lie below the conservative history ceiling. Graph identity is `2f5f816407ba914bda6024fa0bda47c5fa69e381f182b8d5e53086a88613615c`. The policy records 1,248 explicit-permission decisions; other restrictions can still block a transition, and current crossing eligibility remains unverified. The same three source-marked uncertain Otay ways remain in the inventory.

The completed larger import takes **247.55 s** through barrier preparation, parsing, seven base builds/fallback resolution and history construction. Its complete build/reference qualification takes **3,094.33 s (51m34s)**, dominated by deliberately expensive independent oracles and route recovery. Worker maximum RSS is **2,478,776 KiB (2.36 GiB)**; observed cgroup peak is **4,294,967,296 bytes**, with **633 limit events and zero OOM/kill events**. The cap was encountered; successful completion does not establish container headroom. Resource observations stop before final small reports. No extraction or provider request is included.

Actual retained exports are **44,834,976-byte CSR**, **17,341,346-byte gzip**, **605,560,826-byte compatibility JSON**, **339,201,575-byte prepared XML** and **12,513,557-byte audit**, plus five 17,113,048-byte oracle vectors and small source/summary files. These separate routing adjacency from geometry/metadata and validation data; they are not a Vercel deployment bundle.

Five full Dijkstra fields agree with independent flat-edge Bellman–Ford: **10,695,655 full costs** and **85,565,240 bounded costs** at 5/15/30/60/120/360/600/720 minutes. Both partial sinks agree: permitted port half-segment **374 ms** and uncertain Otay half-segment **1,167,889 ms**. All twelve city-direction routes are finite, with the same costs as the previous wider v3 sample; all avoid the three explicitly uncertain ways. The forced Otay branch still traverses permissive gate 7229150207 and uncertain way 114198251, with `carEligibilityVerified: false`. The source-backed private gate remains closed and the qualified one-way San Ysidro controls remain permitted. Neither these paths nor the absence of a source hint verifies current real access.

Native verification passes **96,260,895 cost / 85,565,240 membership comparisons**, matched traversal counts and both partial destinations. These totals count source/budget/mode cases; five repeated timing samples per case are not independent journeys. The compiled binary is byte-identical to the previous wider-v3 binary, and its source is unchanged. Compact reload recomputes JSON identities and reproduces the saved CSR before execution.

The median of five per-origin membership-search p50s is **156.49 ms at 60 minutes**, with **157.67 ms local pipe round trip**, and **164.75 / 165.86 ms at 720 minutes**. The long-budget plateau reflects the finite clipped component, not complete 12-hour geography. Five samples per case make p95 the case maximum, not a robust tail estimate. Native maximum RSS is **123,696 KiB (120.8 MiB)**; the Python verification parent peaks at **635,776 KiB (620.9 MiB)** while retaining graph views, vectors and expected payloads. These high-water marks have separate scopes and are not a combined application-memory budget.

Local process launch through hello takes **338.66 ms**, including **40.61 ms** internal CSR load/validation. The verifier's separate JSON reload/identity step takes **29.93 s**; the whole native-verification worker takes **100.03 s**. Reference execution is Linux Docker/Python, native execution is macOS/Apple Clang on M4; no cross-environment speed ratio is attributed solely to implementation. There is no HTTP, browser, WASM or Vercel performance measurement in this phase.

The source is the checksum-pinned California/northern-Baja OSM snapshot from **2026-10-14T20:21:12Z**, using the exact prepared XML checksum recorded in the [preflight](coverage-buffer-preflight.md). The immutable tools image and parent boundaries are unchanged. The experimental engine revision is recorded through Python/native source hashes and recipe snapshots; the repository has no committed Git revision. The model still uses the v3 profile's integer-millisecond segment costs, 5-second signal delay and 20-second U-turn delay.

The larger graph's first potential cuts are:

| Origin | First reachable cut endpoint |
| --- | ---: |
| San Diego | 35m17.096s |
| El Cajon | 22m22.449s |
| Tijuana | 24m38.037s |
| San Ysidro | 29m9.406s |
| Port attachment | 29m10.892s |

All selected 60-minute/longer cases are potentially truncated. These mark reachable inside endpoints of cut ways; legal outside continuation is not independently established. Absence of a flag at a smaller budget would not validate source/access completeness. The default cut is later than the previous wider graph's 10m15s, but the original long-range requirement remains unfinished.

Build-stage times include parsing, restriction fallback passes and identity hashing. Resource checkpoints report Linux worker high-water RSS separately from cumulative cgroup memory, including children and charged file cache. Sequential runs reuse cached files; they are not isolated cold-cache benchmarks. Native search-loop wall time, setup, encoding and local pipe time are separate measurements; none is isolated CPU time or HTTP round trip.

The Docker wrapper enforces a 4 GiB **RAM** limit; its existing default also allows 4 GiB of swap. Live cgroup observations at `20:20:02Z`, `20:37:53Z` and `20:42:24Z` on October 17 cover construction/export, the completed port sink and the final Otay oracle. Each records swap current/peak **0 bytes**, zero swap-limit events and worker `VmSwap: 0 kB`. These observations do not make swap a disabled resource or cover the small final report writes after the last sample. Keep the allowance and observation separate when reproducing or assessing capacity; future strict-total-memory experiments should explicitly pin swap policy in a new recorded recipe.

The larger candidate retains the same `[-117.4,32.3,-116.6,33.2]` rectangle and `exploratory-static-car-v3` model. Qualifying searches on this graph must not imply complete 60-minute or 10–12-hour geographic reachability. Parent California/Mexico source cuts, missing AZ/NV roads, border queues/documents/current eligibility, source-marked Otay uncertainty, conditional exclusions and default speeds remain unresolved. Browser/provider limits and the single TanStack Start/Vercel architecture are unchanged.

The next storage bottleneck is decoded OSM input and its restriction-resolution lookups: parsing the buffer alone reaches 1,375,596 KiB worker high-water RSS before road construction. Evaluate sorted ID/coordinate/reference arrays or a disk-backed lookup while retaining the frozen import control flow. Prove the same smaller cases **and this new buffer** byte-identical, reusing their frozen oracle vectors by checksum rather than repeating the expensive full reference runs. Pin an explicit swap policy in the new capacity recipe and preserve this original allowance/observations. Investigate Osmium's extraction peak separately; the prepared cache avoids repeating it here. Use the new reachable cut witnesses to size subsequent coverage, with a measured count/resource gate before downloading Western-US data or computing national anchors.

Commands, hashes, reports, cut-point GeoJSON and the validator are in [saved evidence](../evidence/compact-import-2026-10-17/README.md). `npm run test:routing` passes 86 of 88 cases with two unchanged host Osmium skips; fourteen adapter tests, `npm run check`, `npm run typecheck` and `npm run build` pass. The existing database assertion and MapLibre/TanStack build warnings remain. No dependencies or environment values changed. Source snapshots and old graphs/recipes/binaries are preserved; the generated route tree was not manually edited.
