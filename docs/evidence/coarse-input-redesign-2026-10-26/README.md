# Bounded road-input redesign — October 26, 2026

**Select one finite OSM/Overpass snapshot pilot for synthetic implementation.** The design fixes the existing 21 validation windows, at most **42 HTTP attempts**, no retries/failover, a **512 MiB total response-body ceiling**, 1 GiB memory/zero swap and one hour. It does not fetch data, implement a downloader or qualify source coverage. [Exact proposal](proposal.json), [decision](decision.json), [21 queries and hashes](queries.json).

This completes the preceding [design-only task](../coarse-timing-fragments-run-2026-10-26/next-input-design-plan.json). The stopped Overture pilot and all later cache/matcher results remain untouched. The last measured geometry gain is still 96 records/61.774 original source km, with only five newly supported records/1.033 saved-sample km containing any all-parser-usable candidate; those are unqualified opportunities. [Measured evidence](../coarse-timing-fragments-run-2026-10-26/README.md).

## Two approaches reviewed

| Approach | Documented capability | Decision for this pilot |
| --- | --- | --- |
| Overture cloud GeoParquet extraction | The Python client streams bounding-box results and uses STAC for latest-release discovery. | Not selected. Those features do not themselves enforce our aggregate HTTP/request/resource bounds or demonstrate complete-window attributes. No new package, automatic release selection or stopped-pilot retry. |
| OSM snapshot extraction through Overpass | The manual describes crossing-way selection and retrieval of every referenced way node. Date queries and terminal counts support a bounded capture contract. | Selected for one finite offline pilot, subject to new transport/closure tests and a later executable freeze. Completion, attributes and source usefulness remain unmeasured. |

[Overture client documentation](https://docs.overturemaps.org/getting-data/overturemaps-py/), [Overture catalog](https://docs.overturemaps.org/getting-data/cloud-sources/), [Overpass geometry manual](https://dev.overpass-api.de/overpass-doc/en/full_data/osm_types.html), [QL reference](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL). This is an engineering selection for the present envelope, not a finding that Overture is generally unsuitable or that OSM has better nationwide attributes. [Dated source notes](sources.json).

## Exact capture design

All 21 original bboxes and their order are preserved. Each window has one status GET followed by at most one interpreter POST at `overpass-api.de`; requests are sequential. Snapshot **`2026-10-21T00:00:00Z`** and all query/form hashes are fixed before data access. No current-state fallback, endpoint rotation, repair query or alternate window.

The query selects all highway-tagged ways, retrieves all referenced nodes without a bbox crop, and retains parent `type=restriction` relations from those roads/nodes. Relation member references remain raw; external relation geometry is not recursively fetched or treated as resolved. Output contains full metadata objects and one terminal count over the same payload set, with no output limit. The operator's manual explicitly includes ways crossing the box without an interior node and explains how `node(w)` completes their geometry. [Geometry contract](https://dev.overpass-api.de/overpass-doc/en/full_data/osm_types.html). Restriction relations carry typed from/via/to context; their absence does not capture every implicit driving rule. [Restriction schema](https://wiki.openstreetmap.org/wiki/Relation:restriction).

Capture acceptance requires every selected way node, exact per-type/total counts, valid complete JSON without error/remark, consistent duplicate typed IDs, the requested snapshot and a consistent observed generator/schema. It must preserve every partial/empty/failed window. This is completeness of the documented query result and selected-way node closure, **not** complete real-world roads, all relation dependencies or a national routable graph. No live capability or completeness check was performed during this design.

Record actual response hashes, generator and source timestamps in the later run; no immutable publisher release is claimed. Bind every way geometry to its ordered node IDs, node versions/coordinates and dependency hash. A way's version can remain unchanged while its nodes move, so way ID/version alone is insufficient. [Historical-data identity](https://dev.overpass-api.de/overpass-doc/en/analysis/museum.html).

## Bounds and failure behavior

| Proposed limit | Value |
| --- | ---: |
| HTTP attempts | 21 status GETs + 21 interpreter POSTs = 42 |
| Total received body ceiling | 512 MiB, including metadata/error bodies |
| Accepted query body / status body | 16 MiB / 64 KiB |
| Oversize detection | At most one extra metered byte per response, then stop |
| Maximum body reads under the request plan | 353,697,834 bytes (a bound, not an observation) |
| Tool downloads, retries, paid fallback, provider queries | 0 |
| Unique source elements / total occurrences | 250,000 / 500,000, all types included |
| Normalized extract / working files | 128 MiB / 2 GiB |
| Client memory / swap / bounded tmp | 1 GiB / 0 / 64 MiB |
| Global independent watchdog | 1 hour |

Server settings are 60 seconds and 256 MiB **server RAM**. They are not download or client-memory caps; separate transport meters, local cgroups, disk guards and the watchdog must enforce those. Status/client query deadlines are 10/90 seconds, measured through the complete body, with at most a 30-second status-directed wait. Any refusal, timeout, error, schema drift, oversized/truncated body or cap stops the run and preserves remaining windows as unmeasured. [Operator resource/rate model](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html).

Only the fixed HTTPS host/status/interpreter paths are allowed. Disable inherited proxies/credentials/cookies and redirects; reject unexpected compression. Every status/data/error body passes one meter and budgeted spool. No unmetered native remote filesystem, remote SQL scan, extension fetch or package download. The cached Python standard-library Linux image is sufficient in principle; that is a proposed dependency choice, not implementation/resource qualification.

The public service can refuse requests and does not promise this workload will complete. Its operator discourages world-scale bbox scraping and use as a production backend. This 21-window offline pilot is neither a nationwide acquisition method nor an application dependency. A later national expansion needs its own source/resource plan. [Commons guidance](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html).

## Attributes and original gates

Preserve raw tags, units, source/node/way/relation identities, direction, conditions, access, levels, barriers and restrictions. OSM documents `maxspeed` as a limit with default km/h and optional units; it is not observed driving time. [Speed-tag documentation](https://wiki.openstreetmap.org/wiki/Key:maxspeed). Do not infer statutory limits by road class, flatten directional/conditional tags or grant car permission from generic allowed values. Retain source/license provenance and the required OSM attribution/ODbL notice. [Publisher license](https://www.openstreetmap.org/copyright).

Native OSM fields are not interchangeable with Overture's schema. A separate lossless source adapter/parser contract must be specified, synthetically tested and frozen before any usable-limit/matching conclusion. No such adapter or semantic policy is implemented here. Unsupported/missing applicability stays unknown; capture completeness alone never satisfies feasibility.

Retain all original gates: all 21 window ledgers complete; source/schema/provenance/parser accounting; at least **50%** of original clipped Census km with a unique plausible match and usable limit; all class/window/layer denominators; deterministic independent review of fifty asserted matches or every match if fewer. Keep 25 m/15°/80% geometry criteria and every alternative/grade/access uncertainty. All 83/35 accuracy, physical/source/shore/transfer/path, <=70 MB function, retained decoded <=162,238,546 bytes, first packaged estimate <=5 s and API/software/shared-camera gates remain. None is cleared by this design.

## Next task and commands

Implement new `scripts/coarse_osm_input.py`, its synthetic tests and independent raw-response/count/closure/identity audit. Test transport/status/clock limits, malformed or partial responses, missing nodes, changed node geometry under an unchanged way version, duplicate IDs/counts, raw metadata round trips and hard Linux guards before any live access. Preserve old sealed producers and all historical failures. [Full fixture requirements](proposal.json).

Prospective offline checks; **the new files do not exist yet**:

```sh
python3 -B -m unittest discover -s scripts -p 'coarse_osm_input_test.py'
npm run check
npm run typecheck
npm run build
```

After those checks, freeze exact reader/dependencies/query/inputs/resource rules in a new executable recipe before a later single capture at ignored `data/coarse-quality/osm-timing-pilot-v1/`. The proposal includes a future command template; no live command is ready or executed now. Source-adapter/matching analysis and every original feasibility/model gate remain separate required steps.

Read-only design verification:

```sh
python3 -B docs/evidence/coarse-input-redesign-2026-10-26/verify.py
python3 -B docs/evidence/coarse-input-redesign-2026-10-26/verify.py --local-assets
```

This checkpoint changes documentation/design artifacts only. Official documentation was browsed; **zero road/status/interpreter requests, tool-binary downloads, routing-provider queries or new matcher runs** occurred. No exact byte/HTTP-attempt count is claimed for browsing. V9/grid/UI/env/DB/npm, prior assets/failures and consumed 48/6/29 budgets remain unchanged. Work remains local/uncommitted. [Recovery](../../local-development.md#bounded-osm-input-design), [ordered next task](../../next-steps.md).
