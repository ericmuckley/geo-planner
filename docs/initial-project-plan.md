**Isochrone Research Mapping App — Project Plan**

The goal is to determine new innovative methods for computing isochrones extremely quickly, and displaying them rapidly on a map, ideally in pseudo-real-time. For example, we should be able to compute large isochrones (up to 12 hours, or using miles instead of hours) from a particular location on the map, and see informative visualizations of the results on the map.

We'll also need geographic information about public lands, businesses, etc. One initial use-case will be something like: Show me the isochrone area 10 hours (and/or 150 miles) from location X, and highlight all gas stations inside the isochrone, highlight elevations over 5,000 ft, and highlight all public lands which fall within the isochrone.

Our app will need methods for displaying maps, getting other data, and computing geographic information. Our priority will be using free open-source tools. Postgres is our sql db of choice. Please help me put a high-level plan of action together in terms of which types of technologies, packages/libraries, and mapping data we'll need to fetch and/or compute to be able to satisfy the given use case and similar use cases.

Prepared October 15, 2026. Scope: extend an existing TanStack Start app into an open-source mapping and reachability research environment, using PostgreSQL/PostGIS for spatial data. This is a proposed architecture and experiment plan; performance targets below are hypotheses to test.

**Recommended starting point**

Use TanStack Start + MapLibre GL JS + regional PMTiles basemaps + PostgreSQL/PostGIS + a self-hosted Valhalla service. Use GDAL/OGR and osm2pgsql for data preparation. Add Martin when dynamic vector tiles become useful, and a native experimental routing service when the baseline and benchmarks exist.

Develop two workstreams: a useful reference application that can answer the example query, and interchangeable routing/rendering experiments measured inside that application. A working baseline makes algorithm improvements measurable.

Start with static driving weights and a limited Southern California dataset. Expand routing coverage to an appropriately buffered western-US/multicountry region before evaluating 10–12-hour trips. Routing coverage must include roads needed by paths, including paths that leave and re-enter the destination region. Keep geocoding, natural-language interpretation, transit, live traffic, and a global rollout for later.

**1. Define exactly what a query means**

| Query | Intended meaning | First implementation |
| --- | --- | --- |
| Within 10 hours | Minimum modeled travel time from the origin is at most 600 minutes | Time-weighted reachability |
| Within 150 road miles | Minimum permitted road-network length is at most 241.4016 km | Distance-weighted reachability |
| Within 150 straight-line miles | Geographic radius, independent of roads | PostGIS geography distance predicate |
| Time OR distance | Meets either independently defined reachability test | Union of results |
| Time AND distance, independent tests | Some route meets the time test and some potentially different route meets the distance test | Intersection, explicitly labeled |
| One route meeting BOTH limits | There exists a single permitted path under both budgets | Later constrained/multiobjective search |

The last two rows are different. For example, a fast 180-mile freeway route and a slow 120-mile local route could pass separate tests while neither satisfies both limits. A single combined numerical edge weight also does not generally enforce two independent budgets. A strict implementation may retain multiple nondominated time/distance labels at a graph state.

For each run, record direction (from or toward the origin), mode, road access policy, speed model, time dependence, metric, and thresholds. Treat engine-specific path preferences and generalized costs explicitly; verify that distance mode actually implements the chosen minimum-distance definition.

Distinguish exact reachability on the modeled road graph from the filled area drawn between roads. A raster or polygon is a geographic representation with a stated resolution and fill rule. It does not establish road-free access to every shaded point.

For public lands, offer two separate questions: which land polygons overlap the displayed region, and which known entrances/trailheads are reachable. A large forest's administrative boundary is insufficient to establish reachable entrances or recreation access. Preserve owner, manager, designation, and access fields.

**2. Technology choices and responsibilities**

| Responsibility | Recommended technology | Role |
| --- | --- | --- |
| App and API | Existing TanStack Start; TypeScript; TanStack Query where useful | Controls, query definitions, saved experiments, cancellation, result presentation |
| Browser map | maplibre-gl | GPU-backed basemap, POIs, contour fills, terrain, custom analytical layers |
| React integration | Direct MapLibre initially; an optional React wrapper later | Initialize the map in the browser, outside SSR execution |
| Basemap | Protomaps styles and a regional PMTiles archive; pmtiles browser package/CLI | Independent, cacheable cartographic context |
| Spatial database | PostgreSQL + PostGIS | POIs, public-land geometry, spatial predicates, clipping, metadata, saved runs |
| Existing ORM | Drizzle if already used | Application models; SQL migrations and spatial SQL where appropriate |
| Baseline router | Self-hosted Valhalla | A real routing graph and a usable reference isochrone implementation |
| Dynamic vector tiles | Martin, or an API using PostGIS ST_AsMVT | Deliver changing or large analytical layers by viewport |
| Data preparation | GDAL/OGR, osmium, osm2pgsql flex output | Import, filter, convert, reproject, and prepare datasets |
| Visual inspection | QGIS | Inspect geometry, coordinate systems, and import quality |
| Optional dense overlays | deck.gl | Add when MapLibre layers or custom layers need additional visualization capabilities |
| Research engine | C++ using RoutingKit as a starting point; Rust is another implementation option | Controlled native experiments behind the same query interface |

MapLibre is a renderer; PMTiles is a tiled delivery format; PostGIS is a spatial database; Valhalla is a router. A basemap archive does not replace the routable graph.

Keep expensive graph traversal in a long-running native process with its graph loaded or memory-mapped. Postgres remains the authoritative application/spatial database without becoming the per-edge query loop. SQL/pgRouting can be useful for small reference experiments, but do not make repeated SQL traversal the initial plan for cursor-driven continental reachability.

The first deployment can run locally with the web app, Postgres, and Valhalla. Add tile hosting and an optional Martin process as needed. If the web app later runs on serverless hosting, keep the large, warm routing graph in a persistent service. Defer distributed infrastructure and external cache services until measurements justify them.

**3. Geographic inputs to download**

| Data | Initial source | What to keep | Preparation |
| --- | --- | --- | --- |
| Roads and restrictions | OpenStreetMap PBF extracts from Geofabrik | Road connectivity, direction, access, turn restrictions, class, available speed tags | Build the engine's routing graph; retain source snapshot identity |
| Basemap | Protomaps regional PMTiles extraction | Vector tiles, compatible styles, fonts/glyphs, sprites, attribution | Download a regional archive; generate with Planetiler only when customization requires it |
| Gas stations and other POIs | OSM initially; Overture Places as an optional comparison/supplement | Source ID, source geometry, normalized category, name, provenance, refresh date | Filter OSM fuel amenities; normalize polygon POIs to representative points when useful |
| Public lands | USGS PAD-US; agency datasets when greater detail is needed | Owner, manager, designation, public-access classification, source ID | Select relevant ownership/management classes, validate and subdivide complex polygons |
| Elevation | USGS 3DEP for US coverage | Elevation values, units, nodata, resolution, horizontal/vertical reference | Prepare multiresolution Cloud Optimized GeoTIFFs and display tiles |
| Optional place lookup | A later local geocoder, or search over imported named features | Names and identifiers | Begin with map click and coordinates so geocoding is not a dependency |

PAD-US includes more than publicly owned land. Define public-land filters from attributes rather than treating every PAD-US feature as public. Keep source identities when polygons overlap, and deduplicate feature-level counts after subdivision.

OSM and Overture are independently maintained datasets; compare coverage before combining them. Preserve attribution, licenses, category mappings, and provenance. Do not treat a place record as evidence of current fuel prices, business hours, or real-time availability.

Use bulk dataset downloads and locally indexed data for interaction. Public Overpass queries can assist exploration, but should not be the backend for repeated cursor queries. OpenStreetMap's public tile servers have usage policies; open data does not imply unlimited free public hosting.

For elevation, 5,000 ft is 1,524 m. Start with coarser derived rasters for large views and use finer DEM data when zoom or analysis requires it. Keep nodata distinct from low elevation. Terrain hillshading and 3D terrain are context; a numerical elevation threshold requires an analytical mask.

**4. What to precompute, store, and compute per request**

| Timing | Products |
| --- | --- |
| On import/update | Routing graph; source manifests; POI category normalization; spatial indexes; public-land geometry repair/subdivision; raster overviews; basemap archives |
| During later research preprocessing | Graph partitions, hierarchy/shortcut indexes, per-metric customizations, conservative cell bounds, selected coarse cached fields |
| On origin change | Snap to permitted road state(s), compute reachability, build preview representation, identify candidate features |
| On threshold change with a reusable field | Re-threshold retained costs, update map mask/contours, update relevant memberships |
| On POI or land-filter change | Query already-computed reachability and spatial data, without rerouting |
| After the pointer settles | Refine geometry, verify selected POIs/entrances, compute complete counts or exports |

Use GiST indexes for spatial columns and ordinary indexes for categories and source identifiers. Store geographic coordinates consistently; use geography or suitable projected coordinates for physical distances and areas rather than treating longitude/latitude degrees or Web Mercator areas as physical units.

Suggested logical tables: data_sources/dataset_versions, pois, land_features, land_geometry_parts, raster_assets, saved_queries, analysis_runs, benchmark_runs. Large DEMs and graph files belong in versioned file/object storage, with their references and metadata in Postgres. Cache large transient fields in a bounded cache rather than retaining every cursor position indefinitely.

A cache key must include graph version, snapped source/offset and relevant direction state, mode, cost profile, metric, maximum computed range, and output resolution where applicable. Layer-result caches additionally need dataset versions. Coordinate bucketing introduces approximation and should be recorded.

Avoid precomputing a complete field for every possible origin. All-origin/all-destination cost storage grows quadratically. Begin with graph indexes and bounded recent-origin caches; measure serialized bytes and peak resident memory for every proposed preprocessing scheme.

**5. End-to-end handling of the example**

1. Accept a structured query: origin, driving profile, time/distance interpretation, threshold(s), POI categories, elevation threshold, land classes, viewport, and requested quality.
2. Snap the origin to valid directed road states and preserve both input and snapped locations.
3. Compute the required time and/or distance reachability. Independent metrics may require separate searches/customizations; same-path dual-budget reachability is a separate algorithm.
4. Return a lightweight result ID, version/coverage metadata, timings, and a preview contour or tiled cost field.
5. Select candidate gas stations with indexed spatial predicates. Polygon membership is suitable for an initial visual result; stronger road-access verification uses permitted road/driveway connections and partial-edge travel cost. Checking only the nearest road vertex is insufficient.
6. Draw elevation >1,524 m within the displayed reachability mask. Raster masking can happen on the GPU or through prepared/query-specific tiles; it need not polygonize the entire DEM on every request.
7. Select and draw intersecting public-land pieces. Render an overlap mask first, and compute clipped geometries/areas only when requested. Use an area test if boundary touching should not count as an overlap.
8. Fetch visible tiles and clustered POIs for display while calculating full-region counts independently when needed.
9. After interaction stops, refine the result and allow inspection/export with its resolution and data versions.

Showing three layers together is different from filtering gas stations that satisfy every layer. Make these independent layer filters initially, and add explicit combined predicates when desired.

Do not use only currently rendered map features for complete counts: rendered tiles are viewport- and zoom-dependent, may be simplified, and can omit or duplicate features. Server-side counts operate on the relevant analytical dataset.

**6. Performance work, ordered by likely value**

First measure separate stages: snapping, graph search, field construction, contouring, spatial joins, serialization, network delivery, browser decoding, and first paint. Keep raw graph results available in the experimental engine so algorithm speed can be measured independently of geometry.

Practical experiments:

- Compare the baseline's GeoJSON contours with its underlying grid output. Valhalla documents time/distance contours and a GeoTIFF grid response. Its generated default configuration caps contours at 120 minutes and 200 km; raise the relevant self-hosted limits for 720-minute and >=241.4016-km experiments, then test runtime, memory, warnings, and completeness.
- For a fixed origin and static single metric, retain the cost field up to a maximum budget. Smaller-threshold slider movements can reuse it. This is easiest in an engine that exposes labels; do not assume a returned coarse grid retains every exact graph label.
- Render travel cost as a scalar texture/tiled raster and compare a shader threshold with repeated polygon generation. Elevation and reachability masks can be combined for display without a new geometry intersection for every pixel.
- Use viewport tiles, zoom-dependent resolution, and stable source/layer objects. Keep the complete analytical extent separate from the visible payload.
- Throttle origin updates, keep one active computation plus the newest pending request, cancel work where supported, and discard stale response IDs. Browser cancellation alone may not stop server computation.
- Compare coarse preview followed by refinement against exact-result-only interaction. Label approximation and define spatial/temporal error metrics.
- Reuse selected nearby-origin fields as a preview experiment. Euclidean proximity does not guarantee similar driving reachability across rivers, divided roads, or one-way systems; interpolation is not an exact method.
- Investigate directed same-edge source reuse and local connector corrections under an explicit static turn-aware model. Validate before calling it exact.
- Test GPU/WebGPU rasterization or field operations after profiling. GPU computation does not automatically solve routing constraints or browser data-transfer costs.

Proposed user-experience targets, not measured guarantees: keep camera interaction fluid; aim for roughly 5–10 useful preview updates per second and p95 preview latency below 100–200 ms on named hardware; initially target a refined click/settled-origin response around 1–2 seconds. Assess 12-hour requests separately. Smooth rendering does not require a new server query on every animation frame.

**7. Algorithm research track**

Begin with a native bounded Dijkstra reference on a controlled graph and fixed costs. It provides understandable correctness checks and a baseline for reachability labels. Include one-way roads, turn restrictions/costs, disconnected components, partial edges, ferries/access policy, and source snapping in the chosen model.

Next compare optimized graph layouts and queues, then contraction/partition methods. RoutingKit supplies CH/CCH building blocks; it is not a turnkey isoPHAST map API. Isochrone-specific methods such as isoPHAST, isoCRP, and isoGRASP are established prior art. Published experiments report millisecond-scale network computations, with preprocessing and hardware assumptions; these do not establish end-to-end app latency.

Candidate contribution: combine conservative graph-cell classification with adaptive display resolution, refine cells near the threshold, and reuse source-local work during pointer movement. Measure exact graph membership and display error separately. A method that avoids resolving every interior road label might help boundary rendering while requiring extra work to provide exact costs for every POI.

Evaluate hypotheses independently:

| Experiment | Question |
| --- | --- |
| Native bounded search | How much does a compact in-memory implementation improve graph time? |
| CH/CCH with one-to-many/all techniques | Which query/index tradeoffs fit time and distance profiles? |
| isoPHAST-style selective scans | Can proven bounds avoid interior work at long ranges? |
| Partition-based methods | Can preprocessing and metric updates stay inexpensive enough? |
| Grid versus polygon output | How much latency comes from geographic representation? |
| Source-local reuse | How much work can successive mouse positions share, with what error? |
| Selective POI verification | Can exact POI/entrance answers be returned without fully detailed geographic output? |
| Dual-budget labels | What additional cost is required for one path satisfying both time and mileage? |

Exactness claims apply to a specified graph/metric model. Static-weight performance does not imply performance with live traffic, arbitrary road preferences, or frequent topology updates. Create separate per-metric indexes/customizations as required, and include turn-state modeling in correctness and memory comparisons.

**8. Delivery milestones**

| Phase | Deliverable | Completion evidence |
| --- | --- | --- |
| 1 — Map and benchmark scaffold | Client-only MapLibre map, regional PMTiles, origin selection, structured query controls, visible timing panel, saved runs | Same query can be replayed and browser/network timings inspected |
| 2 — Reference reachability | Self-hosted regional Valhalla, time/distance controls, multiple contours, documented query semantics | Known locations and sampled routes checked; default range limits and output quality recorded |
| 3 — Full example at small range | Imported gas stations and public lands; numerical elevation mask; basic PostGIS queries | Selected origin answers the complete example at a modest budget with inspectable sources |
| 4 — Long-range coverage | Broader road dataset, explicit coverage reporting, 2/6/10/12-hour and road-mile tests | No silent boundary truncation; peak memory, preprocessing, p50/p95 and payloads recorded |
| 5 — Responsive interaction | Reused fields, tiled/raster previews, latest-request scheduling, refinement | Cursor and slider benchmark traces meet defined targets or clearly identify remaining bottlenecks |
| 6 — Research comparisons | Native reference and one advanced candidate under a common interface | Reproducible latency/accuracy/storage comparisons on identical graphs and costs |
| 7 — Selected advanced semantics | Same-path dual budgets, reachable entrances, or additional modes, chosen from evidence | Correctness validated independently and additional runtime measured |

Build the benchmark scaffolding early and use it throughout. Do not wait until the end to measure 12-hour behavior or data-preprocessing requirements.

**9. Benchmark protocol and decision gates**

Use a fixed collection of urban, rural, coastal, mountain, border-adjacent, and disconnected origins. Include short and long budgets and a recorded cursor trace, rather than benchmarking one favorable point.

Record hardware/threads, graph size, data versions, profile, cold/warm cache state, preprocessing duration, index size, peak RAM, stage timings, p50/p95 latency, request throughput, bytes, and time to visible response.

For correctness, compare candidate methods to reference search on the same graph and weights. Different engines can disagree because of data import, snapping, or costs. Separately validate source-data realism. Test boundary crossings, restricted turns, disconnected islands, partial-edge destinations, and limit monotonicity.

For approximate display, report graph/POI membership false positives and false negatives, sampled boundary errors, raster resolution, and geometry differences against a higher-resolution reference. Polygon overlap scores alone can hide errors around individual destinations.

Advance to heavier graph research when graph traversal dominates. Advance to GPU/tile work when representation and rendering dominate. Increase geography or concurrency only after recording the resulting build, disk, and RAM requirements. A full result's output size remains a lower bound on delivery time.

**Immediate first vertical slice**

A user clicks near San Diego, selects 60 minutes of driving, sees a contour, toggles imported gas stations and public-land overlap, and enables an elevation-above-5,000-ft mask. The app shows stage timings and stores the run. Then expand the same pipeline to 10–12 hours and replace individual components based on measured bottlenecks.

**Primary references checked**

- MapLibre GL JS: https://maplibre.org/maplibre-gl-js/docs/
- MapLibre terrain sources: https://maplibre.org/maplibre-gl-js/docs/API/classes/RasterDEMTileSource/
- PMTiles concepts: https://docs.protomaps.com/pmtiles/
- Regional basemap extraction: https://docs.protomaps.com/guide/getting-started
- Protomaps basemap generation/styles: https://github.com/protomaps/basemaps
- Martin: https://maplibre.org/martin/
- PostGIS vector tiles: https://postgis.net/docs/ST_AsMVT.html
- PostGIS spatial indexes: https://postgis.net/documentation/faq/spatial-indexes/
- PostGIS geometry subdivision: https://postgis.net/docs/ST_Subdivide.html
- Valhalla isochrone/grid API: https://valhalla.github.io/valhalla/api/isochrone/
- Valhalla configuration limits: https://github.com/valhalla/valhalla/blob/master/scripts/valhalla_build_config
- Valhalla graph expansion: https://valhalla.github.io/valhalla/api/expansion/
- RoutingKit: https://github.com/RoutingKit/RoutingKit
- Baum, Buchhold, Dibbelt, Wagner, Fast Computation of Isochrones in Road Networks: https://arxiv.org/abs/1512.09090
- Geofabrik extracts: https://download.geofabrik.de/north-america.html
- osm2pgsql: https://osm2pgsql.org/doc/manual.html
- Osmium extraction: https://docs.osmcode.org/osmium/latest/osmium-extract.html
- USGS PAD-US: https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview
- USGS elevation datasets: https://www.usgs.gov/faqs/what-types-elevation-datasets-are-available-what-formats-do-they-come-and-where-can-i-download
- Overture Places: https://docs.overturemaps.org/guides/places/
- GDAL COG: https://gdal.org/en/stable/drivers/raster/cog.html
- GDAL raster tools: https://gdal.org/en/stable/programs/gdal_raster.html
- OSM public tile usage policy: https://operations.osmfoundation.org/policies/tiles/

