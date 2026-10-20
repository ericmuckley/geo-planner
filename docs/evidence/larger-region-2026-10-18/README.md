# Expanded regional routing evidence

Completed October 18, 2026. Read [the report and exact commands](../../larger-region-experiment.md).

- `build-report.json`, `rebuild-report.json`, `calibration-report.json`, `qualification-report.json`, `native-verification.json`, `cuts-report.json` and `release.json` bind the new graph, unchanged model, pinned inputs/tools/recipes, comparisons and measured resource limits.
- `coverage-summary.json` records 60/90/120-minute edge counts for all five formal origins. `summary.json` contains the twelve city witnesses and both partial destinations.
- `source-provenance.json`, `control-point-comparison.json` and `expanded-snaps.json` preserve data dates/checksums, the expected newly included gate and three independent new-area snaps.
- `app-query-samples.json` and `new-area-query-samples.json` record 20 real app samples with separate timings. Large raw JSON/graph/field files remain ignored under `data/`; their hashes are in `validation.json`.
- `browser-90.png`, `browser-120.png`, `browser-palm-springs.png`, `browser-ensenada.png`, `browser-final.png` and DOM snapshots show actual Chrome results. `browser-checks.json` records budget/input behavior. `browser-console.json` retains unrelated wallet-extension errors; no app/MapLibre errors were observed.
- Test/check/build logs and `vercel-disabled-final.json` record 20 adapter tests, 189 routing tests (9 existing skips), typecheck, Biome, both build targets and compiled-handler isolation. The only Biome warning is the existing database non-null assertion.
- The superseded first calibration is intentionally preserved, with its reason and incomplete-proof status. `preserved-sha256.json`, `recipe-sha256.json` and `validation.json` record existing-file preservation and final identities.

The current scope is a qualified regional static model and sampled road display. Two-hour/US-wide completeness, real border eligibility, filled contours and long-range cloud execution remain unfinished. No provider quota, credentials or environment-file contents are used by this experiment.
