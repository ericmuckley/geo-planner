# V4 charged road attachment — October 22, 2026

The local app now serves `coarse-road-grid-v4`. Generic input access can follow the source-road visit owning its existing cell anchor, charging checked local travel at 25 km/h plus the retained polyline distance at the unchanged road-class speed. No selected city, coordinate, route or region is special-cased. The v3 graph, land/display masks, shore connections, road weights, anchors and speeds are byte-for-byte unchanged. No source download, reference request, hosted routing quota, new environment variable or database migration was used. V4 is uncommitted and has not been deployed; the user's visual deployment acceptance concerns the earlier baseline at repository commit `887ab50`.

## Implementation and limits

The [builder](../../../scripts/build-coarse-grid-v4.py) adds **26,946** canonical-owner road visits with **142,029** points. Coordinates are stored as integer offsets at 0.00001° resolution. Every source bend is retained before quantization; consecutive duplicate points are removed, and the unchanged canonical anchor is inserted at the source visit's midpoint. Source and v2/v3 artifact hashes are checked. The [initial owner-selection failure](builder-development-note.txt) stopped before artifact creation; it did not weaken the ownership assertion.

The [runtime](../../../src/server/coarse-grid.ts) considers segment projections and endpoints within the input's own cell visit. Local connectors require continuous generalized land, with the existing input-only 1 km shore tolerance. Only explicit retained source-road geometry can cross water on the road leg. It keeps v3 direct access and fallback/bridge ports, takes the minimum charged time for each anchor, and seeds all supported anchors. Costs round upward to 0.1 second for the new road paths. Proxy point comparisons use the same attachments for arrival and departure. `attachmentKm` now describes the physical distance of the lowest-time retained initial attachment; another seed may supply a reached path.

This remains one selected road visit per cell, not a full road topology or legal access model. A nearby different road does not acquire a free transfer to the selected anchor. Missing roads, merged grade-separated crossings, approximate overland travel and whole-cell shading remain. **Palm Springs' nearby road is not its cell's canonical-owner visit**: its origin cost stays 19.0m, so this scoped change does not resolve that access limitation. More general road transfers or a more complete compact source are separate work; no speed fitting was used to hide it.

## Saved comparisons

The [comparison](comparison.json) checks every v3 baseline point cost against the preserved v3 report, then evaluates both saved sets offline. The [path diagnostic](path-diagnostics.json) reconstructs all 35 v4 point costs and endpoint/road/local sums.

| Set | Common-finite cases | Mean absolute reference difference, v3 → v4 | Changes |
| --- | ---: | ---: | --- |
| Original San Diego set | 11 | 31.381m → 22.181m | 11 improve; zero regress |
| Broader regional set | 24 | 38.886m → 34.234m | 20 improve; four unchanged; zero regress |

Both models reach and shade every sample destination; no newly reached/unreached case is excluded. The broader mean now includes **all 24** cases, including the shore destination v3 restored. It must not be compared directly with the older 23-case v2/v3 means. These sets informed development; they are regression evidence, not holdouts, real-world ETA truth, national accuracy or six-/twelve-hour frontier validation.

| Case | V3 → v4 total | Origin attachment, v3 → v4 | Road steps / local steps | Destination attachment, v3 → v4 |
| --- | ---: | ---: | ---: | ---: |
| San Clemente → Temecula | 86.877m → 73.280m | 10.306m → 4.210m | 62.277m / 0m | 14.294m → 6.793m |
| Palm Springs → Idyllwild | 96.430m → 95.530m | 18.993m → 18.993m | 61.313m / 0m | 16.124m → 15.223m |
| Bakersfield → Big Bear | 271.884m → 268.185m | 13.126m → 9.427m | 177.858m / 72.230m | 8.669m → 8.669m |
| Salton City → Bombay Beach | 145.985m → 140.761m | 13.285m → 8.062m | 27.990m / 66.943m | 37.766m → 37.766m |

Road/local intercell steps stay unchanged on these reconstructed paths; improvements come from charged endpoint access. Endpoint totals include any new road leg. Earlier [source coverage observations](../coarse-access-2026-10-22/README.md) remain: roughly 30 km without a source road near Big Bear and 22.5 km near Bombay Beach. Their large residual errors are not solved.

## Validation and deployment

- [45 server tests](server-tests.log), including road bends, positive local/road charges, time-based seeds, narrow channels, explicit source bridges, unrelated islands, malformed visit data, all **142,029** source-point arc/chord bounds and unchanged v3 graph fields. The earlier [development test log](development-tests.log) retains the single expected fixture failure when attachment results gained explicit minutes; final tests pass without removing the assertion.
- [Eight Python geometry tests](geometry-tests.log) include source-bend/anchor insertion and duplicate-point quantization. [42 national smoke cases](national-smoke.json) preserve connected origins and budget monotonicity; no case loses cells against v3. New York 6h/12h has 4,107/11,249 cells, Key West 6h has 363, and ferry-only Nantucket stays at six. Larger cell counts are model consequences, not accuracy scores.
- Biome (144 files), app typecheck, [strict diagnostic typecheck](diagnostic-typecheck.log), [ordinary build](build.log), [Vercel build](vercel-build.log) pass. Artifact and [repeat build](repeat-build.json) match: **7,995,142 bytes**, SHA-256 `6905fa38d198f6c89201fb731db484a1b7ff911078648c005165b5ba7be654f3`.
- [Generated Vercel handler](vercel-handler.json): **13,449,441 bytes / 27 files**, three representative contours, zero outbound fetches, no server dataset/secrets in public JS, no raw source/Python/environment files, local experiment disabled, database-free history fallback. This is local execution, not a cloud deployment/performance/peak-memory claim.
- [Browser observations](browser.json), [San Diego 6h](browser-san-diego-6h.png) and [New York 12h](browser-new-york-12h.png) show filled v4 contours and visible warnings/metadata. Two public test inputs used the existing automatic save flow; no bulk history upload was triggered. No app console error was observed; the pre-existing wallet-extension error remains unrelated. No live DB integration rerun was needed because persistence code is unchanged.

```sh
npm run routing:compare:coarse:candidate
node --import tsx scripts/inspect-coarse-access.ts src/server/data/coarse-grid-v4.json docs/evidence/coarse-v4-2026-10-22/comparison.json
npm run test:coarse-data
node --import tsx --test src/server/*.test.ts
npm run routing:verify:coarse
npm run check
npm run typecheck
npm run build
npm run build:vercel
npm run check:coarse:vercel
```

The current builder uses only the existing pinned roads and unchanged v2/v3 artifacts; [setup/repeat commands](../../local-development.md#regenerate-the-coarse-grid). Preserve all previous artifacts and evidence. Adjacent provenance/checksums are dated observations, not freezes on product code. Next ship/verify this bounded v4 refinement, then prioritize a more complete compact road source rather than further blanket speed changes or detailed graph expansion.
