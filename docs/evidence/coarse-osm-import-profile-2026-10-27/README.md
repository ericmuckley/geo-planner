# Node-index prototype reduces sample time by 31%

October 27, 2026. A bounded, offline comparison on **64,000 real OSM nodes** passes the frozen correctness and speed criteria. The new validation prototype takes **1.790 s versus 2.589 s** for the median first-index loop: **1.446× throughput, or 30.86% less time**. All projected-record hashes, counters and coordinate-index bytes match. The sample contains nodes only; this is not a whole-import, national-runtime or map-accuracy result. Deployed v9 is unchanged.

The [complete national source](../coarse-osm-data-v3-run-2026-10-27/README.md) is reused read-only. The former four-hour stopped import, its unfinished index and all earlier evidence remain intact. New scripts/reports/docs are local and uncommitted; ignored sample/index outputs are absent from a fresh clone.

## Fixed comparison and measured result

| Item | Result |
| --- | --- |
| Source sample | First **9 complete PBF frames / 377,536 bytes**, selected by frame order, not geography |
| Objects per case | **64,000 nodes**, no ways or relations |
| Actual native projected visits | **640,000**, across ten prefix scans |
| Plain paired index runs | Three per implementation, fixed reference/candidate, candidate/reference, reference/candidate order |
| Reference times | 2.584404 / 2.589015 / 2.642883 s |
| Candidate times | 1.790098 / 1.775388 / 1.813743 s |
| Median index time | **2.589015 → 1.790098 s** |
| Frozen speed criterion | At least **1.25×**, passed at **1.446298×** |
| Projected records and counters | Identical across all ten cases |
| Coordinate indexes | Eight identical **1,748,992-byte** files, SHA256 `766e482dbd226e8b54126ac8dbd5e102f23d746d7d2bb497f5b02628fa768fec` |
| Corrected controls | **18 pass on host and network-disabled Linux** |
| V2 worker / client | Both exit0, not OOM; owned removal and separate absence inspection pass |
| V2 closed output | **47 files / 14,545,627 bytes** |

The timed loop includes the unchanged native projector, canonical record hashing, validation, checkpoint work, SQLite insertion and final index integrity check. Four additional instrumented cases separate projection, reference validation, reference indexing and candidate indexing. **Instrumented timings are excluded from the paired median.** No retry, parameter sweep or threshold change after results. [Measured interpretation](execution-result.json), [raw successful result](v2/result.json), [all retained hashes](v2-output.json).

An independent bounded byte comparison confirms the sample exactly equals the saved source's leading 377,536 bytes. [Prefix audit](independent-prefix-audit.json). Decoder EOF is for this prefix only. No whole-source native EOF, real-way/relation validation, complete selection/dependency extraction, usable-speed coverage or model qualification follows from it.

## Diagnosis and selected design

A preliminary [generated-node host profile](preliminary-synthetic-profile.json) ran before any real-source scan and identified repeated timestamp parsing. The real prefix confirms it: the reference index profile makes **320,000 `strptime` calls**, while the candidate makes **64,000**. The unchanged native projector accounts for those remaining calls. Candidate validation uses its strict fast parser 64,001 times: once per record plus once for the stream's fixed publisher timestamp. [Reference profile](v2/reference-profile/profile.json), [candidate profile](v2/candidate-profile/profile.json).

Selected [validator prototype](../../../scripts/coarse_osm_validation_v4.py): validate node fields once, parse the fixed snapshot once per nonempty stream, and use `datetime.fromisoformat` only after the same exact timestamp-shape check. Non-ASCII digits retain the original parser fallback. Calendar, visibility, coordinate, identity/order, raw-tag, reference, canonical-byte, object/time/storage and 128-record checkpoint checks stay enforced. The native projector and SQLite implementation are unchanged. Malformed/boundary/Unicode and cap controls compare against the frozen reference.

The full synthetic primary integration retains the frozen independent audit and produces identical selected node/way/restriction records, crossing geometry, outside-node closure, typed-ID collisions, raw conditional/private tags and unresolved external member references. Test-only substitution exercises this prototype; **the production/frozen national launchers still use the original implementation**. Shared decoder, canonical helpers and SQL schema are explicit; this is not independent source truth or exhaustive input equivalence proof.

One concrete follow-up design is therefore supported: a separately versioned importer using this single-pass validation path while preserving independent selection/dependency auditing. Before another full extraction, freeze a read-only national-count and mixed-object feasibility screen. Node-prefix speedup alone does not establish mixed-entity correctness, full coordinate-index size or a four-hour fit.

## Preserved control failure and separate correction

V1 stopped **before any prefix copy or native scan**. Its 17 controls passed on the host, but three fake-Docker cleanup scenarios failed in Linux. They consulted the worker's 256 MiB temporary filesystem while simulating a host that requires 2 GiB of free headroom. The fake host stopped before creating its fake container, then its incomplete absence simulation masked that stop with an assertion. Recorded resource limits/trace and the new controlled reproduction support this diagnosis; the initial inner temporary-directory failure record was not retained. [Original controls](v1/controls.json), [trace](v1/worker.log).

V1 exits2/not OOM, retains **13 files / 83,801 bytes**, and its exact owned worker is removed and independently absent. No sample, index or timing result was produced. Its full-source identity hash matched. [Closed V1 roster](v1-output.json), [separate cleanup](v1-cleanup-audit.json).

The separately frozen V2 changes the fake-host capacity/absence controls, adds a regression reproducing the small-filesystem stop, and selects that portable suite. **Actual resource guards, candidate validator, sample logic, case order, benchmark and speed threshold are unchanged.** V2 reuses the exact V1 benchmark functions rather than rewriting them. All V1 files/code/recipe are preserved; this is not a replay or repair of its used output.

| Recipe | SHA256 / bindings |
| --- | --- |
| [V1 plan](execution-plan.json) | `85da7b36a24bea4bf5c3aa2f3705228b7d8448d372fe51317ae439e96e697373`; 223 host / 210 worker files |
| [V2 correction](correction-plan-v2.json) | `22d2160b410330f506df99b763d6277b9a658fdf4e362a39485f41da94687cc1`; 242 host / 213 worker files |

[Original command](commands.json), [corrected command](correction-commands-v2.json) are **used historical commands**. Their `executedAtFreeze:false` fields describe preparation, not the current state. Do not invoke either producer as a health check.

## Bounds, timing and remaining limits

Each attempt uses the qualified cached image/site/runtime, networking disabled, read-only source/code/root,4 GiB memory/zero swap/two CPUs/64 PIDs/256 MiB tmp,64 MiB per-file and32 MiB per-index caps. The owned writable/tmp ceiling is1 GiB; the existing read-only12.23 GB source/tools plus that allowance remain below the original64 GiB ceiling. Per-case60s, worker300s, total host600s with570s work deadline. Maximum source prefix2 MiB/nine complete frames;200,000 objects per case/two million aggregate. Original21 validation windows remain unchanged. No unfinished old index is mounted.

A separate full-byte SHA256/MD5 identity pass occurs before each worker; it decodes no native objects and is distinct from the bounded prefix reads. V1 host duration **21.878 s** and V2 **51.220 s** include that identity check, input checks/startup/worker/cleanup before the summary. V2 worker **30.098 s** includes bindings,18 controls, sample/framing, ten cases and reports before its summary. These are not graph-search timings. Observed process maximum RSS is48,016 KiB for this small Linux worker, excluding host/kernel accounting; no national or production memory qualification.

Both workers' normal final exits/OOM states and independent removals are known. [V2 cleanup](v2-cleanup-audit.json), [verification matrix](verification.json). Zero source/dependency/provider/metadata/DB/paid requests, image pulls or fallback. App/grid/slider/env/Postgres/npm/Vercel are unchanged. No commit, push or deployment. All source/publisher/50% usable-limit/independent matching/physical/83ORS-35Valhalla accuracy/package/startup/API/visual/model gates remain held; original consumed provider budgets are unchanged.

Safe saved proof, no Docker/network/native replay:

```sh
python3 -B docs/evidence/coarse-osm-import-profile-2026-10-27/verify.py
python3 -B docs/evidence/coarse-osm-import-profile-2026-10-27/verify.py --local-assets
```

The proof chains the previous40 sealed runs and204 unchanged producers, then binds nine new implementation/control files. Local verification hashes retained outputs and compares prefix bytes without trusting an old partial index or replaying native scans. Check197/typecheck/build pass; existing build warnings remain. [Current ordered task](../../next-steps.md).
