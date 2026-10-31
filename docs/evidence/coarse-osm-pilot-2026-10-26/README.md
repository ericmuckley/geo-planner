# Native OSM capture controls — October 26, 2026

**Implemented and verified with 28 synthetic tests on both host and Linux; live capture has not run.** This completes the [selected acquisition design's implementation stage](../coarse-input-redesign-2026-10-26/README.md). The reader captures native objects and metadata without interpreting speed/access tags, running a matcher or changing the application.

The [executable recipe](execution-plan.json), SHA `c8dd8d24f91a9fa679cd22ebd48bc06d38728a3605b8c29494c29d1d6e53fd48`, freezes **41 inputs / 29 worker files / 21 queries** after tests and resource proofs. [Exact controls](controls.json), [readiness](readiness.json). No response, source availability/completeness, attribute coverage, capture timing/output or peak-memory result exists yet.

## Implementation

- [Capture budget, direct HTTPS meter and window ledger](../../../scripts/coarse_osm_input.py).
- [Native fields, counts, selected-way node closure and identity](../../../scripts/coarse_osm_records.py).
- [Independent raw-body/count/closure/identity/prefix audit](../../../scripts/coarse_osm_audit.py).
- [Hash-bound isolated launcher](../../../scripts/run_osm_capture.py).
- [Synthetic fixtures](../../../scripts/coarse_osm_input_test.py) and [explicit Linux resource probe](../../../scripts/coarse_osm_resource_probe.py).

The request contract remains unchanged: snapshot `2026-10-21T00:00:00Z`, original 21 bboxes/order/QL/form hashes, one status GET and at most one POST per window. Direct standard-library HTTPS uses only the fixed host/status/interpreter paths; no proxy/cookie/auth handler, redirect, polling, retry, mirror rotation, repair query, tool download or paid fallback.

The meter journals an attempt before I/O and spools received chunks before semantic validation. It retains bounded error/redirect/partial bodies, rejects oversized declared bodies before reading and retains exactly the one-byte sentinel for streamed oversize detection. Bytes mean payload returned by `read1` or `IncompleteRead.partial`, including late/error bytes; headers, TCP/TLS and kernel buffering are not counted as metered payload. POSIX alarms and monotonic checks apply through connection, headers, body and normal close. An independent process watchdog and host container timeout cover the global interval.

Native validation requires strict JSON, no duplicate/nonfinite keys/values, the fixed snapshot, generator consistency, per-type/total terminal counts and every selected way's referenced node. It retains outside-bbox nodes for crossing ways and checks selected geometry intersects the original box, including boundary touches. Typed IDs can collide across node/way/relation namespaces. A way's dependency hash includes ordered node records/versions/coordinates; way version alone cannot identify geometry. Raw tags and external restriction-member references remain intact without granting permission. Empty valid query output is distinct from missing/failed data and proves no real-world road absence.

Normalization limits are acceptance/commit gates after a bounded response is decoded. A rejected response may contain more logical elements than the limit; its raw body remains preserved. The validated-occurrence counter can therefore exceed its limit in a **stopped** attempt, while retained normalized output never exceeds its admission limits. Malformed responses have unknown logical counts. No failed window or counter is silently truncated/reset to claim completeness.

The audit independently reconstructs native fields/counts/closure/dependencies, complete normalized prefixes, raw file hashes, inventories, status waits, deadlines and ledger totals. It does not call the primary batch/normalizer. JSON/time/hash primitives are shared explicitly. Soft failures retain an auditable prefix and every remaining window outcome. Hard kill/OOM/audit failure preserves the last state and flags possibly partial counters; the driver admits nothing. This is no usable-limit, independent physical-road or driving-permission review.

## Validation and limits

**Twenty-eight tests pass on host and network-disabled Linux.** They cover complete/empty/overlapping/crossing results, raw conditional/directional/access metadata, typed-ID collisions, missing nodes, changed node geometry under an unchanged way version, duplicate conflicts, final-count/schema/snapshot/generator failures, HTTP refusals/redirects/compression/framing, partial bodies, exact/sentinel bounds, status waits, connection/read/cleanup deadlines, storage/row/extract/occurrence caps, reuse/path refusal and independent tamper detection. [Host results](unit-tests.txt), [Linux results](linux-tests.txt).

The [network-free Linux probe](resource-proof.json) verifies actual **1 GiB / zero swap / 64 MiB tmpfs**, a kernel-killed over-limit child, an independently watchdog-killed stalled child and a POSIX timer interrupting a blocking call. No application/model peak-memory or latency claim. The probe error log is empty. Biome checks 197 files; typecheck and ordinary build pass. No new dependency or app/environment/database change.

Future limits remain <=42 HTTP attempts, <=512 MiB total delivered payload, accepted data/status bodies <=16 MiB/64 KiB plus one metered sentinel each, <=353,697,834 maximum planned body reads, <=250,000 unique normalized typed elements/500,000 validated occurrences, <=128 MiB normalized extract, 2 GiB working files, one hour and 64 MiB tmp. Disk accounting reserves temporary/driver/state space. Server declarations of 60 seconds/256 MiB RAM do not replace client guards.

Synthetic containers used network=none, cached image/no pull, `--init`, read-only scripts/design inputs/root and no real road-data/env/credential mount. The **future capture** uses a bridge namespace with frozen direct-HTTPS host/path/form restrictions in code; this is not an OS hostname firewall. Only individual bound code/input files are mounted. Resource controls, source hashes and owned-container inspection/removal are checked before/after execution. No live use of that path occurred here.

## Next single capture

Read-only readiness first:

```sh
python3 -B docs/evidence/coarse-osm-pilot-2026-10-26/verify.py
python3 -B docs/evidence/coarse-osm-pilot-2026-10-26/verify.py --local-assets
```

Future live command, **not executed in this checkpoint**:

```sh
python3 -B scripts/coarse_osm_input.py data/coarse-quality/osm-timing-pilot-v1 c8dd8d24f91a9fa679cd22ebd48bc06d38728a3605b8c29494c29d1d6e53fd48
```

The new output is absent at this checkpoint. Run once; preserve every refusal/cap/error/partial response, normalized prefix, full window ledger and audit/state/container/failure/cleanup record. No resume, overwrite, alternate endpoint/query/window/snapshot, raised cap or automatic fallback. Success requires all 21 `capture_complete` windows and independent `captureComplete: true`, with state `captured_all_windows_analysis_pending`. That is source-query/node closure only, not complete real-world roads, all relation dependencies or a routable graph.

A separate lossless native-source adapter/parser/matching freeze, original complete-window/50% unique plausible usable-limit Census-km screen, deterministic independent match review and every 83/35 accuracy/physical/package/startup/API/visual gate remain. No Overture parser is applied to native OSM, no source policy is relaxed and no timing candidate is admitted. Public Overpass remains a finite offline pilot source, not the app backend or a national scraping plan.

This work remains local/uncommitted. **Zero actual road/status/interpreter/tool/provider requests, new matcher runs or deployments.** All old source/cache/matcher/failure assets and 2.827 baseline provisional eligible km stay unchanged; deployed v9/grid/UI/env/DB/npm and consumed 48/6/29 routing-provider budgets remain. [Recovery and commands](../../local-development.md#native-osm-capture-controls), [ordered task](../../next-steps.md).
