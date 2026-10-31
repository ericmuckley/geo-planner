# Offline OSM controls implemented — October 26, 2026

**Thirty-nine synthetic tests pass on both host and network-disabled Linux.** Generic extraction, independent reconstruction, bounded transport, dependency-lock/ZIP validation and isolated metadata setup are implemented. Check/typecheck/build and actual safe Linux/SQLite probes pass. No live metadata, wheel, PBF, provider or app DB request occurred. The app remains v9. [Readiness](readiness.json), [control scopes](controls.json).

This completes the [preceding implementation scope](../coarse-osm-offline-plan-2026-10-26/next-implementation-plan.json), with actual Pyosmium compatibility explicitly pending. A **metadata-only** recipe is frozen next, not a tool-binary or national-data run. No larger data limit or publisher snapshot is activated.

## Implementation and proof

- [Extractor and capped coordinate index](../../../scripts/coarse_osm_bulk.py): primary index/segment selection, second-pass native records/full outside-node closure, native/heap/output/occurrence/upstream/storage/time guards and retained failures.
- [Separate audit](../../../scripts/coarse_osm_bulk_audit.py): a second index with separate SQL insertion/lookup, clipping, membership and native reconstruction. It reads the input stream, not primary matches, and checks normalized bytes/counts/node-dependent identities after four complete scans.
- [PBF framing and optional native projection](../../../scripts/coarse_osm_bulk_pbf.py): bounded protobuf/zlib framing, required features/state/precision/EOF/source identity, copied views with duplicate-tag/subsecond rejection. Actual Pyosmium is not installed; projection tests inject native iterators/views.
- [Transport and tool validation](../../../scripts/coarse_osm_bulk_transport.py): direct verified TLS, exact request order, absolute/idle/global deadlines, framing/hash/exact/kind/aggregate/storage limits, bounded spooling and failed cleanup; compatible dependency closure from immutable-image pip-vendored packaging and archive integrity/path/type/byte checks.
- [Owned metadata-only launcher](../../../scripts/prepare_osm_bulk.py): pre-I/O source/recipe hashes, individual read-only mounts, no env/credentials/pull, bounded worker/host time and inspect/removal/failure reporting. Only metadata lock setup is enabled.
- [39 fixtures](../../../scripts/coarse_osm_bulk_test.py), [safe resource probe](../../../scripts/coarse_osm_bulk_resource_probe.py), [host results](unit-tests.txt), [Linux results](linux-tests.txt).

Fixtures cover inclusive no-inside-node/touching/overlap/empty selections, retained raw conditions/private access/restrictions/external roles, typed collisions and changed-node dependencies, missing nodes/source order/state/precision/EOF/framing/bombs, expired views, selected/native/heap/upstream/output/SQLite caps and retained normalized prefixes. Separate clipping and SQL tests detect deliberately broken primary selection/lookups. Transport tests include refusals/redirects/certificate errors/partial bodies/sentinels/hash drift/deadlines/proxy isolation. Lock/ZIP and mocked OOM-driver tests cover incomplete/changed closure, malformed paths/hooks/symlinks, unbound recipes and owned cleanup.

One development test initially used a 500-byte cap larger than its fixture records, so its expected-stop assertion failed. The corrected fixture derives a cap that admits native records and rejects normalized wrapper overhead. [Original failure](development-cap-test-failure.txt) remains intact. Earlier passing development Linux/probe outputs remain separately named; current results above use final code. The duplicate-ZIP warning is an intentional unsafe-archive fixture.

The [actual network-free resource probe](resource-proof.json) verifies **1 GiB/zero swap/64 MiB tmp**, kernel kill of an over-limit child, independent watchdog kill of a stalled child, absolute timer interruption and a real **16,384-byte SQLite page cap** stopping writes. Error log is empty. This qualifies safe metadata/control probes, **not the proposed 4 GiB national workload**, actual decoder, peak memory, source coverage or completion time. Biome checks 197 files; typecheck/build pass.

Shared low-level native validation/time/hash/ordered-counter/SQLite-configuration/optional-decoder primitives are explicit. Reconstruction is independent of primary selection/native output, not an independent road survey. Native speed/access interpretation, publisher-boundary/global completeness and every original feasibility/model gate stay unqualified.

HTTP bytes mean payload delivered by `read1`/`IncompleteRead.partial`, including late/error/sentinel bytes, excluding headers/TCP/TLS/kernel buffering. Native/JSON/heap admission checks follow bounded frame/view projection; cgroups remain the hard memory guard. Read-only raw/tool reservations count against working storage. Decoder failure before a native yield can leave raw-object counts unknown. Every stop retains indexes/prefixes/window outcomes untrusted; hard stops can leave last counters partial. No resume or fallback.

## Next: one frozen metadata-only setup

Recipe **`1f802ec11e3491a375ca80327a9968a482bd1db6a0d162448c793842400a1fa2`** binds **12 host inputs / 7 worker files**. [Exact recipe](metadata-plan.json). It permits only five ordered GETs for PyPI dependency catalogues, seeded by the already captured Pyosmium metadata. Cap **16 MiB delivered bodies**, each at most 2 MiB plus one sentinel, **zero wheel/PBF bytes**, five minutes, 1 GiB/zero swap, 512 MiB work and 64 MiB tmp. No retry, redirect, source endpoint, paid/provider/DB use or automatic install. Bridge host/path restrictions are code-level, not an OS hostname firewall.

Read-only recovery:

```sh
python3 -B docs/evidence/coarse-osm-offline-controls-2026-10-26/verify.py
python3 -B docs/evidence/coarse-osm-offline-controls-2026-10-26/verify.py --local-assets
```

Future single metadata command, **not executed in this checkpoint**:

```sh
python3 -B scripts/prepare_osm_bulk.py docs/evidence/coarse-osm-offline-controls-2026-10-26/metadata-plan.json 1f802ec11e3491a375ca80327a9968a482bd1db6a0d162448c793842400a1fa2 data/coarse-quality/us-osm-tool-lock-v2
```

New output is absent. Accept only a complete compatible exact dependency lock, reconciled metadata ledgers, successful worker/resource/cleanup and preserved raw catalogues. Any refusal/drift/overflow/closure error stops and preserves all attempted/remaining outcomes; no overwrite/resume/retry or automatic binary download. Frozen inputs include captured metadata, not road caches/graph arrays/secrets.

After lock review, a separately specified tool-only setup must verify binary hashes/install bounds and actual ABI/tiny-PBF/malformed decoder behavior with networking disabled. Only then freeze an exact national-data recipe. The old [12 GiB/64 GiB/4 GiB/four-hour/publisher-state proposal](../coarse-osm-offline-plan-2026-10-26/README.md) remains proposed; no data run is enabled here. Same 21 boxes/denominators and all source/50% usable-limit/independent match/83-35 accuracy/physical/package/startup/API/visual gates remain required. Vercel still serves compact compiled costs.

All work is local/uncommitted; no app/UI/env/DB/npm/deployment change or old producer replay. Both stopped captures, all old assets/failures, 2.827 baseline provisional eligible km and consumed 48/6/29 provider budgets remain. [Handoff](../../agent-handoff.md), [next scope](../../next-steps.md), [commands](../../local-development.md#offline-osm-controls-and-metadata-setup).
