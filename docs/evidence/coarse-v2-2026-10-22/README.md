# Coarse v2 correction — October 22, 2026

The local app now serves v2 geometry-based road times, consistent per-cell road positions with charged transfers, revised explicit class speeds and road-supported border/coastal shading. It remains a small bundled TypeScript estimator in the existing Vercel app. No new environment variable, database migration, graph rebuild or hosted routing call is needed. This session did not commit or deploy it. [Model and interpretation](../../coarse-estimator.md#v2-cost-correction-and-border-shading).

## Comparison and rejected attempt

All comparisons use the same eleven preserved Southern California static reference routes from San Diego. No fresh service requests were made for v2. This sample informed the speed assumptions and is not held-out, live-traffic or national accuracy validation.

| Model/attempt | Mean absolute cell-arrival difference | Assessment |
| --- | ---: | --- |
| Preserved v1 | 42.4m | Original baseline |
| Naive road-midpoint costs | 7.7m | Rejected: free within-cell transfers skip distance |
| Corrected geometry/positions, original speeds | 41.4m | Four improve, seven regress; insufficient alone |
| Final v2, corrected geometry/positions and revised class speeds | 20.3m | All eleven improve; Calexico cell shaded |

- [Final comparison](comparison.json) records artifact identity, individual differences, node positions and destination-access sensitivity. Representative positions differ across models. Adding straight destination access at 25 km/h to both changes mean difference from **51.5m to 31.4m**, also improving all eleven. Both comparisons remain approximate; whole-cell shading does not promise access to every point by the deadline.
- [Original-speed isolation](original-speeds-repeat.json) reproduces the geometry-only result through the final builder's `--speed-profile original` option. Most aggregate gain comes from changed class-speed assumptions, not geometry alone. The [initial original-speed result](original-speeds-comparison.json) and [builder snapshot](original-speeds-builder.py) retain the earlier attempt before encoding chosen-link speeds explicitly. Their arrival costs agree; artifact bytes differ.
- [Rejected naive result](rejected-naive-comparison.json) and [builder snapshot](rejected-naive-builder.py) preserve the failed formula. [Provenance](provenance.json) records its local-only artifact and a concrete impossibility: LA's apparent 111.9m is below the 127.5m physical lower bound implied by that attempt's cell positions, source attachment and maximum 90 km/h speed. Do not ship or cite it as an accuracy improvement. Snapshots are review records; their relative root calculation assumes execution from the project's `scripts/` directory.
- [Original reference bundle](../coarse-quality-2026-10-22/README.md) is unchanged. V1 and its original builder remain intact. Rejected intermediate artifacts stay in ignored `data/coarse-quality/`, with hashes recorded; they are not bundled in a fresh clone.

## Verification

- [33 passing server tests](server-tests.log): geometry weights, origin/transfer costs, every one of 33,398 physical link lower bounds at its encoded speed, Calexico shading, water/bridge behavior, island isolation, API validation and unchanged history/provider behavior.
- [Three passing Python geometry tests](geometry-tests.log): bent-road length, bidirectional connector charges and polygon holes.
- [42 national smoke cases](national-smoke.json): fourteen origins at 6/10/12h, monotone reached counts, all responses below 1 MB. This tests availability and model behavior, not driving accuracy.
- [Biome](check.log), [typecheck](typecheck.log), [ordinary build](build.log) and [Vercel build](vercel-build.log) pass. Two artifact builds reproduce SHA-256 `76d3216310c8c776eab3385b077a1ff6ab85c1f72f542e9a3ff4c7fee852c063` at 4,460,777 bytes.
- [Generated Vercel handler](vercel-handler.json): 8,242,734-byte server function; San Diego 6h, Denver 10h and New York 12h contours; zero outbound fetches; detailed experiment disabled; data absent from public JS; no embedded configured secrets; database-free history fallback. This is local invocation, not a deployment or cloud resource measurement.
- [Browser observation](browser.json), [screenshot](browser-san-diego-6h.png): visible San Diego 6h contour, v2 graph/engine provenance and current warnings. One pre-existing wallet-extension error is unrelated to the app. The default public San Diego test run uses the ordinary automatic saved-history flow; no bulk browser-history backup was triggered. Database implementation is unchanged and the earlier live write integration suite was not repeated.

## Reproduce safe checks

```sh
npm run routing:compare:coarse:v2
npm run test:coarse-data
node --import tsx --test src/server/*.test.ts
npm run routing:verify:coarse
npm run check
npm run typecheck
npm run build
npm run build:vercel
npm run check:coarse:vercel
```

The offline comparison consumes saved responses. Artifact regeneration additionally needs ignored pinned Natural Earth sources; [exact setup](../../local-development.md#regenerate-the-coarse-grid). No detailed producer, database write check or provider call is required. `sha256.json` binds evidence records; provenance source hashes identify the observation and do not freeze normal product code. Next broaden independent origins/destinations and verify hosted v2 when its URL/revision is available.
