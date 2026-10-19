# Static turn-aware routing reference

October 16, 2026. **Implemented and checked on a small real downtown San Diego road extract.** This is an independent search/reference model for the long-range experiments. The browser still uses the hosted 60-minute baseline; complete 10–12-hour coverage remains unimplemented.

## Run and reproduce

Use the completed regional PBF and cached tools image from the [regional recipe](regional-routing.md). No new road downloads, public API calls, app service or key are required.

```bash
npm run routing:reference
npm run test:routing
npm test
npm run check
npm run typecheck
npm run build
```

The command runs with Docker networking disabled, `--pull never`, a read-only root/graph/recipe, a writable output directory, two CPUs and a 4 GiB memory limit. `routing/offline.mjs` now shares that setup with the anchor runner; a regression run reused all 32 existing anchor rows and performed zero native routing calls. `.env.local` is never loaded or modified by either command.

Output: `data/reference-pilot/downtown-static-v1/`. Repeating the command verifies/reuses the extracted OSM, then recomputes the small index and qualification checks. A changed source, model or worker requires a fresh `--run-name`; existing results are preserved. The worker uses a single-writer lock. This is a deterministic qualification job, separate from the anchor runner's row-by-row resume behavior.

`routing/profiles/reference-downtown-v1.json` pins bbox `[-117.18,32.70,-117.13,32.74]`, the default San Diego origin, eight landmarks, eight held-out origin states and **30/60/120/300-second** budgets. These short budgets suit the small extract. They are not 30/60/120-minute or 12-hour coverage tests.

The source is checksum-verified `data/valhalla-v2/region.osm.pbf`, SHA-256 `7f3cdfc99196d51e732fff06dabb004c0d2f1a4d557442daec9789a19b633dbe`, derived from the pinned October 14 Southern California/Mexico snapshot. Provenance is retained from its build manifest. Extraction uses cached Osmium 1.16.0, `smart` strategy and completion of ordinary/car-specific restriction relation types, then filters highway ways and restriction relations. [Osmium's extraction manual](https://docs.osmcode.org/osmium/latest/osmium-extract.html) explains why ordinary complete-way extraction alone does not guarantee complete relations. Completion can retain objects outside the requested box; our importer explicitly cuts road segments to the box.

Files: `extract.json` and `extract-resources.txt` record input identity/checksums/resources; `roads.osm` retains the source-backed subset; `graph.json` contains ordered directed roads and weighted state transitions; `import-audit.json` lists every exclusion/unsupported restriction; `manifest.json` records profile, code/image/source hashes, graph identity and artifact checksums; `recipe/` retains Python source snapshots. Large inputs/outputs remain ignored under `data/`. [Retained evidence](evidence/state-reference-2026-10-16/) contains reports/audits rather than the full road dataset.

## Exactness contract

An algorithm can be exact for a simplified model while that model remains incomplete for real driving. This reference minimizes a single **static integer-millisecond cost** on its imported directed state graph. It does not use Valhalla route durations, preferences or its generalized contours as truth.

Each state represents arrival at the head of a particular directed OSM segment, preserving the incoming road. A transition pays the next segment's cost plus the model's fixed signal/U-turn delays and exists only when the modeled turn is allowed. A forbidden turn cannot become allowed by resetting direction at a coordinate. This initial representation supports via-node restrictions; longer maneuver histories require additional states.

`state_graph.py` contains bounded heap Dijkstra. A separate Bellman–Ford implementation uses flat-edge relaxation with no heap/Dijkstra calls. They share the imported graph/weights, so agreement checks search correctness rather than independently proving the OSM import or real-world travel times. Tests separately exercise import and turn semantics, including `no_*`, `only_*` alternatives, same-way U-turns, directed asymmetry, zero-cost/disconnected cases, partial sources and source-state unions.

Driving model `exploratory-static-car-v1`:

- Segment length is spherical endpoint distance. Cost is `ceil(lengthMeters * 3600 / speedKph)` milliseconds, minimum 1 ms. Numeric km/h or mph speed tags and directional speeds are supported; missing speeds use explicit class defaults in `import_roads.py`. Those defaults are assumptions, not measured traffic.
- Fixed delays: 5 seconds when departing a node tagged as a traffic signal, plus 20 seconds for an immediate segment reversal. There are no preference penalties, live traffic, calendars, border queues or country-specific legal rules.
- Supported highway classes are motorway/trunk/primary/secondary/tertiary and their links, unclassified, residential, living street and service. Explicit motorcar → motor_vehicle → vehicle → access precedence and directional access apply. The model allows `yes`, `permissive` and `designated`; private/destination/customer/unknown access values, driveways, parking aisles, road areas, fords, conditional/lane-access tags and unsupported oneway/speed values are excluded conservatively. Roundabouts/circular junctions and motorways default to forward-only when no explicit oneway is present.
- Car-applicable, unconditional, single-from/single-to/via-node restriction relations are modeled. Other restrictions exclude all member ways. Malformed node-only restrictions close their member nodes to through transitions. All such cases are audited. Barriers and restricted/conditional nodes also block through transitions. These closures create missing legal routes; the imported graph is not a complete driving network.

For sources, the pilot projects onto the nearest retained segment within 100 m and seeds its permitted directions. Partial traversal cost is rounded upward to milliseconds; the incoming road state survives at the next junction. Several permitted starts form a union/minimum. Tests also use explicit fractions and state IDs to avoid depending on snapping. The nearest-segment tie policy and access realism are not independently qualified; interior destination offsets and geographic polygons are not implemented.

## Stored landmark data and certificates

Eight directed landmarks are selected by deterministic geographic spread among distinct road endpoints. Eight separate held-out endpoint states exclude those landmark nodes; their source positions use one-third segment offsets. Placement is a pilot heuristic, not a coverage guarantee or a tuned national landmark selection.

Each landmark has full forward and reverse Dijkstra cost fields. They are saved, read back, checked against gzip output and decoded before classification queries run. `landmarks.u32le` stores all forward rows followed by all reverse rows, in landmark/state order, using little-endian unsigned 32-bit milliseconds. `4294967295` means unreachable **in this complete imported graph**. It does not mean unreachable in the real road network. The manifest records complete-search status and graph identity; truncated fields, mismatched graphs and malformed packed sizes are rejected. No cost quantization beyond the stated model is added by storage.

For exact directed distances, the per-landmark bounds are:

```text
lower = max(0, d(a,v) - d(a,s), d(s,a) - d(v,a))
upper = d(s,a) + d(a,v)
```

Combine valid lower bounds with maximum and valid upper bounds with minimum. Skip infinity-minus-infinity. Complete fields can sometimes prove disconnection when one operand is finite and the other infinite. For several starting states with attachment costs, compute a bound per start, add that attachment and take the minimum across starts. For budget T: upper ≤ T certifies reachable; lower > T certifies unreachable; otherwise leave unresolved. This follows established [directed landmark/triangle-inequality research](https://www.microsoft.com/en-us/research/wp-content/uploads/2005/01/soda05.pdf); there is no novelty claim.

The [Valhalla coordinate tables](offline-anchor-pilot.md) remain operational baselines. Their elapsed-time triangle disagreements make them unsuitable for these exact lower-bound formulas.

## Measured qualification

Apple M4, 16 GiB host RAM, Docker Desktop approximately 7.65 GiB VM RAM. Extraction at 2 GiB was killed; final extraction took **24.16 seconds** and peaked at **3,649,212 KiB (3.48 GiB)** child RSS. The Python reference worker later peaked at **176,456 KiB (172 MiB)**; this excludes the extraction child's memory. Cached-input qualification took **3.26 seconds**. No page-cache flush was performed.

The final graph has **19,815 states and 37,891 transitions**. It applies 233 source-backed restriction relations, blocking 247 candidate turns. Another 93 relations are unsupported: 87 close member roads and six malformed node-only relations close nodes. Exclusions include 206 otherwise eligible restriction-member ways, 291 access-limited ways, 737 area/ford/driveway/parking ways and two lane-access ways. Fifty-nine supported relations have no remaining candidate turn after clipping/exclusions; their IDs are retained. These counts explain important coverage gaps.

OSM way 5987900 (`4th Avenue`, `oneway=yes`) imports 11 forward segments and zero reverse segments. The default input snaps approximately **0.51 m** to segment `436291033:1`, retaining both permitted directions and their distinct remaining costs. The report includes source-backed blocked-turn samples and the Fourth Avenue tags/segment IDs.

For nine origins, Dijkstra and Bellman–Ford agreed on **178,335 state costs**. Across four budgets per origin, bounded membership and every lower/upper interval were checked against the independent results: **713,340 state/budget checks, zero unsafe reachable/unreachable certificates or bounded-search mismatches**. Unresolved states remain unresolved; they are not counted as correct predictions. Tests include seeded random small directed graphs as additional adversarial checks, not real-road coverage evidence.

| Budget | Mean states certified across nine origins | Median bounded Dijkstra | Median full-state classification | Origins reaching a cut exit |
| --- | ---: | ---: | ---: | ---: |
| 30 seconds | 93.05% | 0.093 ms | 31.67 ms | 4/9 |
| 60 seconds | 91.18% | 0.071 ms | 31.39 ms | 4/9 |
| 120 seconds | 83.36% | 0.187 ms | 31.31 ms | 6/9 |
| 300 seconds | 67.16% | 2.575 ms | 31.37 ms | 9/9 |

Many certificates identify unreachable states, including disconnected parts of this restricted model. For the default source at 300 seconds, 1,093 states are certified reachable, 4,974 unreachable and 13,748 unresolved; the reference finds 12,533 reachable states. The first modeled cut-exit arrival is 215,966 ms (3m35.966s). The five-minute query therefore explicitly flags boundary uncertainty. A missing boundary flag does not independently prove source completeness or real-world coverage.

The fields occupy **1,268,160 bytes**, or **550,298 bytes gzip**, excluding graph/geometry/metadata. Building the 16 directional fields took 69.12 ms of graph work. Packing/compressing/writing took 58.29 ms, and reading/decompressing/checking/decoding took 16.09 ms. These are single warm local observations. Dijkstra timings surround the in-memory graph routine; classification timings surround the full-state bounds pass. They exclude acquisition, import, snapping, serialization and browser display. They are not HTTP measurements or national performance predictions.

**Current result: the certificates are safe on the specified model, but full-state landmark classification is slower than bounded Dijkstra here.** It scans all states and loads all fields; it does not yet save query work. A high certified percentage alone is not a speedup.

A repeat cached-input run reproduced the graph, import audit and raw/gzip landmark fields byte-for-byte; source snapshot hashes were also verified. The repeat took 3.49 seconds of worker time. `npm run test:routing` passes 23 Python tests; `npm test` passes 14 adapter tests. Biome, typecheck and production build pass with the existing database assertion and bundler warnings. No app route/UI changes were needed, and the route tree was generated only by the normal build.

## Next task

The [cell-summary comparison](cell-routing-experiment.md) is complete. It checks grouped certificates, selective binary range reads and exact refinement against this frozen reference. It saves detail reads but exact queries remain slower than direct search. The [compact native baseline](native-routing-baseline.md) packs this unchanged graph and matches its selected costs/memberships with faster direct search. Keep performance experiments separate from import quality and broader coverage.

A separate [v2 model](maneuver-routing-model.md) now handles 40 unambiguous prohibited via-way sequences and legal interior destinations, preserving this v1 reference. Conditional/ambiguous exclusions remain explicit; complete real-driving correctness remains unproven. The [regional capacity probe](regional-routing-capacity.md) now measures a larger corridor and preserves these fixtures; it finds a wider-import OOM and concrete border-access exclusions. Next qualify barriers and reduce importer memory before the [US West bulk-source option](offline-anchor-pilot.md#broader-data-assessment). Canada/Mexico crossings remain unqualified; this downtown instance has no international crossing. Keep the hosted baseline and original 12-hour requirement active. No national 10k batch, Vercel query kernel or expanded browser contour was implemented in this step.
