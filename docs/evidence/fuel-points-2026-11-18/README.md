# Fuel point feasibility

November 18, 2026. OpenStreetMap documents `amenity=fuel` on a node or a closed way. The prototype keeps the mapped point for a node and chooses an interior point on a closed way's outline. The file keeps the source type and ID, plus the name or brand when present. [OpenStreetMap fuel tagging](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dfuel#How_to_map).

| Cached sample | Fuel nodes | Fuel ways | Output points |
| --- | ---: | ---: | ---: |
| Downtown San Diego, `data/reference-pilot/downtown-static-v1/region.osm.pbf` | 3 | 8 | 11 |
| Malta reader control, `data/valhalla/sources/malta-261014.osm.pbf` | 55 | 23 | 78 |

Both runs used the cached Linux image and pyosmium with read-only inputs and no network. The pilot reconciled every matched record, resolved all required way vertices and emitted valid coordinates. Tests exercised a concave outline and a degenerate outline. The app's polygon check placed all eleven downtown points inside one local 30-minute v9 estimate. These are mapped features in two small snapshots. Nationwide counts, duplicate locations, multipolygon relations, business status and coverage have yet to be measured.

[Extractor](../../../scripts/extract_osm_fuel_sample.py). It takes a local extract path and expected SHA-256, caps inputs at 16 MiB and writes JSON to stdout. It is meant for a small sample, not the cached 12 GB country snapshot. The sample input hashes are `c1830a4f833e1bfb4b8420b1ecf1127a0405e6df14267ca5aeab647e9a8cae89` and `996bd058510cf562dd9b4ac7aad45d880a9f89f4a83ec49e9d626588d0b22f79`.

The national and app results below supersede the pilot-only status.


## National inventory and local app layer

The [US inventory report](../coarse-osm-car-capacity-2026-11-01/fuel-inventory-us-v1-raw-v1/report.json) verifies the cached US snapshot dated October 25, 2026. The first pass found 43,919 nodes, 65,710 ways and 903 relations tagged as fuel. The second pass resolved all 371,538 nodes referenced by eligible closed ways. The extraction took 175.51 seconds including the complete source checksum and both passes in a bounded, network-disabled container.

The 108,634 output points have unique OSM IDs and valid finite coordinates. The accounting removes 312 explicitly restricted records, 670 outlines that duplicate a contained point, eight identical coordinate and name records, six unsupported ways and 902 unsupported relations. A rectangle spanning the contiguous US contains 108,049 points distributed across 50 five-degree bins. This verifies geographic spread in the source snapshot. It does not provide a count of every retail site or verify current business hours.

The 4,997,468-byte [public catalog](../../../public/places/fuel-us-v1.json) contains attribution, source date and the ODbL 1.0 link. Its SHA-256 is `67316f816137691ef867b8e309904732800460bdb075346472d9a755daac1319`. A local gzip sample is 1,811,641 bytes. The app requests the catalog only when the layer is turned on. [OpenStreetMap attribution and license](https://www.openstreetmap.org/copyright).

| Origin | Driving time | Matched fuel locations |
| --- | ---: | ---: |
| San Diego | 30 minutes | 382 |
| San Diego | 8 hours | 8,741 |
| Denver | 2 hours | 1,605 |
| Central Kansas | 6 hours | 5,223 |
| New York | 12 hours | 36,891 |

The direct and indexed filters returned the same counts and agreed on independently sampled catalog points for all five contours. Edge and hole tests also pass. The long New York filter went from 7.63 seconds to about 44 milliseconds in local Node measurements. These times cover filtering, without route computation, download or map rendering.

Chrome checked the short and 12-hour San Diego areas, a named station popup with unchanged origin, and hiding and re-enabling the fuel layer. The build, typecheck, Biome and 89 server tests pass. The local Vercel build retains the exact catalog under its static files. The packaged routing function is 65,072,092 bytes and the first estimate after configuration took 3.67 seconds in the local handler test with zero outbound requests.

Recovery: [sample sealed roster](../coarse-osm-car-capacity-2026-11-01/fuel-inventory-sample-v1-closed-v1.json), [national sealed roster](../coarse-osm-car-capacity-2026-11-01/fuel-inventory-us-v1-closed-v1.json), [offline runner](../../../scripts/run_osm_fuel_inventory_v1.py), [staging verification](../../../scripts/stage_osm_fuel_catalog_v1.py). Do not repeat a completed root. Use the existing public file or restage from the completed national output. [Preview and package verification](../../local-development.md#try-the-fuel-layer).


## Hosted release

GitHub main release `25af389` deployed successfully to [Geo Planner](https://geo-planner-orcin.vercel.app/). The deployed catalog matches the local public file SHA-256 exactly. Production API estimates for San Diego at 30 minutes and 12 hours returned contours matching 382 and 12,184 fuel locations. The same destination check was outside at 30 minutes and inside at 12 hours. The clean release passed 89 tests and local Vercel package verification. [Hosted result](hosted-release-v1.json) · [Vercel deployment](https://vercel.com/erics-projects-d68d5ce3/geo-planner/DAAc4gwXDQj3Um1Uj76UWz2aSu9j).
