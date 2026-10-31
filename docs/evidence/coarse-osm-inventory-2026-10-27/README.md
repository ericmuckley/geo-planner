# National inventory complete; four-pass importer rejected

October 27, 2026. The saved US OSM source reaches normal native EOF with **1,606,229,364 nodes, 162,688,797 ways and 1,624,265 relations**. Both validators accept identical deterministic samples: the first 1,000 objects of each type. The inventory takes **1,260.770 seconds (21.01 minutes)**; no coordinate index is created. These measurements rule out the current all-node/four-pass importer under its existing limits. **Deployed v9 and map accuracy are unchanged.**

The next design to prototype is a two-pass streaming importer with fused native validation, batched compact coordinate storage and independently reconstructed audit indexes. This is a design decision, not qualified extraction code. [Exact arithmetic, proposal and blockers](design-decision.json), [ordered implementation task](../../next-steps.md).

## Measured inventory and samples

| Measurement | V3 result |
| --- | --- |
| Source | Saved 12,229,320,016-byte PBF; no download |
| Native callbacks / EOF | **1,770,542,426 / normal EOF** |
| Nodes / ways / relations | **1,606,229,364 / 162,688,797 / 1,624,265** |
| Sampling | First 1,000 delivered objects per type, fixed before scans; no geographic selection |
| Saved sample | 3,000 records / 3,304,488 bytes; SHA256 `fd45e8844f790da058c708689548ee477382826d202ff06968d91db5ee1aee95` |
| Reference / candidate replay | Both accept 3,000; hashes, loaded counts, visits and EOF counters match |
| JSON sample replay times | Reference 0.131311 s; candidate 0.107294 s; single runs, not a speed benchmark |
| Native inventory time | **1,260.770212 s**, including fixed sample projection/writes and final checks |
| Worker before summary | 1,261.188555 s, including controls/bindings/header/inventory/sample comparison/report |
| Host before summary | 1,282.554261 s, including full-byte identity hash/startup/worker/cleanup |
| Observed process maximum RSS | 251,712 KiB; Linux inventory process only, not host/kernel/cloud/full-import peak |
| Controls | V3 host 23 pass + 2 native skips; Linux **25 pass, no skips** |
| Worker / client / cleanup | Both exit0, not OOM; owned removal and separate absence inspection pass |
| Closed V3 output | 23 files / 3,411,188 bytes |

[Raw result](v3/result.json), [sample comparison](v3/sample-comparison.json), [closed roster](v3-output.json), [independent byte reconciliation](sample-byte-audit.json), [cleanup audit](v3-cleanup-audit.json), [timing summary](execution-result.json).

Counts are **delivered node/way/relation callbacks**, not independently verified unique IDs, routable roads or usable speed attributes. Unsampled objects are counted without copying/validating their metadata. Normal native EOF establishes completion of this decoder's inventory; it does not establish global metadata validity, publisher-boundary adequacy, complete selected geometry/dependencies or nationwide accuracy. Sample replay EOF is separately scoped to the 3,000 saved records. The earlier [native fixture](../coarse-osm-tools-v2-run-2026-10-26/README.md) and synthetic independent audit remain tool/control evidence only.

The source SHA256 is `1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff`; publisher MD5 `c5abaec55e724255277f22fb97941e5a`, header state `2026-10-25T21:21:21Z`. Each attempt hashes the full file once before native work and checks its file identity afterward. The worker reads the 191-byte header separately and then one native stream with `locations=False`; no global coordinate index/cache. Full framing was already verified in the [source run](../coarse-osm-data-v3-run-2026-10-27/README.md); this screen does not repeat it. Tiny native controls create separate fixtures and are excluded from source callback totals.

## Why the old design fails

The complete counts establish a hard incompatibility: four source passes would deliver **7,082,169,704 callbacks**, above the old **4,440,000,000** aggregate ceiling. Nodes exceed its one-billion per-pass limit and ways exceed its 100-million limit. These full-import limits remain held; observer-only count revisions do not qualify that importer.

The separately scoped [64,000-node prefix profile](../coarse-osm-import-profile-2026-10-27/README.md) supplies the frozen time/storage screen. Extrapolation estimates **89,853 s** for just two candidate node-index loops; the fixed 2× margin gives **179,707 s**, versus 14,340 s of original work time. Index storage extrapolates to **43.895 GB each**, or **65.843 GB each** at the fixed 1.5× margin; total margined working estimate **145.416 GB**, versus 64 GiB. These are **prefix extrapolations, not measured national import durations or physical storage bounds**. They exclude remaining passes/way/relation work and cannot become runtime claims. The callback-limit failure is exact arithmetic independent of those forecasts. [Unaltered frozen decision](v3/result.json).

Selected proposal: reduce to two full native passes (**3,541,084,852 callbacks**), fuse exact metadata checks with native projection, batch coordinate writes, and prototype a compact ordered index. A 16-byte payload of 64-bit ID plus two native 32-bit coordinate integers would require **25,699,669,824 bytes/index**, leaving only **70,133,952 bytes** below 24 GiB before headers/lookup structures. Exact native-integer-to-float equivalence is **unproven**. Two full copies fail the retained storage margin; test bounded shard replacement while independently rebuilding audit storage from the second source pass. Do not share the primary coordinate DB or trust its selection as audit truth.

Pass one would select highway ways/dependency IDs; pass two would materialize their complete raw nodes/ways/restrictions while independently recomputing audit geometry/membership. Primary IDs may be a bounded materialization hint only: an independently computed exact key-set comparison must reject omitted/extra dependencies, including adversarial omissions. No such two-pass implementation or peak storage/runtime proof exists yet. A later full recipe would also need an explicit inventory-backed per-type cap revision; no original physical/source/model gate is waived. [Detailed design limits](design-decision.json).

## Preserved stops and observer-only revisions

| Attempt | Delivered source callbacks | Outcome | Count / worker / host seconds | Closed files / bytes |
| --- | --- | --- | --- | --- |
| V1 | 1,000,000,001 nodes | Node cap; no national EOF; ways/relations unmeasured | 814.385 / 814.634 / 835.983 | 23 / 232,320 |
| V2 | 1,500,000,001 nodes | Revised observer node cap; no national EOF; ways/relations unmeasured | 1,171.028 / 1,171.304 / 1,192.314 | 23 / 238,082 |
| V3 | 1,770,542,426 across all types | Normal EOF; mixed-sample equivalence; old importer rejected | 1,260.770 / 1,261.189 / 1,282.554 | 23 / 3,411,188 |

V1/V2 normal worker/client exits2, not OOM. Both retain accepted identical 1,000-node samples, counters, errors and all files; their zero way/relation counters mean **not reached**, not absence in the source. All three exact owned workers are removed and independently absent. Native teardown after a stop is included in final count timing; progress checkpoints are not final timing. Validation state files may retain their historical stage; final result/summary/container-result/cleanup establish closure.

V2/V3 are separately frozen observer-only row/time allocations sharing the same projection, counting, comparison and forecast functions. V3 is the **final native inventory allocation in this stage**: one shared 1.93-billion callback ceiling across types, 1,500 s count / 1,800 s worker / 2,100 s host. Actual source callbacks across the three attempts total **4,270,542,428**; frozen maximum with sentinel **4,430,000,003**, below the original 4.44-billion aggregate. Host intervals total **3,310.852 s**, below four hours. This bookkeeping neither repairs the stopped attempts nor relaxes original full-import typed gates.

| Frozen recipe | SHA256 / file bindings |
| --- | --- |
| [V1](execution-plan.json) | `32459e6f534412de7dad837f5b6241712ab043ad108dcd0f97fb1efcd3e7641d`; 250 host / 219 worker |
| [V2](inventory-plan-v2.json) | `0292d5f66edbf6a38df2c31a8e002a4204221d93bfab283d5e9ecc1346514466`; 279 host / 222 worker |
| [V3](inventory-plan-v3.json) | `cf1d2b7fcb228b4a64324d3333e83cf4a40857ce6ac5b6717564fef49b64b30f`; 308 host / 225 worker |

[V1 command](commands.json), [V2 command](commands-v2.json), [V3 command](commands-v3.json) are **used historical commands**, never health checks. Freeze receipts describe pre-execution state. Do not replay, resume, overwrite or retune any sealed run. All code and earlier negative outcomes remain unchanged.

## Controls, resources and recovery

The new inventory/driver controls cover native N/W/R projection against the frozen reader, truncated decoder rejection, caps/sentinels, time/byte/source-change failures, sample identity/accept/reject equivalence, forecasting, source-bound inputs and owned cleanup/create/monitor failures. V1 runs24 Linux tests; V2/V3 run25 each with no skips. Host native tests skip because qualified native libraries are isolated to Linux. Existing validator guards/negative/Unicode tests are retained. [Verification matrix](verification.json).

Each actual worker: cached qualified Python/image/site/runtime, no network/pull/install, read-only inputs/root, **4 GiB memory/zero swap/two CPUs/64 PIDs/256 MiB tmp**,64 MiB per-file/1 MiB log and1 GiB owned writable+tmp caps. Sample16 MiB total/1 MiB raw element, first1,000/type; no source-wide metadata projection/index. Source/old-index assets are preserved read-only/unused respectively. This is an offline research screen; no app/cloud resource qualification. Source/provider/metadata/dependency/DB/paid requests are zero. App/grid/UI/env/Postgres/npm/Vercel and commits/deployment remain unchanged.

Safe saved proof, no Docker/network/native or producer replay:

```sh
python3 -B docs/evidence/coarse-osm-inventory-2026-10-27/verify.py
python3 -B docs/evidence/coarse-osm-inventory-2026-10-27/verify.py --local-assets
```

The proof chains41 prior sealed runs/213 producers plus10 new frozen inventory/control files. It checks recipes, all retained negative outcomes, actual final resource/exit/cleanup records, exact counts/sample equivalence and decision arithmetic. Local mode also checks raw output rosters, canonical sample bytes/type hashes/node-sample identity and header-prefix bytes; parent proof checks the full saved source and failed-index chain. No repeated source-native scan. V3's 3.3 MB sample stays ignored; small raw receipts are mirrored here. Ignored assets and all new uncommitted code/evidence are absent from a fresh clone.

All original21 windows, publisher/source/50% usable-limit/independent matching/physical/83ORS-35Valhalla accuracy/package/startup/API/visual/model gates remain held. Provider48/6/29 budgets remain consumed. No complete road-attribute dataset, matcher change, graph, ETA or national accuracy result follows from this milestone. [Resume guide](../../agent-handoff.md).
