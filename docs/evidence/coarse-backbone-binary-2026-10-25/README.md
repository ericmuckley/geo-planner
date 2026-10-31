# Binary backbone package/load probe — October 25, 2026

**The isolated binary probe passes its unchanged packaging/load gates.** Active v9, app routing, display resolution and configuration are unchanged. All work here is local/uncommitted at HEAD `648c731`; no commit, deployment, provider call, source download or DB write.

The [previous geometry run](../coarse-backbone-geometry-2026-10-25/README.md) preserved 25 m source geometry, all original costs/cell visits/components, but its inline-base64 projection failed at 88,930,930 bytes. This experiment packages the exact same 17 gzip arrays and 12 retained-v9 gzip payloads in one server-only binary file. It does not change geometry or try another tolerance/codec/budget.

| Frozen gate | Actual result |
| --- | --- |
| Function + 4,194,304 reserve <=70,000,000 bytes | 64,511,568 + 4,194,304 = **68,705,872**; 29 function files |
| Three fresh local handler loads <=3,000 ms each | **581.84 / 584.01 / 583.79 ms** |
| Internal file/decode/validation <=3,000 ms | **580.12 / 582.49 / 582.28 ms** |
| Post-GC heap+arrayBuffer delta <=162,238,546 bytes | **159,253,098 / 159,253,098 / 159,253,562** |
| Exact values, complete graph/base retained | 17 arrays, 92,126,186 raw graph bytes, all 12 base blobs, 978,572 nodes/1,234,223 arcs; unchanged existing base decoder |
| Server-only; zero outbound fetches; DB-free | Pass in every fresh process; no public binary/client payload, research disabled, missing-DB history fallback |
| Ordinary/Vercel build and real generated handler | Pass; contour endpoint explicitly unavailable in this probe |

The binary is 60,846,203 bytes, SHA `4d455bec6c02f3da5a189dd8bbe36b4e2da98be124cd4c45d8309f0234de4b20`. [Independent Python audit](parity-v3.json) compares every gzip to the prior arrays, every raw SHA and all restored kept-v9 values to the original JSON. Original gzip payloads are copied byte for byte; retained metadata excludes only the old Census layer and supplemental visits that the new graph replaces. [Full report](report.json), [package/file inventory](measurements-v3/packaging-v2.json), [three-process summary](measurements-v3/result-v2.json), [exact descriptor/source bindings](probe-v3.json).

## Mechanism and preserved failures

The [original plan](plan.json) used a standalone Nitro `rollup:before` hook. The Vite-based app bypasses that hook; [first build](probe-build.txt) failed import resolution. [V2](plan-v2.json) registered the same emitted-file plugin as an enforced Vite plugin restricted to the `nitro` environment. Its [ordinary](probe-v2-build.txt) and [Vercel](probe-v2-build-vercel.txt) builds passed, but [packaging verification](measurements-v2/verification.log) found no binary: Vite deletes assets when server `emitAssets` is false. No load measurement ran in either incomplete build.

[V3](plan-v3.json) adds only `environments.nitro.build.emitAssets=true`. The plugin emits `server-data/backbone.bin` inside the function; `import.meta.ROLLUP_FILE_URL` resolves to a Node file URL. No `raw:`/Nitro serverAssets inline base64, public/CDN copy or network fallback. All three ignored experiment directories remain intact. An earlier verifier invocation [rejected its output directory](verification-v2.log) before scanning/loading; subsequent invocations use the required child directory. These integration corrections preserve the format, exact binary SHA and all gates. V2-suffixed measurement filenames under `measurements-v3/` come from the unchanged verifier, and refer to the v3 package pinned in their plan SHA.

The [measurement recipe](measurement-plan-v3.json) froze worker/verifier/preparer/config hashes before the first load. Each credential-free Node process rejects fetch before importing the generated Vercel handler. Baseline follows module/config load. Three forced collections with event-loop yields precede baseline and post-load measurement. Full graph and decoded base remain cached and referenced on the second request; temporary encoded file/strings are released. Module/config times are separate in [raw measurements](measurements-v3/load-v2-1.json). The OS file cache is warm from builds/package scanning/parity audit; fresh processes do not establish disk-cold performance. Post-GC RSS is 408.78–409.04 MB; it is neither peak memory nor a cloud observation. The retained-storage gate measures heap+arrayBuffers delta, not RSS.

Eight new Node fixtures, 71 Python fixtures, 186-file Biome, TypeScript, ordinary root build and both probe builds pass. No full app/DB/browser suite was repeated for unchanged application code. The probe does not read/copy env files or receive DB/provider credentials. Normal root builds retain existing environment handling; no secret-value scan requiring env reads was used. No hosted/provider APIs were invoked.

## Recovery and next step

[Commands and prerequisites](../../local-development.md#binary-backbone-package-probe). Preserve completed outputs; verification writes with exclusive creation and must not overwrite measurements. Quick read-only proof checks:

```sh
python3 -B docs/evidence/coarse-backbone-binary-2026-10-25/verify.py
python3 -B docs/evidence/coarse-backbone-binary-2026-10-25/verify.py --local-assets
```

The second command additionally verifies ignored arrays/probe files/generated outputs. A fresh clone at HEAD lacks this uncommitted work; even after committing scripts/evidence it would lack ignored local assets. Do not rerun completed graph producers or consume provider quota as a readiness check.

Next freeze and implement one exact source-junction/cell-crossing routing candidate and evaluation recipe **before any routing search**. Retain all [original 83 ORS/35 Valhalla gates](../coarse-backbone-preflight-2026-10-25/next-design.json), source/physical/shore/transfer/path checks, full first packaged estimate <=5 s, storage/package limits and shared-camera gains/losses review. The saved cases are observed development data. This result qualifies packaging/loading only; accuracy, complete query timing, cloud cold starts/peak/load and activation remain unqualified. V9 stays active, display grid stays 0.025°, and all 48/6/29 provider budgets remain consumed.
