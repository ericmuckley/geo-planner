# Actual native tool proof completed

October 26, 2026. **The pinned native toolchain passes the real tiny-PBF/decoder/extractor/audit proof.** One exact runtime-package download was followed by a preserved extraction refusal and a separately frozen, entirely offline correction. No national road data or provider request, model change, host/global package installation, environment/database/npm/Vercel change, commit or deployment. All new research code/evidence/docs remain local/uncommitted.

## Results and preserved versions

| Scope | Measured result |
| --- | --- |
| Runtime package | One GET / **83,528 bytes**, exact expected size/SHA |
| V2 acquisition/extraction | Worker exit2, not OOM; conservative unselected-symlink check stops before bundle/offline worker |
| V3 correction | Both workers **network=none**, exit0, not OOM; zero additional requests |
| Extracted library | **174,168 bytes**, SHA `96c872449f41ac16cf6c974ea93e053713b41ea103165cb2c99bb0ebdc2e94be` |
| Library/runtime package | `expat_2.4.7` / Ubuntu `libexpat1 2.4.7-1ubuntu0.9 arm64` |
| Copyright retained | 1,756 bytes; copied as a regular file |
| Saved six wheels | No redownload; validation **8,236,978 bytes** |
| Installed tools | **8,241,646 bytes /182 files**; six versions match prior lock |
| Real generated PBF | **564 bytes /4 frames**, exact synthetic publication state |
| Actual projection/extraction | **9 records**, **4 retained**, **36 visits across four EOF passes** |
| Invalid inputs | Seven framing negatives rejected; native decoder separately rejects truncated PBF |
| Complete retained V2 output | **101,981 bytes /10 files** |
| Complete retained V3 output | **16,741,766 bytes /382 files** |

[V2 recipe](execution-plan.json), SHA `c3a7ee162f29a67fc9a284e327edcc0f0dcd84be8fa03540f7c38a963a68f301`, was frozen before its one GET at ignored `data/coarse-quality/us-osm-tools-v2/`. The download completed with the [official metadata pin](../coarse-osm-runtime-v2-2026-10-26/next-package-plan.json). Extraction then stopped on an additional valid in-package symlink for the wide-character library. No bundle or offline worker was created. That failure/source/recipe/body remain intact. An early commentary description calling it a documentation link was incorrect; the recorded cause is the wide-character library link. [Stopped audit](v2-stop-audit.json), [HTTP ledger](v2/acquire/http/http-ledger.json), [failure](v2/acquire/failure.json).

[V3 recipe](offline-execution-plan.json), SHA `7a8e2b4a2cbf78d8b062c7917328c7cbd63c6be4b6f92f0a663dbe811be82591`, freezes a fresh `data/coarse-quality/us-osm-tools-v3/`, new source/tests and the saved package/wheels. All links must resolve directly to regular files inside the archive; no symlinks are created or followed on disk. Only the selected library and copyright are copied as regular files. This generic archive rule accepts an unselected in-package link without adding a package-name/city/region exception. V2 producers and native-smoke/extractor/audit code were not edited. No second GET or retry. Both commands ran once and are closed; do not replay, resume, overwrite or repair either output.

## What the native proof establishes

The corrected library passes actual aarch64 ELF/loader/glibc dependency checks. All pinned packages import from the isolated target: osmium4.3.2, requests2.34.2, charset-normalizer3.5.2, idna3.20, urllib3 2.8.0 and certifi2026.10.23. `LD_LIBRARY_PATH` is scoped only to the native child. The retained native fixture exercises typed node/way/relation ID collisions, crossing segments whose endpoints are both outside the windows, complete outside-node closure, raw private/conditional tags and an unresolved restriction member. Actual Pyosmium projection, framing, capped SQLite indexes, four-pass extraction and separate selection/native-output audit agree on exact fields/hashes/window membership/counts. [Native result](v3/offline/native/smoke-result.json), [projected records](v3/offline/native/projected.json), [extractor state](v3/offline/native/extract/state.json), [selection audit](v3/offline/native/extract/audit.json).

Truncation, malformed framing, sub-coordinate/subsecond/offset precision, decompression overflow and unsupported compression are rejected by framing; the actual native decoder additionally reports unexpected EOF for the truncated PBF. This is **tiny native-tool compatibility**, not national performance, geographic completeness, publisher/global boundary identity, usable speed/access attributes, matching, routing accuracy or a promoted model. The extractor's source/boundary/native admission flags remain false; the separate tool receipt qualifies only this actual fixture. Shared decoder/normalization/hash/SQLite-configuration primitives are explicit.

## Controls, independent audit and timing

V2 has17 controls: macOS16 pass/one Linux-decoder skip; Linux17 pass. V3 adds five controls: macOS4 pass/one real-package Linux skip; Linux5 pass, including real saved-package-format extraction into a temporary target before the corrected executable freeze. No native reader smoke before that freeze. Six existing host runtime-guard tests and Biome197/typecheck/build pass; existing build warnings remain. [Initial checks](pre-execution-checks.json), [correction checks](offline-pre-execution-checks.json).

The cached **Zstandard1.5.5** decoder is pinned by image/path/SHA, with fixed output bounds and real valid/overflow/truncation/concatenation controls before acquisition. No decompressor installation. The implementation follows the [stable Zstandard APIs](https://raw.githubusercontent.com/facebook/zstd/v1.5.5/lib/zstd.h). Debian ar/control/data paths/types/counts/expansion and package identity/dependency are checked; package maintainer scripts are never executed.

[Independent reconciliation](tool-audit.json) re-reads the package ar/tar/member bytes, six saved ZIP archives, expanded/installed trees, metadata versions, raw XML/projected/output fields and hashes, read-only SQLite indexes, native fixture hashes/counts and resource/cleanup receipts. The archive parser/member selection are separate; the immutable cached Zstandard decoder is shared. It does not rerun acquisition, installation or native reader production. The actual native proof still uses the shared Pyosmium decoder for primary and separate selection audit; this is not an independent source decoder or national proof.

Actual workers use1GiB memory/zero swap/two CPUs/64 PIDs/read-only roots/64MiB tmp, individually bound inputs and no credentials. V2 has one bridge worker; V3 uses separate preparation and proof workers, both network=none. All three owned containers were removed, with independent post-run absence checks. [Cleanup audit](cleanup-audit.json). One600-second host deadline per version reserves30 seconds for cleanup; native child/watchdog60 seconds. Installed aggregate storage is polled/finally checked, not a filesystem quota. Read-only input reservations5,456,947/5,542,985 bytes, retained outputs and tmp fit512MiB. No peak-memory measurement.

V2's meter **0.488698s** ends after its package fetch/ledger; driver **1.002999s** includes startup/download/stopped extraction/cleanup before summary. V3 driver **1.720116s** includes preparation/library validation/offline install/native proof/cleanup before summary; offline interval **0.797419s** includes preflight/ZIP validation/install/native proof/inventory before its receipt. Initial host recipe/input hashing and final summaries are outside driver scopes. None is app HTTP latency, graph-search time or national throughput.

Safe read-only recovery:

```sh
python3 -B docs/evidence/coarse-osm-tools-v2-run-2026-10-26/verify.py
python3 -B docs/evidence/coarse-osm-tools-v2-run-2026-10-26/verify.py --local-assets
```

Small reports and synthetic fixtures/indexes are mirrored here. The downloaded runtime package, runtime bundle, six wheel archives and full validation/installed trees remain ignored; local-assets requires them and checks the prior source/tool/output chain. Fresh clones lack these local assets and uncommitted research files.

**Next:** [implement and freeze an exact national-input recipe](next-data-freeze-plan.json), using this qualified runtime and the unchanged offline-US proposal. Rediscover capacity, bind every installed/runtime file and all source/header/checksum/state/cap/mount/deadline rules, test resource/failure controls with tiny synthetic/native inputs, and produce the exact later command. No national download in this completed tool stage or recipe-preparation task. Proposed12GiB transfer/64GiB work/4GiB memory/four-hour/new publisher state remain inactive until a separate explicit executable data freeze. All original21 windows/denominators/source completeness/50% usable-limit/independent review/83-35 accuracy/physical/package/startup/API/visual gates remain. V9 and consumed provider48/6/29 budgets are unchanged.
