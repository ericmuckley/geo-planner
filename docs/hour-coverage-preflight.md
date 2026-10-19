# Qualification headroom and the next one-hour buffer

October 17, 2026. This follows the [regional coverage increment](regional-coverage-increment.md): 2,938,992 states, exact rebuild/native verification, but one San Diego potential cut still reached within 60 minutes. Its flat partial-destination checks peak at **3.74 GiB**, leaving insufficient 25% margin for another increment under 4 GiB.

This follow-up preserves every graph, source, prior oracle, recipe, failed attempt and environment value. Experiments use cached files with **zero downloads and zero routing-provider requests**. No application dependencies, configuration, provider limits or UI behavior change. Complete 60-minute and original 10–12-hour coverage remain separate, unfinished goals.

Follow-up: [east/south one-hour qualification](hour-coverage-qualification.md) now builds and reproduces this admitted candidate, passes fresh Python/native checks and records zero reachable 60-minute potential cuts for all five selected origins. The preflight results below remain unchanged; complete real-world and 10–12-hour coverage are separate unfinished goals.

## Virtual terminal and unchanged checks

`routing/virtual_sink.py` represents the original graph plus a terminal node through a read-only adjacency view. It stores only terminal-entry arcs. Entry arcs retain legal maneuver-history transitions and replace the destination road's full traversal with its partial cost, preserving entry delays. Direct same-road starts are separate terminal seeds. The frozen queue Bellman–Ford oracle independently relaxes this augmented view; it has no priority queue or Dijkstra calls. It avoids the old copies of every adjacency row and a second flat arc list, but still needs labels/queue storage proportional to graph states. National requirements and worst-case queue behavior are unmeasured.

Synthetic checks compare the virtual terminal with the unchanged flat-edge oracle and partial-cost formula across **180 history/detour/delay/multiple-start/fraction cases**, plus explicit direct-before/at/after, unreachable-history and invalid-input cases. Two recorded partial destinations on the old 2,139,131-state buffer provide real-data calibration. Fresh qualification then repeats the current 2,938,992-state graph's five independent full fields, eight budgets, twelve city directions and both partial destinations.

`lean_checks.py` retains the exact function bodies of the frozen qualifier and route diagnostics, changing only the sink-oracle import. `lean_qualification.py` compares the entire functional summary, omitting run ID and measured search/oracle timings only; requires exact five field files and CSR bytes; and binds the previous native evidence to the unchanged graph, fields, partial costs and native source/binary hashes. **No new native run or native timing is claimed.** The prior 249,814,320 comparisons are reused by identity.

The worker also verifies/checksums the graph after compact reload and requests the existing per-file `POSIX_FADV_DONTNEED` policy for completed large checksum reads. It does not edit files or drop global caches. Reported resource changes apply to **both the virtual sink and the explicit post-reload advice boundary**; they do not isolate either change's contribution. Complete wall-time spans also have different calibration work: the previous run recalculated five old-buffer full fields; this run checks two old-buffer sinks while reusing the unchanged full-field oracle's prior calibration. Both runs freshly qualify all five current fields/eight budgets and both current partials. Do not treat their total times as a controlled algorithm speedup.

## Measured qualification result

Fresh qualification passes with **the entire functional summary unchanged**: all city paths/costs, source snaps, source warnings, boundary flags, first cuts, membership digests and both partial destinations. Five 64-bit full-field files and the CSR are byte-identical. It compares **14,694,960 full + 117,559,680 bounded state costs** and both current partials, after calibrating the two old-buffer sink costs. The existing native evidence remains checksum-bound and reused; it is not a new set of native comparisons.

| Qualification workflow | Worker peak | Complete cgroup peak | Recorded worker wall |
| --- | ---: | ---: | ---: |
| Previous flat sink checks | 3,011,984 KiB / 2.87 GiB | 4,021,116,928 B / 3.74 GiB | 1,705.86 s |
| Virtual terminal + post-reload advice | **1,614,536 KiB / 1.54 GiB** | **1,664,774,144 B / 1.55 GiB** | **898.55 s** |

Observed complete-container peak falls **58.6%**. All checkpoints record zero OOM/kill/limit events and swap max/current/peak zero. The new qualification peak with 25% margin is **2,080,967,680 bytes / 1.94 GiB**, restoring that gate for the current graph. This does not reduce the separately measured 2.94–2.97 GiB import/export peaks; the next candidate must include those and actual preparation too. Wall-time spans and calibration differences are described above; these are single preprocessing observations, not a search benchmark.

## Pinned inputs and candidate

Current graph identity: `e8a6bc98cac1729637f73fd75a22519e7bcfc1f108d1207d7b7a286a09afb3a8`. Source XML is `data/sparse-pilot/sparse-paged-candidate-v1/car-roads.osm`, **442,764,751 bytes**, SHA-256 `f7c4bda33bfa33a1f2f6cc7ca0f32257bac68559ebe31c1488f7b8510effa92e`. Bounds: `[-117.65,32.0,-116.3,33.6]`; static v3 model retains 5-second signal and 20-second U-turn penalties.

The [next pinned profile](../routing/profiles/coverage-hour-v1.json) targets **[-117.65,31.9,-116.0,33.6]**. It extends the observed eastern/southern 60-minute exits, retains northern/western margins and Mexico, and stays within the existing parent rectangle. All directions still need checking after a new graph is built: new geometry can change shortest paths. The existing cut inventory is 309 nodes / 365 history states, all source-linked. Within 60 minutes the current graph reaches 1 cut for San Diego, 6 for El Cajon, 9 for Tijuana and 7 each for San Ysidro/port lane; every one is east or south. Zero west hits is not proof of source completeness.

Parent `data/valhalla-v2/region.osm.pbf`: **677,680,499 bytes**, SHA-256 `7f3cdfc99196d51e732fff06dabb004c0d2f1a4d557442daec9789a19b633dbe`. Road snapshot: **2026-10-14T20:21:12Z**; separate admin supplementation is October 16. Parent AZ/NV road gaps and absent Canada remain. See [source provenance](regional-routing.md).

Qualification uses cached base image `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7` (tools based on Valhalla revision `7fd2228e5863b442bc1ac8d25eece6415dd91bff`). Preparation uses the separate pinned Linux arm64/CPython 3.12/Pyosmium 4.3.1 reader image `sha256:025ebba8267c0aad21bc4cb52b40c4726b65a13a1ebe66b8642df5495261ddd5`. The [six-wheel lock](../routing/tools/pyosmium-v1.json) and [sparse recipe](sparse-routing-resources.md) remain unchanged; this turn adds no tooling downloads. These are our separate static-model experiments, not a rebuilt Valhalla service graph.

## Exact commands

Requires Docker, Node/npm, all current/frozen graph/source/fixture artifacts, the cached images and wheel record. No provider key is used. In order:

```sh
# New output; preserves all original graph and oracle artifacts.
npm run routing:qualify:lean

# Refuses to proceed unless qualification restores 25% headroom.
# Six native fixtures plus exact current-region XML/census.
npm run routing:coverage:hour -- --case calibration

# Same-code/image/profile calibration is mandatory before new geography.
npm run routing:coverage:hour -- --case candidate

python3 -B docs/evidence/hour-preflight-2026-10-17/analyze.py
```

Defaults are `data/qualification-pilot/virtual-sink-v1`, `data/coverage-pilot/hour-calibration-v1` and `hour-candidate-v1`. Completed or failed identities refuse overwrite. Lean reproduction accepts `--run-name fresh-name`; its report is the pinned prerequisite of the recorded preflight recipe. Preparation accepts `--run-name fresh-name` and candidate `--calibration-run fresh-calibration-name`; proof scripts/profile/image must match. A changed prerequisite needs a new versioned identity rather than modifying saved attempts. Both source and candidate preparation use the unchanged original-ID sparse selector and recursive native reference completion, with six boundary/reference fixtures. The rejected simple selector remains rejected.

## Admission and measurement scope

`hour_admission.py` uses the largest corresponding candidate/calibration node, way, relation, eligible-segment, restriction-prefix/rule, road-ceiling and history-ceiling ratio. It scales the **larger of the recorded import and rebuild complete-container peaks**, and separately scales the measured lean-qualification peak. Compare those forecasts with the larger measured calibration/candidate preparation peak; take the maximum of sequential phases and add **25%**. Require exact calibration/oracle parity, zero limit pressure, no OOM and explicit no-swap 4 GiB policy. The candidate XML need not equal the old region: its distinct bounds/source checksum identify new geography.

This is a heuristic for an isolated **4 GiB/two-CPU** build and qualification, not a memory bound. Restriction topology, fallback complexity, page ownership/cache and runtime noise may scale differently. Preserve failures without raising the cap. Passing preflight does not build a graph or qualify a contour; a hold is recorded as a hold.

All new workloads are Linux containers with networking/swap disabled and read-only input mounts. The 16 GiB M4 host and Docker VM are unchanged. Worker/child RSS, cumulative cgroup peak and sampled anonymous/file maxima have separate scopes and must not be summed. Periodic samples can miss composition peaks. Preprocessing timings include validation/calibration, reload or selection, checking/census/output and final verification reads as applicable; Docker startup/module imports/final small metadata writes are excluded. Host cache/concurrency is uncontrolled. None is isolated HTTP graph-search time or a controlled CPU benchmark.

## Measured preparation and admission

The current-region calibration reproduces the **442,764,751-byte XML and complete census exactly**, with all six native fixture graph/audit comparisons passing. Candidate preparation then completes reference checking and a fresh census for **[-117.65,31.9,-116.0,33.6]** using the same code, profile and image.

| Preparation | Worker peak | Largest child peak | Complete cgroup peak | Worker wall |
| --- | ---: | ---: | ---: | ---: |
| Current-region calibration | 1,587,616 KiB | 2,578,640 KiB | 3,173,371,904 B / 2.96 GiB | 205.80 s |
| East/south candidate | 1,612,792 KiB | 2,542,300 KiB | 3,145,691,136 B / 2.93 GiB | 208.06 s |

Both record zero OOM/kill/limit events and zero container swap. Worker and child maxima are separate observations; do not add them. Final verification reads are included in the checkpoints. Inputs, code snapshots, intermediate products and logs remain under the ignored run directories.

Candidate XML: `data/coverage-pilot/hour-candidate-v1/car-roads.osm`, **451,794,442 bytes**, SHA-256 **`64462b578bd9b688290fa8777bbb2564ea40ed649c47d88146353c72097ab1a1`**. Census: **2,334,810 nodes / 462,588 ways / 10,095 relations**; road-state interval **2,955,664–3,043,312**, history-state ceiling **3,047,196**. These are pre-build bounds, not actual graph counts. There are 540 supported boundary segments; they are not a newly qualified cut inventory.

The largest scaling ratio is **1.0368167045**, from candidate history ceiling/current built states. It scales the worst build/rebuild peak to **3,309,731,792 bytes**, and lean qualification to **1,726,065,642 bytes**. Measured preparation is **3,173,371,904 bytes**. The maximum plus 25% is **4,137,164,740 bytes / 3.85 GiB**, below the unchanged **4,294,967,296-byte** cap by 157,802,556 bytes. The recorded decision is **eligible for a separate capped build and qualification**. The forecast is close enough to require the cap and preserved failure evidence; it is not a bound, built graph or complete-hour result.

The [evidence folder](evidence/hour-preflight-2026-10-17/README.md) records exact reports, identities, source/code/profile/tool hashes, the recalculated resource rule, raw check logs and comparison scopes. Its analyzer passes against the saved local artifacts and confirms the functional/byte equality and resource decision.

## Original next task (completed in the follow-up)

See the [completed build and current next task](hour-coverage-qualification.md). The following preserves the original recommendation.

Version a separate build/rebuild/qualification recipe for the admitted candidate XML and profile above. Preserve the frozen increment and these preflight recipes; do not repoint an existing identity. Bind the exact source, admission report and scripts, retain static v3 semantics, and enforce two CPUs/4 GiB/no swap/no network throughout Linux work. Use the qualified virtual-sink oracle and unchanged full-field checks, with calibration before fresh five-origin/eight-budget/twelve-city-direction/two-partial qualification. Rebuild all seven artifacts identically, rerun the unchanged native verifier, then inventory every source-linked cut/history state in every direction. Expanded topology may change best routes: explain changed legal witnesses rather than requiring old clipped paths.

The geographic target is **no reachable potential cut within 60 minutes for the selected origins**. If clipping remains or the resource gate fails in practice, record it and refine the next bounded experiment without raising the cap. At this preflight stage the build recipe was not implemented; the commands above reproduce qualification and preflight only. The linked follow-up adds the separate build workflow.

Validation this turn: **110 host Python cases (106 pass, four tool/platform skips)**, **19 scoped Linux cases (no skips)**, **14 adapter cases**, `npm run check`, `npm run typecheck`, `npm run build`, the new analyzer and the prior regional-increment analyzer pass. The cached Linux reader lacks a C++ compiler; compiler/kernel checks run on the Mac, and no new full Linux discovery or native qualification run is claimed. Existing Biome database/upstream build warnings remain. See the evidence validation record for exact commands and copied logs.

Final integrity checks match **all 126 preserved routing/lockfile/generated-route hashes**. `.env.local` remains ignored and was neither read nor changed, nothing is staged, and the existing Valhalla container is healthy. Host disk has approximately **240 GiB free** after retained outputs; packed graph size excludes source, JSON, rebuild and oracle artifacts.

## Limits carried forward

The graph, routes and cuts remain those of the prior qualified region until a separate next graph is built. Default first potential cut stays **57m47s east/Kumeyaay Highway**; a full 60-minute result is still clipped. Three Otay ways **114198251, 185333061, 577149752** remain explicitly source-marked uncertain. Static permissions, legal witnesses and absence of a warning do not verify current ordinary-car eligibility. Border queues, delays and document requirements remain unmodeled. A way-only outward permission is not proof of legal node/turn/history continuation beyond the extract.

The interactive app remains free hosted openrouteservice with a **60-minute driving cap**. No long-range browser contour, nationwide index or Vercel deployment is added. PostGIS, elevation, road-distance semantics, national anchors, query caching and advanced routing remain deferred.
