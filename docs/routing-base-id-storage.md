# Base-graph road-ID storage — October 18, 2026

This follow-up replaces the temporary set of road-ID strings with one previous numeric key when compact roads are ordered. It keeps the original string-set behavior for other inputs. The goal is to make larger offline road graphs practical without changing routing results or spending provider quota. It continues [the source-evidence memory work](routing-source-evidence.md); [the short progress summary](progress.md) describes the overall project.

Follow-up: [range-advised source XML reads](routing-xml-streams.md) now reproduce all four cases and lower the current complete peak further to **1.214 GiB**. The measurements below preserve this earlier ID-storage version.

## Change and preserved behavior

The frozen base builder stores every road ID in a Python set while also building per-node outgoing-road lists. `base_ids.py` first checks whether the exact `Roads` class has nondecreasing `(way, segment, direction)` keys. This pass keeps one predecessor and raises no new validation error. For eligible input, duplicate IDs must be adjacent, so the builder retains only the previous key. Direction values are normalized to the same truth-value rule used by the canonical `f`/`r` IDs. Node/way IDs remain integer values, including values above JavaScript's safe-integer range.

Unordered roads, generic row sequences, subclasses with potentially different ID behavior and incomplete key arrays use the original string-set body. The cost, duplicate/self-loop, delay and restriction validation order/messages remain unchanged. Duplicate directed geometry with different segment IDs remains distinct from duplicate IDs; the separate global geometry guard and conservative maneuver fallback are preserved. The precheck does not assume that sorted IDs are unique.

Outgoing-road lists, turn/access rules, adjacency order, costs, audits, graph identity, canonical JSON, CSR and gzip encoding retain their frozen implementations. `base_id_input.py` copies the frozen source-import body with only the builder binding and optional measurement arguments changed. `base_id_import.py` binds this builder through every original/fallback pass. Existing producers are not edited. The new wrapper/worker are `base-ids-parity.mjs` and `base_id_parity.py`.

Both the original string-set body and ordered body have checkpoints at outgoing-index completion, rule preparation, adjacency completion, index release and hashing. The original body is AST-identical after removing measurement statements; the routing/restriction body and source-import body are constrained separately. Outgoing dictionary/list container sizes and ID set/string sizes use `sys.getsizeof`; these are shallow object measurements, excluding allocator overhead and outgoing node/index integer objects. They are separate from cgroup and process RSS measurements.

Eleven focused tests cover ordered/unordered inputs, adjacent/nonadjacent duplicate IDs, self-loops, cost/delay/error priority, generic rows and subclasses, direction truth values, large IDs, incomplete arrays and turn/blocked-node behavior. Seventeen fresh importer fixtures compare both modes with the frozen importer, including barrier/access and global duplicate-geometry fallback cases, with 296 full and 888 bounded Bellman–Ford fixture comparisons per mode. Every worker runs the selected mode's importer fixtures and the prior 11 source-evidence/failure fixtures. Regional independent/native qualification is reused on identical graph bytes rather than rerun here.

## Reproduce

Prerequisites are the original qualified graphs and canonical `data/evidence-pilot/evidence-v1-*` records from [the prior workflow](routing-source-evidence.md). Inputs and tools are already cached; these commands use no environment file, provider key, network or download:

```sh
# A fresh corridor-only measurement of the unchanged string-set method.
npm run routing:base-ids -- --case corridor-v3 --id-mode strings --series base-strings-v1

# Ordered-ID parity on all four frozen cases, smaller cases first.
npm run routing:base-ids -- --case downtown-v2
npm run routing:base-ids -- --case corridor-v3
npm run routing:base-ids -- --case wide-v3
npm run routing:base-ids -- --case hour-v3
python3 -B docs/evidence/routing-base-ids-2026-10-18/analyze.py
```

Completed attempts are sealed under ignored `data/base-id-pilot/base-strings-v1-corridor-v3` and `data/base-id-pilot/base-ids-v1-*`. Repeat with fresh series names; use the same fresh ordered series for all four cases. The current case requires three smaller same-code/same-mode proofs. Equality references remain canonical `evidence-v1-*`; changed code requires a new version and output identity. Preserve sealed failures and successes.

The wrapper retains two CPUs, 4 GiB RAM, no container swap, `--pull never`, no networking, read-only sources/recipes/root filesystem and a 256 MiB temporary filesystem. Tools remain pinned to image `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`, Python 3.12.3/Linux arm64, Valhalla tools revision `7fd2228e5863b442bc1ac8d25eece6415dd91bff`. These custom graph imports do not use Valhalla search. No dependencies are added.

Run identities bind the ID mode, source/profile/image/code, predecessor report/manifest and original qualification. Workers verify actual frozen source/artifact/recipe files and snapshot their code. The current case also verifies independent/native report hashes, counts and native source/binary bindings before success. No larger graph is attempted.

## Measurements

| Case | Exact ordered artifacts | Before complete peak (GiB) | After complete peak (GiB) | Complete wall time (s), before → after |
| --- | ---: | ---: | ---: | ---: |
| downtown-v2 | 4 | 0.053 | 0.050 | 2.34 → 2.11 |
| corridor-v3 | 6 | 0.315 | 0.270 | 47.33 → 47.54 |
| wide-v3 | 7 | 0.608 | 0.539 | 149.55 → 147.21 |
| hour-v3 | 7 | 1.543 | 1.413 | 476.17 → 475.29 |

The four ordered runs reproduce **24 artifacts** exactly; the fresh string-profile corridor reproduces another **six**. All five runs record zero memory-limit/OOM/kill/swap events. Current complete peak falls **1.543 → 1.413 GiB** (**8.4%**), to **1,517,146,112 bytes**. Including the 25% factor gives **1,896,432,640 bytes (1.766 GiB)**. This checks current-workload headroom, not larger admission.

Current worker high-water RSS falls **1,584,232 → 1,256,536 KiB** (1.511 → 1.198 GiB). Import time is **402.68 → 401.32 s**, with complete wall time **476.17 → 475.29 s**. These close times are single uncontrolled observations, not a general speed claim. The prior table baseline is the preceding uninstrumented workflow; the separately profiled corridor uses the same new instrumentation in both modes.

The fresh corridor string profile retains at most **387,764 IDs**, with **16,777,432 set bytes + 20,781,476 string bytes = 37,558,908 shallow bytes (35.82 MiB)**. The corresponding ordered passes retain **one key**, no ID set and no ID strings retained for validation. Outgoing node/reference counts and container sizes match exactly per build. Paired complete peaks are **0.311 → 0.270 GiB**. This original-method profile is corridor-only; no fresh full-sized string-ID byte inventory is claimed.

Every real-data pass uses the ordered path with no fallback. The current graph has seven base builds; each retains one key. All seven order checks together take **0.976 s**. The largest outgoing index still has **1,567,609 node entries** and **221,840,968 shallow dictionary/list bytes (211.56 MiB)**, excluding node/index integer objects and allocator overhead. These lists are unchanged.

Current base construction reaches a cumulative **1,322,049,536-byte** peak before evidence. Whole-file source-evidence reads then raise it to **1,517,146,112 bytes**, while file cache rises from **39,804,928 to about 491,601,920 bytes**; completed-input advice returns it to the earlier level. The highest periodic current-memory sample is **1,515,511,808 bytes**, including **1,018,429,440 anonymous / 491,601,920 file bytes**. It is a sample, not the exact kernel peak composition. Export and final verification do not raise the peak.

These are single local observations on Apple M4/16 GiB, with uncontrolled host/VM/cache conditions. Complete cumulative cgroup peaks include fixtures, parsing, all base passes, history, evidence, export and final verification reads. A checkpoint's `memory.peak` is cumulative, not an isolated stage peak. RSS and periodic anonymous/file samples are separate scopes; maxima must not be summed. Host/VM paging is unmeasured. Shallow object sizes and the 25% headroom factor do not predict larger-graph query memory.

The current graph remains `b50422b83537cecf12f1ecb4f7a3fa4e80df206726796b562135715f3737d048`: 3,034,771 roads, 3,036,124 states, 6,411,757 arcs and 1,160 via-way prohibitions. Bounds remain `[-117.65,31.9,-116.0,33.6]`; model `exploratory-static-car-v3` retains 5,000 ms signal and 20,000 ms U-turn delays. Source XML remains 451,794,442 bytes, SHA-256 `64462b578bd9b688290fa8777bbb2564ea40ed649c47d88146353c72097ab1a1`, from the cached California/Mexico snapshot dated `2026-10-14T20:21:12Z`. [Preparation and provenance](two-hour-coverage-preflight.md) are unchanged.

The original regional full/bounded/partial/native qualification is checksum-bound to identical graph bytes. The saved current native report has 258,070,540 cost/membership comparisons plus two partial destinations; that original macOS run was not Docker-memory-capped. Fresh synthetic fixture checks are reported separately. These measurements describe graph preparation/verification, not graph-search or HTTP latency, contours, browser behavior or Vercel execution.

## Remaining work

The next bounded task is a versioned read-only range-aware stream for the source-evidence XML readers. Whole-file XML reads now set the complete current-workflow peak: the kernel retains approximately one source file until completed-read advice. Test advice for completed read ranges without changing parser events, bytes, ordering, audit/excerpts, EOF/malformed-input errors or source permissions. No global cache drop or input writes are needed. Require focused stream/source fixtures plus exact graph/audit/source/CSR/gzip outputs on all four frozen cases and the original qualification bindings under the same cap.

Keep the remaining per-node outgoing lists and qualification/reload storage in the resource assessment. They are unchanged here; outgoing container measurements exclude their node/index integer objects and allocator costs. After memory/source admission, a larger region still needs fresh independent qualification and cut checks. Preserve old modules and all sealed attempts.

Coverage remains unchanged. Five sampled origins have no potential graph-edge cuts within 60 minutes; first cuts occur at 63m32s–77m34s and every selected 120-minute case reaches cuts. This does not establish all-origin/source completeness or long-range contours. Northern Baja is retained; uncertain Otay ways `114198251`, `185333061` and `577149752` remain reported. Border queues, documents and current crossing eligibility are unmodeled. The larger continuation envelope still exceeds cached eastern/southern source geography, including missing Arizona/Nevada roads.

Larger admission remains **on hold** until source and complete-workflow resource requirements are met. The old 20.64 GiB figure is a previous workflow's scaling forecast, not measured candidate graph/query RAM or a forecast for this path. Any admitted graph requires a fresh identity, exact rebuild, independent full/bounded/partial/native checks and all-direction cut inventory at 120 minutes. US-wide acquisition, the 10k-anchor batch, app range increases, caching and Vercel rollout remain deferred. The hosted app's 60-minute cap is unchanged.

Raw records and exact validation commands are in [the evidence directory](evidence/routing-base-ids-2026-10-18/README.md).

The five retained attempts total **2,284,466,187 logical file bytes (2.13 GiB)**; **216.97 GiB** remains free. All source/tool inputs were already cached.

Validation passes: **151 host Python cases (142 pass, nine tool/platform skips)**, **60 scoped Linux cases (no skips)**, **14 adapter tests**, `npm run check`, `npm run typecheck`, `npm run build` and the saved analyzer. Existing database lint and upstream build warnings remain. All **181** pre-existing routing/lockfile/generated-route fingerprints match, seven new recipe files remain frozen, local documentation links resolve and nothing is staged. Environment values were neither inspected nor changed; `.env.local` remains ignored. The existing Valhalla service is healthy. Exact commands and logs are in the evidence directory above.
