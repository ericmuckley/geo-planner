# Wider v3 routing qualification

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

October 16, 2026. The saved wider San Diego–El Cajon–Tijuana region now uses the qualified v3 control-point policy and streaming importer. All twelve sampled city directions have finite, recomputed legal-in-model witnesses. The six US–Tijuana directions use explicitly permitted San Ysidro controls, while source-marked Otay access uncertainty remains visible in separate diagnostics. **Complete 60-minute or 10–12-hour coverage is still unverified; the browser range is unchanged.**

## Inputs and reproduction

The input is the same **162,045,477-byte** cached `data/regional-pilot/san-diego-tijuana-v2/car-roads.osm`, SHA-256 `2db3f467a62182314fc94a4fe5bb6c919f36d4c17e3784aae0fb1ad8720cc0fd`, bbox `[-117.25,32.48,-116.9,32.85]`. Southern California/Mexico source timestamp remains **2026-10-14T20:21:12Z**. Full original download/checksum/extraction provenance is in [regional routing](../regional-routing.md) and [streaming capacity](streaming-import-capacity.md). No geographical data was downloaded in this phase.

Model `exploratory-static-car-v3` and policy `explicit-control-point-car-v1` are unchanged. The wider graph has a distinct identity because its roads/coverage differ from the corridor. New source-uncertainty fields are diagnostics and do not open or close ways. Changing unknown-way eligibility would require a new semantic identity.

Run ID: `13f1652082013ac9fd899eeef8a14c53d376affec200504585003d73f8a7a763`.
Graph ID: `575557c073aec3e4e0a84cdd1fd6e6336ca6e2aede6d8648ca635ef4850db3d2`.
CSR SHA-256: `073996d8eaacabb1790f1fd4dba3176183bc5b63d3cc371c689e52a5e95ed3ad`.
All input/profile/recipe hashes are in the [build manifest](../evidence/wide-v3-2026-10-16/build-manifest.json).

Prerequisites: the saved failed wider XML, completed `data/import-pilot/stream-v1-wide-v2/`, frozen downtown v2 fixture, cached tools image and Docker. Native verification uses the existing macOS C++17 compiler and `sandbox-exec` prerequisites.

```bash
# Existing default is complete and refuses a build overwrite; recheck it:
npm run routing:wide:rebuild
npm run routing:wide:verify
python3 -B docs/evidence/wide-v3-2026-10-16/analyze.py

# A fresh full reproduction:
npm run routing:wide -- --run-name wide-v3-repeat
npm run routing:wide:rebuild -- --run-name wide-v3-repeat
npm run routing:wide:verify -- --run-name wide-v3-repeat
```

Outputs remain ignored under `data/barrier-pilot/san-diego-tijuana-wide-v3/`. Build/rebuild use `--pull never --network none --read-only`, two CPUs, **4 GiB** memory and 256 MiB `/tmp`; prior sources/graphs/recipes are read-only. Native verification first checks that its network sandbox denies loopback, then uses the unchanged C++ kernel. Completed graphs/oracles are preserved; rebuild/native reports can be refreshed and bind to the exact manifest. Changed inputs/code require a fresh run name. No provider calls, key/environment changes or app server are needed.

The cached image remains `sha256:6652906bfea590161b144a6e4fac146a41e14cbafae581dcb9e38c74ceaa53a7`, with Python 3.12/Osmium 1.16.0 and Valhalla revision `7fd2228e5863b442bc1ac8d25eece6415dd91bff`. This experiment runs our static graph model rather than Valhalla routing. C++ search remains `csr-dijkstra-v1`, Apple Clang 17, `-std=c++17 -O3 -Wall -Wextra -Werror`; the binary is unchanged from prior qualification. Signal/U-turn costs remain 5,000/20,000 ms and road speeds retain the prior static defaults/numeric tags.

## Directed routes and source uncertainty

| Journey | Static model minutes |
| --- | ---: |
| San Diego → Tijuana | 22.55 |
| Tijuana → San Diego | 23.70 |
| El Cajon → Tijuana | 33.14 |
| Tijuana → El Cajon | 31.12 |
| San Ysidro → Tijuana | 7.78 |
| Tijuana → San Ysidro | 8.08 |

US → Mexico witnesses traverse node `9357332258` (`motorcar=yes`) on one-way MEX 1; reverse journeys traverse node `8181606580` (`motor_vehicle=yes`) on one-way I-5 “All Travelers Lane.” These six selected witnesses avoid the source-marked uncertain ways. This is qualified **static permission**, not current operational eligibility, inspection time or a driving ETA. All route diagnostics retain `carEligibilityVerified: false`; absence of a source hint is not evidence that all access is known.

Source way IDs **114198251, 185333061 and 577149752** explicitly mark border-barrier/access information as uncertain. They retain 1/42/6 directed road segments respectively. A deliberately selected interior destination on `114198251:0:f` is reachable from Tijuana in **1,167,889 modeled ms (19.46 minutes)** and agrees with an independent terminal-sink oracle. Its witness traverses permissive gate `7229150207` and carries the source-uncertainty flag. The previously recovered v2 Otay journey is separately replayed through v3 as a full warned route; it is not presented as a minimum-cost v3 journey.

The original OSM excerpt names nearby CHP inspection-facility ways. [CHP describes its Otay Mesa facility](https://www.chp.ca.gov/find-an-office/border-division/646-otay-mesa-commercial-vehicle-enforcement-facility/) as inspecting commercial vehicles entering California from Mexico, at the Enrico Fermi Drive address. Combined with the local tags, this establishes commercial inspection context. It does **not** establish per-edge ordinary-car permission or prohibition; `hgv=designated` alone is not treated as exclusive truck access. No live wait/operating-state data or eligibility decision is imported into the graph. See [recorded source assessment](../evidence/wide-v3-2026-10-16/official-source-audit.json).

The private through-gate at node `1228835396` (`vehicle=private`) stays blocked in both directions despite retained roads on both sides. Missing-permission toll booth `2984024603`, qualified port node `2859219644`, conditional/unknown fallback and the source-backed Commercial Street maneuver examples retain their decisions. Four new audit tests cover hint selection, complete source excerpts, exact partial-route cost/flags and prohibited through-gate evidence.

## Coverage and measured resources

The graph has **926,306 directed roads, 926,900 history states, 1,957,330 arcs and 501 via-way prohibitions**. The policy admits 822 explicitly permitted control points. Comparison with saved wide v2 proves unchanged roads, history states and maneuver patterns, **1,985 added transitions at 634 qualified nodes**, and zero removed/reweighted prior transitions. All five selected sources reach the same 859,848 states in a complete search of this finite graph. CSR is **19,366,292 bytes**, gzip **7,549,832**; geometry, snapping, source/audit data and oracle vectors are additional. CSR alone is not a deployable full map/query package.

| Origin | First cut exit |
| --- | ---: |
| San Diego | 10m14.768s |
| El Cajon | 4m40.140s |
| Tijuana | 5m56.393s |
| San Ysidro | 11m21.491s |
| Port attachment | 11m22.977s |

All selected origins reach a cut by 15 minutes; all 60-minute and 2/6/10/12-hour cases are potentially truncated. V3 permissions make the San Ysidro cut earlier than wide v2's 22m25s by allowing additional paths; that does not represent a loss of imported geography. The default still hits the west edge at West Point Loma Boulevard. Snaps remain approximately 0.514/13.586/4.562/17.874 m for the four city origins, within the 100 m cutoff. Cut witnesses, original node/way tags and route geometry are retained in [evidence](../evidence/wide-v3-2026-10-16/README.md).

| Observation | Build/qualification | Independent rebuild |
| --- | ---: | ---: |
| Import/preparation | 71.49 s | 72.24 s |
| Worker wall time | 556.43 s, including expensive oracles/routes | 91.26 s, no oracle recomputation |
| Worker maximum RSS | 2,361,520 KiB (2.25 GiB) | 2,362,760 KiB (2.25 GiB) |
| Observed cgroup memory peak | 3,072,937,984 bytes (2.86 GiB) | 3,572,604,928 bytes (3.33 GiB) |

Fresh containers enforce 4,294,967,296 bytes. Both runs have zero OOM/kill/limit-hit counters. Worker RSS and cgroup accounting have different scopes; preflight/artifact reads and temporary-output cache can affect the latter. Observations end before writing the small report/snapshot files. These are single capped-container observations on Apple M4/16 GiB with the approximately 7.65 GiB Docker VM, not a national memory forecast. Import still stores decoded inputs/graphs and scales with region size.

## Verification and remaining work

Five complete fields agree between Python Dijkstra and independent flat-edge Bellman–Ford: **4,634,500 full costs**, plus **37,076,000 bounded costs** at 5/15/30/60/120/360/600/720 minutes. Two partial destinations are checked with independent terminal sinks. Native verification matches **41,710,500 costs and 37,076,000 memberships**, matched traversal counts and both partial destinations. These are state/budget comparisons on five sources, not millions of independent real journeys. The rebuild reproduces graph JSON, audit, CSR/gzip, prepared XML, original barrier examples and uncertain-source excerpt exactly; previous oracle vectors are checked rather than recomputed.

Native verification uses the unchanged kernel and records source setup, search-loop wall time, encoding and local pipe round trips separately. Five sequential samples per case/mode are retained; p95 is the case maximum, not a robust tail estimate. **There is no HTTP measurement, CPU-only, contour, browser, WASM or Vercel performance claim.** The reference runs in Docker and native search on macOS; cross-environment ratios are not attributed solely to implementation.

The median of five per-origin bitmap search-loop p50s is **69.04 ms at 60 minutes** (local pipe 69.57 ms) and **69.33 ms at 720 minutes** (pipe 69.85 ms). The long-budget plateau reflects this finite clipped graph, not complete 12-hour coverage. Native process maximum RSS is 54,512 KiB (53.2 MiB); Python verification peaked at 2,528,624 KiB (2.41 GiB) while reading/validating JSON, packed graph and oracles. Initial launch through hello took 295.1 ms, including 24.90 ms internal graph load/validation; these local observations do not reproduce a Vercel cold start.

`npm run test:routing`: 79 Python cases, 77 pass and two host Osmium skips; all seven regional-helper cases, including those integrations, pass in the cached network-disabled Docker image. Fourteen adapter tests, `npm run check`, `npm run typecheck` and `npm run build` pass. Existing database assertion and MapLibre/TanStack warnings remain. No dependencies, environment values, old graphs, failed attempts or generated route-tree source were manually changed.

The model still lacks border queues/delays, live traffic, document/citizenship eligibility, authoritative per-edge access and independently surveyed speeds. Border lanes without numeric speed tags retain unrealistic motorway defaults. Tagged barriers and source hints are incomplete, and unsupported road/restriction/conditional cases still exclude valid paths. Fast, consistent searches of this graph do not meet the 10–12-hour requirement.

**Next: preflight a broader buffer from the cached parent California/Baja PBF**, using the recorded cut witnesses to expand all affected directions. Measure filtered road/state counts and import/geometry memory under the existing cap before a full build. If that increment exceeds capacity, compact or stream graph storage further instead of silently raising the cap. Keep source uncertainty attached to diagnostics; changing eligibility semantics needs a new model identity. No Western-US download, national 10k-anchor batch, browser range increase or Vercel rollout is justified by the current coverage.
