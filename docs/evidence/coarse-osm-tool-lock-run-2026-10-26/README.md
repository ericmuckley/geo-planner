# Dependency metadata stop and v3 correction — October 26, 2026

**The one frozen v2 setup stopped on its second GET, before reading an oversized catalogue. No dependency lock or binary/data download resulted.** Two requests delivered **192,973 metadata body bytes**: Requests completed, then `charset-normalizer` declared **2,390,209 bytes**, above the frozen **2,097,152-byte** response cap by **293,057 bytes**. Its body was not read; the last three catalogues remain unmeasured. [Raw ledger](http/http-ledger.json), [state](setup-state.json), [summary](run-summary.json), [stopped accounting audit](audit.json).

The unchanged [v2 recipe](../coarse-osm-offline-controls-2026-10-26/metadata-plan.json), SHA `1f802ec11e3491a375ca80327a9968a482bd1db6a0d162448c793842400a1fa2`, ran once at ignored `data/coarse-quality/us-osm-tool-lock-v2/`. All eleven files/**200,572 bytes** are preserved here and at that original location. No retry, resume, endpoint change, cap increase or unused-allowance transfer occurred in that run.

## Measured result

Requests metadata identifies **Requests 2.34.2** and its runtime dependencies. That complete [192,973-byte response](http/001.bin) has SHA256 `bcfc6a202592e4e90f5a28ff002694eaa7c58ba741b76077f432b8bee1480111`. The empty [second body](http/002.bin) is distinct from an empty successful catalogue. Header-only evidence establishes declared size; it does not establish the unfetched catalogue's version, schema or compatibility.

The independent stopped accounting proof reconciles both raw hashes/lengths, the exact request prefix, declared oversize rejection and all five complete/failed/unmeasured outcomes. Full dependency closure remains false. Worker exits **2**, not OOM; [actual guards](resource-guards.json) and [container result](container-result.json) record 1 GiB/zero swap, bridge network and read-only root. [Driver stop](driver-stop.json) confirms retained state with no hard-stop partial-counter warning. [Cleanup](cleanup.json) records removal; a later Docker inspection independently returned no such container for that owned ID.

Meter elapsed **0.120135 seconds** includes setup/two requests/spooling/checkpoints and the first JSON parse through the final ledger snapshot. It excludes later setup-state writing and host/Docker startup/cleanup. This is neither routing time nor app latency; peak memory/end-to-end time were not measured. Body counts exclude headers/TCP/TLS/kernel buffering.

## Separately versioned correction, not executed

The project-wide catalogue includes release history, so the earlier 2 MiB assumption was too small. Preserve that failure and use a fresh **v3** recipe/output. Reuse the complete SHA-bound Requests response with captured Pyosmium metadata, reducing future live GETs from five to **four**. Each remaining catalogue gets a uniform **3 MiB plus one sentinel** limit; total **16 MiB**, five minutes, 1 GiB/zero swap, 512 MiB working/64 MiB tmp and zero wheel/PBF/provider/app DB access remain unchanged. Maximum planned body reads are **12,582,916 bytes**, below the total cap. No larger national-input limit or snapshot is activated.

New [v3 launcher](../../../scripts/prepare_osm_lock_v3.py) and [six focused fixtures](../../../scripts/coarse_osm_lock_v3_test.py) preserve all sealed v2 sources. The launcher shares the frozen direct meter/dependency solver; its isolated entry point and resource policy follow the existing bounded launcher. Fixtures pass on [host](v3-unit-tests.txt) and [network-disabled Linux](v3-linux-tests.txt), covering a catalogue above the old cap/below the new one, hard oversize refusal, four-request order, saved-seed identity, closed compatibility and failure/reuse behavior. Check/typecheck/build pass. Prior 39-fixture/kernel/SQLite proofs remain bound to unchanged shared controls. [Correction readiness](correction-readiness.json), [decision](decision.json).

Recipe **`bd5bb8358cbbe41005f762578de83aae8ad34b8549008efd7b772da1a3b69044`** freezes **15 host inputs / 8 worker files**. [Exact v3 recipe](metadata-v3-plan.json). New ignored `data/coarse-quality/us-osm-tool-lock-v3/` is absent. This checkpoint makes **zero live requests for v3** and downloads no tool binary or PBF.

Read-only recovery first:

```sh
python3 -B docs/evidence/coarse-osm-tool-lock-run-2026-10-26/verify.py
python3 -B docs/evidence/coarse-osm-tool-lock-run-2026-10-26/verify.py --local-assets
```

Future single v3 command, **not executed here**:

```sh
python3 -B scripts/prepare_osm_lock_v3.py docs/evidence/coarse-osm-tool-lock-run-2026-10-26/metadata-v3-plan.json bd5bb8358cbbe41005f762578de83aae8ad34b8549008efd7b772da1a3b69044 data/coarse-quality/us-osm-tool-lock-v3
```

Success requires all four catalogues, exact stable compatible <=six-wheel dependency closure, reconciled bodies/attempts/bytes/seed hashes and worker/resource/cleanup. Failure stops/preserves every attempted and remaining outcome without retry, resume, overwrite, fallback or automatic binary install. Larger/unexpected future catalogues may still stop; this is a finite cap, not a size guarantee.

After lock success/review, a separate tool-only binary/native ABI/tiny-PBF/malformed decoder proof remains, then an exact national-data freeze. No source or model admission. All original boxes/denominators/completeness/50% usable-limit/independent match/83-35 accuracy/physical/package/startup/API/visual gates remain. No road/provider/app DB query, timing/matcher policy, runtime/UI/env/DB/npm/Vercel or deployment change. V9 and old stopped source/cache evidence stay intact; new work remains local/uncommitted. [Handoff](../../agent-handoff.md), [next task](../../next-steps.md), [commands](../../local-development.md#metadata-v2-stop-and-v3-correction).
