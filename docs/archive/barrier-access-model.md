# Qualified control-point access (v3)

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

October 16, 2026. The experimental importer now admits explicitly permitted car travel at recognized control points. **All six previously disconnected US–Tijuana direction pairs have finite, legal state-path witnesses in the new model.** This fixes a concrete importer limitation; it does not validate real driving times, current border availability or complete long-range coverage. The browser still uses the existing hosted adapter and its 60-minute cap.

## Model and policy

`exploratory-static-car-v3` composes the frozen v2 maneuver importer. `explicit-control-point-car-v1` recognizes node barriers `gate`, `lift_gate`, `border_control` and `toll_booth`. It requires an explicit applicable permission, selecting `motorcar`, then `motor_vehicle`, then `vehicle`, then `access`. Allowed values are `yes`, `permissive` and mode-specific `designated`; generic `access=designated` is held closed. A more specific car prohibition wins over a general permission. Bicycle/foot prohibitions do not prohibit cars.

Unknown barrier types, missing/unknown/private car access, any conditional tag, unsupported access qualifiers/direction/lane/citizenship fields, opening hours other than `24/7`, locked/unknown lock state, and tagged unmodeled dimensions remain closed. This intentionally underestimates access: even a conditional restriction for another mode closes the node. No default gate/toll-booth permission is inferred. Other road/access exclusions, one-way rules, turn history and costs remain the frozen model's rules.

The preparation pass streams XML and removes only the `barrier` tag at qualified nodes in a separate file; it retains the original tags in an audit. **424,812 source objects were compared**: all other node/way/relation attributes and child tags are identical. Existing importers and the native kernel are unchanged. New graph/run identities distinguish the changed access semantics.

OSM documents barrier-dependent access and mode-specific overrides; these inform this limited policy rather than establishing current operational access. Sources checked October 16: [barriers](https://wiki.openstreetmap.org/wiki/Key:barrier), [access hierarchy](https://wiki.openstreetmap.org/wiki/Key:access#Transport_mode_restrictions), [border controls and citizenship](https://wiki.openstreetmap.org/wiki/Tag:barrier=border_control).

## Inputs, identity and reproduction

No new road data was downloaded. The input is the frozen corridor's `car-roads.osm`, **72,875,471 bytes**, SHA-256 `088262b37e681041b12cffb55437cce5b42928d5eca89167b0d7f0c41de6f903`, bbox `[-117.18,32.49,-117.0,32.75]`. It derives from the same Southern California/Mexico OSM snapshot, timestamp **2026-10-14T20:21:12Z**; full source URLs/checksums and extraction settings remain in [regional provenance](../regional-routing.md) and [capacity evidence](regional-routing-capacity.md).

The cached tools image is `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`, with Osmium 1.16.0/Python 3.12 and Valhalla revision `7fd2228e5863b442bc1ac8d25eece6415dd91bff` (3.9.1). The custom graph/search experiment does not invoke Valhalla routing. Native search remains `csr-dijkstra-v1`, source SHA-256 `1b583ac8e02d7aa033c42d7652f7278eeb4af4da72d447faedf9474bd59a0d29`, compiled with Apple Clang 17, C++17, `-O3 -Wall -Wextra -Werror`. Its binary is byte-identical to prior runs.

Run ID: `e32f63482677cb1610cba98809f1c1c5cdf54da0b70b83be3cb9d713433775a4`.
Graph ID: `60c539ac4c44001db94b3923671dbbff7c06520989f4d47f0d5b13a921435820`.
All script fingerprints, profile settings and artifact checksums are in the [manifest](../evidence/barrier-access-2026-10-16/build-manifest.json). Signal delay remains 5,000 ms, U-turn delay 20,000 ms; road costs retain class defaults/numeric speed tags and integer-ms rounding.

Prerequisites: completed `data/regional-pilot/san-diego-tijuana-corridor-v2/`, `data/model-pilot/downtown-maneuvers-v2/`, the cached tools image, Docker, and the [macOS native compiler/sandbox prerequisites](native-routing-baseline.md). From the repository root:

```bash
# First build into a fresh output directory; the recorded default is already complete.
npm run routing:barriers -- --run-name barrier-reproduction-1
npm run routing:barriers:rebuild -- --run-name barrier-reproduction-1
npm run routing:barriers:verify -- --run-name barrier-reproduction-1

# Recheck the existing recorded run without replacing its graph/oracles.
npm run routing:barriers:rebuild
npm run routing:barriers:verify
python3 -B docs/evidence/barrier-access-2026-10-16/analyze.py
python3 -B docs/evidence/regional-capacity-2026-10-16/analyze.py
```

Build/rebuild use Docker `--pull never --network none --read-only`, two CPUs, **4 GiB** memory and a 256 MiB `/tmp`; prior graphs/recipes are read-only mounts. Native verification denies networking with `sandbox-exec` and first verifies that even a loopback connection is denied. No provider key/environment changes, public routing requests, paid fallbacks or app server are involved. Changed build code/input needs a new run name; completed graphs are not overwritten. Local outputs remain ignored in `data/barrier-pilot/san-diego-tijuana-barriers-v3/`. Native/rebuild reports may be refreshed and bind to the saved manifest.

## What changed and what was checked

There are **387,002 directed roads, 387,236 history states and 819,241 transitions**. The roads, 185 via-way patterns, history states and initial states are identical to v2. Of 3,083 tagged barrier nodes, 308 qualify; 543 transitions are added at 206 of them, with **zero previous transitions removed or reweighted**. Other qualifying nodes have no usable retained transition, for example because adjacent ways were excluded. The source-backed Commercial Street prohibited/alternative maneuvers retain their decisions.

| Source-backed example | Decision and directed evidence |
| --- | --- |
| San Ysidro node `2859219644`, `motorcar=yes` | Allows `468334902:0:f → 468334902:1:f`; half-incoming to half-outgoing costs 374 modeled ms and agrees with an independent terminal-sink oracle. This tiny cost excludes inspection/waits. |
| Gate `2091673581`, `access=permissive` | Allows `1014945719:9:f → 1014945619:0:f`. |
| Private gate `1228835396`, `vehicle=private` | Both through directions on way `106861013` stay blocked despite retained roads on both sides. |
| Toll booth `2984024603`, no car permission | `294782458:1:f → 294782458:2:f` stays blocked. |
| Gate `2666304927`, `motorcar=yes` plus unsupported `access:delivery=no` | All four incident transitions stay blocked by the qualifier fallback. |
| Locked gate `9425876180`, `motor_vehicle=no` | Remains closed. |

The recovered city routes actually use **different qualified border controls**: US → Mexico crosses node `9357332258` (`motorcar=yes`) on one-way `MEX 1`, `1014246484:0:f → 1014246484:1:f`; Mexico → US crosses node `8181606580` (`motor_vehicle=yes`) on one-way `I 5`, `879503574:0:f → 879503574:1:f`, named “All Travelers Lane.” Reverse road states are absent at these two examples. Original node/way tags, complete incident-way excerpts, transition evidence and full route-state witnesses are retained in [evidence](../evidence/barrier-access-2026-10-16/README.md). Opening the originally noticed node alone was not established as the cause of restored city connectivity.

| Directed journey | v3 static model minutes | v2 |
| --- | ---: | --- |
| San Diego → Tijuana | 22.55 | Unreachable |
| Tijuana → San Diego | 23.70 | Unreachable |
| Chula Vista → Tijuana | 16.83 | Unreachable |
| Tijuana → Chula Vista | 17.25 | Unreachable |
| San Ysidro → Tijuana | 7.78 | Unreachable |
| Tijuana → San Ysidro | 8.08 | Unreachable |

All twelve city-pair witnesses have recomputed legal transition/partial-endpoint costs. Six domestic pair costs remain unchanged. The four city snaps remain 0.514, 3.994, 4.562 and 17.874 m from their inputs, within the 100 m qualification cutoff; source and destination fractions stay explicit. Five origins, including the source-backed port arrival, agree on every full Python Dijkstra/Bellman–Ford cost and five bounded fields at **5/15/60/120/720 minutes**: 1,936,180 full plus 9,680,900 bounded costs. Native verification checks **11,617,080 costs and 9,680,900 memberships**, matched traversal counts, and the partial port destination. These checks prove consistency on the imported model, not independently surveyed road/access truth. The independent rebuild reproduces graph/audit/CSR/gzip and prepared/source-example bytes exactly, without recomputing the expensive oracles.

Eight new policy tests cover permissions, precedence, conditional/unknown fallback, transform preservation, one-way roads, turn restrictions and version separation. `npm run test:routing`: 69 Python cases, 67 pass and two host Osmium skips; all seven regional-helper cases pass in the cached network-disabled Docker image, including those integrations. Fourteen adapter tests, `npm run check`, `npm run typecheck` and `npm run build` pass; existing database assertion and MapLibre/TanStack warnings remain.

## Resources, timings and remaining limits

Import/preparation took **95.51 seconds**; qualification through graph serialization/packing took **196.10 seconds**. Maximum Python worker RSS was **3,314,556 KiB (3.16 GiB)** under the 4 GiB cap. These are worker observations, not a combined cgroup peak. The new preparation pass streams, but the underlying importer still retains full trees and repeated indexes. The earlier wider bbox still has a confirmed 4 GiB OOM failure and has not been retried here. CSR is **8,102,924 bytes** (gzip **3,145,667**); JSON/geometry is 108,238,288 bytes, prepared XML 74,087,980 bytes, plus audits/oracles. CSR alone is not a deployable map/snapping/geometry package.

The independent rebuild imported in **94.55 seconds**, completed through equality checks in **99.86 seconds**, and peaked at **3,309,424 KiB (3.16 GiB)** worker RSS under the same enforced cap.

Native maximum process RSS was 23,904 KiB (23.3 MiB); the Python verifier peaked at 1,248,688 KiB. Compilation took 674.9 ms; initial launch through hello 263.5 ms included 10.94 ms internal graph load/validation. These are local Mac observations, not serverless cold-start evidence.

| Budget | Median of five origins' membership search-loop p50 | Complete local pipe round trip p50, same aggregation | Origins reaching a cut |
| --- | ---: | ---: | ---: |
| 5 min | 0.58 ms | 0.74 ms | 4/5 |
| 15 min | 15.52 ms | 15.76 ms | 5/5 |
| 60 min | 25.40 ms | 25.63 ms | 5/5 |
| 120 min | 25.30 ms | 25.52 ms | 5/5 |
| 720 min | 25.35 ms | 25.57 ms | 5/5 |

Five sequential samples per case/mode; p95 is the maximum, not a robust tail estimate. Search is elapsed wall time around the native heap/adjacency loop, excluding source setup and encoding. Local pipe time includes those stages, scheduling and transfer; **there is no HTTP measurement**. Native runs on macOS while the reference runs in Docker. No implementation-only speed ratio, CPU-only, WASM, Vercel, concurrency, contour-generation or browser-rendering claim is made.

The default first cut remains **219,374 ms (3m39.374s)**. All 60-minute and longer cases reach a cut; all five sources reach the same 364,209 states in complete searches of this finite imported graph. Reaching its end does not establish complete geographic coverage. Otay and routes outside this narrow corridor are absent. Another 197 port-area closed barriers have some reachable arrivals and unreachable outgoing states across the selected origins; this diagnostic does not prove a particular route's only obstruction.

There is **no control-point delay, live queue/traffic, opening-state, citizenship/document eligibility or authoritative crossing verification**. Border-lane ways without numeric speed tags inherit the model's 100 km/h motorway default, so the table is especially unsuitable as a border ETA. Unknown/default barrier handling still excludes many potentially valid roads; the model also retains unsupported restriction/lane/speed/road-type exclusions. Finite sampled routes and fast searches do not meet the original 10–12-hour requirement.

**Follow-ups completed:** the [streaming importer](streaming-import-capacity.md) reproduces frozen v2/v3 output with approximately 69% less corridor worker RSS, and [wider v3 qualification](wide-v3-routing.md) now applies this policy to the saved wider input under the same 4 GiB cap. Three explicitly uncertain Otay ways remain diagnosed without changing v3 semantics. **Next preflight a broader cached-data buffer and its memory requirements.** National anchors, production query packaging and browser range changes remain later work. Keep the single TanStack Start/Vercel goal and quota independence; analytical layers remain deferred.
