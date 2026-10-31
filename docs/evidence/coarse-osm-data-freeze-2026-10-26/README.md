# National-input recipe frozen; source not acquired

October 26, 2026. The data-phase launcher, resource/failure controls and exact recipe are ready for **one later bounded national-file extraction attempt**. The read-only command passes. **No source request, national PBF/header read or data worker execution occurred in this preparation.** V9, application/environment/database/npm/Vercel configuration and all earlier source/model gates remain unchanged. New scripts/evidence/current docs remain local/uncommitted.

## Exact command and source identity

The [executable recipe](execution-plan.json), SHA **`bc57f4e3e82a03201b4964efd0d33c5813a04410e5e048544bd2e7df4a459f14`**, binds206 host inputs,200 worker files,16 individually mounted static files, the qualified182-file installed tree and isolated Expat runtime. No package resolution/install/tool or metadata download. The [completed tiny-native proof](../coarse-osm-tools-v2-run-2026-10-26/README.md) supplies the pinned reader/runtime; it does not predict national processing performance.

Read-only check, completed once during preparation:

```sh
python3 -B scripts/prepare_osm_input_v2.py docs/evidence/coarse-osm-data-freeze-2026-10-26/execution-plan.json bc57f4e3e82a03201b4964efd0d33c5813a04410e5e048544bd2e7df4a459f14 data/coarse-quality/us-osm-input-v2 --check
```

**Later execution command; not run in this checkpoint:**

```sh
python3 -B scripts/prepare_osm_input_v2.py docs/evidence/coarse-osm-data-freeze-2026-10-26/execution-plan.json bc57f4e3e82a03201b4964efd0d33c5813a04410e5e048544bd2e7df4a459f14 data/coarse-quality/us-osm-input-v2
```

[Commands as structured arguments](commands.json), [read-only result](readonly-check.json). Commands require the repo root, current local ignored tools/runtime, Python, Docker, cached image and sandbox Docker/network access. `--check` hashes bindings, checks capacity/cached image/unused output and creates no output or data worker. The execution command alone activates the larger limits and new publisher-state expectations for this separate input version; it does not qualify a source or change the app. Refuse existing output, input/capacity/image/recipe drift, redirects, retries, range/resume, alternate dates/latest/mirrors or raised-cap fallback. After execution, preserve every output and do not replay these commands as health checks.

Source remains the unchanged [offline-US proposal](../coarse-osm-offline-plan-2026-10-26/proposal.json):

| Binding | Exact value |
| --- | --- |
| URL | `https://download.geofabrik.de/north-america/us-261025.osm.pbf` |
| Body bytes | **12,229,320,016** |
| Publisher MD5 | `c5abaec55e724255277f22fb97941e5a` |
| Expected replication state | `2026-10-25T21:21:21Z` |
| Windows | All original21 boxes, unchanged bit-for-bit in the recipe |
| Requests | One PBF GET; zero metadata/tool/provider/app-DB requests |

This explicitly departs from the old exact-time query `2026-10-21T00:00:00Z`; all old evidence/snapshot semantics remain intact. Exact bytes/publisher MD5, newly measured SHA256 and the real frame/header/state must agree during the later attempt. Publisher MD5 is an integrity check, not strong authenticity proof; header time does not establish global snapshot or boundary completeness. No header has been observed in this stage.

## Capacity, arithmetic and enforcement

Current [capacity observation](capacity.json) at `2026-10-27T01:07:42Z` (October26 locally): **165,530,894,336 bytes free**, host RAM17,179,869,184, Docker RAM8,218,034,176,10 host/Docker CPUs. Required initial free space85,899,345,920 bytes; minimum host/Docker RAM8/6GiB and two CPUs. The sandbox initially blocked the memory query; [that failure](capacity-initial.json) is retained separately from the successful read-only escalated observation. Capacity is rechecked before actual execution; it is not reserved and does not establish speed or peak usage.

| Bound/assignment | Value |
| --- | --- |
| Worker memory/swap/CPU/PIDs | **4GiB /0 /2 /64** |
| Working cap including tmp | **64GiB** |
| Working components assigned | **65,270,488,400 bytes**,3,448,988,336 slack |
| Raw source | 12,229,320,016 bytes |
| Primary /separate audit SQLite | 24GiB each;4,096-byte pages,6,291,456 pages maximum |
| Normalized output | 128MiB |
| Tool/metadata reservations | 512MiB/16MiB, conservatively covering actual10,722,475-byte read-only reservation |
| Tmp /reports /driver reserves | 256MiB /512MiB /8MiB |
| HTTP body cap | 12GiB; maximum planned source read12,229,320,017 including sentinel |
| Shared wall /source GET /idle | **14,400s /5,400s /30s** |
| Selected identities /window occurrences | 250,000 /500,000 |
| Upstream visits | At most4,440,000,000 across four passes; original per-pass caps retained |

[Arithmetic](arithmetic.json) preserves the original conservative assignment; body allowances are narrowed to one source GET, with no transfer from completed metadata/tool stages. The cached image is excluded from working output; all mounted code/tools/config and a2MiB recipe allowance are reserved. Raw source is retained once, mounted read-only for analysis. Working storage is guarded by streaming/SQLite page/per-file bounds, stat-size polling and final checks; **not** an aggregate filesystem quota. Host polling never repeatedly hashes the national source. Host free headroom is checked during work. Per-file hard limit24GiB, core dumps disabled; worker logs capped1MiB each.

One host execution deadline spans container startup, acquisition, worker cleanup, framing, four native passes/audit and final verification. Initial read-only host binding/capacity/image preflight and initial recipe/capacity writing precede that execution clock.60 seconds are reserved from worker work for cleanup/finalization. The final preserved-source SHA scan has a remaining-time alarm. HTTP incrementally hashes SHA/MD5; framing separately reads/hashes the full file, native passes count projected objects, final verification hashes raw source once and normalized output separately. Their scopes must be reported separately; no graph-search or four-hour completion forecast.

## Implemented controls and actual small tests

[Data guards](../../../scripts/coarse_osm_data.py), [launcher](../../../scripts/prepare_osm_input_v2.py), [tests](../../../scripts/coarse_osm_data_test.py) reuse the frozen transport, framing, native projection, SQLite/full-segment/full-node extractor and separate selection audit. A new4GiB guard preserves the old sealed1GiB helper. The download worker uses direct verified TLS/one exact URL; the extraction worker uses **network=none**, scoped runtime path, read-only source/tools/code/root and only owned output/tmp writable. No credentials, system installation or app database access. Code endpoint restrictions are not an OS hostname firewall.

**17 Linux tests pass** under the configured4GiB/zero-swap/two-CPU/64-PID/256MiB tmp environment, including real qualified tiny-native PBF extraction through the actual wrapper, final-source SHA validation and a deliberately stopped valid normalized prefix. Host16 pass/one qualified-Linux-native skip. Other controls cover exact source/windows/caps/activation, refusal/truncation/checksum failures, no retry/reuse, capacity/arithmetic, changed inputs before HTTP, size-only polling, completion/source drift, all-window unqualification, OOM counter partialness, stalled-worker host deadline and owner-label recovery/removal after create timeout. Tests use synthetic transport/tiny saved fixtures, **zero live source requests**. `npm run check` (197 files), typecheck and build pass; existing build warnings remain. [Pre-freeze checks](pre-freeze-checks.json).

The source-bound [final resource probe](resource-probe-v2.json) reads actual4GiB memory/zero swap, two-CPU quota,64 PIDs, read-only root, core0/per-file24GiB and256MiB tmp; it interrupts a tiny stalled child/timer and proves a16KiB SQLite page limit stops writes. The [earlier probe](resource-probe.json) remains preserved. No4GiB allocation, OOM-pressure test, national source, national index, native throughput or workload peak was measured. All probe/test containers used cached image/no pull/network=none/`--rm`; the proposed data workers themselves have not been created.

## Later result criteria and limits

Success requires both owned phases exit0/not OOM with independently confirmed removal, exact source bytes/MD5/acquisition-framing-final SHA agreement/header state, all four matching EOF/count streams, all21 windows complete **from acquired file only**, independent selection/native/dependency/output audit, valid output hashes/byte bounds and shared time/storage/resource limits. The launcher also checks actual worker exit against the Docker client result. It leaves source/boundary/usable-attribute/model qualification false even on success.

Refusal, malformed identity, partial transfer, source drift, limits, OOM, native/SQLite/audit failures or cleanup uncertainty retain every body/ledger/index/normalized prefix/state and mark results unqualified/untrusted. Raw decoder failures before projection and hard kills may leave partial counters. Do not resume/reuse OFF-journal indexes or delete failure evidence. A correction requires a new versioned recipe/output; no latest/date/provider fallback.

**Next:** execute the exact frozen command once, then reconcile all saved outcomes read-only. This is an offline national-file/21-window feasibility experiment, not model integration. File completeness alone leaves publisher clipping/global completeness,50% plausible usable-limit coverage, independent matching/physical review and all83/35 accuracy/package/startup/API/visual gates pending. No speed/access adapter/matcher/graph/ETA, paid/cloud/service, app/UI/env/DB/npm/Vercel/commit/push/deploy work is activated. Provider48/6/29 budgets remain consumed. V9 remains the deployed model.

Safe saved-record proof, without Docker/network/producer replay:

```sh
python3 -B docs/evidence/coarse-osm-data-freeze-2026-10-26/verify.py
python3 -B docs/evidence/coarse-osm-data-freeze-2026-10-26/verify.py --local-assets
```
