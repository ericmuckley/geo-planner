# Regional capacity evidence — October 16, 2026

Read [findings, commands and limitations](../../regional-routing-capacity.md).

- `build-summary.json`, `build-manifest.json`, `build-preparation.json`: completed corridor qualification, identities, source/artifact hashes, source snaps, budget/cut cases, partial targets and sampled route state paths.
- `build-car-filter.json`, `build-extract-resources.txt`, `build-car-filter-resources.txt`: exact source-filter commands, checksums and child resource measurements.
- `build-source-samples.osm`: unchanged source-backed maneuver fixtures; © OpenStreetMap contributors, ODbL.
- `rebuild-verification.json`: independent re-import/repack reproduces graph JSON, audit, CSR and gzip; expensive oracles were verified, not recomputed.
- `native-verification.json`: all native timing samples, comparison counts, launch/load observations, compiler/binary identity and actual network-denial probe.
- `failed-*`: larger profile, failed worker identity, preparation/filter, exit 137 and matching Docker OOM event. No completed larger graph exists.
- `comparison.json`: local preservation checks, reconstructed legal route costs, exact first-cut witness, native aggregates and San Ysidro source barrier tags/model closures.

From the repository root, with original ignored data present:

```bash
python3 docs/evidence/regional-capacity-2026-10-16/analyze.py
python3 docs/evidence/maneuver-model-2026-10-16/analyze.py
python3 docs/evidence/native-routing-2026-10-16/analyze.py
```

The first checks completed/rebuilt artifacts, source fingerprints, prior graph/field preservation, native binary identity and route witnesses. It regenerates the table from eight per-origin p50s with five samples each. The other commands check the preserved downtown experiments. These analysis scripts perform no new routing/provider calls. Large graphs, source XML and full oracle vectors remain in ignored `data/`; retained manifests record their hashes.

No HTTP, Vercel cold start, live traffic, border-queue or complete long-range result is measured. Build commands deny networking; native verification separately proves its inherited network denial. The hosted provider and app limit remain unchanged.
