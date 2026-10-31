# Full national source acquired; extraction hit its deadline

Started October 26 and closed October 27, 2026. The separately frozen V3 run made one source GET and preserved the complete **12,229,320,016-byte** dated US OSM file. Publisher MD5, acquisition SHA256, full framing SHA256 and a separate closed-file hash agree. The generic importer then reached its configured work deadline during its first native pass. **No complete extraction, new speed coverage or model improvement is qualified.** Deployed v9 is unchanged.

This checkpoint executes the [previously frozen correction](../coarse-osm-data-run-2026-10-26/README.md), preserving its recipe/code and every earlier failure. The raw file and partial index remain ignored local assets; new reports/docs are local and uncommitted. A fresh clone does not contain these assets. No app, environment, database, dependency, Vercel, commit or deployment change.

## Measured result

| Item | Observed result |
| --- | --- |
| Frozen recipe SHA256 | `a7155c25e61516c9cd61bb3b32f5bd96e5ef8811c265a93f4b845c69f448857e` |
| Source | Dated `us-261025.osm.pbf`; one HTTP200 GET, no retry/resume |
| Full body / declared length | **12,229,320,016 bytes**, equal |
| Publisher MD5 | `c5abaec55e724255277f22fb97941e5a`, matched |
| SHA256 | `1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff` |
| Format check | **221,321 frames**, full-byte scan, expected `DenseNodes`/`OsmSchema-V0.6` and `2026-10-25T21:21:21Z` header |
| Download meter interval | **1,530.112 s**; acquisition interval, excluding host startup/cleanup |
| Framing/hash interval | **104.131 s**; before native passes |
| Last extraction checkpoint | **12,806.940 s including framing**, unfinished snapshot |
| Native progress at that checkpoint | **320,881,664 projected nodes**, first pass not at EOF |
| Complete native passes / normalized records | **0 / 0** |
| Driver stop / host exit | `Data shared host deadline` / **1** |
| Windows | All **21 unqualified** after driver stop |
| Preserved partial node index | **8,783,028,224 bytes**, untrusted |
| Closed output | **21 files / 21,012,429,809 bytes** |
| Owned workers | Both removed; separate post-exit absence inspections pass |

[Execution interpretation](execution-result.json), [closed output hashes](retained-output.json), [independent cleanup audit](cleanup-audit.json). Small raw records are mirrored under [v3](v3/execution-plan.json). The large source and SQLite index remain at `data/coarse-quality/us-osm-input-v3/`; neither was altered, resumed, repaired or deleted.

## What passed, and what stopped

The [HTTP journal](v3/download/http/http-ledger.json) and [source receipt](v3/download/source-receipt.json) record exactly one complete GET. The preserved raw body independently matches both SHA256 and publisher MD5 after closure. This establishes the received file's integrity against the captured publisher value, not strong publisher authentication or geographic completeness.

The [native checkpoint](v3/extract/extract/state.json) records matching full-file framing hashes/date/features. It is still marked `running` because the host stopped the worker outside its normal finalization. The [driver failure](v3/extract/driver-failure.json) and cleanup establish that the job is closed. Do not infer a live process from that stale state. The node count is the last projected checkpoint, potentially partial at forced removal; whole-source node/way/relation totals remain unmeasured. No complete first stream, dependency closure, independent selection audit, normalized JSONL or final completion receipt exists.

The first index interval excluding framing is about 12,702.809 s, roughly 25,260 projected nodes/s. This includes validation, indexing and checkpoint work. It is neither pure native-decoder throughput, graph-search latency nor a forecast for complete national extraction. The measured conclusion is that **this importer did not fit the current time budget**; the specific performance bottleneck still needs profiling.

Download worker exited0/not OOM. Extraction's [pre-removal snapshot](v3/extract/container-before-removal.json) shows it still running; its observed OOM flag was false then, but **final worker exit/OOM are unknown** because there is no normal extraction container-result. The host preserved this distinction and removed only the recorded owned IDs. Both independent absence checks pass. An OFF-journal interrupted index remains untrusted; no integrity check or repair was used to promote it.

Actual worker guards record4GiB memory/zero swap/256MiB tmp; initial inspections bind two CPUs/64PIDs/read-only inputs and root/24GiB per-file limits. Source body/storage remain within the frozen12GiB/64GiB caps. The four-hour execution allowance reserves60s for cleanup/finalization, so work stops at14,340s. No final whole-driver duration was written after the host exception; do not relabel the partial extraction interval as total runtime or routing latency. No peak-memory or complete-workload performance qualification.

## Next action and unchanged limits

Profile and redesign the offline import path under a **separately versioned bounded recipe**, reusing the complete source by exact size/SHA/MD5. Preserve V2's failed prefix and every V3 artifact. Do not rerun either used-output producer, redownload the source, raise caps, resume the partial SQLite database or change selection after seeing results. A later implementation must retain generic selection, the original21 validation windows, outside-node/member closure, typed identity/raw tags, independent auditing and honest partial-stop outcomes. First freeze the profiling/sample bounds and success criteria; no new full scan is authorized by documentation verification.

All source/publisher/usable-attribute/matching/physical/83ORS-35Valhalla accuracy/package/startup/API/visual/model gates remain pending. No speed/access parser, matching, graph, ETA or live grid change. The app already uses real Census roads and coarse assumptions; this additional OSM input is not yet integrated. Provider48/6/29 budgets remain consumed; this run made zero provider, metadata, wheel, DB or paid calls.

Safe saved proof, with no Docker/network/native replay:

```sh
python3 -B docs/evidence/coarse-osm-data-v3-run-2026-10-27/verify.py
python3 -B docs/evidence/coarse-osm-data-v3-run-2026-10-27/verify.py --local-assets
```

The local form hashes the closed raw/index files without scanning native objects or trusting the index. The proof reuses the preceding sealed verification for all204 unchanged producers,38 older sealed runs,3098 earlier assets and22 earlier closed output rosters, then verifies this run separately. The prior report's “V3 not executed” fields retain their historical preparation scope.
