# Timing-input decision and bounded pilot — October 25, 2026

**Decision: obtain better road-specific timing inputs before selecting another cost rule.** The cached sources lack structured speed-limit and reliable junction-control/delay fields. Geometric angles and incidence can be derived, but do not justify invented intersection penalties. The concrete next step is a hard-capped **Overture attribute-coverage and road-matching pilot**. No data was acquired, speed policy selected or candidate produced in this design task. Deployed v9 stays unchanged.

This completes the [timing-design task](../coarse-distance-budget-2026-10-25/next-timing-plan.json) with a bounded missing-input proposal, rather than another open-ended residual analysis. All older producers, decisions and evidence remain unchanged. The work is local/uncommitted at HEAD `648c731`.

## What the existing inputs actually contain

The [inventory recipe](inventory-plan.json), SHA `6b15e94a00b7162769c99aacf3f1fd7f38ea000c9995301d0ee6139d846e4f84`, froze before inspecting cached schemas. [Inventory tool](inventory.py), [all field lists/reference IDs](inventory.json), [independent Census header check](schema-check.json).

| Input | Recorded availability | Timing limit |
| --- | --- | --- |
| All 49 Census primary/secondary ZIP schemas | `LINEARID`, `FULLNAME`, `RTTYP`, `MTFCC`; uniform headers | IDs/names/classes, no speed-limit, traffic-control or turn-restriction field |
| Cached Natural Earth roads | 31 property names including `type`, `expressway`, `toll`, `level` | No explicit speed limit or junction-delay field; do not reinterpret `level` as verified grade separation |
| Backbone's 17 graph arrays | Coordinates, incidence, source distance, assumed class speed/cost, geometry and indexes | Original source nodes can be distinguished from added crossing nodes; neither source incidence nor an angle identifies an allowed/controlled turn or measured delay |
| All 83 saved ORS references | Summary time/distance and route geometry; instructions disabled, zero instruction steps | No per-maneuver timing. Seventy have empty extras; thirteen expose `roadaccessrestrictions`, not road-specific speed observations |
| All 35 older Valhalla references | Shapes, summaries and maneuver fields including time, length, type and bearings | Useful provider-side maneuver aggregates, but no direct common model-road IDs or per-road speed-limit field; different reference profile/date semantics remain |

The adapter explicitly assigns class speeds; the `arcSpeedKph` array is a model assumption, not measured speed. The producer preserves original endpoint nodes and adds separate cell crossings; a penalty per graph edge/node would make time depend on artificial segmentation. [Graph schema](../../../src/server/backbone-geometry.ts), [source adapter](../../../scripts/coarse_census.py), [original-node construction](../../../scripts/coarse_backbone_geometry.py), [supplementary reference schema inspection](reference-schema-notes.json).

The prior 95/85 and 100/82 class revisions remain rejected. The [expressway check](../coarse-damped-calibration-2026-10-24/README.md) found the flag in both misses and severe underestimates; the [curvature/corridor work](../coarse-path-features-2026-10-24/README.md) did not establish a universal timing rule. The newer [cost control](../coarse-road-time-control-2026-10-25/README.md), [class exposure](../coarse-timing-exposure-2026-10-25/README.md) and [distance budget](../coarse-distance-budget-2026-10-25/README.md) retain all 83/35 contrary cases. None supplies the missing road-specific timing attribute.

This does not prove that no useful heuristic can be built from the current graph. It means there is insufficient evidence to choose another numerical rule without repeating broad-factor guessing or assigning unsupported delays to source geometry. [Decision](decision.json).

## Concrete proposed input

Test **Overture transportation segments** for numeric speed limits with units/direction/subrange provenance, plus access, connector and level context for screening road matches. Overture documents scoped speed/access/turn rules, but leaves implied speed limits to applications; schema availability is not observed US coverage. [Road rules](https://docs.overturemaps.org/guides/transportation/roads/), [segment schema](https://docs.overturemaps.org/schema/reference/transportation/segment/).

The proposal names release **2026-10-21.0 / schema v2.0.0**, as reported by the publisher on this date. Actual object manifests, identities and schema must be verified and frozen before a data run; the STAC URL was inaccessible through the web tool during metadata research. No catalog or road object was downloaded or verified. Stop if the pinned release is unavailable instead of silently choosing latest. [Release information](https://docs.overturemaps.org/release-calendar/), [recorded metadata findings and limitations](source-notes.json).

Speed limits constrain lawful speed; they are not observed average speeds or traffic/turn delays. The pilot measures whether a useful attribute and a sufficiently conservative mapping exist, not whether copying limits into the engine would improve ETA. [OSM maxspeed semantics](https://wiki.openstreetmap.org/wiki/Key:maxspeed).

## Frozen proposal scope and stop conditions

[Full machine-readable proposal, exact 21 windows and criteria](data-input-proposal.json).

- **Selection:** every distinct origin from all 83 frozen captures, sorted by longitude/latitude, with a fixed ±0.05° box. All 21 windows remain, including empty/failed/stopped ones. No route-error filtering or replacement. These are data-validation windows, never runtime regional exceptions or national coverage.
- **Network:** at most **512 MiB of received HTTP bodies**, including metadata, listings, footers, wheels and data; at most 10,000 requests, zero retries/paid services/routing-provider requests. All library access must pass the same meter. No whole-US extract or implicit extension download.
- **Local processing:** at most **1 GiB process RSS, 2 GiB total working storage, 128 MiB retained extract, 250,000 unique segment rows and one hour**. Guard enforcement must be demonstrated on the host before live access. Stop at the first error/cap, preserving all window statuses.
- **Parsing:** preserve source/license/version metadata and complete linear/directional/conditional rules. Missing, conflicting, variable or unsupported limits stay explicit. Only whole-span numeric ordinary-car limits applicable in both directions without time/vehicle/use conditions count as usable for this first screen.
- **Matching:** original-source-km-weighted coverage against cached detailed Census geometry. Predeclared plausible-match checks are ≤25 m corridor, ≥80% clipped source-length coverage and ≤15° tangent difference; multiple passing candidates remain ambiguous. Preserve grade/identity uncertainty. Natural Earth/base alignment is reported separately; representative chords are not road geometry.
- **Go/no-go:** all 21 windows must complete within caps. At least **50%** of clipped detailed-Census source km must have a unique plausible match and usable limit; independently review 50 matches selected by fixed hash rank, or all if fewer. Any definite wrong-road match fails readiness. This prospective engineering screen assesses usefulness only; it is not an accuracy or national-coverage gate.

Bbox-filtered cloud GeoParquet makes this a plausible bounded experiment, but predicates and row limits do not themselves bound bytes transferred. The proposed controlled range reader must enforce the cap and reject ignored ranges, identity changes and unmetered fallback before reading road data. Publisher examples support intersecting-segment filtering. [Query examples](https://docs.overturemaps.org/getting-data/duckdb/).

## Integration and next task

Build and test the capped reader/parser with synthetic local fixtures first. Resolve/pin metadata/object identities and tools under the same budget, freeze the exact pilot recipe, then execute one pilot. Preserve partial failures; no automatic release switch, larger budget, retry or new window. Actual road-data acquisition was outside this completed design task.

If the pilot passes, design one attribute-based policy and a separately bounded nationwide input expansion. A later offline producer could compile accepted attributes into existing static road-cost payloads, retaining generic class fallback for missing/unsupported/unmatched data. The Vercel app would still query bundled TypeScript data without a new database or online routing/data service. This integration is proposed, not implemented or qualified; compression, startup, retained memory and arbitrary-origin accuracy remain gates.

All original 83/35 accuracy/missed/tail/individual limits, physical/source/path checks, ≤70 MB function, ≤162,238,546-byte retained decoded storage, ≤5 s first packaged estimate and API/visual checks remain. Pilot results cannot activate either rejected candidate. Raw inputs/tool environment stay ignored and excluded from Vercel. Preserve publisher/source attribution and license metadata in later derivatives. [Overture transportation attribution](https://docs.overturemaps.org/attribution/#transportation).

## Verification and recovery

All **49 DBF headers** independently match the already-pinned pyshp 2.3.1 reader; no dependency was installed. All **83 ORS/35 Valhalla** schema records and 17 graph fields remain. Biome checks 197 files, app typecheck and ordinary build pass. No model/graph search, source rebuild/download, provider request, env/key/DB input or deployment. Official web documentation research is separate from road-data acquisition. [Checks](checks.json).

Completed inventory outputs refuse overwrite. Read-only recovery:

```sh
python3 -B docs/evidence/coarse-timing-design-2026-10-25/verify.py
python3 -B docs/evidence/coarse-timing-design-2026-10-25/verify.py --local-assets
```

[Exact commands](../../local-development.md#timing-input-design), [next task and pass/fail criteria](../../next-steps.md).
