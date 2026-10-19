# Wider v3 evidence — October 16, 2026

See [model, exact commands, measurements and limitations](../../wide-v3-routing.md). These are experimental static-model results; no provider credentials are included.

- `build-manifest.json`, `build-summary.json`: source/recipe/image identities, artifacts, independent costs, snaps, budgets and complete route witnesses with access diagnostics.
- `rebuild-verification.json`: seven materialized artifacts reproduced exactly under the same cap; prior oracles checked, not recomputed.
- `native-verification.json`: unchanged C++ kernel, full/bounded costs and memberships, partial destinations and separately timed setup/search/encoding/pipe observations.
- `barrier-source-samples.osm`, `uncertain-crossings-source.osm`: original complete incident/source ways and referenced nodes.
- `official-source-audit.json`: CHP facility context, retrieval date and explicit limits on car-eligibility inference; no live queues or operational state.
- `comparison.json`: preserved wide v2 graph/binary, graph differences, recomputed route/cut witnesses, original crossing tags and native aggregates.
- `retained-otay-route.json`: the previous full v2 Otay journey replayed and cost-checked in v3 with explicit uncertainty, without claiming it is a shortest-v3 route.
- `city-crossings-source.osm`: original node/way excerpt for border controls used by the selected city routes.
- `route-and-cut-evidence.geojson`: road-line witnesses with partial endpoints and cut markers for GIS review. **This is not a filled isochrone or independently verified car-access map.** OSM geometry: © OpenStreetMap contributors; see the source/license provenance in the regional documentation.
- `analyze.py`: reproduces the derived checks/excerpts/GeoJSON from the saved local artifacts.

```bash
python3 -B docs/evidence/wide-v3-2026-10-16/analyze.py
```

Large files/oracles remain in ignored `data/barrier-pilot/san-diego-tijuana-wide-v3/`; all frozen v2/v3 inputs/failure evidence remain unchanged. Analysis also reads the saved wide v2 artifacts and its previously derived Otay witness. Source hints are incomplete, so absence of a hint is never reported as verified eligibility. Graph/route consistency does not establish actual border permission, real driving time, complete long-range coverage or cloud feasibility.
