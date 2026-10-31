# Capped timing-input importer and stopped pilot — October 25, 2026

**The importer is implemented and tested; the first pilot stopped on a source timeout.** It received **123,155,489 bytes in 1,115 attempted GETs** and retained **55,120 unique road records**. The zero-retry rule was honored. All **21 windows remain unmeasured/incomplete**; coverage, matching and independent match review were not reached. No timing policy, candidate or production change is qualified.

The [exact execution recipe](execution-plan.json), SHA `0f8c66eabacbef0fb9ad2db666441c3820b3e03a35e92984f6b06255d2641a0d`, froze after offline tests and hard-resource proof, before public requests. It implements the prior [bounded proposal](../coarse-timing-design-2026-10-25/data-input-proposal.json). The work remains local/uncommitted at HEAD `648c731`. Deployed v9, all earlier producers/decisions, env/DB/config/dependencies and provider budgets stay unchanged.

## Implemented controls

[Transport/limits/driver](../../../scripts/coarse_timing_input.py), [Parquet/scoping/weighted matching](../../../scripts/coarse_timing_parquet.py), [22 synthetic tests](../../../scripts/coarse_timing_input_test.py).

All HTTP access passes a byte/request meter with a fixed host allowlist, identity encoding, no credentials/proxy inheritance, no redirects followed and no retries. Tool metadata/wheels, publisher listings, footers and column ranges share the same 512 MiB cap. Strong object ETags, exact Content-Range, declared/actual lengths and response status are checked before returning range data. An actual seekable file boundary feeds the pinned Parquet engine; no native remote filesystem/dataset API is used. Partial extracts are flushed as records arrive, and received bodies/checksums—including failed/empty bodies—are retained.

Speed rules preserve missing, malformed, partial, variable, conditional, directional and conflicting cases. Units are explicit; only compatible whole-span static ordinary-car rules in both directions count as usable. Access restrictions stay separate and conservative. Geometry clipping retains original Census cumulative-km weights; disconnected WKB parts never gain joining lines. Multiple plausible roads stay ambiguous. Matching and review selection are implemented/tested but were **not executed on this stopped live capture**.

The macOS host rejected the attempted address-space/RSS limit settings. A previously cached Linux Python image provides the hard cgroup boundary; no image was downloaded. [Network-free resource probe](resource-proof.json) proves that a 64 MiB cgroup kills an over-limit child, and that the actual 1 GiB limit has zero swap. An independent watchdog and host timeout enforce time limits. The worker has a read-only root/code/inputs, a bounded temporary filesystem and a budgeted output directory; it receives neither the whole workspace nor credential directories. This is an offline-tool control, not application/cloud memory or performance qualification.

Both host and network-disabled Linux runs pass **22 tests**. They cover body/tool/request/time/storage caps, partial-file preservation, failed-response checksums, ignored ranges, changed identities, truncation, redirect behavior, publisher listings, speed-rule scopes and source-weighted clipping/ambiguous matching. Biome checks 197 files; app typecheck and ordinary build pass. [Kernel proof](resource-proof.txt), [Linux tests](linux-tests-final.txt), [host tests](unit-tests.txt).

## Actual source attempt

The planned primary manifest method uses Azure's listing API at the already-proposed release prefix; this was frozen before the request, not selected after a failure. It produced **128 pinned object identities** for release `2026-10-21.0`. The exact PyArrow 21.0.0 wheel was downloaded under the shared byte cap, SHA/size locked and extracted only into the ignored working directory. The real in-memory Parquet/range and bbox-stat selftests passed before publisher file reads.

| Measured item | Result |
| --- | ---: |
| Total received HTTP body bytes | 123,155,489 (117.45 MiB), below 512 MiB |
| Included tool metadata/wheel bytes | 41,148,539, below 128 MiB |
| Attempted HTTP GETs | 1,115, below 10,000 |
| Retained unique road rows | 55,120, below 250,000 |
| Retained JSONL bytes | 65,157,173, below 128 MiB |
| Working-file bytes after stop | 362,386,111 |
| Working-file bound including maximum temporary filesystem | 429,494,975, below 2 GiB |
| Last worker elapsed scope | 320.005 s, below one hour |
| Completed windows | **0 of 21** |

The final attempted ranged read timed out **before an HTTP status or body was returned** (`URLError`, `timed out`). The worker stopped at publisher object index four (zero-based), retained the failure and marked every planned window `unmeasured_after_stop`. It did not retry, switch sources/releases, grow a budget or use the partial cache to claim feasibility. The worker exited with code two; it was not OOM-killed. Its owned container was removed. [Final raw state](state.json), [container result](container-result.json), [capture status](capture.txt).

This result establishes source reachability, schema/reader operation and partial data capture. It does **not** establish usable speed-limit coverage, globally unique road matches or the 50% gate. Bbox candidate counts in the audit only describe retained records; incomplete source data can omit competing roads and change apparent uniqueness.

## Independent audit and preservation

The separately [frozen audit](analysis-plan.json) verifies every received-body checksum/count, all 55,120 retained identities and bbox predicates, object/tool locks, extract/storage limits, kernel settings, stop state and all 21 window statuses. [Audit source](audit.py), [results](analysis.json). Live response headers were validated by frozen capture code but were not separately retained for header replay; a later collector should record complete range/identity receipts. No new feature matching or source request occurred during this audit.

Ignored `data/coarse-quality/overture-timing-pilot-v1/` preserves the raw response bodies, partial `segments.jsonl`, isolated tool, object/tool/schema locks, live-state final checkpoint and container/driver results. Do not resume or rerun this producer, overwrite its evidence or install its tool into the app. Small metadata/stop records are copied here; large road data, binaries and raw range bodies remain ignored and excluded from Vercel. Source/license/version/scoped properties remain in the raw extract.

## Next action

Use the preserved cache **offline**, under the same network-disabled Linux guard. The [recovery specification](recovery-plan.json) requires a separately frozen analysis of observed attribute availability and provisional cached alignments, preserving every incomplete window. A single candidate in this partial cache is not globally unique and is not a lower bound on eventual usable-match coverage. Original feasibility stays unqualified.

That offline task must make one concrete input decision. Any later acquisition/recovery proposal needs exact missing ranges/object identities, cache reuse, explicit retry rules and resource accounting before new requests. The unused **413,715,423-byte** allowance is not permission to resume the stopped run. No extra routing-provider budget exists, and no timing candidate is authorized by this result. All original model/physical/software/package/startup/visual gates remain.

Read-only recovery:

```sh
python3 -B docs/evidence/coarse-timing-pilot-2026-10-25/verify.py
python3 -B docs/evidence/coarse-timing-pilot-2026-10-25/verify.py --local-assets
```

[Exact completed commands](../../local-development.md#capped-timing-input-importer), [current task](../../next-steps.md).
