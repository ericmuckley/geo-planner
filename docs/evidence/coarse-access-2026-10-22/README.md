# V3 local-access diagnosis — October 22, 2026

The user reports the current Vercel deployment looks fine. Repository commit `887ab50` contains v3 and its previous evidence; the exact deployed revision and independent cloud measurements were not checked here. This follow-up changes only offline diagnostics/documentation. V3 remains the application model, with no dataset, API, environment or database changes.

[`diagnostics.json`](diagnostics.json) reconstructs one minimum-cost path for **all 35 saved point comparisons** (eleven original and 24 broader regional cases), using production v3 search labels. Every point cost matches the preserved v3 result, and every path's endpoint/road/local components sum to that cost. No new reference requests were made. The saved sets already guide refinement; they are not independent holdouts or national accuracy evidence.

## Two distinct limits

| Regional case | Static reference | V3 total | Origin access | Road steps | Local steps | Destination access |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Bakersfield → Big Bear | 186.8m | 271.9m | 13.1m | 177.9m | 72.2m | 8.7m |
| Salton City → Bombay Beach | 61.3m | 146.0m | 13.3m | 28.0m | 66.9m | 37.8m |
| Palm Springs → Idyllwild | 53.2m | 96.4m | 19.0m | 61.3m | 0m | 16.1m |

“Road steps” include the existing within-cell anchor connectors and rounding. “Local steps” and endpoint access use the assumed 25 km/h local model, including travel without roads. These components describe a model path, not measured causes of real-world travel time; the reference uses different path/cost semantics.

**Source omissions:** the nearest road in the pinned Natural Earth source is approximately **30.0 km from Big Bear**, **22.5 km from Bombay Beach**, and **13.2 km from Borrego Springs**. At these endpoints the nearest source feature is also eligible under the existing importer rules; changing its road-class/country filter would not supply nearby roads. Missing source roads force substantial modeled local travel. The data support a later richer-road-source task, not raising local speeds or adding hand-selected connections.

**Endpoint representation:** Palm Springs lies approximately **0.029 km from a retained road**, but accessing its single canonical cell representative costs **19.0m** (7.91 km at 25 km/h). Idyllwild's endpoint adds 16.1m; the two endpoints account for **35.1m** of the 96.4m model total. Changing source coverage alone does not diagnose or eliminate that detour. A source road close to an input does not by itself prove a legal or well-connected real road attachment.

Source distances inspect all source feature classes/countries within a 0.75-degree segment window at the 23 distinct saved endpoints. Projection onto each segment uses local scaled longitude/latitude, followed by haversine distance. Results are approximate source-coverage observations, not a nationwide snapping service or an assertion that the source geometry is accurate. All selected results lie within 40 km, inside that window at these regional latitudes.

## Chosen next refinement

Evaluate **generic attachment to retained road geometry** rather than forcing every supported interior origin through its one cell representative at local speed. Derive attachment geometry offline from the source road visit that owns the canonical anchor, charge local distance to that road plus actual along-road distance at its existing class speed, and preserve land checks/explicit bridge access. Apply the same rules for every supported input and proxy destination. Do not introduce city, coordinate or regional exceptions, free within-cell transfers, or a speed retuning.

This is a scoped candidate, **not implemented or an accuracy claim**. Keep v3 active until a separately versioned candidate passes the two saved comparisons and national/shore/physical-bound checks. Report common-finite cases and reachability separately, explain regressions, and retain server-only compact Vercel packaging. The larger missing-road errors will still require a more complete compact road source; endpoint work cannot invent absent roads. No full detailed graph rebuild is proposed.

## Reproduce

With the already cached, hash-pinned roads source available:

```sh
node --import tsx scripts/inspect-coarse-access.ts
```

Runtime deployment does not need this source file. The diagnostic verifies the v3 artifact against the preserved comparison and the source against the artifact's recorded hash. It performs no service/database/network call and does not write its inputs. The script is outside the app TypeScript include list, so check it explicitly:

```sh
npx tsc --ignoreConfig --noEmit --target ES2022 --module ESNext --moduleResolution bundler --skipLibCheck --strict --types node scripts/inspect-coarse-access.ts
```

The diagnostic's 35 path/cost assertions, Biome (143 files), app and diagnostic typechecks, and [ordinary build](build.log) pass. Database integration, Vercel packaging, national smoke and browser tests were not repeated: application code/data are unchanged, and their earlier [v3 results](../coarse-v3-2026-10-22/README.md) remain scoped to that milestone. No routing quota, source download, graph producer or deployment was used. The adjacent checksum manifest records this evidence and observational input/source identities; previous evidence is unchanged.
