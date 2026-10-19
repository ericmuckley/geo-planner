# Targeted source-evidence indexes — October 18, 2026

Follow-up: [base-graph ID storage](routing-base-id-storage.md) is now complete at a 1.413 GiB current complete peak. Whole-file XML reads are the next memory target; the results below remain the historical source-indexing baseline.


This experiment removes temporary indexes for unrelated road nodes while producing the same graph and source evidence. It continues the [restriction-member lookup work](routing-member-lookup.md). Our own router still needs larger geographic coverage and app integration to meet the original 10–12-hour requirement; the hosted app remains at 60 minutes. See [the plain-language progress summary](progress.md).

## Change and verification

The frozen `barriers.source_examples` indexes incoming and outgoing roads for every node, then uses those indexes for five source-backed control points. The new `targeted_evidence.py` scans the existing numeric endpoint arrays and retains road indices only for those five nodes. Road order, repeated references, empty lists and large node IDs are preserved. It allocates no per-road dictionaries during this scan.

The remaining function body is unchanged apart from optional measurements/checkpoints: audit selection/order, transition replay, closed-control failures, the required port permission, both XML passes, original tags, incident ways and excerpt serialization retain the frozen behavior. An AST check verifies this constraint. No routing rules, graph construction, source bytes or encoders change. Old code and all prior recipes, artifacts and failed attempts remain preserved.

Five focused tests include **11 synthetic source-evidence cases**: permitted/closed/isolated controls, a source incident way excluded from the routing graph, Unicode tags, reordered decisions, missing decisions, an unsafe through transition, a closed port, malformed XML, invalid references and error priority. Return values, mutated audit, excerpt bytes and exception type/message match the frozen function. Each real-data worker also reruns the prior 17 importer fixtures, including global duplicate detection and fallback priority, with 296 full and 888 bounded independent fixture cost comparisons. Regional route qualification is reused on identical bytes; it is not freshly run here.

## Reproduce

Prerequisites are the cached qualified graphs and canonical `data/member-pilot/members-v1-*` records from the preceding workflow. These commands use no provider keys, environment files, downloads or public API calls:

```sh
npm run routing:evidence -- --case downtown-v2
npm run routing:evidence -- --case corridor-v3
npm run routing:evidence -- --case wide-v3
npm run routing:evidence -- --case hour-v3
python3 -B docs/evidence/routing-source-evidence-2026-10-18/analyze.py
```

Completed defaults are sealed in ignored `data/evidence-pilot/evidence-v1-*`. To repeat, append the same fresh `--series evidence-repeat-01` to all four build commands, smaller cases first. Equality references remain canonical `members-v1-*`. Code changes require new versions and output identities; preserve sealed attempts.

`evidence_parity.py` and `evidence-parity.mjs` retain the existing resource policy: two CPUs, 4 GiB RAM, no container swap, no networking, `--pull never`, read-only source/recipe/root filesystem, and a 256 MiB temporary filesystem. The tools image remains pinned to `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7` (Python 3.12.3/Linux arm64, Valhalla tools revision `7fd2228e5863b442bc1ac8d25eece6415dd91bff`). These custom graph imports do not use Valhalla search. No dependencies are added.

Each worker verifies actual source and frozen artifact/recipe hashes, snapshots its code and binds source/profile/image/code, predecessor manifest/report and original qualification. The hour case requires its three same-code smaller proofs and verifies original independent/native reports, counts, source and binary bindings. It adds substage measurements around indexing, transition evidence, each XML pass and subsequent uncertainty processing. No larger graph is built or admitted.

## Measurements

| Case | Exact artifacts | Before complete peak (GiB) | After complete peak (GiB) | Complete wall time (s), before → after |
| --- | ---: | ---: | ---: | ---: |
| downtown-v2 | 4 | 0.052 | 0.053 | 1.94 → 2.34 |
| corridor-v3 | 6 | 0.322 | 0.315 | 46.87 → 47.33 |
| wide-v3 | 7 | 0.653 | 0.608 | 148.97 → 149.55 |
| hour-v3 | 7 | 1.730 | 1.543 | 479.98 → 476.17 |

All **24** graph/audit/source/CSR/gzip artifacts match exactly; all four runs record zero memory-limit/OOM/kill/swap events. The current complete peak falls **1.730 → 1.543 GiB** (**10.8%**), to **1,657,176,064 bytes**. With the 25% factor, the result is **2,071,470,080 bytes (1.929 GiB)**. This passes the current-workload headroom check, not a larger-graph admission.

Worker high-water RSS rises slightly, **1,569,680 → 1,584,232 KiB** (1.497 → 1.511 GiB). Current import time is **403.26 → 402.68 s**. Downtown peak and the three smaller wall times rise slightly. These single observations do not establish a general speed or worker-RSS improvement.

All three v3 cases retain **six incoming and six outgoing road references across five nodes**. On the current graph, scanning 3,034,771 road endpoint pairs takes **166.10 ms**; transition evidence takes 1.36 ms and the unchanged way/node XML passes take **8.38 / 8.26 s**. No per-road dictionary is materialized during the index scan.

The current cumulative peak is first recorded at **baseReady2 (189.75 s)**, before evidence generation. Indexing (405.84 s), both XML scans, uncertainty processing, exports and final verification do not raise it. At the evidence checkpoints, anonymous memory remains 1,150,464,000 bytes; file cache rises from 39,346,176 to about 491,151,360 bytes during whole-file reads and returns to 39,346,176 after completed-input advice. The highest periodic current-memory sample is 1,656,913,920 bytes, with 1,612,210,176 anonymous and 39,346,176 file bytes; this is a sample rather than the exact peak composition. Base construction is now the measured complete-workflow high-water stage, supporting the next task below.

These are single local observations on Apple M4/16 GiB with uncontrolled host/VM/cache conditions. Complete container `memory.peak` includes fixtures, import, evidence, export and verification reads. Each checkpoint peak is cumulative from container startup; it is not an isolated phase peak. Current anonymous/file samples and worker high-water RSS are separate scopes. Periodic samples can miss brief composition peaks; maxima must not be summed. Host/VM paging is unmeasured. The 25% factor checks headroom for this workload and does not predict candidate graph/query memory.

The current graph remains `b50422b83537cecf12f1ecb4f7a3fa4e80df206726796b562135715f3737d048`: 3,034,771 directed roads, 3,036,124 states, 6,411,757 arcs and 1,160 via-way prohibitions. Bounds remain `[-117.65,31.9,-116.0,33.6]`; the `exploratory-static-car-v3` model retains 5,000 ms signal and 20,000 ms U-turn delays. Source XML remains 451,794,442 bytes, SHA-256 `64462b578bd9b688290fa8777bbb2564ea40ed649c47d88146353c72097ab1a1`, from the cached California/Mexico snapshot dated `2026-10-14T20:21:12Z`. [Original preparation/provenance](two-hour-coverage-preflight.md) is unchanged.

The original full/bounded/partial/native qualification is checksum-bound to identical graph bytes. The current saved native report contains 258,070,540 cost/membership comparisons plus two partial destinations; its original macOS run was not Docker-memory-capped. Fresh synthetic fixtures are recorded separately. Measurements here describe preparation and verification, not graph-search time, HTTP time, contours, browser behavior or Vercel execution.

## Remaining work

The next bounded task is to profile the temporary base-graph construction indexes, especially the global road-ID string set and per-node outgoing lists in `compact_storage.build_graph`. Source-evidence indexes are now targeted, while base construction still has substantial live and retained anonymous allocations. Version a smaller ID-validation representation on the guaranteed ordered compact-road input first, preserving duplicate/self-loop/cost validation and error priority. Require focused adversarial fixtures and all four frozen graph/audit/source/CSR/gzip comparisons under the same cap before considering a broader build. Preserve all original modules and attempts.

Whole-file XML reads also retain file cache until completed-input advice; range-aware read-only streams remain a separate candidate after the new phase evidence is assessed. Qualification/reload memory needs its own assessment. Keep these tasks and any forecast separate from measured larger-graph admission.

Coverage has not changed. Five sampled origins have no potential graph-edge cuts within 60 minutes, with first cuts at 63m32s–77m34s; every selected 120-minute case reaches cuts. This does not prove all-origin/source completeness. Northern Baja is retained, while three source-uncertain Otay ways (`114198251`, `185333061`, `577149752`) remain reported. Border queues, documents and current crossing eligibility are unmodeled. The larger continuation envelope also exceeds cached source geography to the east/south, including missing Arizona/Nevada roads.

Larger graph admission remains **on hold** pending a measured complete-workflow resource rule and source admission. The old 20.64 GiB figure is an earlier workflow's scaling forecast, not measured candidate graph/query memory or a forecast for this implementation. An admitted graph needs a fresh identity, exact rebuild, independent full/bounded/partial/native checks and all-direction cut inventory at 120 minutes. US-wide acquisition, the 10k-anchor batch, app range increases, caching and Vercel rollout remain deferred.

Raw records and exact validation commands are in [the evidence directory](evidence/routing-source-evidence-2026-10-18/README.md).

The retained parity series totals **2,086,382,246 logical file bytes (1.94 GiB)**; **219.17 GiB** remains free. All inputs were already cached.

Validation passes: **140 host Python cases (131 pass, nine tool/platform skips)**, **49 scoped Linux cases (no skips)**, **14 adapter tests**, `npm run check`, `npm run typecheck`, `npm run build` and the saved analyzer. Existing database lint and upstream build warnings remain. All **176** preserved routing/lockfile/generated-route fingerprints match, the five new recipe fingerprints remain frozen and nothing is staged. Environment values were neither inspected nor changed; `.env.local` remains ignored. The existing Valhalla service is healthy. Exact commands and logs are in the evidence directory above.
