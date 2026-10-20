# Regional routing capacity and border findings

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

October 16, 2026. **The offline model now builds a 387,236-state San Diego–Chula Vista–Tijuana corridor, about 19 times the downtown v2 graph.** The unchanged native kernel matches the independent oracle and takes approximately 21 ms for warm, component-saturating search on this dataset. The wider first attempt exhausted the 4 GiB importer cap. Cross-border samples are disconnected by this restricted model, including a documented barrier-access limitation. **Complete 60-minute or 10–12-hour reachability is not established.** The browser still uses the hosted 60-minute service.

## Reproduce the working dataset

Prerequisites: the completed [regional Valhalla source recipe](../regional-routing.md), cached Docker tools image and [downtown v2 semantic reference](maneuver-routing-model.md). Native verification additionally requires the existing macOS/Clang/Python setup. From the repository root:

```bash
npm run routing:regional
npm run routing:regional:rebuild
npm run routing:regional:verify

npm run test:routing
npm test
npm run check
npm run typecheck
npm run build
```

`routing:regional` extracts, prefilters, builds and qualifies the graph in Docker with `--network none`, `--pull never`, two CPUs, a 4 GiB memory limit and read-only source/recipe/semantic-reference mounts. Output is ignored under `data/regional-pilot/san-diego-tijuana-corridor-v2/`. The cached immutable tools image is `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`.

`routing:regional:rebuild` reimports and repacks the graph, comparing graph JSON, audit, CSR and gzip hashes without overwriting those files or recomputing all expensive oracle cases. `routing:regional:verify` runs the unchanged C++ kernel under the network-denying macOS policy, checks the actual loopback permission denial, verifies all input hashes and records five timing samples per case/output mode. The agent tool sandbox needed outer exceptions for Docker and nested `sandbox-exec`. No provider endpoint, app server, key, download or remote fallback is used. `.env.local` remains unchanged. The existing local Valhalla service was left running.

Changed source/model/profile/worker inputs require a new `--run-name` on the commands. Full qualification reruns replace reports; preserve them first, then rerun native verification because it is tied to the exact manifest hash. For cached extraction reuse, `routing:regional -- --stage extract --run-name corridor-extract` prepares a separate extraction; `routing:regional -- --extract-cache corridor-extract --run-name corridor-build` verifies/mounts it read-only. Bounds, source snapshot and image must match. Archived larger-extract caches do not match the current corridor profile.

## Source, scope and graph settings

The [profile](../../routing/profiles/regional-border-v1.json) fixes bbox **`[-117.18,32.49,-117.0,32.75]`** and the unchanged `exploratory-static-car-v2` costs: inherited speeds/access/one-way/via-node rules, qualified prohibited via-way history, 5,000 ms signal delay and 20,000 ms U-turn delay. It retains conservative closures for conditional/ambiguous restrictions and barriers. OSM timestamp is **2026-10-14T20:21:12Z**. Input regional PBF: 677,680,499 bytes, SHA-256 `7f3cdfc99196d51e732fff06dabb004c0d2f1a4d557442daec9789a19b633dbe`, derived from the pinned Southern California/Mexico snapshots. [Original acquisition/build provenance](../regional-routing.md) records their URLs, checksums and admin dates. No new OSM acquisition occurred here.

Osmium smart extraction completes ways/restrictions. The importer still drops road segments outside the declared bbox and records cut exits; completed OSM objects outside that bbox do not expand graph coverage. A supported-highway prefilter retains all restriction relations/references and original referenced-node tags while dropping irrelevant highway classes. Its synthetic and frozen-real-graph integration tests pass; the downtown v2 graph remains byte-identical after filtering.

| Working asset | Bytes | SHA-256 |
| --- | ---: | --- |
| Extract PBF | 22,623,030 | `62336b8d6a716180dbfc8892f62d578e3bb4d96e21fead0c697bd1af730868ef` |
| Raw road/restriction XML | 93,204,944 | `f299dd65f19c227c30ab68430ff9d047ca9e36ad120d7a7bb7b7d17620b415b1` |
| Supported-highway XML | 72,875,471 | `088262b37e681041b12cffb55437cce5b42928d5eca89167b0d7f0c41de6f903` |
| CSR adjacency | 8,098,580 | `3b2390d678ef782350f84f35ef5f97dc1631855f13865e74647254a733577d5f` |
| CSR gzip, mtime 0 | 3,144,021 | `9db5c3f31c23d549f973d7463dadb246e0b01ad123155d67daba4ea1d3ca18bd` |

Run identity: `ec496e844a4872594297e74d78f3a66d3e1c877b7d745e126ada587adff87122`; graph identity: `d7461e1c58d0563e44091b7001e4126531714c4b206346f261dea434ac78e335`. There are **387,002 directed road segments, 387,236 history states and 818,698 transitions**. The importer handles 185 via-way prohibitions, restores 478 ways and retains 229 unsupported-relation closures. V1/v2 downtown graph/fields/scripts remain unchanged; their state IDs/indexes cannot be reused for this graph. Data attribution remains © OpenStreetMap contributors, ODbL.

Graph JSON is 108,223,414 bytes and includes geometry, road IDs, base transitions and history mappings. CSR excludes geometry/snapping/attribution and is not a complete deployment asset. Full cost replies occupy **3,097,888 bytes**; membership bitmaps **48,405 bytes**. The working directory occupies approximately 336 MB including sources/oracles. Failed wider assets are also retained; all stay outside Git/Vercel uploads.

## Resource assessment, including the failure

Hardware: Apple M4/16 GiB; Docker VM 8,218,034,176 bytes (about 7.65 GiB). Disk preflight showed 257 GiB free. These are sequential local observations, with no OS-cache flushing. Initial qualification overlapped routine app checks; the dedicated graph rebuild and native benchmark ran afterward.

| Stage | Elapsed observation | Maximum process RSS |
| --- | ---: | ---: |
| Corridor Osmium extraction | 24.84 s | 3,963,076 KiB (3.78 GiB) |
| Supported-highway filter | 1.67 s | 2,222,608 KiB (2.12 GiB) |
| First import/history construction | 92.67 s | included in worker maximum below |
| Complete Python qualification | 450.99 s | 3,306,576 KiB (3.15 GiB) |
| Independent graph rebuild | 90.62 s total, 88.15 s import | 3,309,744 KiB (3.16 GiB) |

Python qualification includes eight complete Bellman–Ford searches, bounded searches, sink-oracle checks and artifact writing; **7.5 minutes is batch qualification time, not query latency**. Worker timers exclude Docker launch and final summary/manifest/recipe writes. Child extraction/filter RSS and Python worker RSS are different per-process measurements; a simultaneous cgroup peak was not recorded. The 4 GiB cap was enforced throughout.

The earlier bbox `[-117.25,32.48,-116.9,32.85]` produced a 53,321,088-byte PBF, 207,924,722-byte road XML and 162,045,477-byte supported-highway XML. Its importer was killed with **exit 137 and a matching Docker `oom` event** under the same 4 GiB cap. No completed graph was published. Its profile, identities, failure record, OOM event and recipe snapshots are preserved. Compressed size and state count alone do not establish build capacity. Do not launch western-US/national imports with this full-tree importer or raise memory blindly.

## Correctness and native timing

Eight origins cover San Diego, Chula Vista, Tijuana, San Ysidro and the earlier restricted/alternative Commercial Street starts. All four coordinate origins snap within 100 m; measured offsets are **0.51/3.99/4.56/17.87 m** respectively. The default physical segment remains `436291033:1`, with 91/572 ms source attachments. Snap/access realism is still unqualified.

The Python run checks **3,097,888 complete** and **24,783,104 bounded state costs** against independent Bellman–Ford across 5/15/30/60/120/360/600/720-minute budgets. Sixteen interior costs and 128 bounded interior memberships also agree with the terminal-sink oracle. Both earlier real maneuver fixtures still block the specified sequence while allowing the alternative arrival.

The byte-identical C++ executable passes **27,880,992 complete/bounded cost checks, 24,783,104 membership checks and 16 interior costs**, with matching traversal counts on every bounded request. That is 52,664,096 reported state comparisons on selected cases, not independent real journeys. Five repetitions produce identical bytes. The separate rebuild reproduces graph/audit/CSR/gzip exactly; it does not rerun the costly independent oracles.

Native timing rows are medians of eight per-origin p50s, five sequential samples per case/mode. Per-case p95 is the largest of five samples; raw observations are retained.

| Budget | Search loop | Setup + search | Cost reply + Python decode | Bitmap reply + checked view | Origins with cut flag |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5 min | 0.99 ms | 1.04 ms | 11.26 ms | 1.10 ms | 4/8 |
| 15 min | 14.87 ms | 14.92 ms | 24.82 ms | 14.67 ms | 8/8 |
| 30 min | 21.31 ms | 21.35 ms | 30.51 ms | 21.15 ms | 8/8 |
| 60 min | 21.21 ms | 21.25 ms | 30.58 ms | 21.40 ms | 8/8 |
| 120 min | 21.33 ms | 21.37 ms | 30.77 ms | 21.14 ms | 8/8 |
| 360 min | 21.15 ms | 21.19 ms | 30.53 ms | 21.17 ms | 8/8 |
| 600 min | 21.32 ms | 21.36 ms | 30.65 ms | 21.06 ms | 8/8 |
| 720 min | 21.22 ms | 21.26 ms | 30.55 ms | 21.10 ms | 8/8 |

Search is elapsed wall time around the in-memory heap/adjacency loop, not dedicated CPU time. Setup includes allocation/seeding, excluding coordinate snapping; encoding is separate. Pipe round trips include scheduling, metadata decoding and complete transfer. Label decoding expands a Python list; bitmap decoding creates a checked view/padding check, not all-state iteration. Correctness comparisons occur outside decode timing. Separate output-mode medians cannot be subtracted to isolate overhead. **There is no HTTP measurement.** Python reference timings run in Docker while C++ runs on the Mac; no implementation-only speed ratio is claimed.

Native process maximum RSS was **23,936 KiB (23.4 MiB)**; the Python benchmark worker peaked at 1,245,472 KiB while retaining JSON/oracles/results. Compilation took 734 ms. Initial launch through hello took 264.7 ms versus 12.54 ms internal load/validation. Three subsequent fresh processes took 7.02–8.09 ms through hello, 4.12–4.29 ms internal load, and 21.68–22.14 ms for the first bitmap request through complete pipe read. Fresh processes do not reproduce a Vercel cold start. WASM/Node/cloud, WAN/concurrency, contour construction and browser display remain unmeasured.

Host tests: 61 Python cases, 59 passed and two Osmium integrations skipped; all seven regional-helper tests, including those integrations, passed in the cached Docker image. Fourteen adapter tests, Biome, typecheck and production build pass. Existing database assertion and MapLibre/TanStack warnings remain. No manual route-tree edits or hosted calls were needed.

## Coverage and Mexico findings

The default source reaches a cut exit in **219,374 ms (3m39.374s)**, at road `25330751:12:f`, head `[-117.1790389,32.7375206]` near the west boundary. Downtown v2 reached its cut at 215,966 ms. Adding many southern roads therefore barely moves the nearest cut for this origin. All selected origins reach cuts by 15 minutes; every 60-minute and 2/6/10/12-hour query is potentially truncated. A missing cut flag would still not independently prove complete OSM/access coverage. Keep `coverageVerified: false`.

Six sampled domestic directed routes have tight legal state-path witnesses. Examples: San Diego → Chula Vista **12.86 modeled minutes**, reverse **13.53**; San Diego → San Ysidro **17.63**, reverse **19.64**. These are static model costs with snapped/partial endpoints, not actual driving predictions or filled-contour evidence.

All six sampled US–Tijuana direction pairs are unreachable in this imported model. The targets have valid interior attachments, so these are model connectivity findings, not a destination-endpoint API limitation. The conservative barrier policy closes **OSM node 2859219644**, tagged `barrier=border_control`, `motorcar=yes`, `motor_vehicle=yes`, name `San Ysidro Port of Entry`, with two retained incident road segments. It also closes permissive gates and toll booths in that neighborhood. The retained diagnostic lists source tags and modeled closures. This is a concrete access-handling limitation; it does not prove that any particular node is the sole cause of disconnection, or that real cross-border driving is impossible. Otay and alternative paths are also outside this corridor. No border queues or current crossing availability are modeled.

**Follow-ups completed:** the separate [v3 barrier-access model](barrier-access-model.md) qualifies explicit car permissions while retaining private/conditional/unknown closures. All six sampled corridor cross-border directions now have legal witnesses through qualified one-way control points. The [streaming importer](streaming-import-capacity.md) then reproduces frozen v2/v3 output, reduces corridor worker RSS by approximately 69%, and retries the failed wider profile successfully under the same 4 GiB cap (926,900 states). Original findings/graphs/failure remain preserved. No queues/delays/current crossing eligibility are modeled; the wider v2 path through Otay has source-marked uncertain access. **Next qualify wider v3 access and coverage**, including that uncertainty, before broader acquisition. Western-US acquisition, national anchors, browser range increases and Vercel rollout remain later steps; the original 10–12-hour requirement is active.

See [evidence and analysis commands](../evidence/regional-capacity-2026-10-16/README.md).
