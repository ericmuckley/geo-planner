# Native dependency lock: config redirect safely stopped V1

October 27, 2026. The frozen metadata-only launcher ran once and **stopped after two GETs /6,901 payload bytes**. Quay returned a digest-verified public image manifest, then **HTTP302** for its config JSON. The signed redirect points to `cdn01.quay.io`; V1 deliberately refuses cross-host redirects. No config, image layer, source archive, compiler or road sample was acquired. **The build closure remains unlocked and deployed v9 is unchanged.**

All **19 host and network-disabled Linux controls pass**. Both actual workers have known final exits/OOM states and independent removal checks. This is the preserved stop accepted by the stage's criteria, not a successful lock or tool qualification. [Result](raw/acquire/result.json), [public ledger](public-http-ledger.json), [next version proposal](redirect-correction-proposal.json).

## Measured outcome

| Item | Result |
| --- | --- |
| GET1 | Quay manifest, HTTP200,5,542 bytes |
| Root manifest identity | SHA256 `a3e02308c822fb6ce0d12248b0c941817ba5e1a1bc9e7bb5929f29c50eaa40a9`, matching published digest header |
| Declared config | 14,396 bytes, SHA256 `607462577eb2ec84031739355771637c602d54af7d4cd22b89805504753b063b`; **not acquired/verified** |
| Manifest layers | 25 descriptors; declared compressed sum565,413,699 bytes, **not downloaded** |
| GET2 | Quay config endpoint, HTTP302,1,359-byte redirect response; no redirect followed |
| Config redirect | HTTPS `cdn01.quay.io`, path contains exactly the config digest; signed query values omitted |
| Source metadata | Neither GitHub repository requested; commit/tree/blob identities remain unresolved |
| Actual quotas | 2 of16 attempts /6,901 of16 MiB delivered body bytes; no retries |
| Resolver before summary | 0.586513 s, includes the two HTTP operations/parsing and stop before final ledgers; excludes worker setup |
| Total host before summary | 2.313653 s, includes input hashes/startup/offline controls/acquisition/offline audit/cleanup |
| Closed local output | 24 files /91,013 bytes |
| Controls worker/client | Exit0, not OOM, network none |
| Acquisition worker/client | Exit2, not OOM, configured bridge network |
| Cleanup | Both exact owned workers removed and separately inspected absent |

[Independent manifest review](partial-manifest-review.json), [closed roster](closed-output.json), [host summary](raw/run-summary.json), [controls](raw/controls/controls.json), [offline stop audit](raw/offline-audit.json). Manifest integrity alone does not establish arm64 config, expanded size, compiler contents, source-header identities or runtime ABI.

## Implemented controls and frozen scope

Three new versioned files: [metadata protocol core](../../../scripts/coarse_osm_native_lock_v1.py), [bounded launcher](../../../scripts/prepare_osm_native_lock_v1.py), [offline tests](../../../scripts/coarse_osm_native_lock_v1_test.py). All earlier producers remain unchanged. The new launcher reuses the frozen label/image-checked cleanup helper; its historical `geo-planner.stream-owner` label identifies these metadata jobs without replaying an old profile producer.

The tests cover OCI single/multiarch selection, root/descriptor/config hashes and sizes, wrong architecture/layer closure, anonymous-auth scope/token redaction, no auth forwarding, redirect/HTTP refusals, Git lightweight/annotated tags and cycles, tree identity/truncation/path/parent/mode/blob-size checks, source/header selection, partial-source preservation, exact request/body/storage/deadline stops, failed-read prefix accounting, isolation and owner-safe interrupted-worker recovery. Successful synthetic locks replay exactly from saved public JSON using an explicitly synthetic auth placeholder. No real endpoint is contacted by the controls.

[Plan](execution-plan.json) SHA256 **`698a0269066901147b60c60b72b074ddb29e1c24c975f46db11b04c38ca38348`** binds233 host/232 worker files;19 host/Linux controls, exact source selectors and request state machine. [Freeze](freeze.json) describes preparation; [command](commands.json) is used historical provenance. Do not invoke it again, edit sealed files or repair/overwrite this output.

The cap is16 attempts,2 MiB/response,16 MiB total,30 s/request and600 s shared host/570 s work deadline;540 s metadata watchdog. Unknown-length bodies that exhaust quota stop without an extra sentinel read or invented EOF. No redirect, layer/source-blob/archive GET, image pull, package install or fallback version is allowed. Protocol behavior follows the [OCI distribution model](https://specs.opencontainers.org/distribution-spec/) and [Git reference](https://docs.github.com/en/rest/git/refs)/[tree](https://docs.github.com/en/rest/git/trees) identities; the frozen policy is intentionally narrower than general clients.

Both phases use the cached qualified image/site/runtime, read-only root/inputs,4 GiB memory/zero swap/two CPUs/64 PIDs/256 MiB tmp,64 MiB file/1 GiB owned writable+tmp. Controls run network none; the bridge phase necessarily parses protocol metadata to generate its bounded next URLs. Host reconciliation is offline afterward. No source/sample mount or parser/native scan. [Actual acquisition isolation](raw/acquire/container-initial.json), [guards](raw/acquire/resource-guards.json), [separate absence](acquire-cleanup-audit.json). These are configured/actual guards, not peak-memory or importer-speed measurements.

## Signed-URL evidence handling

The raw refused Location and HTML body contain a signed config URL. **They remain unchanged only in ignored local output.** The report omits raw `acquire/http/ledger.json` and `002.bin`; it provides an explicitly redacted public ledger, host/path/query-key names, URL/body hashes and exact byte counts instead. No signed query values or bearer token are committed or printed. [Redaction mapping](redactions.json). All other22 output records are mirrored unaltered. This does not rewrite original evidence to pass a check.

The first request needed no anonymous bearer exchange. V1's general token redaction is tested, but its Location/body logging did not anticipate signed redirects; a later version must avoid persisting those values from the outset. The default proof checks public records/roster bindings; local proof hashes all retained raw files and reconstructs the same redaction without printing values.

## Exact next action

Implement a separate **V2 config-only redirect correction**, preserving V1. Reuse the saved, digest-verified5,542-byte manifest; **do not query `latest` again**. Request its pinned config at Quay, permit one302 hop only to the observed HTTPS CDN host and exact config-digest path, require the bounded query-key shape, and never forward bearer/cookie headers. Keep signed values only in memory; receipts contain hashes/counts/redacted fields. Require exact14,396-byte config SHA256 and platform/rootfs checks before any image lock can complete.

Keep the same two source selectors and all Git/resource/owner guards. Proposed separate caps are12 attempts/2 MiB each/14 MiB total/600 s/no retries; V1 plus those maxima stays below the previous16-request/16 MiB diagnostic envelope. This is a **versioned protocol revision**, not reuse of unused V1 quota. New code/tests/request bindings/output must be frozen before one attempt. [Detailed correction proposal](redirect-correction-proposal.json), [ordered task](../../next-steps.md).

No image layer/archive acquisition, build, ABI proof, sample benchmark or national observation follows automatically. Expanded image/source archive SHA256, native helper/guard equivalence, global maximum node ID, all original source/21-window/usable-limit/independent matching/physical/accuracy/package/startup/API/visual/model gates remain held. Provider48/6/29 budgets unchanged; no provider/DB/paid request, app/env/npm/Vercel/commit/deploy change.

Safe saved proof, no Docker/network/worker or producer replay:

```sh
python3 -B docs/evidence/coarse-osm-native-lock-2026-10-27/verify.py
python3 -B docs/evidence/coarse-osm-native-lock-2026-10-27/verify.py --local-assets
```

The proof chains44 prior sealed runs/229 earlier producers and adds three new frozen files. Local mode hashes old assets through the chain but never decodes them. Check197/typecheck/build and19 host/Linux controls pass. New code/evidence/docs remain local/uncommitted; ignored raw outputs/assets are absent from a fresh clone. [Handoff](../../agent-handoff.md).
