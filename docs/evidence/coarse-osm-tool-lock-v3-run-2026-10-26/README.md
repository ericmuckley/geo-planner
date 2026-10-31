# Dependency lock completed — October 26, 2026

**The separately frozen v3 metadata setup completes: six exact compatible wheels are locked, totaling 2,387,936 planned archive bytes. No binary has been downloaded or installed.** Four GETs deliver **2,734,589 metadata bytes**; the saved Requests response and captured Pyosmium metadata are reused. [Exact lock](lock.json), [summary](run-summary.json), [raw ledger](http/http-ledger.json), [setup state](setup-state.json).

| Locked package | Version | Planned wheel bytes |
| --- | --- | ---: |
| osmium | 4.3.2 | 1,729,855 |
| requests | 2.34.2 | 73,075 |
| charset-normalizer | 3.5.2 | 244,624 |
| idna | 3.20 | 69,583 |
| urllib3 | 2.8.0 | 135,717 |
| certifi | 2026.10.23 | 135,082 |

These are captured publisher metadata/selected wheel sizes, not installed size, actual transfer or native compatibility proof. Every exact filename/URL/SHA256/dependency/Python/tag/marker binding is retained. No current-version lookup is needed for the next step.

## Execution and reconciliation

One v3 execution uses the unchanged [recipe](../coarse-osm-tool-lock-run-2026-10-26/metadata-v3-plan.json), SHA `bd5bb8358cbbe41005f762578de83aae8ad34b8549008efd7b772da1a3b69044`, at ignored `data/coarse-quality/us-osm-tool-lock-v3/`. All four responses are 200/complete within 3 MiB each and 16 MiB total, with no retry within v3. The earlier [v2 size-stop](../coarse-osm-tool-lock-run-2026-10-26/README.md) stays sealed and closed. Combined across both versions: **six GET attempts / 2,927,562 delivered metadata bytes**, including the separately versioned repeat of the previously unread oversized catalogue. No unused v2 allowance was resumed.

The [read-only audit](lock-audit.json) reconstructs the saved lock from all captured catalogues using the frozen solver and recorded cached-Linux compatibility tags. Raw hashes/lengths/order/attempts/bytes are independently reconciled. This shares the dependency solver and is not an independent resolver, binary/ABI test or source/model proof.

Worker exit **0**, not OOM; [guards](resource-guards.json) and [container result](container-result.json) record 1 GiB/zero swap, read-only root/bridge and the five-minute watchdog. [Cleanup](cleanup.json) records removal; a later read-only inspection independently confirmed the owned container was absent. Thirteen output files/**2,747,308 bytes** remain intact and mirrored here.

Meter elapsed **0.343501 seconds** covers setup/four requests/spool/checkpoints and inter-request JSON parsing through the final ledger snapshot. It excludes final JSON parse/lock construction/state writing and host/Docker startup/cleanup. It is not graph-search/app latency; peak memory and host end-to-end time are unmeasured. Body counters exclude headers/TCP/TLS/kernel buffering.

The correction's six host/Linux fixtures and check/typecheck/build remain bound to unchanged code; prior 39-control/kernel/SQLite proofs remain unchanged. This execution/reconciliation adds no implementation, metadata re-query, binary, PBF, hosted routing, matcher, app DB or deployment. Audit containers had networking disabled; only the owned metadata worker used the fixed bridge allowlist. No credentials/trust/config/npm changes.

## Next: bounded tool-only setup and real native proof

Implement, synthetically verify and freeze one tool-only runner, then perform one exact six-wheel setup/smoke if those controls pass. [Reviewed scope, pins, budgets and acceptance](next-tool-setup-plan.json). Planned limits: **six GETs / 4 MiB bodies**, exact 2,387,936-byte archives, **1 GiB/zero swap / 512 MiB work / 64 MiB tmp / ten minutes**. No metadata lookup, redirect/retry/source build/apt/image pull/paid fallback. All six archive URLs/hashes are already fixed.

Acquisition must preserve every raw/error/partial body and archive hash. Installation/import/ABI/tiny synthetic PBF/real decoder/SQLite/extractor/audit tests run separately with **network=none**, only in a new owned target directory. No global/host/app dependency installation. Bound unpacked validation and installed trees, capture their exact bytes/hashes/versions, and retain every failed attempt without relabeling old injected tests as native proof. Actual SDK incompatibility needs separately versioned code/tests, not relaxed gates or unpinned tools.

The next runner/recipe does not exist yet; new ignored `data/coarse-quality/us-osm-tools-v1/` is absent. Actual Pyosmium ABI/decoder and the national workload remain unqualified. No national road/PBF download belongs in that tool-only stage. Larger data caps/publisher state remain proposed; original 21 boxes/denominators/source completeness/50% usable-limit/independent match/83-35 accuracy/physical/package/startup/API/visual gates remain required. Vercel still serves the same compact v9 graph.

Read-only result proof; local-assets also reconstructs the lock using recorded Linux tags and checks all ignored assets/tools/output rosters:

```sh
python3 -B docs/evidence/coarse-osm-tool-lock-v3-run-2026-10-26/verify.py
python3 -B docs/evidence/coarse-osm-tool-lock-v3-run-2026-10-26/verify.py --local-assets
```

Both v2/v3 runs are now closed; do not replay their commands or fetch more catalogues to validate docs. Work remains local/uncommitted. V9/UI/env/DB/npm/Vercel and consumed provider budgets stay unchanged. [Handoff](../../agent-handoff.md), [next task](../../next-steps.md), [recovery](../../local-development.md#completed-dependency-lock-and-tool-only-next-step).
