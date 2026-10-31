# Native build tools acquired; tiny compiled PBF interface works

October27,2026. **One frozen run acquires the exact builder layers and header archives, compiles a minimal C++17 shared library and loads it in the original runtime.** The564-byte synthetic PBF yields4 nodes/3 ways/2 relations and exact first-node XY; truncated/invalid/empty PBF and null inputs reject. **This qualifies the build closure for the tiny fixture. The native importer, faster index and real sample performance are not implemented or qualified.** Deployed v9 is unchanged.

[Run summary](raw/run-summary.json), [compile receipt](raw/build/result.json), [target ABI result](raw/abi/result.json), [actual controls](raw/controls/controls.json), [complete metadata parent](../coarse-osm-native-lock-v2-2026-10-27/README.md).

## Measured result

| Item | Result |
| --- | --- |
| Transfer | 52 GETs /567,143,969 delivered payload bytes; no auth/retry/fallback |
| Builder | 25 origin302/CDN200 pairs;565,413,699 verified compressed layer bytes;25 uncompressed diff IDs verified |
| Source archives | libosmium v2.23.1/full commit:568,569 bytes; protozero v1.8.2/full commit:1,127,726 bytes |
| Source admission | All216 selected headers/licenses /1,812,889 bytes match exact Git blob identities, paths/modes/sizes; header macros confirm2.23.1/1.8.2 |
| Uncompressed layer streams | 1,889,123,840 bytes, read twice without storing intermediate expanded layers |
| Prepared rootfs | 67,573 regular file paths /78,517 entries;2,215,610,879 logical bytes (hardlinks counted by path),1,808,281,600 allocated inode bytes |
| Rootfs allocation allowance | 2,859,870,719 bytes after conservative namespace reserve, below10 GiB ceiling; not a peak/physical filesystem-metadata measurement |
| Compiler | GCC14.2.1 /Red Hat14.2.1-11, C++17; no package installation |
| Artifact | 1,930,672 bytes, SHA256 `bcd80e0b8ff911cc49f58bc13218fc941051361f3526f972e0166b1a6588b367` |
| ELF | AArch64; static compiler runtimes, no GLIBCXX dependency; required GLIBC versions2.17/2.25 |
| Dynamic dependencies | zlib/libm/pthread/libc/arm64 loader; actual load in cached glibc2.34 runtime succeeds, zlib header/runtime both1.2.11 |
| Tiny result |4/3/2 objects, first node XY−10,000,000/5,000,000; three malformed PBF cases/null rejected |
| Main workers | Controls/acquire/prepare/build/ABI all client=worker0, not OOM; five removals/independent exact-ID absence checks pass |
| Host elapsed |156.263573 s including input hashes/startup/all phases/storage audits/cleanup; not importer or graph-search time |
| Docker image store | No new builder image or pull/load;0 new image-store/expanded-intermediate-layer bytes |

[Artifact ledger](raw/acquire/http/ledger.json), [archive hashes/paths](raw/acquire/result.json), [source/layer preparation](raw/prepare/result.json), [acquired allocation](raw/acquire-storage.json), [prepared allocation](raw/prepare-storage.json), [compiler output](raw/build/compiler-version.log), [ELF receipt](raw/build/elf.log), [cleanup audit](cleanup-audit.json).

## Frozen implementation and resource scope

Four new files: [acquisition/unpack core](../../../scripts/coarse_osm_build_v1.py), [isolated launcher/tiny ABI proof](../../../scripts/run_osm_build_v1.py), [synthetic controls](../../../scripts/coarse_osm_build_v1_test.py), [minimal C ABI source](../../../scripts/coarse_osm_build_smoke_v1.cpp). All older sealed producers/results remain unchanged.

[Plan](execution-plan.json) SHA256 **`b31290de98ac86c1a6c81db0fa9e6f617b33ae00c39b5ed8eed25e0f48c6b8b1`** binds245 host/239 worker files and the exact complete metadata lock. [Freeze](freeze.json) predates requests; [used command](commands.json) is historical provenance, **never a health check or replay command**. New output is closed at ignored `data/coarse-quality/us-osm-native-build-v1/`. No latest/manifest/config/ref lookup or source/sample/DB/provider call occurred.

Caps:52 attempts,120 s/request,2 GiB builder body/128 MiB each archive/256 MiB archives total/2.25 GiB delivered total, no retries;1,800 s shared host/1,740 s work with60 s cleanup reserve.14 GiB closure ceilings:2 GiB compressed/10 GiB expanded/1 GiB build+scratch including256 MiB tmp/1 GiB source archives+selected trees+receipts.16 GiB starting free/2 GiB ongoing headroom. Actual bounded cached runtime uses4 GiB memory/zero swap/two CPUs/64 PIDs/read-only root/inputs,1 GiB file limit; confined compiler files limited32 MiB. Final allocation is measured; peak process/cgroup memory and filesystem metadata/transient allocation are not directly sampled.

Only acquisition has bridge networking. All other phases are network none. Each origin can redirect once only to the exact digest path on HTTPS `cdn01.quay.io`, with bounded fixed query names and no credentials/cookies. Public source archive URLs use the two full commits directly; no redirects/fallback. Exact layer bytes are verified in memory before saving, bounded by the largest frozen241,333,120-byte layer; error/redirect/unverified-layer bodies and signed URI values never reach files. [Privacy audit](privacy-audit.json).

Two streamed tar passes validate each diff ID/header/path/type first, apply whiteouts to earlier layers, then write verified members with symlink-ancestor/hardlink/traversal/duplicate/sparse/PAX/special-file guards. Directories become0755, file modes retain0777 bits with setid removed; ownership/security xattrs are not restored. This is the verified compiler-filesystem subset, not a claim of general OCI runtime conformance. Source archives extract only selected regular headers/licenses after exact Git blob SHA1 checks. [Protocol references](research-sources.json) include the [OCI layer specification](https://github.com/opencontainers/image-spec/blob/main/layer.md) and [Python streaming tar interface](https://docs.python.org/3.13/library/tarfile.html).

Only offline controls/build add `SYS_CHROOT`. The compiler subprocess changes root/cwd into the owned readonly builder, clears all effective/permitted/inheritable capabilities and executes without outside descriptors under no-new-privileges. Only work/tmp are writable. Target qualification uses the unchanged cached runtime without added capability or builder libraries. No global `LD_LIBRARY_PATH`, host toolchain/env/npm/DB/Vercel change.

## Controls and closed-asset proof

All42 actual network-none Linux controls pass/no skips:27 retained metadata controls plus15 new artifact/tar/source/ownership/confinement controls, including a full synthetic acquire→audit→two-pass preparation and tamper tests. Host41 pass/one Linux-only chroot skip. Check197/typecheck/build pass. The first pre-freeze isolation check stopped before running tests because Docker reports `CAP_SYS_CHROOT`; guard normalization was corrected before freeze, with all old draft code/records retained. A40-control intermediate success and final42-control pre-freeze success are also preserved. [Draft scopes](draft-controls-scope.json), [verification](verification.json).

The original full tree seal includes OS-reported permission/directory metadata. A strict Mac/Linux comparison initially differed. A separate read-only Linux audit reproduces the original worker seal exactly, confirming no Linux rootfs drift. Docker Desktop reports some permission bits differently to the Mac host (for example000 versus0600). The full comparison found only mode differences; file contents, sizes, paths and links agree. The failed strict metadata assumption is preserved, followed by a portable byte/path/link comparison that excludes those platform fields; no original record or asset was altered. [Original-seal audit](closure-audit/comparison.json), [preserved metadata diagnostic](closure-metadata-audit/stderr.log), [portable comparison](closure-contents-audit/comparison.json), [closed assets](closed-assets.json). These extra audits are read-only/network-none, not archive/native/compile or source-data replays; all their final states/removals/independent absence checks are retained.

[Public record roster](public-records.json) mirrors82 small records /1,285,369 bytes without alteration. Bulk layers/archives/rootfs/selected source files/compiled artifact remain ignored; their complete content tree/counts are bound by the closed-asset receipt. Directory sizes and POSIX mode representation remain in the original Linux evidence separately from the portable content seal. Default proof verifies public records/parent chain; local mode hashes every closed artifact and reconciles acquisition accounting and selected Git blobs, without decoding archives/PBF or executing native code.

```sh
python3 -B docs/evidence/coarse-osm-native-build-2026-10-27/verify.py
python3 -B docs/evidence/coarse-osm-native-build-2026-10-27/verify.py --local-assets
```

Proof binds239 cumulative implementation producers/46 prior sealed runs. New code/evidence/docs remain local/uncommitted and ignored assets absent from a fresh HEAD clone. Do not rerun completed producers, overwrite/repair failed outputs, expose old V1 signed URL records, or rely on historical PIDs/container IDs for later jobs.

## Next action

Implement a new native validation/index helper and lossless block/delta format using these **saved** build artifacts. Preserve all frozen metadata/UTF-8/precision/canonical-size/order/byte/counter/audit guards; full-field proof and fast semantic seals have distinct scopes. Use synthetic fixtures only until reference equivalence and independent two-pass adversarial checks pass and a separate fixed saved-sample recipe is frozen. [Guard map](../coarse-osm-native-design-2026-10-27/guard-map.json), [format design](../coarse-osm-native-design-2026-10-27/format-design.json), [ordered next task](../../next-steps.md).

The0.070 s/64k node target is still unmeasured. Sample lookup/equivalence and complete national maximum-ID/storage/time screens remain future gates; tiny compiler compatibility clears none of them. No new national scan/full import/source attribute adapter/matcher/graph/model/accuracy/package/startup/API/visual admission. All original21-window/source/publisher/usable-limit/83ORS-35Valhalla gates and consumed provider48/6/29 budgets remain. No app/UI/env/Postgres/npm/Vercel/commit/push/deploy change. [Handoff](../../agent-handoff.md).
