# Resume Geo Planner

Updated October 30, 2026 after the user reset the product priority to a coarse nationwide Vercel app. Completed detailed-engine measurements below remain preserved. This guide is sufficient to recover the task without the chat. Read [AGENTS.md](../AGENTS.md), then this page, [current status](implementation-status.md), [local setup](local-development.md) and [next steps](next-steps.md). The [two-hour report](two-hour-region.md) contains the detailed proof; older reports live in [the archive](archive/README.md) and describe their named historical runs.

## Where to resume

User authorized autonomous work until real guidance is needed. **No worker remains from completed stages; the latest capture below is also stopped/closed.** Rediscover actual owners for future jobs; never replay an existing output or edit a used producer/recipe.

V9 remains deployed/user-verified at HEAD`648c731` (message`v8`), active artifactSHA`28271c809a04cdfab41ad735ad66b29e3875179b617198b7b1d4490533439bf6`;30–720minutes/default120, saved83ORS MAE29.257minutes unchanged. Current work is offline input preparation; no map/accuracy/model/env/Postgres/npm/Vercel change. New scripts/evidence/docs are local/uncommitted; ignored source/compiler/site/binaries are absent from a fresh clone.

**Current capture is stopped/closed; no worker remains.** Used recipeSHA`8a2e7321dbef9faeda6c49660196cdb04c35e6204b5f7b248c866873604c3ed4`, root`data/coarse-quality/us-osm-filtered-capture-run-v1/`. Formal`Selected unique element cap`stop during first road selection at250,000selected keys. Last recognized1,606,229,364nodes/11,201,886ways, accepted ways11,201,885; partial delivered batches10,736,397highways/170,361,375refs include failed/cap+1scope. No source EOF/relations/second pass/output or capture/source suitability/model admission. This is not a measured wall/IO cap or OOM failure.

Host1845.746947seconds including bindings/cleanup; worker1816.602107seconds; kernel peak4GiB/cache reclaim,oom0/oom_kill0. Worker/client2/not OOM/independently absent. Closed62files/938,722,550bytes, conservative allocation940,490,752.14bank parts remain ignored and match accepted census bank hashes, but the stopped stage is not promoted. Every input/old failure remains unchanged. Safe latest proof:

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_filtered_capture_stop_v1.py
```

**Next: bounded disk-backed selected records.** Implement a separately versioned selector/audit spool and native selected-ID bridge before any new source run. Keep4GiB RAM/zero swap/twoCPU/four-hour/64GiB retained total, original21windows and all source/geometry/independence/accuracy gates. New prospective selected allowance2Munique/4Moccurrences,512MiBraw/state,1GiBnormalized output and8MiBselected row; source-copy/canonical4MiB/frame8MiB remain unchanged. SQLite disk spools avoid keeping raw primary/audit objects in RAM; each proposed DB<=1.25GiB/cache8MiB, OS writable file limit2GiB. Two byte-bound938,364,831cell banks remain unchanged. These are new bounded implementation allocations, not retuning any used recipe or relaxing matching/model gates.

Actual retained reservation before new metadata is58,226,331,751bytes (55,406,628,967prior +1,879,212,032census +940,490,752capture stop). Reserve64MiBmetadata; after256MiBtmp, new owned<=10,157,600,665bytes. Proposed worst case2DBs2.5GiB +2journals4GiB +2exact banks1,876,729,662 +1GiBoutput +64MiBmetadata =9,996,902,206bytes, below owned by160,698,459. Gzip proof mirror only after journals close. Check arithmetic/SQLite journal/file guards, synthetic beyond-old-cap selection/native projection, exact tiny four-pass output/independent audit/input preservation, resource/lifecycle and immutable freeze before a new national run. Source/publisher adequacy and usable-limit/matching/83ORS-35Valhalla/model/package/API gates stay later.

The capture controller passes13actual Linux checks/no skips and complete filtered/read-only/four-pass tiny output:1470bytes/4objects/8occurrences/18source visits, identical581byte banks, unchanged fine inputs/no copies or deletion. Closed26files/159,072bytes; worker independently absent. Its tiny qualification overlapped the census, not an isolated speed benchmark. Three producer files`coarse_osm_capture_resources_v1.py`,`run_osm_filtered_capture_v1.py`,`coarse_osm_capture_v1_test.py` are USED/immutable. Safe proof:

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_filtered_capture_controls_v1.py
```

**Unfrozen attribute-facts draft:**`scripts/coarse_osm_attributes_v1.py`/`_test.py` pass9host synthetic tests. They preserve complete raw way records, ordered geometry/dependency hashes, tags/units/conditions/direction/access/structure/barriers and parse only explicit ASCII numeric km/h or mph. Every result keeps car permission unreviewed and usableForTiming=False. This is factual adapter preparation, not usable-limit/matching qualification or a model change. No national captured records have been read by this adapter. Publisher/Osmium primary clipping documentation was also read; report records the node-based selection/long-crossing uncertainty. No polygon acquired, source-snapshot boundary or all21window adequacy decision yet. Files remain draft/editable until a separately frozen qualification. Primary OSM maxspeed/access/oneway documentation was read through the web tool; no source/provider acquisition or quota was used. Next after capture/source adequacy: specify/freeze semantic applicability and bounded inventory/matching controls, then actual Linux qualification before target data. Keep all unsupported scopes/missing fields unknown; never feed native tags to the Overture parser.

Capture retains55,406,628,967prior bytes plus both census banks at their4GiB combined ceiling and64MiB metadata, total59,768,705,127. Actual census allocation1,879,212,032fits that reservation. Owned8,682,336,153after256MiBtmp under64GiB. Same4GiB/zero-swap/twoCPU/four-hour, original21windows,2GiB/cell bank and selected/output caps. Fine index is read-only: no new14.5GBcopy or deletion. Prospective fine lookup4TiB/pass/48bcodec rows/12mcalls, separate cell1e12rows/100mcalls, masks1.1brefs/1mcalls are finite administrative ceilings, not measured use.

Require two complete source EOF/count/semantic passes, every highway geometry/reference, independent primary/audit materialization, full output/window ledger, fresh readonly fine comparison/closed hashes and resource/lifecycle/proof closure. Then source/publisher adequacy, speed/access adapter, >=50%usable-limit/matching/physical and83ORS-35Valhalla accuracy/package/API/model gates remain. Do not start a duplicate producer or a provider/paid/DB/push/deploy/model change.

**National capacity census V2 passed/closed.** Used recipeSHA`562122a0a5181f5716904a3859bd855f9f708098c565772669e3a15ce627f1fe`, root`data/coarse-quality/us-osm-cell-census-run-v2/`. Two full1,770,542,426object traversals,1,606,229,364nodes/392,146blocks/766fine shards per pass, original source/metadata/semantic/EOF and1532source-coordinate witnesses per pass all pass. Both rebuilt banks are byte-identical at938,364,831bytes,14parts each. Fine readonly payload verification43,472,344,176bytes/pass; all original input bytes preserved. Old failed admissions remain unchanged; this is fresh stage-specific revalidation.

Protected passes817.461429/819.942328seconds; host1683.695520seconds including bindings/cleanup, not graph search. Kernel peak4GiB includes file cache/reclaim, max events104452,oom0/oom_kill0. Worker/client0/not OOM/independently absent. Closed82files/1,877,239,685bytes, conservative allocation1,879,212,032.28bank parts remain ignored; small records/directories mirrored. The success closer and saved proof both executed/passed and are now immutable. Safe proof does not read native/PBF/ignored parts:

```sh
python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_cell_census_run_v2.py
```

No worker remains from the census; the capture above is also stopped/closed. Original55,406,628,967retained bytes include the old stopped full index and2.08GBcell prefix. All source/failed SQLite/failed indices/prefix/old evidence remain preserved. No app/env/npm/Postgres/Vercel changes; latest check197/typecheck/build and56-page/1350-link/diff checks passed before this milestone documentation update.

## Earlier component results

**Preceding lookup result:** the typed-ID lookup reader/replay runner passes6Linux controls/no skips and400native coordinates. Its fixed old/new/new/old replay passed all8,540,032coordinate occurrences and identical integrity/IO/cache/row accounting. Mean points()30.769947→24.730693s (19.627%lower); complete-case mean31.564906→25.524386s. No source PBF read. Closed`data/coarse-quality/us-osm-lookup-v3-controls/`13files/112,622bytes and`.../us-osm-lookup-v3-run/`19files/150,688bytes; workers/client0/not OOM/independently absent. All three lookup producers and used recipes are immutable. [Result/proofs](evidence/coarse-osm-lookup-2026-10-30/README.md).

**Complete prototype passed:** V7corrected the preserved V6test-harness assertion;259Linux controls/no skips and independent four-pass output proof passed. V8separates128MiB transient batch heap from unchanged64MiB selected serialized retention.260Linux/no skips passed, including a valid32768way/65536ref batch measured at78,079,432 conservative heap bytes with zero selected records. Both stages closed, workers independently absent. V6compiled library`data/coarse-quality/us-osm-country-controls-v6/build/country-screen.so`,2,003,688bytes/SHA`1084fc1b6e9b1a627b52180fd91df0b46e01a967fbd399c2bad672a4f675f48a` is unchanged. All V6/V7/V8producers/recipes/results remain USED/immutable. Safe proof:`python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_qualification_v8.py`.

**National V2closed after operator feasibility stop:** full first node index was physically built:766shards/14,503,453,128logical bytes, every write/catalog matched the sealed national census. Road processing was impractical at its observed rate; agent deliberately stopped early, rather than claiming a wall/IO-cap failure. Last checkpoint1,606,229,364nodes/123,727ways (0.0761%of162,688,797ways); no whole-source EOF/output or independent second pass. Host1346.536440seconds including binding/cleanup; source binding20.039778seconds. Worker137/not OOM/independently absent. Closed798files/14,503,551,785bytes; conservative allocation14,512,766,976bytes.766payloads remain ignored in`data/coarse-quality/us-osm-full-extract-run-v2/extract/primary-index/`; all other records mirrored. Source/failedSQLite/V1partial index/V2full index remain unchanged and unqualified. No national capture worker/driver remains; separate qualification is below. [Operator decision/stop/proof](evidence/coarse-osm-extraction-2026-10-30/README.md).

V1national host monitor race is also preserved/closed:6,291,456node checkpoint,3partial shards/56,725,840bytes, worker137/not OOM/absent. V2single-lstat monitor correction passed19Linux controls/no skips, tiny complete index/rebuild/independent reference output and lifecycle; all controller/extractor/source/native files/recipes/proofs used by either run remain immutable. Safe newest proof:`python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_full_run_v2.py`. No national source/native/Docker calls. Optional`--local-assets` hashes closed derived files only (14.5GB), not the source; full payloads were already hashed at closure, so do not repeat just for documentation.

**Native cell bank/filter qualified:** V9codec stage passes276actual Linux tests/no skips; closed80files/3,731,377bytes, build/control peaks455,823,360/296,607,744bytes, host32.017263seconds. V10adds immutable bank, separate native primary-table/audit-half-plane masks and complete filtered extraction:304Linux tests/no skips, exact1470byte four-pass reference output,18source visits/4retained/8window occurrences. All4road refs resolve;2need fine coordinates per pass and one outside way is certified rejected. This is tiny semantics evidence, not national speed/IO/coverage. V10closed95files/3,792,620bytes, peaks456,687,616/325,099,520bytes, host33.827068seconds; all workers independently absent. All used V9/V10files/recipes/results immutable. Compiled V10artifact`data/coarse-quality/us-osm-country-controls-v10/build/country-screen.so`,2,004,312bytes/SHA`a84d4641026dbe250fd13f8e098082ac2ba7987bf54b9e63ff5d1126d94bee38`. Safe newest proof:`python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_qualification_v10.py`.

**Read-only and capacity controller qualified:** V11passed38Linux tests/no skips and tiny readonly/four-pass output, then final reporter stopped on an int/list variable collision; preserved87files/655,311bytes. V12corrects only that runner variable:38Linux/no skips, exact1470byte output/18source visits, unchanged3input files, no duplicate fine writes, independent proof and cleanup pass. Closed86files/660,478bytes, host12.063707seconds, kernel peak248,520,704bytes, worker0/not OOM/independently absent. SourceIndex/bank/filter/native code is unchanged; all used files/recipes immutable. Safe`verify_qualification_v12.py`.

Cell-census V1controller passes11Linux controls and two complete tiny source/fine/bank/witness passes:18objects, identical578byte banks, source-coordinate membership/order/duplicates exact. Closed30files/106,565bytes, kernel48,332,800bytes, worker absent. Safe`verify_cell_census_controls_v1.py`.

**Actual national cell census stopped/closed:** used recipe`cell-census-plan-run-v1.json`, SHA`4111e7509a348b3ac47c7d93d048378b504f6b97030514187cd624eb9aa9bca5`, root`data/coarse-quality/us-osm-cell-census-run-v1/`. Formal`Cell bank projected logical cap`stop at1,577,373,696recognized/1,577,373,695accepted node receipts,98.2035%ofnode denominator. No source EOF/ways/relations/second pass/complete bank/read-only national admission. Native counters include rejected/cap+1; unflushed buffer is not retained.31stored parts/2,080,277,463bytes remain ignored;60closed files/2,080,605,918bytes, conservative allocation2,082,320,384bytes. Host776.984551seconds; worker final sample748.775074seconds; kernel peak4GiB/cache reclaim,oom0/oom_kill0; worker/client2/not OOM/independently absent. Fine view compared385,101blocks/1,577,373,696nodes,752shards, no whole-file verification pass; no promotion. Source/full fine/oldSQLite/all failed bytes unchanged. No active worker remains. Safe newest proof:`python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_cell_census_stop_v1.py`; optional`--local-assets` hashes closed prefix only, not PBF/native. Closure already hashed parts; don't repeat for docs.

**Lossless ID-gap format V13 qualified:** 65 actual Linux checks/no skips pass, including canonical raw fallback, independent bytes, native legacy conversion and complete filtered/readonly four-pass tiny output/input preservation. Closed108files/3,796,019bytes; host18.679201seconds; build/control kernel peaks456,495,104/252,387,328bytes; both workers0/not OOM/independently absent. V13library`data/coarse-quality/us-osm-country-controls-v13/build/country-screen.so`,2,004,888bytes/SHA`e82ccc44579ded7e7a6fcae5cdd3a6267250f3f3e00968195e45e567f1c0138e`. RecipeSHA`e3c3f12d84f0bb0eea3629da292dd6187cf587925eb420c110ca53939ccc2237`. All used V2codec/bank/filter/test/V13runner producers immutable. Safe newest proof:`python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_qualification_v13.py`.

**Preserved-prefix measurement passed/closed:** all31old V1parts authenticated/fully converted with native full ID/cell roundtrips, no modified inputs or saved converted bank.373,002blocks/1,527,816,192stored nodes (distinct from the larger interrupted native receipt count). Old2,080,277,463→new914,994,196bytes,56.0158%smaller. Codec3,055,632,384charged rows/746,004calls. Conversion36.321070seconds; host37.390202seconds including bindings/cleanup; kernel peak2,123,542,528bytes/cache inclusive. Closed42files/151,097bytes, worker0/not OOM/independently absent. V1controller missing-mount failure preserved; corrected V2passes8Linux controls/no skips and exact tiny83→86byte conversion. All used files/recipes/results immutable. Safe proof:`python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_prefix_run_v2.py`. Prefix-only evidence, not complete national capacity.

**Completed prerequisite measurements:** V4 national screen passed two1,770,542,426object source passes; metadata/IDs/order/semantic/EOF/census and all probe/reference/storage/resource/lifecycle checks plus independent default/local proofs pass. Exact logical full index14,503,453,128bytes; margined21,770,926,764<24GiB and retained-work60,661,121,267<64GiB. Only eight fixed source-ordinal portions/16,588,148nodes retained. Protected passes696.958/782.948s; host1536.986s includes bindings/cleanup, not search. [Sealed report](evidence/coarse-osm-country-exec-2026-10-30/README.md), manifestSHA`3cf6a309323e830fb0227e092e8d332e44684bdf8ddae250e485dc4bf827ad69`.

V5helper206Linux controls and V2controller7Linux controls/fixture proofs pass. Full batching measurement scanned the source at normal EOF and delivered135batches/274,570ways/2,135,008refs; every coordinate independently checked. Native points32.626820s, separate reference audit71.742157s; each9,460,848,817authenticated bytes/69,544,680decoded rows. Host809.842328s, not graph search. Closed`data/coarse-quality/us-osm-way-batch-run-v2/`164files/51,390,722bytes;135witnesses ignored, worker absent. [Sealed batch report](evidence/coarse-osm-way-batch-2026-10-30/README.md), manifestSHA`f43b43173e5f667b6b19d525c0a0833c4a8f804bca6a26447c20fc9ead64ca83`. A documentation-link-count typo is corrected in the lookup report without changing the original checksum-bound record.

**Preserved failures:** V3national screen stopped on a valid large relation; complete relation diagnostic supports the generic4MiB source-copy/canonical and8MiB frame policy. V1diagnostic launcher/V2qualification runner import/V1controller tmpfs test-harness failures remain preserved. Never patch used versions or replay them. Full extraction, source suitability/publisher boundaries, raw speed/access adapter,50%usable-limit/matching, physical/accuracy/package/API/model gates are not admitted.

**Local assets:** saved source`data/coarse-quality/us-osm-input-v3/download/http/001.bin`,12,229,320,016bytes/SHA`1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff`, MD5`c5abaec55e724255277f22fb97941e5a`, publisher`2026-10-25T21:21:21Z`. Counts1,606,229,364nodes/162,688,797ways/1,624,265relations. Never redownload/mutate. Failed SQLite index8,783,028,224bytes remains untrusted; never resume/repair/delete/promote it. Runtime cached image`sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402`; site`data/coarse-quality/us-osm-tools-v3/offline/site/`, Expat in`prepare/runtime/`. Compiler rootfs/headers`data/coarse-quality/us-osm-native-build-v1/prepare/{rootfs,source-1,source-2}/`, portable rootfsSHA`a64ef22d93c8b49689ccfefe09c67a62e67422cb84c6edb86089533fb33ebd72`. V5library`data/coarse-quality/us-osm-country-controls-v5/build/country-screen.so`,2,003,456bytes/SHA`9c81c86e3605738430b1c8f9f762bce71830740e5c46737485371ef8c0561166`. Reuse readonly, no installs/pulls/downloads.

Safe saved-evidence recovery, no native/Docker/national PBF/producer/provider calls:

```sh
python3 -B docs/evidence/coarse-osm-country-exec-2026-10-30/verify_closed.py
python3 -B docs/evidence/coarse-osm-way-batch-2026-10-30/verify_closed.py
python3 -B docs/evidence/coarse-osm-lookup-2026-10-30/verify_replay.py
```

Optional`--local-assets` reads ignored closed inputs/probe/witnesses and decodes only the saved probe; no national source read. Source arrays/qualifications are evidence, not nationwide accuracy. Keep all reference-request budgets consumed; no new provider/paid/DB/commit/push/deploy/model switch is implied. Preserve local configuration/cloud`DATABASE_URL`.



## Default coarse app

Start or reuse `http://127.0.0.1:3000/`. `npm run dev` is sufficient; no database, Python or Docker is required. Dependencies are already installed here. The browser still uses an online basemap. Safe readiness check:

```sh
curl --fail --silent --max-time 3 http://127.0.0.1:3000/api/estimate
```

Expect `provider: coarse`, `health: ready`, `engineVersion: coarse-road-grid-v9`, `minMinutes: 30`, `maxMinutes: 720`. The slider defaults to two hours; change/release it for automatic estimation, or use the optional compute button for coordinate edits. Connected-provider selection retains the old hosted/Valhalla path; openrouteservice remains capped at 60 m and spends quota only on computation. No hosted computation was made for the coarse milestone.

Earlier v1 saved-history milestone: **30 server tests and live DB integration pass; check/typecheck/ordinary build/Vercel-target build pass**. The local generated Vercel handler computes San Diego 6h, Denver 10h and New York 12h with zero routing fetches, keeps `/api/experiment` disabled, handles missing database configuration, and packages **5,581,861 bytes** without raw inputs, environment files or embedded DB/API-key values. Chrome verifies private cloud save/reload/model replay. [Saved-history evidence](evidence/saved-history-2026-10-22/README.md) records the new checks. The earlier [coarse milestone](evidence/coarse-estimator-2026-10-22/README.md) retains its 42 national in-process cases; the grid model/data were unchanged at that milestone. Current v9 validation is above; older milestones retain their original scope. These are software/local packaging checks; travel-time accuracy, all-origin completeness, cloud cold/warm behavior and peak memory remain unverified.

Raw Natural Earth downloads are cached at ignored `data/coarse-sources/natural-earth-v5.1.2/`; [regeneration commands](local-development.md#regenerate-the-coarse-grid) enforce pinned hashes. The active artifact at `src/server/data/coarse-grid-v9.json` and preserved v1–v8 JSON files are intentionally exempted from the broad `data/` rule in both Git and Vercel ignore files and must accompany a commit/deployment. Ignore-rule checks include these files while excluding raw downloads, evidence and environment files from Vercel uploads. Do not commit the raw downloads or secrets. The schema now contains `saved_histories` and the starter `todos`; PostgreSQL retains twenty summaries per private browser owner. Geometry is not stored. Inactive owners are not purged automatically, and there is no global owner-count cap or public-write rate limit yet.

## Preserved detailed baseline

| Item | Value |
| --- | --- |
| App | `http://127.0.0.1:3000/experiment` when the existing server is live; use Vite's printed port after restarting |
| Worker | `http://127.0.0.1:8787`, loopback only |
| Graph / cuts | `two-hour-region-v2` / `two-hour-region-v2-cuts` under `data/compact-pilot/` |
| Graph identity | `52b34545379adf83ad09175e7d29b5c445b7cf4193fee0f9b5d10afe0904fda1` |
| Bounds | `[-118.2,31.5,-114.6,34.7]`, west/south/east/north |
| Graph | 8,136,898 states; `exploratory-static-car-v3` plus **`member-scoped-geometry-v1`** |
| UI default / accepted range | 120 minutes / 1–720 whole minutes; range acceptance is not geographic coverage |
| Qualified coverage | Five reference sources have zero detected cuts at 120 m; first cuts 128 m 05 s–135 m 20 s; six-hour cases clip |
| Output | Sampled reachable roads, not a filled experimental isochrone; all-origin/source completeness and real border access unverified |

The optional connected model uses the separate provider path, capped at 60 minutes for hosted driving. Its key is already configured locally. The default coarse estimator and offline experiments must not call it or use hosted fallback. Basemap tiles use the network independently.

## Detailed-engine read-only recovery checks

From the repo root:

```sh
git status --short
git branch --show-current
lsof -nP -iTCP:8787 -sTCP:LISTEN
lsof -nP -iTCP:3000 -sTCP:LISTEN
curl --fail --silent --max-time 3 http://127.0.0.1:8787/health
curl --fail --silent --max-time 3 http://127.0.0.1:3000/api/experiment
```

Both JSON responses should report `ready: true`, the full graph identity above, the same bounds, `maxMinutes: 720` and `publicApiCalls: 0`. GET health/config spends no routing quota. A 503 can mean the worker is loading, the app was launched without the local opt-in, or the local API is disabled on Vercel; inspect the matching terminal/process before restarting.

Earlier recovery found **two different apps on port 3000**,  one on IPv4 and another on IPv6. Those listeners later disappeared; the documented launcher restored the qualified app/worker on October 22. Use **`127.0.0.1`**,  not an assumed `localhost` mapping. Do not stop the unrelated app. PIDs and tool-session IDs are not durable; discover owners again rather than reusing a PID from old logs.

Verify saved evidence and current producer files without recomputation:

```sh
python3 -B - <<'PYTHON'
import hashlib, json
from pathlib import Path
for directory, recipe in [('two-hour-region-2026-10-19', 'final-recipe-sha256.json'),
                          ('six-hour-preflight-2026-10-19', 'recipe-sha256.json'),
                          ('source-outgoing-build-2026-10-19', 'recipe-sha256.json'),
                          ('source-outgoing-2026-10-19', 'recipe-sha256.json')]:
    evidence = Path('docs/evidence') / directory
    for filename, root in [('evidence-sha256.json', evidence), (recipe, Path('.'))]:
        expected = json.loads((evidence / filename).read_text())
        for name, checksum in expected.items():
            with (root / name).open('rb') as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == checksum, name
        print(directory, filename, len(expected), 'files match')
PYTHON
```

At this handoff, **87 baseline evidence / 187 producer files** match. The [six-hour preflight evidence](evidence/six-hour-preflight-2026-10-19/README.md) also matches **79 evidence / 83 producer files**. The new [first-build handoff bundle](evidence/source-outgoing-build-2026-10-19/README.md) binds **28 evidence files / 151 combined build/profile producer files**,  and includes its own safe verification command. The [final calibration bundle](evidence/source-outgoing-2026-10-19/README.md) adds the exact repeat, completed result, fresh checks and next-phase analysis, with 152 combined producer bindings. Both builds’ eight payloads and the existing regional proof bindings were verified end to end. The checksum-only loop above covers all four bundles. These host checks do not rerun the expensive independent/native proofs or supply new capped resource measurements. Inspect future mismatches against authorized work; do not restore files blindly.

Preserved October 21 calibration validation: **20 adapter/server passes; 212 routing cases (203 pass, nine existing skips); check/typecheck/regular build pass**,  with the existing Biome database warning. The Vercel-target build was not repeated for these offline-only changes. Earlier milestone/preflight test counts and Vercel packaging results remain in their named reports. Fresh app/worker GET checks are ready on the same graph with zero provider calls; no new browser/search performance claim is made.

Historical reports moved into `docs/archive/`; evidence paths and checksum-bound indexes stay fixed, with four top-level forwarding pages preserving their links. Frozen diagnostics can still use former report paths; locate their basenames in the archive. The earlier [handoff audit](evidence/handoff-audit-2026-10-19/README.md) remains historical. Current link/anchor and diff checks pass; detailed-engine logs are in the final calibration bundle; current app logs are in the saved-history evidence. Preserve sealed evidence and all local-only assets.

## Start or recover the detailed experiment

If the correct app/worker are live, reuse them. Otherwise, after checking for an already-loading worker:

```sh
npm run dev:experiment
```

This starts/reuses the qualified worker, checks graph identity and starts the app with `LOCAL_ROUTING_EXPERIMENT=1` only in its child process. It preserves environment files. Graph verification/reload/indexing takes about two minutes on this Mac; do not launch duplicate workers while it loads. Use Vite's printed port if 3000 is occupied. A mismatched worker causes a clear rejection, not automatic replacement. The launcher stops only children it created; a worker it reused stays alive after Ctrl+C.

If only the worker is missing while the intended opt-in app is already running, start the worker in its own terminal:

```sh
python3 -B routing/experiment.py --graph-run two-hour-region-v2 --cuts-run two-hour-region-v2-cuts --port 8787
```

To switch graphs, identify and stop only the owned worker (prefer its terminal's Ctrl+C), then use the matching graph/cut pair. Previous baseline:

```sh
npm run dev:experiment -- --graph-run experiment-region-v1 --cuts-run experiment-region-v1-cuts
```

Native runtime prerequisites are already present: Python 3.13.5, Node 24.5.0, npm 11.6.0, Apple Clang 17 arm 64, matching compiled binary and local datasets. Future offline construction also needs Docker and the pinned cached images in the report. Node dependencies are installed; do not install/upgrade tools merely to resume. The host has 16 GiB RAM; about **167 GiB disk was free after the exact repeat**. Measure again before expansion. Fresh GET health/config both report ready, the qualified identity and zero provider calls; Docker has only the retained healthy Valhalla container, with no calibration batch running.

A fresh live validation, when justified, uses an unused output name and the actual app port:

```sh
node routing/verify-experiment.mjs --graph-run two-hour-region-v2 --run-name handoff-smoke-new --port 3000
```

This makes local requests only; do not reuse a completed run name. The verifier's no-flag default still targets the older graph, so the explicit flags matter. For a manual smoke, compute San Diego at 120 m: expect **0 / 805** reached edges and an unverified-coverage label. At 360 m expect **628** and an incomplete warning; Yuma can clip much earlier. Documentation writes can reload the development page and clear an in-progress result; pause writes during browser verification.

## Local assets and frozen recipes

| Directory | Role |
| --- | --- |
| `data/resource-pilot/two-hour-base-owners-v1` | Completed bounded owner diagnostic and frozen profile snapshot |
| `data/compact-pilot/source-outgoing-v1` | Completed first storage calibration: eight identical payloads, manifest/report, recipe snapshot and supplemental fixtures |
| `data/resource-pilot/source-outgoing-validation-v1` | Completed `result.json`, fresh checks/health, next-phase analysis, mutable `active-work.json` and final evidence collector |
| `data/compact-pilot/source-outgoing-v1-rebuild` | Completed exact repeat: eight identical payloads, 2.416 GiB / 1,555.84 s, manifest/report and fixtures |
| `data/coverage-pilot/six-hour-plan-v1`, `six-hour-catalog-v2`, `six-hour-checksums-v1` | Unclipped six-hour plan, official current footprints/listings and partial publisher-checksum observations |
| `data/source-pilot/six-hour-cached-v1`, `data/coverage-pilot/six-hour-cached-v1` | Completed cached-source merge and partial census/admission hold; preserve reports and recipe snapshots |
| `data/coverage-pilot/six-hour-validation-v1` | New tests/build/check logs, resource analysis and evidence collector |
| `data/compact-pilot/two-hour-region-v2` | Current graph/CSR/native binary, summary, oracles, manifest, native proof, release and two-hour acceptance |
| `data/compact-pilot/two-hour-region-v2-rebuild` | Independent exact rebuild |
| `data/compact-pilot/two-hour-region-v2-cuts` | Complete source-linked `cut-nodes.json` / report; next preflight input |
| `data/coverage-pilot/two-hour-region-v2` | Prepared OSM XML/census/resource report |
| `data/source-pilot/two-hour-parent-v2` | Merged parent source/report with Arizona |
| `data/compact-pilot/scoped-current-v1` | Scoped restriction-policy calibration against the previous routing payload |
| `data/experiment-pilot/two-hour-map-v2`, `data/experiment-pilot/two-hour-areas-v2` | Raw live API responses/reports |
| `data/experiment-pilot/two-hour-region-v1` | Planning/acquisition/run logs and helpers; the `v1` name here does not mean the rejected graph |
| `data/valhalla/sources`, `data/valhalla-v2` | Dated road inputs, retained prior parent/source/admin products and Valhalla baseline |

Earlier frozen references under `data/` are still dependencies. Preserve the whole existing data/proof chain; the table is not a standalone export manifest. The current builder/reader image IDs are pinned in the report and were confirmed cached during this audit.

The accepted recipe sequence is `two-hour-source-v2.mjs` → `two-hour-region-prepare-v2.mjs` → `scoped-region.mjs` → **`scoped-region-verify-v3.mjs`** (bootstrap plus v2 field verifier) → `scoped_native.py` → **`scoped-region-cuts-v2.mjs`** → `two_hour_release.py`. Calibration prerequisites and exact commands are in the report. These completed producers, native/release checks and the evidence collector **refuse overwrite or create outputs**; do not rerun them as health checks.

The completed owner-profile and source-outgoing build producers are also frozen. Each build manifest binds 149 scripts. The completed `source_outgoing_result.py` and final collector are now frozen too; they ran unchanged from their pending checkpoint versions. The final recipe index combines 152 producer files, including the result helper. Keep `scoped_load.py` and the named restriction policy. The first `two-hour-region-v1` graph and unversioned scoped verifier/cut wrapper preserve rejected or superseded attempts. **Do not edit sealed files, even for formatting**,  or overwrite graph/source/report bytes to bypass identity failures. Version a changed producer and bind all dependencies explicitly; a fresh output name alone does not rebind downstream hardcoded paths. Never manually edit `src/routeTree.gen.ts`, commit secrets, erase failed attempts or change the hosted environment to enable the experiment.

## Suggested resume message

> Continue Geo Planner at v9/HEAD648c731. User authorized autonomous bounded work until real guidance is needed. Read AGENTS/current docs and docs/evidence/coarse-osm-extraction-2026-10-30/README.md. Native cell/filter V10passes304Linux and exact tiny four-pass output; readonly V12passes38Linux, capacity controller V1passes11Linux/tiny2passes, all closed/proofs pass. Actual national cell census V1stopped at2GiB bank cap after1,577,373,696recognized nodes/98.2%, no source EOF/second pass/complete bank.31parts2.08GB/60closed files preserved; worker2/not OOM/absent, source/fine/oldSQLite unchanged. Safe verify_cell_census_stop_v1.py. Next separately version lossless repeated-ID-gap runs with canonical raw fallback; keep IDs/cells/order and2GiB/4GiB/four-hour/64GiB caps, no resampling. Qualify codec/bank/filter/independent proofs before another unused national freeze; optional prefix recompression is prefix-only evidence. Retained reservation55,406,628,967; new owned work aftertmp13,044,412,313bytes. Preserve all used producers/recipes/failures; no provider/paid/DB/push/deploy/model switch. Work local/uncommitted; ignored assets absent fresh HEAD.
