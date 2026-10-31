# First national-file attempt stopped; monitor corrected separately

October 26, 2026. The one frozen V2 national-file attempt made **one GET**, received HTTP200 and retained **34,603,008 bytes (33MiB)** before the host monitor raised `Special data output`. The driver exited1 and removed its owned worker. No complete source checksum or native extraction; all21 windows remain unqualified. The live V9 app still uses real Census road geometry and its existing coarse travel estimates; this new OSM-input experiment does not change that model.

A separate V3 monitor correction is tested/frozen and its **read-only preflight passes**. It has **not executed a source request**. The failed V2 body/recipe/code are unchanged; no retry, range/resume or fallback occurred in this checkpoint. New research code/evidence/docs remain local/uncommitted; no app/env/database/npm/Vercel change, commit or deployment.

## Measured stop and retained evidence

| Item | Result |
| --- | --- |
| Frozen V2 recipe SHA | `bc57f4e3e82a03201b4964efd0d33c5813a04410e5e048544bd2e7df4a459f14` |
| Source | Dated `us-261025.osm.pbf`, unchanged URL/MD5/header expectation |
| Request /HTTP status | One PBF GET /200 |
| Declared Content-Length | 12,229,320,016 bytes, matches expected size |
| Last journal /retained spool | **34,603,008 /34,603,008 bytes** |
| Prefix SHA256 | `35d5005766e6a2a4e0f76723586b3b232dc0e493055420f0841797c85a12175a` |
| Meter outcome | `started`; unfinished snapshot, no finalized full-body digest |
| Driver | Exit1, `Special data output` |
| Native scans /projected records | Not started /0; raw entity counts unmeasured |
| Windows | All21 `unqualified_after_driver_stop` |
| Retained output | **9 files /34,670,122 bytes** |
| Worker cleanup | Owned removal and separate absence check confirmed |

Ignored `data/coarse-quality/us-osm-input-v2/` is closed. Its [raw journal](v2/download/http/http-ledger.json), [driver failure/all-window outcomes](v2/download/driver-failure.json), [actual memory/tmp guard](v2/download/resource-guards.json), [cleanup](v2/download/cleanup.json), copied recipe/capacity and empty worker log remain intact. Small records are mirrored here; the33MiB body stays ignored. There is no source receipt, extraction phase, final container-result or run-summary. [Execution interpretation](execution-result.json), [independent stop audit](stop-audit.json), [separate cleanup check](cleanup-audit.json).

The journal's `stopped:false` does not mean the job is still running: the host stopped it outside the meter, then forcibly removed the container. Retained bytes and last journal agree, but delivered/wire totals may be partial at a hard stop. No full-source MD5/SHA verification or final worker exit/OOM state was captured before removal. Do not infer exit2/not-OOM or complete transfer from these records. Actual recorded memory4GiB/zero swap and tmp256MiB match the frozen configuration; final workload memory/performance is unmeasured.

The last meter checkpoint is **7.096054s**, an unfinished download interval excluding later host cleanup; no complete driver timing exists. This is not graph-search latency. No metadata/wheel/provider/app-DB request or native road-object scan occurred.

## Actual partial header

A separate bounded read of the first **191 bytes** verifies the OSMHeader in the preserved prefix: required features `OsmSchema-V0.6`/`DenseNodes` and publisher state **`2026-10-25T21:21:21Z`**, matching the recipe. [Header audit](partial-header-audit.json). Frozen protobuf helpers are shared; byte/hash/journal/stop reconstruction is separate. This is evidence about the received header only; the entire file, publisher MD5, all frames/objects and source completeness remain unqualified. No extra request or native scan was needed.

## Diagnosis and separate V3 correction

The V2 monitor calls `is_symlink()`, `is_dir()`, then `is_file()` for each output entry. If an atomic checkpoint replacement removes a path between checks, `is_file()` returns false rather than raising the `FileNotFoundError` caught by the helper. That produces the same `Special data output` error. The offending live path was not recorded, so attribution of this specific stop to that race is an inference supported by the identical deterministic regression and the absence of retained special entries.

New [single-snapshot monitor](../../../scripts/coarse_osm_data_v3.py) uses one `lstat()` per entry, skips a path that vanished before that snapshot, and checks type/size from the same result. It continues to reject symlinks/FIFOs/other special entries; no payload hashing in polling. Source/window/cap/decoder/extraction semantics remain delegated to the frozen V2 data helpers.

New [V3 launcher](../../../scripts/prepare_osm_input_v3.py) uses a fresh output and additionally saves initial container configuration and a pre-removal state snapshot, including on caught failures/keyboard interruption. A pre-removal live state still does not establish final exit/OOM unless a normal final result exists. New [stop auditor](../../../scripts/audit_osm_data_stop.py) reconciles this closed V2 prefix without requests, native scans or producer replay.

**11 new tests pass on macOS and network-disabled Linux**: deterministic old failure, vanish-before/after-snapshot, same-name replacement, concurrent checkpoint updates, real symlink/FIFO rejection, no raw hashing/repeated type queries, unchanged source/windows/caps, initial/pre-removal snapshots, keyboard interruption and labelled-owned recovery after create timeout. [Regression tests](../../../scripts/coarse_osm_data_v3_test.py). Check197/typecheck/build pass, existing warnings unchanged. The original17 controls/native tiny-wrapper/safe4GiB probes remain bound to unchanged shared data semantics; no national throughput or OOM-pressure claim. [Correction checks](correction-checks.json).

## Corrected recipe: checked, not executed

[V3 recipe](correction-plan.json), SHA **`a7155c25e61516c9cd61bb3b32f5bd96e5ef8811c265a93f4b845c69f448857e`**, binds212 host inputs/201 worker files/17 static-file mounts plus the same182-file tools/runtime. It keeps the exact source URL/size/publisher MD5/state, original21 windows, single-GET/12GiB body ceiling,4GiB/zero swap/two CPUs/64PIDs/256MiB tmp/64GiBwork/four-hour execution cap. Only phase/output/monitor/diagnostics change. The old partial body is bound as historical evidence, never mounted as a complete source or resumed. This is an independently bounded future full attempt; no unused V2 allowance transfer or automatic request reissue.

Read-only preflight completed, creating no output/worker/request:

```sh
python3 -B scripts/prepare_osm_input_v3.py docs/evidence/coarse-osm-data-run-2026-10-26/correction-plan.json a7155c25e61516c9cd61bb3b32f5bd96e5ef8811c265a93f4b845c69f448857e data/coarse-quality/us-osm-input-v3 --check
```

**Later fresh attempt, not run here:**

```sh
python3 -B scripts/prepare_osm_input_v3.py docs/evidence/coarse-osm-data-run-2026-10-26/correction-plan.json a7155c25e61516c9cd61bb3b32f5bd96e5ef8811c265a93f4b845c69f448857e data/coarse-quality/us-osm-input-v3
```

[Structured commands](correction-commands.json), [read-only check](correction-readonly-check.json), [current capacity](correction-capacity.json). Capacity remains above declared minimums; it is rechecked before execution and is not reserved. The new output is absent at correction freeze. Preserve old frozen code and every failed file. After the new command runs once, close it too; never use either producer as a health check.

**Next:** one separately versioned V3 full attempt, then read-only outcome reconciliation. Full bytes/MD5/acquisition-framing-final SHA/header/four matching EOF streams/all21 file-complete/audit/resource/time/storage/owned-cleanup criteria are unchanged. Even a pass is acquired-file completeness only: publisher/global completeness,50% usable-limit coverage, independent matching/physical review,83/35 accuracy, packaging/startup/API/visual and model integration remain pending. No source adapter/matcher/ETA/app/UI/env/DB/npm/Vercel/paid/cloud/commit/deploy change; consumed provider48/6/29 budgets unchanged.

Saved proof, no Docker/network/producer replay:

```sh
python3 -B docs/evidence/coarse-osm-data-run-2026-10-26/verify.py
python3 -B docs/evidence/coarse-osm-data-run-2026-10-26/verify.py --local-assets
```
