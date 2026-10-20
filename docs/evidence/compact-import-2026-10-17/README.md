# Compact importer evidence — October 17, 2026

See [implementation, measurements and limits](../../archive/compact-routing-import.md). Everything uses cached OSM and zero public routing requests. The original model/graphs/recipes remain preserved.

Recorded commands, in order:

```bash
npm run routing:compact -- --case downtown-v2
npm run routing:compact -- --case corridor-v2
npm run routing:compact -- --case corridor-v3
npm run routing:compact -- --case wide-v3
npm run routing:compact -- --case buffer-v3
npm run routing:compact:reload
npm run routing:compact:verify
python3 -B docs/evidence/compact-import-2026-10-17/analyze.py
npm run test:routing
npm test
npm run check
npm run typecheck
npm run build
```

The first four compare immutable artifacts, not just selected queries: graph identities, canonical graph JSON, import audits and CSR; gzip, prepared XML, barrier samples and uncertainty XML also match where present. Their original oracle vectors are checksum-verified without recomputation. The larger buffer reuses its prepared supported XML, checks the same source-backed fixtures, and runs independent full/bounded/partial-destination qualification. Each Docker case uses a fresh **4 GiB/two-CPU** container with networking denied and inputs/recipe read-only. Cgroup counters/worker high-water RSS are recorded separately.

The [separate reload report](reload-report.json) binds the exported JSON/CSR checksums and reproduces the CSR under a **1 GiB** container cap. Worker peak 357,580 KiB, cgroup peak 1,051,291,648 bytes, with zero OOM/kill/limit-hit events. This runs while the reference qualification is active; it is a memory/identity check, not an isolated performance benchmark.

Live swap observations ([early](swap-observation-early.json), [after the port sink](swap-observation-port.json), [during the final Otay sink](swap-observation-late.json)) record cumulative swap peak/current zero through the last sample. The cgroup allowed 4 GiB of swap; it was not disabled. The late observation records 628 RAM-limit events and zero OOM/kill counters, with worker `VmHWM` 2,478,776 KiB. These are explicit observation times, not a claim about unobserved final report writes.

`<case>-manifest.json` and `<case>-report.json` are exact copies of the corresponding local artifacts under ignored `data/compact-pilot/compact-v1-<case>/`. `buffer-v3-summary.json` contains the new graph's five sources, eight budgets, twelve city-direction witnesses, partial sinks and uncertainty diagnostics. `native-verification.json` checks the reloaded graph with the unchanged C++ kernel, including full/bounded labels, bitmaps, traversal counts and partial targets. Loader/worker/kernel hashes are bound in the reports and recipe snapshots.

[analyze.py](analyze.py) streams artifact checksums, checks immutable recipes and prior graphs, verifies CSR headers/size, validates count bounds and comparison totals, and derives [comparison.json](comparison.json) and [cut-witnesses.geojson](cut-witnesses.geojson). The GeoJSON contains reachable inside endpoints on cut ways; it is not a filled contour or proof that an outside continuation is legal. The validator requires retained ignored local data and the frozen code. It does not load full graph JSON into memory.

[Validation results](validation.json) record 88 Python cases (86 pass, two unchanged host Osmium skips), fourteen adapter passes, lint/typecheck/build and the existing warnings. The completed buffer records 633 RAM-limit events and zero OOM/kill events; all four parity cases and the separate reload have zero limit-hit events. Native verification passes 96,260,895 cost and 85,565,240 membership comparisons plus two partials. The twelve sampled city costs and native binary bytes remain unchanged from wider v3. The larger graph expands coverage but still reaches cuts before an hour.

Resource observations are local sequential runs with reused file caches. Peaks are cumulative through recorded checkpoints and stop before final small report/manifest writes. Native loop wall time, source setup, encoding, startup and local pipe time remain distinct; there is no HTTP, CPU-only, browser, WASM or Vercel measurement. These are exact checks on a clipped static model, not millions of independent real journeys. Source crossing uncertainties, queue/eligibility omissions and California/Mexico parent cuts remain explicit. Complete 60-minute/12-hour coverage and national capacity are unproven.
