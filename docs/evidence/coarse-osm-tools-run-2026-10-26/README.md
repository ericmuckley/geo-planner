# Locked tool setup: preserved native ABI failure

October 26, 2026. One tool-only run completed acquisition and offline installation, then stopped on **`ImportError: libexpat.so.1`**. Tiny PBF creation/decoder/extractor/audit tests did **not** execute. Native compatibility and all national/source/model gates remain unqualified. V9, app configuration, PostgreSQL, npm and Vercel remain unchanged. Research code, evidence and current docs remain local/uncommitted.

The [exact executable recipe](execution-plan.json), SHA `f01f06dda71c7b24e6de2c43d0ead5f391673645676bea242bf40bdc172e194b`, was frozen before the first binary GET: 25 input bindings, 18 individual read-only worker mounts, the cached Linux aarch64 Python 3.13.5 image, six exact locked wheels and a fresh ignored `data/coarse-quality/us-osm-tools-v1/`. That command ran once and is closed; do not replay, resume, overwrite or repair it. The [previous dependency lock](../coarse-osm-tool-lock-v3-run-2026-10-26/README.md) and all older failures remain sealed.

| Measurement | Result |
| --- | --- |
| Wheel GETs / delivered bodies | 6 / **2,387,936 bytes** |
| Metadata / road PBF / provider requests | 0 / 0 / 0 |
| Validation unpack | **8,236,978 bytes** |
| Isolated installed target | **8,241,646 bytes / 182 files** |
| Complete retained output | **18,921,586 bytes / 368 files** |
| Acquisition / offline worker exits | 0 / 2; neither OOM killed |
| Native result | Import fails; no native fixture generated |
| Working envelope | 512 MiB including 64 MiB tmp; within bounds |
| Actual container limits | 1 GiB, zero swap, two CPUs, 64 PIDs, read-only root |
| Network and cleanup | Bridge acquisition; separate network=none installation/proof; both owned workers removed and absence checked |

[Archive/ledger/install reconciliation](tool-audit.json) independently reads all six saved archives and checks exact URLs, size/SHA/MD5/content lengths/order, expanded member bytes against saved trees, installed-tree hashes and all six installed metadata versions. `pip` successfully installed osmium 4.3.2, requests 2.34.2, charset-normalizer 3.5.2, idna 3.20, urllib3 2.8.0 and certifi 2026.10.23. Installation success is not native import success. The [native failure](offline/proof-failure.json) is retained separately from the enclosing [offline failure](offline/failure.json).

The separate [read-only shared-library inspection](runtime-diagnostic.json) runs `ldd` on ten installed extensions in the same cached image with networking disabled; it does not import or install the reader. All eight Pyosmium extensions report `libexpat.so.1` missing; the two charset-normalizer extensions report no missing libraries. This identifies the observed runtime dependency failure; it does not prove that every other API/format check will pass after correction. No library, image, environment or trust-store repair was performed.

The runner uses the sealed direct-HTTPS meter and ZIP/lock primitives. Wheels are prevalidated with bounded expansion and dependency metadata checks before offline `pip --no-index --no-deps --no-compile --no-cache-dir --target`. Installed aggregate storage uses 20 ms subprocess checks plus a 64 MiB per-file limit and final inventory; this is **not** an aggregate filesystem quota. Host storage polling is 100 ms. The reserved envelope has 182,161,440 bytes slack. The host deadline reserves 30 of 600 seconds for cleanup; the native proof has a separate 60-second process/watchdog bound. No claim of measured peak memory.

The meter interval **0.477673 s** ends at the final wheel fetch/ledger, excluding subsequent archive validation, installation and cleanup. The driver interval **2.060897 s** includes owned-container startup, acquisition, validation, installation, failed native import and cleanup, ending before the final summary write. Neither measures graph search, app HTTP latency or national processing performance.

Before acquisition, **15 new host/Linux network-disabled synthetic controls** passed, alongside **39 existing host extraction/transport tests**, Biome's 197-file check, TypeScript check and production build. The build retained its existing chunk-size/directive warnings. These synthetic tests cover acquisition failure preservation, hash/size/aggregate/ZIP/dependency controls, subprocess deadlines/log/storage/exit handling, path identity, owned cleanup/no second stage after failure, raw fixture semantics and seven invalid-frame controls. They do not replace the unexecuted actual native proof. [Pre-execution checks](pre-execution-checks.json).

Implementation: [setup runner](../../../scripts/setup_osm_tools.py), [native smoke](../../../scripts/coarse_osm_native_smoke.py), [synthetic controls](../../../scripts/coarse_osm_tool_setup_test.py), [independent stopped-run audit](../../../scripts/audit_osm_tools.py), [read-only runtime inspection](../../../scripts/diagnose_osm_runtime.py). The smoke follows the official [writer](https://docs.osmcode.org/pyosmium/latest/reference/Data-Writers/) and [header](https://docs.osmcode.org/pyosmium/latest/reference/IO/) interfaces; actual compatibility remains unproved because import stopped first. Shared decoder/normalization/hash primitives in extraction and audit remain explicit.

Read-only recovery, without HTTP, Docker or producer replay:

```sh
python3 -B docs/evidence/coarse-osm-tools-run-2026-10-26/verify.py
python3 -B docs/evidence/coarse-osm-tools-run-2026-10-26/verify.py --local-assets
```

The first verifies retained report/protocol records, producer bindings, prior sealed runs and stopped-run facts. The second additionally checks ignored assets/tools/completed-output rosters and independently reconciles the saved wheel/expanded/installed trees. Small reports are mirrored here; binary wheels, expanded tools and installed tree remain ignored and are required for local reconciliation. Fresh clones lack these local assets and uncommitted research files.

**Next:** [prepare a versioned runtime correction](next-runtime-plan.json) for the missing Expat library, preserving Python 3.13 and all six wheel pins. Inspect cached compatible runtime libraries first; freeze a minimal official-package acquisition proposal if no local source is suitable. Preserve this failed run and use a fresh output/code/recipe for any correction. Reuse the saved wheels; no metadata lookup or wheel redownload. A successful tiny native proof must precede any separate national-data freeze. All original 21 windows, source completeness, usable-limit/matching, accuracy, physical, packaging, startup, API and visual gates remain required; no larger data limits or publisher state activated.
