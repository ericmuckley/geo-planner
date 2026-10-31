# Native delta index: synthetic correctness passes after cache correction

The native C ABI payload codec and lossless block/delta index pass **all46 actual offline Linux controls**, including independent two-pass output/audit checks and a deterministic unchanged-metadata corruption regression. On20,000 consecutive synthetic IDs, the complete new index is**181,044 bytes versus320,252** for the fixed-width predecessor (**43.468%smaller**), with exact coordinate/query/output agreement. **No real road sample or performance benchmark ran.** The C++ metadata validator/projector and streaming index IO remain unimplemented; the live v9 app is unchanged.

[Controls](raw/controls/controls.json), [actual test log](raw/controls/worker.log), [measured synthetic result](raw/controls/result.json), [host summary](raw/run-summary.json), [closed roster](closed-output.json).

## Implemented component and exact scope

The unchanged compiled [C++ payload codec](../../../scripts/coarse_osm_delta_v1.cpp) exports bounded encode/decode operations behind a versioned C ABI. It checks positive signed63 IDs/order, shortest positive LEB128 deltas≤9bytes, lengths/buffer capacities/nulls/overflow, exact signedXY32 values/range and payload closure. The independent Python codec supplies a byte/value oracle. SHA256, headers/catalogs/file IO/cache and source metadata validation remain Python. C++ objects/CPython objects do not cross the ABI.

[Original storage core](../../../scripts/coarse_osm_delta_v1.py), [V2 reader/index correction](../../../scripts/coarse_osm_delta_v2.py), [two-pass integration](../../../scripts/coarse_osm_delta_extract_v2.py), [controls](../../../scripts/coarse_osm_delta_v2_test.py), [offline runner](../../../scripts/run_osm_delta_v2.py). The V1 extractor/kernel and its code/results are also frozen. The new integration reuses unchanged reference validation/selection and the separately source-built audit; it does not move validation into C++.

The [frozen byte layout](../coarse-osm-delta-2026-10-27/format-spec.json) has4096rows/block,64-byte block headers,32-byte directory entries,128-byte shard/directory headers, up to512blocks/shard, exact XY32 and checked positive-ID LEB128. Default shard capacity512; small synthetic rotation cases use capacity1 without exceeding object budgets. Maximum block/shard sizes are69,687/35,679,872bytes. Headers, lengths/offsets, ordering/counts, flags/reserved fields, hashes and catalog identity reject corruption. Fixed shard filenames never come from untrusted path strings.

A newly built audit shard must match the primary descriptor/full SHA, and all primary block data are verified before its exact owned removal. Independently built final catalogs and source/output/geometry/membership must agree. A mismatch preserves failed partial output and never promotes it. Batched lookup preserves order/duplicates and rejects missing IDs.64 cached packed ID64/XY32 blocks occupy≤4MiB payload, plus array/object/directory/query/transient overhead separately.

## Preserved V1 failure and narrow V2 correction

The first frozen run compiles the payload codec and passes43/44 Linux controls, but one cache-drift control fails. A rapid overwrite can leave identical file metadata on Linux, even when comparing nanosecond fields; an unchanged-stat check cannot authorize cached data. V1 is closed/stopped, unmodified and unqualified. [V1 report/proof](../coarse-osm-delta-2026-10-27/README.md).

V2 reuses that exact201,016-byte artifact, SHA256 **`efe338cabf78035b93b936afb623741162e376df8451e5fede8590bbf724dc23`**, without recompiling or changing payload bytes/layout/validators/caps. Before each lookup batch it verifies catalogs and a full SHA256/size for every queried shard, then consumes an authenticated immutable byte snapshot. Cache hits save decoding only; they never bypass shard authentication. One shard snapshot at a time keeps transient data bounded. The new regression forces unchanged metadata: frozen V1 accepts cached data after tampering, V2 rejects it by checksum. [Correction contract](lookup-correction.json).

Full-shard hashing per batch is a correctness tradeoff, **not a lookup-speed result**. First-use format validation has an additional bounded full-shard read; later queries still read/hash their queried shards. Future native IO/lookup optimization needs equivalent drift controls and a separately frozen benchmark; no timestamp-only shortcut is admitted.

## Frozen execution and measurements

| Item | Result |
| --- | --- |
| Host controls |44 pass/two native-only skips,46 total |
| Actual Linux controls |46 pass/zero skips:27 retained+19 new |
| Frozen compiled artifact |201,016bytes; GCC14.2.1/AArch64, libm/libc only, no GLIBCXX requirement |
| Synthetic ordinary IDs |20,000; new181,044/fixed320,252bytes,43.468%smaller |
| Integration |Two-pass18 visits/four-pass36 visits; identical retained canonical output/geometry/window membership |
| Output SHA256 | `dd2315bf022fa0ebe4ac7db1fee38329d40fb5c87f2e236577627d73730d875c` |
| Bounded wrapper rows |73,663encode/96,967decode,422calls, below2million aggregate cap |
| Counter scope |Includes refused decode calls through the wrapper; direct fixed raw ABI negatives and legacy controls are separate |
| Target max RSS |46,432KiB for this synthetic worker process, not whole cgroup/national/cloud peak |
| Worker/client |Exit0/not OOM, owned removal and independent exact-ID absence pass |
| Host elapsed |23.114546s includes input hashes/controls/synthetic proofs/cleanup, not index/decode/search time |
| Closed V2 output |30files/626,105bytes; all mirrored unchanged |
| Network/recompile/source/sample |0requests/no recompile/0real source or saved sample reads |

[Independent cleanup](cleanup-audit.json), [resource guards](raw/controls/resource-guards.json), [actual isolation](raw/controls/container-initial.json), [synthetic indices](raw/controls/delta-index/index.json), [same reference output](raw/controls/four-pass/elements.jsonl).

[Plan](execution-plan.json) SHA256 **`08a033d5d00f9ebae6d6464f346a882462eeef5f9ed7665fc77c90bd0f74913e`**,263host/251worker bindings; [freeze](freeze.json) predates this run. V1 recipe/code/records, failed control and compiled artifact stay unchanged. V2 uses new wrappers/tests/runner/output, not replay or alteration of the stopped producer. [Used command](commands.json) is historical and must never be a health check.

Actual cached runtime/site/Expat only, read-only root/inputs, networking none/no added capability/no pull,4GiB zero-swap/two CPUs/64PIDs/256MiB tmp/64MiB file limit. Owned writable+tmp≤1GiB,32MiB per synthetic index,2million wrapped codec rows,300s worker/600s host/570s work plus cleanup reserve. Encoded payload batches≤4096rows and query batches≤65,536 IDs. No extra compiler image/store, package install or environment change. All previous checks/source/index/tool/negative evidence remain preserved.

## Proof and remaining work

Safe saved proof, standard library only, no Docker/network/compile/native/PBF or producer replay:

```sh
python3 -B docs/evidence/coarse-osm-delta-v2-2026-10-27/verify.py
python3 -B docs/evidence/coarse-osm-delta-v2-2026-10-27/verify.py --local-assets
```

The default proof hashes every mirrored record and independently compares all20,000 on-disk delta coordinates with fixed-width rows using the Python oracle, including float bits and full record/output hashes. Local mode also checks closed raw assets/reused artifact through the parent chain.248 cumulative implementation producers/48 prior sealed runs are bound. New source/evidence/docs remain local/uncommitted; ignored binaries/tool assets are absent from a fresh HEAD clone.

**Next:** implement the full native metadata validator/projector and bounded streaming index path while retaining every [source guard](../coarse-osm-native-design-2026-10-27/guard-map.json), canonical-boundary fallback, independently rebuilt audit and exact coordinate/output identity. Freeze synthetic compiled equivalence controls first. This index component does not establish UTF-8/calendar/tag/copy/canonical-cap/callback/semantic-seal equivalence for a native validator. Python currently supplies those source checks.

No real prefix/mixed sample or lookup/timing benchmark before the remaining guards and a separate exact sample freeze. The≤0.070s/64k target, full maximum-ID/storage/time screen, national extraction, source attributes/matcher and all physical/83ORS-35Valhalla accuracy/package/startup/API/visual/model gates remain held. No new origin/route/region exception, app/UI/env/Postgres/npm/Vercel/commit/push/deploy change. V9 stays active. [Next task](../../next-steps.md), [handoff](../../agent-handoff.md).
