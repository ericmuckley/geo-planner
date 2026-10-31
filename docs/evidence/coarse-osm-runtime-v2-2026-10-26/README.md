# Expat runtime investigation and exact package proposal

October 26, 2026. The cached Expat library is **incompatible** with the locked Python runtime. No corrected native setup ran. This closes the local-cache investigation and prepares one exact external runtime-package proposal, as allowed by the preceding [next-runtime scope](../coarse-osm-tools-run-2026-10-26/next-runtime-plan.json). Native PBF/source/model gates remain unqualified; deployed v9 and app/env/PostgreSQL/npm/Vercel configuration are unchanged. New research code/evidence/docs remain local/uncommitted.

## Measured local-cache result

The cached native-tools image `025ebba8267c…` supplies Ubuntu `libexpat1 2.6.1-2ubuntu0.6 arm64`: `/usr/lib/aarch64-linux-gnu/libexpat.so.1.9.1`, **198,712 bytes**, SHA `b4b445a092ad711e535cfa7241974f709b716194c58227abc75b05e3a3bec7f7`. The symlink target was copied as a regular `libexpat.so.1`, with its copyright/license, into new ignored `data/coarse-quality/us-osm-runtime-v2-inputs/`. No older Pyosmium reader was imported. [Source identity/license](cache-inspection-v2.json).

Read-only loader inspection in the locked Python 3.13.5 image reports **GLIBC_2.36 and GLIBC_2.38 missing**; that image has glibc 2.34. `ldd -v` nevertheless returns **exit 0**. The [complete diagnostic](library-closure-inspection.json) is retained. The two other cached Ubuntu/glibc images contain the identical library hash; two cached Amazon Linux runtimes have no Expat at the inspected standard library paths. Alpine/musl images are not a compatible glibc library source. These are local inspections, not a claim about every possible system/library distribution. [Other Amazon runtimes](other-cached-runtime-inspection.json), [other Ubuntu images](remaining-glibc-cache-inspection.json).

The first inspection attempted to use `readelf`, which the source image lacks. Its empty output and [failure](cache-inspection-failure.json) remain; the second inspection used bounded file/header/hash/package/license reads, followed by the existing target loader diagnostic. No tool install, image pull/build, libc replacement, host/global/environment modification or failed-v1 output repair.

## Package proposal, not acquired

The frozen [metadata-only recipe](metadata-inspection-plan.json), SHA `b686bf9919a7aa980514a6bc42382c4f3fff83de29dd032cc877070d37d08a66`, made **two controlled Linux GETs / 3,640,481 delivered metadata bytes** from the official Ubuntu ports repository: Release plus the ARM64 package index. The index's compressed size/SHA match Release; decompressed index **20,328,441 bytes** stays below 64 MiB. Verified TLS was used; no repository GPG signature verification is claimed. Raw [Release](package-metadata/001.bin), [index](package-metadata/002.bin), [ledger](package-metadata/ledger.json) and [selected stanza](package-metadata/package-candidate.json) are preserved. No retries/redirects or package binary fetch in this controlled metadata run.

| Selected package | Pin |
| --- | --- |
| Name/version/architecture | `libexpat1 2.4.7-1ubuntu0.9 arm64` |
| Official URL | `https://ports.ubuntu.com/ubuntu-ports/pool/main/e/expat/libexpat1_2.4.7-1ubuntu0.9_arm64.deb` |
| Exact archive bytes | **83,528** |
| SHA-256 | `b61d2bdf82134f6db0ba5c73d9cfe88805a64cbadbd0d0dffff8410958aab005` |
| Declared dependency | `libc6 (>= 2.25)` |
| Declared installed size | 399 KiB; metadata, not measured extraction |

The declared libc minimum fits 2.34, which makes this a candidate for a bounded isolated test. **Actual ELF/library-symbol/ABI/PBF compatibility remains unproved.** The archive, library bytes and license have not been acquired or examined. The existing six wheel pins/Python interpreter remain fixed; no package substitution or system installation.

External web lookups were separate from the metered Linux run. Debian pages reported differing cached revisions and an unsuitable libc minimum. One package-page link probe returned a web-tool cache error with no binary content; peer transfer is unknown. Several Ubuntu detail-page reads were inaccessible. These were not successful package acquisitions; [web provenance](web-provenance.json) distinguishes them from exact measured Linux request/body totals. Do not repeat those probes or label all external web traffic metered/zero-attempt.

## Implemented guard and checks

New [runtime preflight](../../../scripts/coarse_osm_runtime.py) validates a bounded, pinned, regular aarch64 ELF64 shared library and rejects loader text containing missing libraries/versions, undefined symbols or invalid dynamic linkage even on exit 0. It is separate from the sealed failed-v1 runner. [Six tests](../../../scripts/coarse_osm_runtime_test.py) pass on macOS and network-disabled cached Linux, including the actual exit-zero diagnostic, hash/ELF/size/symlink/output checks. `npm run check` (197 files), typecheck and build pass; existing build warnings remain. The new [metadata inspector](../../../scripts/inspect_osm_runtime_package.py) is bound before its two-GET execution; read-only checks reconstruct its selected stanza from captured raw bytes. No old graph/source/test producers were replayed.

All Docker inspection/test commands used cached images, no pull, no credentials, read-only roots, requested 1 GiB/zero swap/two CPUs/64 PIDs/64 MiB tmp and `--rm`; library inputs were read-only except the one fresh capture folder. Metadata used a separate bridge worker; other probes/tests used network=none. This checkpoint does not independently remeasure memory enforcement or claim native performance. Metadata processing **3.142001 s** spans reads, decompression and candidate selection before candidate JSON writing; host/Docker startup/cleanup excluded, not routing latency or peak memory.

Safe read-only recovery:

```sh
python3 -B docs/evidence/coarse-osm-runtime-v2-2026-10-26/verify.py
python3 -B docs/evidence/coarse-osm-runtime-v2-2026-10-26/verify.py --local-assets
```

These verify records/producer bindings/prior sealed evidence and reconstruct the official-index pin without network, Docker or producer replay. Local-assets also checks ignored old assets/tools/rosters plus the captured incompatible library/license and metadata run.

**Next:** implement/test/freeze the [exact one-package setup/native-proof proposal](next-package-plan.json), then run it once under its bounds. One GET, 1 MiB body ceiling, exact 83,528-byte/SHA pin, no wheel/metadata/road/provider calls; unchanged 1 GiB/512 MiB work/ten-minute tool envelope. Safe bounded archive/control/data parsing, copyright retention and actual loader closure precede native imports. Never execute package maintainer scripts or install into a system environment. Unsupported compression must stop unless a separately bound existing decoder is already reviewed/tested. Reuse the six saved wheel archives in a separate network=none proof; preserve both the failed v1 and this incompatible local candidate. `data/coarse-quality/us-osm-tools-v2/` remains absent and no executable corrected recipe exists yet. Only an actual successful tiny native proof may precede a separate national-data freeze. All original source/matching/accuracy/physical/packaging/startup/API/visual gates and inactive larger data limits remain.
