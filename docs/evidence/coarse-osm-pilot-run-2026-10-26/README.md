# Native OSM capture stopped before road query — October 26, 2026

**One frozen capture attempt stopped on its first status GET: HTTP 502, 534 delivered body bytes, zero interpreter POSTs or road objects.** The response body reports capacity/full queue. That content is not independent evidence of server internals, permanent source infeasibility, an oversized query or missing roads. [Raw response](http/00001.bin), [measured summary](run-summary.json), [state](state.json).

The unchanged [executable recipe](../coarse-osm-pilot-2026-10-26/execution-plan.json), SHA `c8dd8d24f91a9fa679cd22ebd48bc06d38728a3605b8c29494c29d1d6e53fd48`, ran once at ignored `data/coarse-quality/osm-timing-pilot-v1/`. Its 41 inputs, 29 worker files, 21 original queries and all limits stayed frozen. No retry, polling, redirect, mirror, repair query, fallback, tool download, provider quota or DB access occurred. Text in the error body suggesting retries did not change the frozen policy.

## Measured result

| Item | Result |
| --- | ---: |
| HTTP attempts / status GETs / interpreter POSTs | 1 / 1 / 0 |
| Delivered response payload | 534 bytes |
| Completed / incomplete / unmeasured windows | 0 / 1 / 20 |
| Normalized elements / validated occurrences / extract bytes | 0 / 0 / 0 |
| Retained output files / bytes | 11 / 19,429 |
| Worker exit / OOM kill | 2 / false |

The [independent audit](audit.json) reconciles every delivered byte/hash, attempt, empty normalized prefix and all 21 stopped-window outcomes. `captureComplete` is false; no source or model admission. The [driver stop](driver-stop.json) confirms retained state and no hard-stop partial-counter warning. All query/node-closure, schema, speed/access, physical-identity and completeness capabilities remain untested because no data POST occurred.

Capture elapsed was **0.588102 seconds**, from worker capture setup through status I/O/checkpoints to the stopped-state snapshot. It excludes the subsequent audit and host/Docker startup/teardown; it is neither graph-search nor application latency. No host end-to-end or peak-memory measurement is claimed. Payload counts exclude headers/TCP/TLS/kernel buffering.

[Resource guards](resource-guards.json) and [container result](container-result.json) record 1 GiB memory/zero swap, bridge networking, a read-only root and the one-hour watchdog. The worker was not OOM-killed. [Cleanup](cleanup.json) records removal; a later read-only Docker inspection independently returned “No such container” for that owned ID. Source restrictions were code-level HTTPS host/path/form checks, not an OS hostname firewall. Output bytes plus the 64 MiB tmp reserve remain below the 2 GiB cap.

## Decision and next task

**Close this public-endpoint recipe with the failure intact.** Do not resume, overwrite, retry, use unused allowance, rotate endpoints or change windows/snapshot/caps to obtain a passing result. This single availability failure does not prove a permanent Overpass limitation.

Next perform a primary-documentation/metadata design for **one deterministic bounded bulk/native OSM input**, or record no-go if no documented approach can meet the unchanged snapshot, 21 windows and original envelope. No new acquisition, tool binary, downloader, service setup or adapter/matcher is part of that design task. [Exact design scope and acceptance criteria](next-input-design-plan.json).

The original all-21-complete-window, 50% unique plausible usable-limit Census-km and independent match-review gates remain, followed by every 83/35 accuracy, physical/source/shore/transfer/path, package/memory/startup/API/visual gate. Native tags still require a separately specified lossless source adapter/parser/matching step. Public Overpass is not the app backend or a national scraping plan; eventual Vercel queries continue to use compiled static costs.

No implementation/dependency/app/UI/env/DB/config or deployment change occurred. The preceding 28 host/Linux fixtures, resource probes and check/typecheck/build remain valid for unchanged code; no completed producer or test suite was rerun for documentation. All previous caches/failures, 2.827 baseline provisional eligible km, consumed 48/6/29 provider budgets and deployed v9 stay unchanged. Work remains local/uncommitted.

Read-only recovery; the second command additionally verifies ignored old assets/tools and the complete stopped output:

```sh
python3 -B docs/evidence/coarse-osm-pilot-run-2026-10-26/verify.py
python3 -B docs/evidence/coarse-osm-pilot-run-2026-10-26/verify.py --local-assets
```

[Handoff](../../agent-handoff.md), [ordered next task](../../next-steps.md), [commands and historical run](../../local-development.md#native-osm-capture-controls).
