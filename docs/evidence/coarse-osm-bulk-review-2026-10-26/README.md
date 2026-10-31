# Native OSM bulk-input review — October 26, 2026

**No-go for the two reviewed whole-file bulk approaches under the unchanged pilot envelope.** No acquisition design is selected, executable recipe created, limit increased or snapshot changed. This completes the [frozen review scope](../coarse-osm-pilot-run-2026-10-26/next-input-design-plan.json). [Decision and exact arithmetic](decision.json), [dated primary-source notes](sources.json).

## Reviewed approaches

| Approach | Documented blocker |
| --- | --- |
| Geofabrik regional PBF/history plus local extraction | The listed `socal-261020.osm.pbf` alone is **671,829,508 bytes**, exceeding the entire **536,870,912-byte** body budget by **134,958,596 bytes**, before other regions, metadata or tools. The publisher lists no smaller child there. [Regional listing](https://download.geofabrik.de/north-america/us/california/socal.html). |
| OSM planet/history plus local time filtering/extraction | The publisher lists `planet-261019.osm.pbf` as **89G**, already beyond both transfer and retained whole-file storage limits. This is a rounded metadata size, not a measured download. [Planet directory](https://planet.openstreetmap.org/pbf/). |

The Geofabrik national listing provides useful scale for the next proposal: `us-261020.osm.pbf` is **12,219,271,434 bytes** (22.760 times the current transfer ceiling). This is listed source size, not normalized-road, graph or Vercel function size. [US listing](https://download.geofabrik.de/north-america/us.html).

These are sufficient blockers for the reviewed whole-file methods, not proof against all spatial distributions, OSM routing or a larger offline build. No other acquisition service was evaluated as a third candidate. No source-header/checksum/geometry coverage was inspected; directory metadata is distinguishable from immutable verified input identity.

## Snapshot and closure checks

The required state stays `2026-10-21T00:00:00Z`. Filename dates and modification times do not establish that state. Geofabrik documents limited retention of older extracts, login-protected regional history and extract-to-extract updates. No exact historical reconstruction chain was established. Optional editor fields absent from public files are not themselves a rejection of native geometry/tag metadata. [Publisher technical details](https://download.geofabrik.de/technical.html).

Osmium time filtering can select historical object versions from history input in one streaming pass. A later state-only file lacks superseded/deleted versions needed for general reconstruction; this is an inference from the documented input contract. Streaming does not eliminate source-transfer bytes. [Time-filter manual](https://docs.osmcode.org/osmium/latest/osmium-time-filter.html). The history directory was inaccessible through the browser tool; the [project's history documentation](https://wiki.openstreetmap.org/wiki/Planet.osm/full) is not a verified post-snapshot object.

There is also a generic extraction mismatch: Osmium `complete_ways` starts with nodes inside the region, then completes ways referencing them, using two input passes. It does not establish selection of a segment crossing a box with both nodes outside. For example, the horizontal segment from `[-1, 0.5]` to `[2, 0.5]` intersects `[0, 0, 1, 1]` and has no inside node. The [synthetic reasoning record](closure-review.json) checks this distinction; no Osmium extraction was executed. `simple` supports pipes but leaves boundary ways incomplete. A future implementation needs segment intersection plus full selected-way node closure and its own resource proof. [Extract manual](https://docs.osmcode.org/osmium/latest/osmium-extract.html).

## Decision and next action

Close this design branch without a downloader prototype or further public-endpoint requests. Preserve both stopped captures and every old source/cache/matcher result. Neither the original 502 nor this budget review establishes road quality, usable speed coverage, car access, model accuracy or national completeness.

Next prepare **one explicit versioned offline US-input resource/snapshot revision proposal**. Use the Geofabrik national PBF path as the candidate; specify exact identity, proposed transfer/working/memory/time bounds, local capacity and crossing-way semantics. A publisher snapshot change may be proposed explicitly in a new version; the old snapshot and evidence stay intact. No larger budget or changed state is activated by this decision. [Exact next scope and acceptance](next-scope-plan.json).

Larger offline preparation need not enlarge the Vercel runtime. The product path remains compiled compact static costs, with all original 21-window denominators/source gates, 50% unique plausible usable-limit Census-km, independent match review and 83/35 accuracy/physical/package/memory/startup/API/visual gates. Retain OSM provenance, attribution and ODbL notice. [Publisher license](https://www.openstreetmap.org/copyright).

Only primary documentation/directory descriptions were browsed; their HTTP bytes/attempts are not claimed as metered. **Zero road/PBF/replication/status/interpreter payloads, tool binaries, routing-provider requests or matcher runs.** No new implementation, graph arrays, service, dependency, app/UI/env/DB/config or deployment. The old 28 host/Linux fixtures/resource/check/typecheck/build evidence stays bound to unchanged implementation and was not rerun. Work remains local/uncommitted; deployed v9 is unchanged.

Read-only proof commands, with no network, Docker or producer replay:

```sh
python3 -B docs/evidence/coarse-osm-bulk-review-2026-10-26/verify.py
python3 -B docs/evidence/coarse-osm-bulk-review-2026-10-26/verify.py --local-assets
```

[Handoff](../../agent-handoff.md), [next steps](../../next-steps.md), [local commands](../../local-development.md#native-osm-bulk-input-review).
