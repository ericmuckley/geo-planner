# Native metadata lock V2: image and source identities resolved

October 27, 2026. **The config-only correction succeeds in one frozen run: 8 GETs /246,045 delivered payload bytes.** It reuses V1's saved verified manifest, follows one narrowly validated config CDN redirect and locks both original source versions. All27 host and actual network-disabled Linux controls pass, with no skips. The deployed v9 application is unchanged; this is build preparation, with no accuracy or performance improvement measured.

[Complete metadata lock](raw/acquire/lock.json), [identity summary](locked-identities.json), [result](raw/acquire/result.json), [ledger](raw/acquire/http/ledger.json), [offline audit](raw/offline-audit.json).

## Measured outcome

| Item | Result |
| --- | --- |
| Manifest reuse | V1's5,542-byte saved public manifest, SHA256 `a3e02308c822fb6ce0d12248b0c941817ba5e1a1bc9e7bb5929f29c50eaa40a9`; no latest/manifest request |
| Config | Quay302 /1,359 bytes, one HTTPS `cdn01.quay.io` hop200 /14,396 bytes |
| Config identity/platform | SHA256 `607462577eb2ec84031739355771637c602d54af7d4cd22b89805504753b063b`; linux/arm64,25 valid rootfs diff IDs |
| Layers | 25 descriptors,565,413,699 declared compressed bytes; **none acquired**; expanded size unknown |
| libosmium v2.23.1 | Commit `97dccf105391d410701ae8bd52170dc0ee041373`, tree `c17441c8de31e1d51b596879fe61cc232c1a0367`;552 tree entries /197 selected header-license files /1,668,371 declared bytes |
| protozero v1.8.2 | Commit `af2f6e274e0a873a00e34d8c9ab99fca76898047`, tree `3efd40b2a7469960081054e16819191daa24d21a`;400 tree entries /19 selected files /144,518 declared bytes |
| Git metadata | Both tags lightweight; six GETs, recursive trees not truncated; source file contents/archive hashes still unverified |
| Requests /body bytes | 8 of12 /246,045 of14 MiB, each≤2 MiB; no auth, retry or fallback |
| Resolver before summary | 1.815363 s for HTTP/parsing/locking, excludes worker setup |
| Host before summary | 3.577633 s including input hashes/startup/controls/requests/offline audit/cleanup |
| Closed ignored output | 33 files /810,713 bytes; all33 mirrored unchanged here |
| Actual workers | Controls0/acquire0, both not OOM, removed and separately inspected absent |

[Host summary](raw/run-summary.json), [closed roster](closed-output.json), [actual controls](raw/controls/controls.json), [separate controls absence](controls-cleanup-audit.json), [acquire absence](acquire-cleanup-audit.json). Metadata locks identify future artifacts; they do not establish their acquired bytes, compiler availability, expanded footprint or runtime ABI.

## Correction, tests and freeze

New [core](../../../scripts/coarse_osm_native_lock_v2.py), [launcher](../../../scripts/prepare_osm_native_lock_v2.py) and [tests](../../../scripts/coarse_osm_native_lock_v2_test.py) reuse unchanged V1 Git/descriptor/accounting/resource/owner helpers. The V1 stop, original recipe/code and ignored sensitive raw records remain unchanged. [V1 preserved report](../coarse-osm-native-lock-2026-10-27/README.md).

Only the already pinned config can be requested: exact Quay origin; at most one302 to HTTPS `cdn01.quay.io`, exact digest path, no port/userinfo/fragment, bounded URI and exactly ten unique permitted query names with bounded nonempty values. No Authorization/cookies, second hop, layer/archive request, manifest re-fetch, image/version substitution or auth exchange. Exact config size/SHA, platform and rootfs count/hashes must pass.

The27 tests comprise all19 unchanged V1 controls and eight V2 controls with multiple failure cases. They cover direct/redirect success, exact blob request lists, URL/query/digest/port/host/path refusals, extra hop, auth/HTTP errors, config identity/platform/rootfs, source partial stops, header/framing/partial reads/caps/deadlines and source-mount/recipe drift. Injected private values in URLs/bodies/open/close errors never reach saved files or captured logs. Host, [pre-freeze Linux](pre-freeze-controls/worker.log) and frozen actual controls pass; check197/typecheck/build pass. [Verification](verification.json).

[Plan](execution-plan.json) SHA256 **`360263cb9c63f5c897a8ee22391997f8e833cd85fd8efe9fe3bf5c8d5c19e69a`** binds239 host/236 worker files, exact saved manifest, source selectors, state machine and stops. [Freeze](freeze.json) records pre-request preparation. [Used command](commands.json) is historical provenance; **never run it again or overwrite this output**. V2 has a separate12-request/14 MiB/600 s budget, rather than transferred V1 quota. Combined actual V1/V2:10 requests /252,946 payload bytes.

Actual cached runtime/site/Expat, read-only inputs/root,4 GiB memory/zero swap/two CPUs/64 PIDs/256 MiB tmp/64 MiB files and1 GiB owned writable+tmp apply. Controls network none; acquisition bridge; saved-record reconciliation afterward offline. No road source, sample or partial index mounted. [Isolation](raw/acquire/container-initial.json), [guards](raw/acquire/resource-guards.json). No peak-memory, graph-search or national import-speed claim.

## Privacy and offline proof scope

V2 **never persists signed query values, raw Location or redirect/error body bytes**, including partial reads or raw exception messages. It saves validated public host/path/query names, original URL/body hashes and byte counts. Only successful config bytes matching the pinned descriptor and public Git JSON are spooled. The1,359 redirect bytes are counted/hashed but absent from the saved body roster. [Privacy audit](privacy-audit.json).

Offline replay substitutes an explicitly synthetic signed URL and empty redirect body. It reproduces the complete lock from saved public config/Git JSON, proving state-machine/identity consistency. It cannot reconstruct/authenticate the original signature or redacted body contents; their hashes are receipts only. V1's original signed records remain unchanged only in ignored local storage, excluded from its public report.

Safe saved proof, standard library only, no Docker/network/native or producer replay:

```sh
python3 -B docs/evidence/coarse-osm-native-lock-v2-2026-10-27/verify.py
python3 -B docs/evidence/coarse-osm-native-lock-v2-2026-10-27/verify.py --local-assets
```

The proof binds235 cumulative implementation producers/45 prior sealed runs. Local mode also hashes closed raw assets through the parent chain without decoding them. New code/evidence/current docs remain local/uncommitted; ignored outputs/tools are absent from a fresh clone.

## Exact next action

Implement and synthetically test a **bounded acquisition and minimal compiler/ABI qualification stage using this lock**. Freeze code, all25 layer identities, both full-commit source archives, tar/link/whiteout/digest/selected-header checks, expanded/image-store/copy accounting, resource/ownership controls and fresh output before any acquisition. [Concrete proposal](acquisition-build-proposal.json), [ordered task](../../next-steps.md).

The proposed14 GiB closure ceiling remains unmeasured:2 GiB compressed builder/10 GiB expanded/1 GiB build+scratch/1 GiB source trees+archives+receipts. The52-request/2.25 GiB delivered-body/1,800 s proposal is inactive; archive endpoint behavior and hashes are unqualified. It allows only25 exact layer origins with at most one exact digest CDN hop each, plus two direct full-commit archives, no new metadata/auth/fallback. Account every extra image-store/intermediate copy; stop if it cannot fit, rather than bypass caps with Docker pull/load.

Qualify a minimal C++17 C ABI shared artifact with pinned PBF headers, compiler/zlib versions, ELF dependencies/symbol versions and actual ctypes load/tiny synthetic positive/negative PBF fixtures in the qualified runtime. No saved sample/national input. Missing headers, compiler requirements or ABI mismatch stop; no package fallback, global environment changes or library graft. Full native helper/guard equivalence, real sample performance/lookup, national maximum-ID/storage/time screen and road/model work remain later gates. Original source/21-window/usable-limit/matching/physical/83ORS-35Valhalla accuracy/package/startup/API/visual gates remain held. Provider48/6/29 budgets consumed; no provider/DB/paid call, app/env/npm/Vercel/commit/deploy change. [Handoff](../../agent-handoff.md).
