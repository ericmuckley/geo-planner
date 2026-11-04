# Road-only static-car cost prototype — November 1, 2026

The user selected road-only scope. Vehicle ferries are deferred. This is a bounded captured-data cost/encoding experiment, not a new deployed model or nationwide ETA claim. Original83ORS/35Valhalla accuracy cases and application gates remain unchanged. No provider/PBF/application-DB request is authorized here.

## Frozen design

The fixed major-road profile, full source-way geometry and native-point aliases come from the [independently checked lineage prototype](../coarse-osm-way-lineage-prototype-2026-11-01/README.md). The cost prototype reads that sealed graph and the existing477MBcaptured JSONL; it does not rebuild geometry or read the country source.

Reuse the existing pure generic `routing/import_roads.py` speed/access functions and `routing/barrier_policy.py` barrier decision. Role defaults, direction precedence, allowed speed units, unknown-speed/conditional/lane closures and exact constants are bound in each recipe. Motorways/roundabouts default one-way; direction-specific car access and speed tags take precedence. Signal delay5s, physical U-turn20s; no traffic/calendar evaluation. Unsupported car relations, including via-way restrictions, conservatively close their member ways. Excluded and unsupported counts remain visible. This first prototype is deliberately incomplete car policy; it cannot establish nationwide coverage or ETA quality.

Raw and contracted graphs use the same incoming-arc turn state. Physical reverse identity distinguishes parallel arcs/closed loops. Reversal is allowed at source-way ends, selected-major junctions, tagged nodes or explicit relation nodes; an arbitrary shape point or validation-window cut alone grants no reversal permission. A trip may start/end at a control node without having crossed it; passing through a blocked control is prohibited. This declared policy is narrower than arbitrary mid-segment U-turns. All primitive distances use the existing car reference earth radius6371008.8m; integer primitive costs are rounded upward to milliseconds before lossless contraction.

Costs use125msupward-rounded u16ticks;65535is a sentinel for a sorted `(arc:u32,ticks:u32)` lossless overflow table. No saturation. A reachable u32tick overflow fails the run. Reverse physical arc identity uses an outgoing-at-head u8ordinal,254overflow with sortedu32arc/target table,255absent. Node flags encode blocked/signal/reversal; supported via-node turns use sparse forbidden incoming/outgoing arc pairs. All emitted arrays are little-endian. Source geometry and paid internal-point partial costs remain offline; snapping/geography/search/JS/package data are **excluded** from isolated payload bytes.

## Qualification and acceptance

Run26synthetic Linux checks, no skips, under the same2GiBzero-swap/1CPU/64MiBtmp/128MiBfile/256MiBowned allocation/600sworker/660shost bounds. Checks cover the separate flat-state Bellman-Ford oracle, all native-point pair costs/reachability, one-way and directional speeds, access/barriers/signals/no/only turns, conservative unsupported closures, coincident distinct native IDs, loops/parallel/repeated/zero geometry, cost/reverse overflow, malformed binary, input/cap/deadline and observed isolation drift. A separate binary-array reader imports neither graph producer nor codecs/turn policy.

Only after controls pass, freeze the actual command. Keep all41original native geometric cases across21areas and separately check their41reversals: raw versus contracted exact car costs/reachability, binary-reader versus quantized queries, and finite error bound0..124msper best exact contracted fragment. These are82directional checks of41existing geometric pairs, **not83ORSaccuracy cases**. Unreachable cases remain in the denominator. Validate every serialized cost/reverse identity and all source geometry partitions/aliases. All worker/network/ownership/cleanup evidence must close; failures remain preserved and any correction uses a separate version.

Reserve64.5GBfor prior retained assets plus every new closed allocation, within64GiB. Do not modify old failed evidence or rerun completed producers. Deployed v9, app source, env and DB stay unchanged.

## Completed results

All26protected Linux tests pass, no skips. The separate tiny wire proof decodes44bytes exactly. The captured run preserves all41original pairs across21areas and checks their41reversals:82/82raw-versus-contracted car cost/reachability checks pass,68finite and14unreachable retained. All82binary-reader results agree. Sixteen directional endpoints are internal native points. Maximum measured upward quantization difference is8,476ms, within the frozen per-fragment bound; this is encoding error, not real-world ETA error.

The captured source has28,995selected ways/143,560native points. Directed raw arcs218,666contract to86,517arcs at53,672anchors. Isolated compact payload1,321,511bytes: no cost/reverse overflow entries in these samples,2,269forbidden turn pairs. All89,888offline internal aliases remain. These measured sample bytes are **not** a country-size extrapolation.

Policy inventory:28,610way-eligible,198access exclusions,155conditional/way-restriction exclusions and32lane-access exclusions. Before relation closures,42,389eligible directions include20,396role-default speeds and14,831one-way ways. All4,900relations are retained:4,078supported via-node rules,819unsupported/conditional closures and3non-car rules. Unsupported closures touch1,404selected ways; this overlaps the way-eligibility counts. Selected nodes include24,323tagged,81blocked and5,319signals. Counts are measured in the captured samples, not nationwide applicability/completeness.

The separate source audit passes against the sealed read-only auditSQLite. It reconstructs all28,995ways/143,560selected native nodes/4,900relations, independently computes218,666primitive directed arcs, checks every86,517compact arc cost/reverse identity, all53,672node flags and2,269forbidden pairs, and matches all82queries using an independent incoming-arc Dijkstra (415,958settles). It imports no car graph producer/codec/payload reader. Eight audit self-controls pass. Existing pure reference speed/access/barrier helpers are shared and remain explicitly bound.

| Stage | Host elapsed | Protected work scope | Cgroup peak | Closed logical / conservative allocation |
| --- | ---: | --- | ---: | ---: |
| Controls |0.712951s|0.093044s including tests/tiny producer|28,913,664B|34,008 /1,363,968B|
| Captured run |30.173281s|29.359809s including input bindings/source scan/build/queries/output|956,424,192B|1,420,004 /2,723,840B|
| Independent audit |3.285574s|2.726472s including SQLite/hash/source/array/query checks|606,859,264B|16,620 /1,187,840B|

All workers/clients exit0, no swap/OOM; all three workers are independently absent. The captured query-check scope1.365004s includes82raw/contracted/quantized/binary checks and is not a packaged first request or national graph-search benchmark. New closed conservative allocations total5,275,648B, additional to64.5GBprior reserve. No source PBF, provider, appDB or network request, new input download, app/model/env/config change or deployment occurred.

The new format also changes the earlier national arithmetic: with5,731,903vertices and both directions on6,674,747edges, `13V + 7A + 4` is167,961,201Bbefore overflow/turn/snap/geography/runtime extras. That exceeds the162,238,546Bretained-decoded gate by5,722,655B. This is a hypothetical both-direction layout, not an actual national car graph; one-way/access/closure effects need exact country counts. The earlier149MBu16estimate omitted reverse identity and node flags. Regional ratios cannot establish fit.

## Resume safely

```sh
python3 -B docs/evidence/coarse-osm-car-prototype-2026-11-01/verify_audit_v1.py
PYTHONPATH=scripts:routing python3 -B -m unittest coarse_osm_car_v1_test -q
```

The default proof reads repository code, frozen plans and small mirrored records only. It does not read ignored graph/SQLite/PBF/tool files or replay any worker. The independent actual source audit has already completed; do not repeat it for documentation. Frozen commands are historical/single-use, with controls recipeSHA`48bfccad50efe20cb329e9b5e11c6b97998c286c9d8bc917dbd00d6ae32f63b2`, actual recipeSHA`859e4e09615c2c63aa60401ee6f90bdc8d2bb52e9e3f2a88ef81aceee6508420`, audit recipeSHA`dee66b77e18ef58bfc7a03c3f0ce68a6d8e4adf8a78b570ec87252083e707429`.

The code is in `scripts/coarse_osm_car_{policy,codec,graph,payload}_v1.py`, `coarse_osm_car_v1_test.py`, `run_osm_car_v1.py`; audit code and frozen/mirrored evidence are in this directory. Controls/run use the V1closer; the V2closer adds the audit root without changing old closures. All used code/recipes/evidence are immutable. Large graph payloads remain ignored under `data/coarse-quality/us-osm-car-{controls,run,audit}-v1/`; a fresh clone lacks these and the source/SQLite/runtime. New code/docs/results remain local/uncommitted.

[Next scope](next-national-cost-scope-v1.json): account for unreachable cases, qualify typed native car-capacity rules, and budget the complete app representation before freezing a country candidate. No country command exists. Whole-app source snapping/geography/runtime/search/JS/package memory, national car coverage/cost overflow and all original accuracy/physical/API gates remain unqualified. Deployed v9 is unchanged.

## Reachability diagnosis completed

All 82 frozen baseline reachability checks agree, including the 14 unreachable cases. Eight protected Linux controls pass. Six diagnostic switches were frozen before analysis. Individually ignoring unsupported member-way closures reconnects 10 cases, direction limits 6, excluded ways 3, supported via-node turns 2, blocked controls 0; all-geometry reconnects all 14. Effects overlap and are not unique causes or valid permission corrections. The witnesses identify 34 unsupported source relations (31 via-way, three other/conditional). Reachable points outside the query windows show exposure only; no legal missing detour is inferred.

Host 3.840875 s, core 2.906755 s including sealed SQLite bindings/reconstruction/queries; 921,450 settles, peak 562,159,616 B. Closed conservative allocation 1,396,736 B; worker/client 0/no OOM/independently absent. V2 recipe adds explicit frozen baseline bindings before any execution; the unused V1 recipe remains preserved. No original case or permission/model rule changed.

```sh
python3 -B docs/evidence/coarse-osm-car-prototype-2026-11-01/verify_reachability_v1.py
```

The [native-policy and national-capacity continuation](../coarse-osm-car-capacity-2026-11-01/README.md) follows this diagnosis. Its current national count is separate from these completed captured results.
