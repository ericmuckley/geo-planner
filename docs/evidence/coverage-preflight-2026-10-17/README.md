# Broader-buffer preflight evidence — October 17, 2026

See [findings and interpretation](../../archive/coverage-buffer-preflight.md). This phase prepares data and measures capacity; it does not build/qualify a larger routing graph.

Recorded commands from the repository root:

```bash
npm run routing:coverage
npm run routing:coverage -- --run-name san-diego-tijuana-buffer-preflight-r2
python3 -B docs/evidence/coverage-preflight-2026-10-17/analyze.py
npm run test:routing
npm test
npm run check
npm run typecheck
npm run build
```

The first run precedes explicit SQLite connection cleanup. Its recipe snapshots remain unchanged. The repeat uses the corrected cleanup and adds the derived preparation-limit-pressure flag. Both complete successfully under the same 4 GiB/two-CPU/network-disabled container settings, reproduce source products/counts exactly and record zero OOM/kill counters. Both encounter the memory cap during extraction (`memory.events.max` 405/398), so preparation has no demonstrated headroom. No environment values, old graph files or provider quotas change.

- [First identity](first-identity.json) and [report](first-report.json): run `dc197ca5c35f6506d622c752543bf1df87e0ea7c0eccfa6cad867331eb8692ad`.
- [Repeat identity](repeat-identity.json) and [report](repeat-report.json): run `f9fa7952e9a65f6cf638a2a31a93abc62856428fb984146b4a2de924571fbbc4`.
- `first/repeat-extract-resources.txt` and `first/repeat-filter-resources.txt`: original GNU-time child resource output; their commands use container mount paths.
- [Comparison](comparison.json): byte-identical PBF/XML/SQLite products, identical census counts, unchanged parent/wider artifacts, memory cap/pressure and held-build decision.
- [Validator](analyze.py): verifies saved reports/identities, all retained product and recipe hashes, prior wide artifacts, count containment and resource assertions. It streams checksums and does not load graph JSON into memory. Requires the ignored local data and current frozen recipes.
- [Validation results](validation.json): Python/adapter tests, lint, typecheck/build, existing warnings and local Docker capacity. Two unchanged host Osmium integrations are skipped; this phase's actual extract/filter runs succeed in the cached container.

Full products and recipe snapshots are retained under ignored `data/coverage-pilot/san-diego-tijuana-buffer-preflight-v1/` and `.../san-diego-tijuana-buffer-preflight-r2/`, approximately 0.88 GiB each before small reports/snapshots. Existing identities refuse overwrite; reproduction uses a fresh name. Counts bound 2,071,923–2,144,619 road states, with a 2,147,832 history-state ceiling. These are not exact built-state counts. The calibrated full-import forecast fails the unchanged 4 GiB admission gate; no OOM was deliberately induced and no cap was raised.

There are no graph-search/HTTP timings, routes, new contours or coverage/access correctness claims here. California/Mexico parent cuts and absent AZ/NV roads remain; Mexico control-point uncertainty and queues/eligibility limitations are unchanged. Next compact the importer/geometry/export storage and prove frozen parity before attempting the same broader graph.
