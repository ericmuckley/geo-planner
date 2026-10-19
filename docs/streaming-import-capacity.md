# Streaming importer and wider-region retry

October 16, 2026. A separate streaming importer reproduces the frozen downtown v2, corridor v2 and corridor v3 graph/audit/packed bytes. The previously OOM-killed wider v2 input now imports under the **same 4 GiB / two-CPU cap**, producing **926,900 history states**. No new road downloads or routing-provider requests were needed. This is an importer resource improvement; the original 10–12-hour requirement remains unfinished.

## Implementation and semantic safeguards

`routing/stream_import.py` decodes nodes/ways once while releasing completed XML objects. It retains the small relation elements needed by existing restriction parsing, releases the original conservative graph after recording its identity/road IDs, releases failed intermediate graphs before rebuilding, and constructs one directed-road lookup per restriction pass instead of one per relation. Source references, ordering, integer costs, access rules, audit reasons and maneuver-state construction retain the frozen behavior.

The decoded inputs and graph still grow with region size; this is not a constant-memory national importer. The original `import_roads.py`, `import_maneuvers.py`, `barrier_policy.py`, graph builders and old workflows remain unchanged as reproducibility references. The new base-building control flow mirrors the frozen importer and reuses its cost/access helpers; changes to this implementation must pass artifact equality before reuse. Frozen experiments should continue using their recorded recipes. New imports use `routing:import` and the streaming module.

Six new regression cases compare full graph objects and audits against the frozen implementations, covering supported/conditional/ambiguous/non-car restrictions, fallback closures, duplicate road geometry, speed/access/direction/cut behavior, v3 barrier permissions/prohibitions and prepared-source preservation, plus malformed inputs. Duplicate directed geometry retains per-rule conservative fallback rather than aborting the import globally.

Real-data equality covers:

| Reference | Identical products |
| --- | --- |
| Downtown v2, 20,332 states | Graph JSON, import audit, CSR |
| Corridor v2, 387,236 states | Graph JSON, import audit, CSR, deterministic gzip |
| Corridor v3, 387,236 states | Graph JSON, barrier audit, CSR/gzip, prepared XML and source examples |

Existing oracle vectors were checksum-verified for these equality runs; they were not needlessly recomputed. Exact output equality preserves the already-qualified v3 crossing/prohibition behavior and Commercial Street maneuver fixtures. It also preserves the conservative v2 blanket barrier closures; optimization does not silently adopt v3 access semantics.

## Reproduction

Prerequisites are the existing frozen reference/model/corridor/barrier datasets, the failed wide attempt with its cached filtered XML, and the pinned local tools image. These remain in ignored `data/`. See [regional capacity](regional-routing-capacity.md) and [barrier policy](barrier-access-model.md) for their original commands/provenance.

```bash
# Recorded runs are already complete; these commands refuse to overwrite them.
npm run routing:import -- --case downtown-v2
npm run routing:import -- --case corridor-v2
npm run routing:import -- --case corridor-v3
npm run routing:import -- --case wide-v2
npm run routing:import:verify

# For a fresh reproduction, give each case a new run directory.
npm run routing:import -- --case downtown-v2 --run-name repeat-downtown-v2
npm run routing:import -- --case corridor-v2 --run-name repeat-corridor-v2
npm run routing:import -- --case corridor-v3 --run-name repeat-corridor-v3
npm run routing:import -- --case wide-v2 --run-name repeat-wide-v2
npm run routing:import:verify -- --run-name repeat-wide-v2

python3 -B docs/evidence/streaming-import-2026-10-16/analyze.py
```

The wrapper mounts saved inputs/recipes read-only and uses the cached tools image with `--pull never --network none --read-only`, a 256 MiB temporary filesystem, two CPUs and 4 GiB memory. Each case runs in a fresh container. Native verification uses the existing [macOS compiler/network-sandbox setup](native-routing-baseline.md) and verifies that a loopback connection is denied. No app server, provider credential or changed environment value is required. Changed code/input needs a new run name.

Recorded outputs: `data/import-pilot/stream-v1-{downtown-v2,corridor-v2,corridor-v3,wide-v2}/`. Each has a run identity, stage/resource report and recipe snapshot. Equality runs retain digests instead of another copy of large unchanged graphs. The wide run retains a new graph/audit/CSR/gzip and complete oracle vectors. The prior failure/graphs are preserved. Native verification may refresh its report, which binds to the exact wide import report checksum.

The tools image remains `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`, Python 3.12/Osmium 1.16.0, with Valhalla revision `7fd2228e5863b442bc1ac8d25eece6415dd91bff`. This experiment uses the custom static graph/search rather than Valhalla routing. Hardware remains Apple M4/16 GiB, Docker VM approximately 7.65 GiB/10 CPUs, approximately 255 GiB free disk before the runs. The native C++17 kernel/compiler/binary remain unchanged from the prior qualified experiments.

## Resource comparison

| Case | Import wall time | Complete worker wall time | Maximum worker RSS | Observed container memory peak |
| --- | ---: | ---: | ---: | ---: |
| Downtown v2 | 0.83 s | 0.97 s | 0.090 GiB | 0.096 GiB |
| Corridor v2 | 17.81 s | 20.08 s | 0.979 GiB | 1.180 GiB |
| Corridor v3 | 26.30 s | 32.24 s | 0.986 GiB | 1.315 GiB |
| Wider v2 retry | 61.15 s | 347.04 s, including independent oracles | 2.201 GiB | 2.350 GiB |

The comparable saved frozen rebuild observations were 88.15 s import / 3.16 GiB worker RSS for v2 and 94.55 s / 3.16 GiB for v3. Worker RSS reductions are approximately **69%** in both corridor cases. These are single observations, not timing distributions; the v3 preparation/source-example passes add work beyond the one streaming graph-input parse. Do not compare these worker observations to whole-VM or container memory as though they were the same measurement.

Reports include `getrusage` worker high-water RSS and observed cgroup-v2 `memory.max`, `memory.peak`, `memory.current` and `memory.events` at preflight, import, packing/hashing and completion. The cgroup limit is verified as 4,294,967,296 bytes; fresh containers make their high-water marks specific to each run. Container accounting also includes other memory charged to the group. Final observations end before writing the small report/snapshot files. **All four runs have zero new OOM/kill/limit-hit counters.** The older rebuilds did not measure cgroup peaks, so no percentage reduction is claimed for container memory. The wider import itself peaked at 2,264,928 KiB worker RSS (2.16 GiB); packing/qualification raised the observed worker high-water mark to 2,307,460 KiB (2.20 GiB). Full qualification time includes four deliberately slow Bellman–Ford oracles, not one interactive query.

The corridor import now does five base builds, four shared lookups and one decoded XML read, with 185 accepted via-way prohibitions. It still rebuilds the base graph when conservative closures propagate; that is required by the existing fallback semantics. National memory/storage/runtime are not established by these two regional sizes.

## Wider input and coverage

The retried input is **exactly the preserved failed v2 profile**, bbox `[-117.25,32.48,-116.9,32.85]`, same source/checksum/model/settings, not a larger memory allocation. Filtered XML: **162,045,477 bytes**, SHA-256 `2db3f467a62182314fc94a4fe5bb6c919f36d4c17e3784aae0fb1ad8720cc0fd`; it derives from the original 53,321,088-byte regional extract and the frozen California/Baja PBF. OSM timestamp remains **2026-10-14T20:21:12Z**; full Southern California/Mexico source URLs/checksums and extraction settings are retained in [regional provenance](regional-routing.md). `exploratory-static-car-v2` retains 5,000 ms signals, 20,000 ms U-turns and the same static road speeds/exclusions.

The new graph has 735,356 source nodes, 214,681 source ways, **926,306 directed roads / 926,900 history states / 1,955,345 arcs**, 501 via-way prohibitions and six fallback passes. Graph JSON is 259,380,721 bytes; CSR is 19,350,412 bytes (gzip 7,543,980). Four complete oracle fields total 29,660,800 bytes. Geometry/snapping/source information is additional to CSR. Source-backed downtown maneuvers retain their decisions. Full and bounded costs at 5/15/30/60/120/360/600/720 minutes agree for San Diego, El Cajon, Tijuana and San Ysidro: **3,707,600 full and 29,660,800 bounded Python costs**. Native verification agrees on **33,368,400 costs and 29,660,800 memberships**, with matched traversal counts and an unchanged compiled binary. Raw measurements and resource checkpoints remain in [evidence](evidence/streaming-import-2026-10-16/README.md).

Wider run ID: `68b5a75a22eee829ea6a45af1b39a2180d5ebe64991f9ad4ff7a17920dd58133`.
Graph ID: `1b98e473181c96eb0c216fc81cfd5851eb9c29346375623de8ade2a41ec8ce4d`.
CSR SHA-256: `171cf87fe1b8c7a4dc2ddf1562d0601a2822a53001a2059477ae47002f2f110e`. Full artifact/recipe hashes are in the saved report.

| Origin | Snap distance | First cut | Source-backed cut witness |
| --- | ---: | ---: | --- |
| San Diego | 0.514 m | 10m14.768s | `1077596899:2:f`, West Point Loma Boulevard, west edge |
| El Cajon | 13.586 m | 4m40.140s | `161937728:6:f`, San Vicente Freeway, north edge |
| Tijuana | 4.562 m | 5m56.393s | `784252846:0:f`, Boulevard de los Fundadores, south edge |
| San Ysidro | 17.874 m | 22m24.555s | `1014516416:0:r`, east edge |

San Diego's first cut improves from 219,374 ms to 614,768 ms, but all four selected origins reach a cut by 30 minutes. Every 60-minute and longer case is potentially truncated. A build that fits and a finite static graph search do not establish complete geographic coverage. Keep `coverageVerified: false`. V2 still closes all tagged barrier nodes; the separately qualified v3 permissions have not been applied to this wider graph.

**Additional border uncertainty:** the larger v2 graph has a finite Tijuana → San Diego witness (2,890,950 ms, 48.18 modeled minutes), while the reverse pair remains unreachable. The path uses Otay inspection-facility ways. Source way **114198251** explicitly carries a `fixme` about a missing border-crossing barrier and uncertain access; adjoining ways mention the CHP Otay Mesa Inspection Facility and `hgv=designated`. The latter tag alone does not establish that cars are prohibited. The model follows its existing default access rules where no car/barrier prohibition is tagged. The source excerpt and recomputed legal-in-model route are retained as an **unqualified crossing**, not a validated ordinary-car route or real driving prediction. This finding shows why conservative handling of tagged barriers alone does not establish conservative real-world border eligibility.

No crossing eligibility, queues/delays, traffic, independently surveyed speeds, filled contours, browser integration or cloud execution are established here.

## Native observations and checks

The unchanged native kernel ran on the Mac under network denial. One observation per origin/budget/output mode was collected for qualification; these do not form a benchmark distribution. The single 60-minute bitmap search-loop observations were 56.73 / 56.39 / 63.65 / 57.62 ms (San Diego / El Cajon / Tijuana / San Ysidro), with corresponding local pipe round trips 57.25 / 56.97 / 64.22 / 58.20 ms. Source allocation/seeding and encoding are recorded separately. Search is steady-clock loop wall time, not dedicated CPU time. Pipe observations include scheduling/encoding/transfer; **no HTTP time is described as isolated search**.

Native process maximum RSS was 54,480 KiB (53.2 MiB); the Python verifier peaked at 2,408,160 KiB (2.30 GiB) while validating JSON/packed/oracle data. Compilation took 661.3 ms, initial launch through hello 274.5 ms, and internal graph load/validation 21.69 ms. These are local qualification observations, not Vercel/WASM/concurrency/cold-start evidence. Python reference runs in Docker; no implementation-only cross-environment speed ratio is claimed.

`npm run test:routing`: 75 Python cases, 73 pass and two host Osmium skips; all seven regional-helper cases pass in the cached network-disabled Docker image, including those integrations. Fourteen adapter tests, `npm run check`, `npm run typecheck` and `npm run build` pass. Existing database assertion and MapLibre/TanStack warnings remain. No app/environment changes, manual route-tree edits, new dependencies or commits were made.

## Next task

**Follow-up complete:** [wider v3 qualification](wide-v3-routing.md) now reproduces its artifacts and checks all selected directed routes, preserving v2 and explicitly tracking three uncertain Otay ways. Current city routes use qualified San Ysidro controls, while an uncertain branch remains reachable and unqualified. **Next preflight a broader buffer from the cached parent PBF**, using cut witnesses and measured memory before a full build. Changing unknown-way semantics requires a distinct model identity. Larger acquisitions/national anchors still need a resource/coverage plan; successful regional retries do not show that all-US data fits locally or in Vercel. Preserve the single-app goal and quota independence. Browser range increases, PostGIS, elevation and road-distance semantics remain later work.
