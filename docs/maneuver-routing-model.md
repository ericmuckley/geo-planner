# Maneuver history and interior destinations

October 16, 2026. **The separate v2 model handles 40 real via-way prohibitions and restores 107 previously closed ways without allowing their forbidden maneuvers.** Destinations partway along a directed road now retain legal turn entry and pay partial traversal cost. Python and the unchanged native kernel agree on the checked real graph. No provider calls, new road downloads or browser range changes were needed. Complete 10–12-hour driving coverage remains unimplemented.

## Run and reproduce

Prepare the [frozen static reference](state-routing-reference.md) first, then run from the repository root:

```bash
npm run routing:model
# Repeat qualification with the same cached source, preserving reports first if needed:
npm run routing:model

# On macOS with C++17/Python installed; denies networking:
npm run routing:model:verify

npm run test:routing
npm test
npm run check
npm run typecheck
npm run build
```

`routing:model` uses the existing `runOffline` wrapper: cached tools image `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`, `--pull never`, `--network none`, two CPUs, 2 GiB memory, read-only root/recipe/reference mounts, and writable output under ignored `data/model-pilot/downtown-maneuvers-v2/`. No extraction or remote fallback occurs. The input is the already-cached 8,676,529-byte `roads.osm`, SHA-256 `e8f53265c9737735f3d095daf892485e22bf90907ed36530204fe3401880438c`. Its regional PBF/source date and acquisition checksums are retained in the manifest and [regional provenance](regional-routing.md).

The [profile](../routing/profiles/model-downtown-v2.json) fixes the new `exploratory-static-car-v2` model, unchanged 5,000 ms signal/20,000 ms U-turn delays, source selection, target fractions and budgets. New run identity: `cf93cb873e53feb90ed0b4ac5b34f267b35c60f9d62146d1e9df8a35aaa80b2a`; graph identity: `11f122d0a182984228629f64f97bd4cd2bca462fc9cb0af1d8c209ef0df854ef`. V1 graph/scripts/fields and its native/cell outputs remain unchanged. Old indexes/state IDs must not be reused for v2. Changed model/worker/source inputs require `npm run routing:model -- --run-name new-name`; use the same name for `routing:model:verify`.

`routing:model:verify` uses the existing host compiler and `sandbox-exec` policy, requires an actual loopback socket permission denial, and checks the saved graph/oracle checksums before running C++. It records the compiler/source/binary identity and verifies the JSON/CSR mapping. The agent tool environment needed outer sandbox exceptions for Docker and nested macOS sandbox execution. Both computations remained network-disabled. Neither command reads or modifies `.env.local`; the Docker worker receives no provider credentials. Other operating systems need a separately qualified network-denying native wrapper. The app remains compatible with its existing Vercel build; this local executable is not integrated into the deployed app.

## Supported rules and fallback

A via-way restriction specifies a maneuver through connecting roads, rather than just a turn at one junction. Our interpretation follows the [OSM relation specification](https://wiki.openstreetmap.org/wiki/Relation:restriction): prohibit the specified from/via/to sequence, preserving arrival history. This is established routing behavior, not a novelty claim.

To preserve the old benchmark, [import_maneuvers.py](../routing/import_maneuvers.py) composes the unchanged v1 importer. It starts from that importer's audited unsupported car relations and accepts only unconditional `no_left_turn`, `no_right_turn`, `no_straight_on` and `no_u_turn` via-way relations with one from/to and an ordered, distinct sequence of via ways. Consecutive ways must have one shared endpoint, simple node lists and a complete permitted directed path inside the retained graph. Every intermediate segment is included. A partial, ambiguous, same-way/repeated-member, conditional or otherwise unsupported rule retains the old member-road/node closure.

Candidate relations are removed only from a temporary XML copy, then resolved against the normal access/one-way/via-node import. Failed candidates reinstate their original conservative closure; this repeats until no further candidate is invalidated. The real run converges in three passes. Some failures are paths already blocked by another node rule; keeping their additional closures is conservative and can exclude otherwise usable roads. `viaWayFallbackReasons` explains the 32 failed via-way candidates; the full audit retains all 53 unsupported relations, conditional/access policy, restored IDs and remaining exclusions. Via-way `only_*` and complex/time-dependent cases remain unsupported. Existing via-node rules continue to apply, with 241 active relations after restoration versus 233 in v1.

[maneuver_graph.py](../routing/maneuver_graph.py) expands each directed road into states distinguished by the longest recent road-sequence suffix that is a proper prefix of a forbidden maneuver. Completing any prohibited sequence removes that transition. Shorter overlapping suffixes remain detectable. Leaving the sequence can clear its history; arriving at a junction alone cannot. Original transition costs are preserved. Every road has a designated initial state for a new trip with no pre-trip history; routing must not reset to that initial state mid-path.

| Quantity | Frozen v1 | V2 model |
| --- | ---: | ---: |
| Directed physical road segments | 19,815 | 20,257 |
| Search states including history | 19,815 | 20,332 |
| Permitted transitions | 37,891 | 39,171 |
| Unsupported relations retaining closures | 93 | 53 |
| CSR adjacency bytes | 382,440 | 394,748 |

The 442 restored directed segments belong to 107 ways; history adds 75 states beyond the v2 road count. All 40 accepted maneuvers block at their final to-road entry in replay. CSR uses the unchanged native format and excludes geometry, snapping indexes and attribution; the reproducibility JSON is 5,390,674 bytes and includes those road records plus state/base mappings. CSR SHA-256: `8bbf4eda30b575897025dfa28d2942ac42518102df125ccc3a1c2552ab469a24`.

## Source-backed examples and partial destinations

Two retained examples use Commercial Street in San Diego:

- Relation **8351113** (`no_left_turn`): way `593614877` → via ways `1458792739`, `1458792738` → way `1457950433` (22nd Street). The five directed segments block at final entry. Arrival from `5986692:2:f` can traverse the same connector and exit.
- Relation **8351682** (`no_left_turn`): way `1547594337` → via ways `1458791068`, `1458791069` → way `993375148` (South Hensley Street). Six directed segments block at final entry. Arrival from `5987820:0:r` can exit.

The [retained OSM subset](evidence/maneuver-model-2026-10-16/first-source-samples.osm) contains the original relations, member ways, alternative approaches and referenced nodes. These checks qualify interpretation of the downloaded OSM records; no street survey independently confirms signs or current access. Data attribution remains © OpenStreetMap contributors, ODbL; see [OSM copyright/license](https://www.openstreetmap.org/copyright).

An interior destination is a fraction strictly between 0 and 1 along a **directed** segment. Evaluate only legal expanded-state transitions into that segment, charging their entry delay plus `ceil(segmentCostMs × fraction)`, rather than the full segment. This stops before the road head and preserves via-node/history rules. For a source already on that same directed segment, a destination ahead can be reached directly with `ceil(segmentCostMs × (destinationFraction − sourceFraction))`; it does not require first reaching the head. Multiple permitted starts form a minimum/union. A target behind the source requires a legal network path or an explicitly permitted opposite direction. Junction endpoints, coordinate destination snapping and filled polygons are deliberately outside this API.

For example, halfway along `1457950433:0:f` costs **27,368 ms** from the partially traversed restricted Commercial approach, using a legal detour; it costs **1,810 ms** from the alternative approach. Halfway along `993375148:0:f` similarly costs **18,556/2,322 ms** from its restricted/alternative starts. The starts differ, so these are model-case observations, not isolated turn-penalty estimates or real travel-time predictions. Blocking a particular maneuver does not make the destination unreachable by every route.

## Verification and measured resources

Both Docker runs pass, with identical graph/CSR/audit/source-example/oracle bytes and deterministic results:

- Eight origins: default San Diego, three earlier holdouts, and restricted/alternative partial starts for both real maneuvers.
- **162,656 complete state costs** match Dijkstra/Bellman–Ford per run, plus **813,280 bounded state costs** over 30/60/120/300 seconds and 12 hours.
- **264 interior costs** match a terminal-sink Bellman–Ford oracle, plus **1,320 bounded interior membership checks**. Unit cases also exercise expected costs, entry delays, overlapping rules, detours, same-road starts and an independent full-history walk enumeration. The sink oracle shares legal transitions, so agreement does not independently prove the importer.
- The unchanged C++ kernel passes **975,936 complete/bounded cost**, **813,280 bitmap membership** and **264 interior-cost** checks on this actual v2 graph. Its arm64 executable is byte-identical to the earlier native baseline.
- **54 Python tests and 14 adapter tests** pass, as do Biome, typecheck and production build. Existing database assertion and MapLibre/TanStack bundler warnings remain. No manual route-tree edits or browser/hosted calls were required.

On Apple M4/16 GiB, import/product construction took **2.625/2.639 seconds**, and complete qualification took **40.13/39.91 seconds** of worker time, with **311,768/311,896 KiB** maximum worker RSS (about 305 MiB) under the 2 GiB container cap. Worker time includes repeated independent sink-oracle searches and artifact writes before final reporting; it excludes Docker launch and final summary/manifest/recipe writes. Some first-run qualification overlapped app checks. These two observations are not a query latency distribution or a national build-RAM estimate.

The single native qualification recorded 714 ms compilation, 283.5 ms launch through hello and 0.556 ms internal graph load/structural validation. Raw per-query setup/search/encoding and pipe round trips are retained; no HTTP measurement is involved. There is one sample per case, no cache flushing and no WASM/Vercel/cloud measurement. Use the [earlier repeated native baseline](native-routing-baseline.md) for its separately defined small-model performance comparison.

## Remaining limits and next task

The bbox remains `[-117.18,32.70,-117.13,32.74]`. The default source still reaches a cut exit at **215,966 ms (3m35.966s)**; every selected origin reaches a cut within five minutes and at 12 hours. This restores some internal connectivity without expanding geographic coverage. `coverageVerified` stays false. Conditional, barrier, lane/access and ambiguous-rule exclusions still reduce coverage, and static speeds/delays are not validated real driving times. This downtown instance has no Mexico crossing; future San Diego coverage must retain and qualify Mexico roads/crossings, with an explicit border-queue policy. Canada and longer routes remain separate coverage questions.

The recommended [regional capacity probe](regional-routing-capacity.md) is now complete on 387,236 states, preserving these v1/v2 assets and semantic fixtures. It reproduces graph/packed bytes and verifies the unchanged native kernel, but a wider import exhausts 4 GiB and conservative barrier handling disconnects sampled cross-border routes. Next qualify barrier access and reduce import memory before wider coverage. The current all-target scan/sink checks are qualification code, not a production destination index. Western-US acquisition, national anchors, heavier shortcuts, browser range increases and Vercel rollout remain later work; complete 10–12-hour coverage remains unmet.

See [raw evidence and reproducibility checks](evidence/maneuver-model-2026-10-16/README.md).
