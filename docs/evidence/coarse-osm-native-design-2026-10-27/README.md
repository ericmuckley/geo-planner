# Native importer design: build tooling is the next prerequisite

October 27, 2026. A bounded, read-only inspection confirms that the qualified runtime exposes native filters and eight location-index backends, but **none of the 14 named compiler/build/OSM command candidates is on PATH**. No libosmium/protozero/zlib headers were found at the named include paths, and the installed 182-file wheel tree contains no C/C++ headers. This is scoped inspection, not a whole-filesystem absence proof. No road source or saved sample was read, and nothing was compiled or installed. **The deployed v9 app is unchanged.**

The selected design is a **small native validation/index helper loaded by the existing Python worker**, with an exact block/delta-ID coordinate format. Its build environment must first be acquired and qualified separately. This report completes the design/capability task; it does not qualify a native implementation, new benchmark or full import. [Decision](capability-decision.json), [next bounded dependency proposal](dependency-proposal.json), [current task](../../next-steps.md).

## What the cached tools can and cannot establish

The cached image is `sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402`, Linux arm64, Python3.13.5/glibc2.34/zlib1.2.11. `sysconfig` names the compiler used to build Python; that does not mean the compiler is installed. Named gcc/g++/cc/c++/clang/clang++/cmake/make/pkg-config/osmium/osmconvert/osmfilter/rustc/cargo probes all return no PATH match. Python.h exists; the named other headers and optional pybind11/setuptools/wheel/cffi modules do not. [Raw capability result](probe-stdout.json).

`NodeLocationsForWays`, `create_map`, native filters and `IdTracker` are available. They support location caching or selection; the inspected interface does not supply the complete frozen metadata/byte/order/audit contract for discarded nodes. `SimpleHandler`'s location path calls `ignore_errors()`, so it cannot silently replace missing-node rejection. Python callbacks still incur per-node Python work; the installed BufferIterator stub offers no Python buffer-construction interface. This conclusion is based on pinned local source/stubs and API inspection, not on a timed data scan. [Exact source bindings](bindings.json).

The one probe used networking disabled, read-only root/mounts,4 GiB/zero swap/two CPUs/64 PIDs/256 MiB tmp,16 MiB file limit,128 KiB stdout and45 s host bound. Worker/client exit0, not OOM; label/image-checked removal and separate exact-ID absence inspection pass. [Plan](capability-plan.json), [command](command.json), [actual isolation](container-initial.json), [cleanup](cleanup-audit.json). The raw summary's timing field incorrectly says it includes input hashing; the timer actually starts afterward. That record is preserved with a separate [scope correction](timing-scope.json). This is not import throughput or compile qualification.

## One proposed fast path, with the old checks retained

Compile a C++17 PBF-only shared library, exporting a small C ABI to standard-library `ctypes` in the qualified Python worker. No C++ objects or CPython extension ABI cross that boundary. The native loop validates every source object **before** filtering; it builds the coordinate index without ordinary per-node Python objects/JSON. Python receives selected raw records, rare canonical-size boundary cases and bounded byte batches for existing hashlib/checkpoint logic. All work stays in one bounded runtime container.

The [guard map](guard-map.json) specifies identity/order/receipt counters, visibility/time/calendar/precision, exact native coordinates, UTF-8/duplicate raw tags, reference/member/copy quotas, canonical byte limits, source identity/framing/EOF and selected-object/audit/resource controls. None is implemented by this proposal. A native filter is not a substitute for those checks.

One subtle size check needs an exact fallback: count escaped string/integer/syntax bytes natively, use a proven32-byte upper bound per finite node float, and accept only when that bound is safely below the original cap. Ambiguous near-cap nodes go to the frozen Python canonical-size check in a bounded integer-XY frame. Do not approximate float formatting or reject a valid boundary record merely to avoid the fallback. Callback failure must stop. Boundary/Unicode/overflow cases must compare reference outcomes before a sample run.

A length-prefixed binary projected-field seal replaces expensive full-stream JSON hashing for drift detection. It must retain every projected field, sort raw tag keys, preserve ordered references/members and be proven equivalent to fields reconstructed from the frozen reference. **Its hash is not the old canonical JSON hash.** Selected canonical output and geometry hashes must remain byte-identical. Full-field proof mode and fast mode must be measured separately; no same-work speed claim from different output work.

Keep two independently built passes: first-pass primary way/dependency selection; second-pass raw materialization plus independent coordinate/geometry/membership/output reconstruction. Primary IDs are hints only. Omitted/extra roads/nodes/restrictions and unselected metadata drift must still fail. Audit blocks are rebuilt from the source, never copied from primary storage. Old two-pass controls remain the comparison baseline.

## Lossless block storage and the honest resource screen

[Proposed format](format-design.json):4,096 rows/block; first ID64 in a64-byte header, later positive ID differences as canonical unsigned LEB128; exact signed32 XY coordinates. A32-byte directory entry locates each block;512 blocks/shard bound the largest replacement file below36 MB. Batched lookup groups by block, preserves requested order/duplicates and uses a fixed cache. Every checksum, offset, length, reserved flag, integer overflow and missing/duplicate ID must be checked. This is an unimplemented format, not a measured compression result.

For a monotone ID span bounded by `M-1`, the total delta bytes are conservatively bounded by `D + sum(min(D, floor((M-1)/128^k)), k=1..8)`, where `D` excludes block anchors. The [pure calculator](resource_screen.py) adds coordinates, headers, directory, receipts and file-rounding reserve. Twelve generated arithmetic cases and the threshold boundary pass; no dataset is used. [Calculated result](resource-screen.json), [checks](resource-proof.json).

| Screen | Result / status |
| --- | --- |
| Node count | Measured earlier:1,606,229,364 callbacks; source-wide unique/order validity still needs validation |
| Illustrative maximum ID | `2^40-1`; **not measured and not a new accepted-ID ceiling** |
| Index upper bound under that assumption | 16,186,821,824 bytes;24,280,232,736 with1.5× margin<24 GiB |
| Full positive signed63 ID-domain bound | 31,810,867,977 bytes at margin; **fails24 GiB** |
| National maximum ID | **Unknown**; a sample maximum cannot establish it |
| Conditional working bound | 63,189,314,471 bytes<64 GiB; includes original other working reserve, old8.78 GB index, cached runtime image,14 GiB proposed build closure and1 GiB small prior-output reserve |
| Largest extra replacement shard | 35,684,480 bytes before margin; both directories and receipts are accounted |
| Future native node-prefix target | **≤0.070 s /64,000 nodes**, unmeasured proposal; at2× margin leaves about7,313 s of14,340 s for other work |

The format supports all positive signed63 IDs; resources may stop it. A measured complete ID bound or another valid proof is needed before national storage admission. **No ID-range/source scan runs in this task.** The working screen remains conditional on actual compiler-image/archive expansion fitting its reserve, measured allocation/FS metadata/memory, lookup and mixed work. Unrelated unmounted research assets stay preserved; host free-space checks must account for them. Original typed full-import caps also remain held.

## One isolated build-closure proposal

Select libosmium `v2.23.1` and protozero `v1.8.2` header sources, with a separate linux/arm64 `quay.io/pypa/manylinux_2_28_aarch64` builder. These are **unlocked selectors**, not executable pins. The candidate builder targets glibc2.28; compatibility with the cached2.34 runtime is an inference requiring actual loader/fixture proof. Prefer static compiler runtimes and only verified target dependencies; do not graft unverified libraries or alter host/app environment. Missing headers/libraries stop the proposal, without apt/pip or version fallback. [Primary release](https://github.com/osmcode/libosmium/releases/tag/v2.23.1), [protozero changelog](https://github.com/mapbox/protozero/blob/master/CHANGELOG.md), [PyPA builder documentation](https://github.com/pypa/manylinux/blob/main/README.rst).

The library's documented PBF dependencies include zlib and protozero; XML/other features bring additional requirements. The chosen helper excludes those features. The actual pinned include/link closure still needs qualification. [Libosmium manual](https://osmcode.org/libosmium/manual.html), [repository requirements](https://github.com/osmcode/libosmium). Documentation browsing was separate from the offline probe; no registry/Git metadata lock, source archive, layer or binary was acquired. Failed document fetches and unresolved identities remain recorded in [research sources](research-sources.json).

**Next:** implement/test/freeze one metadata-only lock stage:≤16 requests/2 MiB each/16 MiB total/600 s, no retries; resolve the exact arm64 image digest/config/layer sizes and full source tag/commit/tree identities. No layer/archive download, image pull, compilation, sample or national read. Only a later separately frozen acquisition/build/ABI stage may use those locked identities.14 GiB is a closure ceiling, not a measured footprint. Exact archive body SHA256/expanded sizes remain unqualified until later verification. [Detailed limits and stop behavior](dependency-proposal.json).

Safe saved proof, without Docker/network/probe/source or producer replay:

```sh
python3 -B docs/evidence/coarse-osm-native-design-2026-10-27/verify.py
python3 -B docs/evidence/coarse-osm-native-design-2026-10-27/verify.py --local-assets
```

Previous229 implementation producers/43 prior sealed runs remain bound; this stage adds evidence/proof/probe files, no application or importer implementation. Local mode may hash old assets through the parent chain but never decodes them. No source/provider/DB/paid routing request, model/env/npm/Vercel/commit/deploy change. All old21-window/source/publisher/usable-attribute/matching/physical/83ORS-35Valhalla/accuracy/package/startup/API/visual gates remain held. Work is local/uncommitted. [Resume guide](../../agent-handoff.md).
