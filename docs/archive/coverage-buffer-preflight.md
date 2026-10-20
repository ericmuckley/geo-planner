# Broader San Diego–Tijuana capacity preflight

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

October 17, 2026. **At this preflight, the broader input was prepared and a full graph build held for compact storage.** This is an offline capacity experiment, with zero provider requests or new downloads. It does not deliver complete 60-minute or 10–12-hour routing. The browser remains on its existing provider limits.

The subsequent [compact-import qualification](compact-routing-import.md) builds and verifies this same candidate under the unchanged RAM cap. This document preserves the original preflight measurements and forecast; follow the compact report for current status.

## Candidate and provenance

The [pinned profile](../../routing/profiles/coverage-buffer-v1.json) expands the previous `[-117.25, 32.48, -116.9, 32.85]` bounds in every direction to **`[-117.4, 32.3, -116.6, 33.2]`**, including northern Baja. The previous graph reached its west/north/south cuts in approximately 10m15s/4m40s/5m56s. This larger rectangle is a capacity increment, not a derived time-budget envelope.

Preparation reads the existing `data/valhalla-v2/region.osm.pbf`: **677,680,499 bytes**, SHA-256 `7f3cdfc99196d51e732fff06dabb004c0d2f1a4d557442daec9789a19b633dbe`. Its California/Mexico road snapshot is **2026-10-14T20:21:12Z**; the [parent recipe](../regional-routing.md) records original dated sources/checksums and the later administrative supplements. The parent rectangle is `[-119.8, 30.8, -114.5, 35.5]`; it lacks Arizona/Nevada road data even within that rectangle. Parent cuts and missing Canadian coverage prevent any national or 12-hour completeness claim.

The cached tools image is `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`, containing Osmium 1.16.0 and Valhalla `3.9.1-7fd2228e5`, engine revision `7fd2228e5863b442bc1ac8d25eece6415dd91bff`. This preflight uses Osmium and Python/SQLite, without running engine queries. Docker denies networking, enforces **two CPUs/4 GiB**, and mounts sources/recipes/calibration read-only. No environment file or provider key is loaded.

The extraction uses Osmium's smart strategy with complete `restriction`, `restriction:motorcar`, `restriction:motor_vehicle` and `restriction:vehicle` relations. It exports highway/restriction XML, then retains the existing model's supported highway classes and referenced objects. Completion can pull objects outside the rectangle; state counts only include segments with both endpoints inside.

## What the census measures

`routing/coverage_census.py` streams objects into an on-disk SQLite node-inside lookup and way-length/count table, with a 32 MiB page-cache setting. It retains individual XML objects/way references while counting; it does not materialize the Python road graph, transition lists or geometry. The SQLite products are capacity inputs, not a new routable graph format.

Way-only direction counts mirror the existing importer’s access, one-way, conditional/lane, service and speed exclusions. The **road-state interval** removes every restriction member way at its lower end and none at its upper end. The actual importer removes a subset under its supported-rule/fallback policy. V3 node permissions affect transitions rather than road records. The **history-state ceiling** additionally counts every proper prefix of every syntactically supported via-way prohibition, including candidates that might later be ignored or fail resolution. Histories are tied to the last road of a prefix, so each prefix adds at most one state. These are measured inputs and conservative count bounds, not exact counts of built states or validated routes.

The same census contains the previously qualified graph's actual **926,306 roads / 926,900 states** within its bounds. Its source has 735,356 nodes and 214,681 ways; the road interval is 890,779–930,703 and the history ceiling 932,461. Synthetic tests also check bounds against a built maneuver graph, clipping, missing references, directional exclusions and the admission calculation.

For the broader input:

| Measurement | Result |
| --- | ---: |
| Filtered source nodes / ways / relations | 1,652,946 / 376,997 / 8,251 |
| Supported physical segments wholly inside | 1,761,699 |
| Road-state interval | **2,071,923–2,144,619** |
| History-state ceiling | **2,147,832** |
| Syntactic via-way candidates / prefix ceiling | 1,449 / 3,213 |
| Supported segments crossing rectangle edge | 440 |
| Extract PBF | 114,416,920 bytes |
| Highway/restriction XML / supported XML | 459,505,142 / 333,753,728 bytes |
| Candidate SQLite table file | 23,080,960 bytes |

The 440 edge-crossing segments are geometric census observations, without reachability or legal-exit checks. A future full graph must find new reachable cut witnesses; the old witnesses are inside the new rectangle but that alone proves no complete time budget.

## Capacity decision

Compared with the same census on the qualified graph, filtered nodes grow **2.25×**, ways **1.76×**, and way-eligible directed segments **2.30×**. Applying the largest ratio to the previous observed build/rebuild peaks estimates **5.19 GiB worker RSS / 7.67 GiB container accounting** for the current importer. A 25% admission allowance gives **9.58 GiB**, exceeding the unchanged 4 GiB cap. This is a heuristic, not a measured larger graph, a formal RAM bound or a national forecast. Topology, restriction failures, Python objects and file cache can change scaling.

**That preflight held the broader build with the then-current streaming importer.** Its census is cheap, but extraction reaches the cap and the graph forecast fails admission. Next reduce graph/geometry/transition materialization and investigate the extraction peak, then qualify the same candidate with a fresh identity under the same cap. Merely raising the cap or choosing a smaller rectangle would not demonstrate scalable storage.

Prepared artifacts occupy approximately **0.88 GiB per run**; both attempts are preserved. Around **253 GiB** remained available on the repository volume during preparation. Scaling the previous graph export by the state/road ratio suggests approximately **573 MiB JSON / 43 MiB CSR**, before geometry, oracle vectors, snapshots and scratch. Those export sizes are estimates; neither graph was built. Disk is currently comfortable, while RAM gates expansion. Compressed PBF size was not used to predict RAM.

## Reproduce and inspect

Prerequisites: Docker running, the exact cached tools image, the parent graph/source manifest, the completed wider v3 graph/rebuild report and its original supported XML. See [earlier setup](offline-anchor-pilot.md), [wider qualification](wide-v3-routing.md) and [local development](../local-development.md). From the repository root:

```bash
npm run routing:coverage -- --run-name san-diego-tijuana-buffer-preflight-new
```

Outputs go to ignored `data/coverage-pilot/<run-name>/`. Existing completed or failed run identities refuse overwrite. The run records source/build/calibration hashes, profile, worker fingerprints and snapshots, stage resources, GNU-time child resources, checksummed PBF/XML/SQLite products and `report.json`. Source/code changes need a fresh name. Keep `run-identity.json` and `progress.json` even if a command fails.

The first run is `san-diego-tijuana-buffer-preflight-v1`; a fresh `san-diego-tijuana-buffer-preflight-r2` follows explicit SQLite connection cleanup. The first run's original recipe and results are preserved. Saved reports and their validation are under [preflight evidence](../evidence/coverage-preflight-2026-10-17/README.md).

| Local observation | First run | Fresh repeat |
| --- | ---: | ---: |
| Calibration census | 4.83 s | 5.25 s |
| Extraction plus highway/restriction XML | 35.15 s | 35.56 s |
| Supported-road filter | 8.25 s | 8.23 s |
| Candidate census | 10.19 s | 10.10 s |
| Complete worker wall time | 59.50 s | 60.17 s |
| Worker maximum RSS | 54,784 KiB | 54,804 KiB |
| Osmium extraction-child maximum RSS | 4,015,004 KiB | 4,021,664 KiB |
| Observed container peak / enforced cap | 4,294,967,296 bytes | 4,294,967,296 bytes |
| Cgroup limit events / OOM kills | 405 / 0 | 398 / 0 |

Both runs have zero `oom`, `oom_kill` and `oom_group_kill` events. Nonzero `memory.events.max` records limit pressure; a successful exit does not establish preparation headroom. The extraction's own GNU-time wall observations are 28.32/28.64 s; the broader extraction stage also verifies the parent checksum and exports XML. The machine is Apple M4/16 GiB, with a 7.65 GiB/10-CPU Docker VM; each worker is capped at two CPUs. These sequential runs reuse cached source files and are not isolated or cold-cache benchmarks.

The two preparations reproduce the PBF, both XML exports and both census databases byte for byte. Candidate PBF SHA-256 is `52f1ec4d1eedb5a9bcdda3364f914167b230bf3320e501fdf858f19693ed9649`; supported XML SHA-256 is `7dbc429816a6cac878b1274580034ab22d35cb17c6265ed55f3e6ecaeae5c81e`. Run identities and every product checksum are in the evidence. The earlier parent and wider-v3 artifacts/recipe hashes also validate unchanged.

Preparation/census numbers are local wall-time and memory observations. Cgroup values are cumulative through each checkpoint, include children and charged cache, and differ from worker RSS and GNU-time child RSS. They are not isolated search timings or HTTP timings. No routing, native-kernel, browser, WASM or Vercel benchmark was performed in this phase.

Validation: `npm run test:routing` passes 81 of 83 Python cases, with two host-only Osmium skips; fourteen adapter tests, `npm run check`, `npm run typecheck` and `npm run build` pass. The existing database assertion and MapLibre/TanStack bundling warnings remain. No dependency, secret, application environment or generated route-tree edit was introduced.

## Remaining limits and handoff

The model remains `exploratory-static-car-v3`; no access or cost semantics changed. Source-marked Otay uncertainty, unknown controls, unsupported restrictions/conditionals, default speeds, missing border waits and document/current eligibility remain as [previously recorded](wide-v3-routing.md). More data or faster queries do not resolve those uncertainties. A later build must preserve the original barrier/maneuver fixtures, source uncertainty diagnostics, partial endpoints, cut detection, independent oracles and native comparisons.

The next task is a compact importer/export path: avoid Python dictionaries and duplicated adjacency/JSON/geometry buffers, prove exact parity on frozen downtown/corridor/wider artifacts, then attempt this candidate under 4 GiB. Keep preprocessing memory separate from eventual Vercel query-memory requirements. No Western-US acquisition, national 10k-anchor batch, contour/UI limit increase or cloud rollout is justified yet.
