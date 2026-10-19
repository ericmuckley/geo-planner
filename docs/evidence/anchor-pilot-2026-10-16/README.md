# Offline anchor pilot evidence

October 16, 2026. See [commands, semantics and findings](../../offline-anchor-pilot.md).

- `manifest-32.json`, `anchors-32.geojson`: source/graph/model/image/worker identity and matrix ordering. No credentials.
- `partial-32.json`: first eight rows.
- `complete-32.json`: reused eight, computed 24, exported the complete 32-by-32 table.
- `reused-32.json`: reused all 32, computed zero.
- `row-checksums-before-resume.json`, `row-reuse-verification.json`: all checkpoint bytes remained unchanged during the final reuse run.
- `analysis-32.json`: packed/gzip exports match every checkpoint; directional and triangle diagnostics.
- `sample-row-19.json`: full returned row containing the largest observed triangle disagreement. Inspect anchor indices 3 and 18 using the manifest/GeoJSON; row 18 remains in ignored local data.
- `partial-256-costmatrix.json`: eight retained 256-target rows; incomplete matrix.
- `forward-256-probe.json`: one forward-search probe while the other probe was active; not a controlled timing comparison.
- `algorithm-comparison.json`: overlapping pairs from different algorithms/target counts; disagreement does not establish which result is correct.

Full checkpoints, the packed matrix, worker snapshots and local graphs remain under ignored `data/`. Public API calls: **zero**. No additional OSM downloads. Networking was disabled for computational containers; the app's hosted routing setting/key was not changed or used.

Validation: eight Python pilot/analysis tests, fourteen adapter tests, Biome, TypeScript and production build pass. The existing database non-null assertion and bundler warnings remain. No browser/product behavior changed in this experiment; the browser's hosted 60-minute limit remains.
