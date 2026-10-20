# Historical routing recipes

**Archived report.** This describes an earlier run or proposal. Use [the current handoff](../agent-handoff.md) and [next steps](../next-steps.md) for active instructions.

Moved from local development on October 19, 2026. These commands describe named earlier experiments, including failed or superseded admission gates. They are not the current app startup or next task. Start with [the agent handoff](../agent-handoff.md); use [the two-hour report](../two-hour-region.md) for the qualified baseline. Preserve completed output directories and sealed recipes.

The research recipes below preserve named historical experiments. Their old graph/default/admission statements apply to those runs; use [the two-hour baseline](../two-hour-region.md) for the current worker, completed resource gates and next six-hour task.

## Run the quota-free precomputation pilot

With the completed regional graph and cached tools image, run `npm run routing:anchors`. It computes/reuses a small directed coordinate matrix in a network-disabled container; no app server or provider key is needed. Use `-- --max-new-rows 8` to checkpoint a partial batch, and rerun to resume. See [exact commands, format, measurements and limitations](offline-anchor-pilot.md). Run `npm run test:routing` for the additional pilot tests. This does not expand the browser’s driving range.

## Run the static turn-aware reference

`npm run routing:reference` imports a small downtown subset from the cached regional PBF, builds/reads directed landmark fields and checks bounded search/certificates against a separate Bellman–Ford oracle. It uses Docker with networking disabled and a 4 GiB limit; the initial extraction needs that memory even though subsequent reference work is small. Results remain in ignored `data/reference-pilot/downtown-static-v1/`. See [exact model, measurements and limitations](state-routing-reference.md). This experiment does not change browser range limits.

## Compare grouped cell summaries

After `npm run routing:reference`, run `npm run routing:cells`. It reads that frozen reference through a read-only mount, builds/verifies three binary cell indexes, and checks grouped certificates plus exact refinement against the independent oracle. It uses Docker networking disabled, 2 GiB memory and no API key/provider calls. Repeating the command reuses indexes and reruns qualification. See [format, counters, comparative measurements and limitations](cell-routing-experiment.md). Exact queries are currently slower than direct search; browser range limits are unchanged.

## Run the compact native baseline

After the static reference is prepared, run `npm run routing:native`. This wrapper currently requires macOS, `/usr/bin/sandbox-exec`, Python 3.11+ and an installed C++17 compiler/standard library (tested with Apple Clang 17 on arm64). It uses the frozen reference directly, compiles a small CSR/Dijkstra executable, denies networking and checks every selected cost/membership against the Python oracle. It neither loads `.env.local` nor uses the provider. Output is ignored under `data/native-pilot/downtown-native-v1/`; repeat runs verify inputs and replace timing reports. Changed inputs/code/compiler require `-- --run-name new-name`. The agent tool sandbox needed an outer exception to allow the benchmark's own network-denying sandbox. See [commands, format, raw evidence and limitations](native-routing-baseline.md). Native local timings are not WASM/Vercel results, and long budgets still hit the downtown cut boundary. Browser limits remain unchanged.

## Qualify maneuver history and interior destinations

Run `npm run routing:model` against the existing frozen reference. It creates a separate v2 model in ignored `data/model-pilot/downtown-maneuvers-v2/`, with Docker networking disabled, two CPUs, 2 GiB memory and read-only source/recipe/reference mounts. It restores qualified prohibited via-way maneuvers, preserves unsupported-rule closures and checks partial destinations against a sink oracle. On macOS with the native baseline compiler prerequisites, follow with `npm run routing:model:verify` to check the changed graph using the unchanged C++ kernel under network denial. Run that verification again after replacing model reports: it is tied to the exact manifest checksum. Changed inputs/code require `-- --run-name new-name` on both commands. The v1 assets/environment/app cap remain unchanged. See [supported rules, exact commands, evidence and remaining limits](maneuver-routing-model.md).

## Run the regional capacity probe

`npm run routing:regional` prepares and qualifies the bounded San Diego–Chula Vista–Tijuana corridor from cached OSM. Docker denies networking and enforces two CPUs/4 GiB; the source and downtown semantic reference are mounted read-only. `npm run routing:regional:rebuild` independently reimports/repacks and compares bytes without rerunning all expensive oracles. `npm run routing:regional:verify` uses the existing macOS native sandbox/compiler setup and records five timing samples per case/mode. Outputs are ignored under `data/regional-pilot/san-diego-tijuana-corridor-v2/`. All commands accept `-- --run-name name`; changed inputs/code/profile require a new identity. See [exact commands, failed wider attempt, measured RAM, cut exits and border findings](regional-routing-capacity.md). The wider importer exhausted 4 GiB; do not expand it or raise the app cap on the strength of native search timings alone. Hosted configuration and prior graphs are preserved.

## Qualify control-point barrier access

Before further coverage expansion, the separate v3 experiment can be rechecked with `npm run routing:barriers:rebuild` and `npm run routing:barriers:verify`. A fresh build uses `npm run routing:barriers -- --run-name new-name`; the recorded default is already complete and refuses overwrite. Build/rebuild read the frozen v2 corridor and downtown reference, deny Docker networking, and enforce two CPUs/4 GiB. Verification uses the same macOS compiler/network sandbox prerequisites as the native baseline. Outputs are ignored under `data/barrier-pilot/san-diego-tijuana-barriers-v3/`. See [exact commands, explicit access policy, route evidence and limits](barrier-access-model.md). Six sampled cross-border directions now connect in the static model, with no border queues/delays; complete long-range coverage and browser integration remain pending. The underlying full-tree importer still needs memory reduction.

## Run the streaming importer and wider retry

`npm run routing:import -- --case downtown-v2|corridor-v2|corridor-v3|wide-v2` selects one case (substitute a single name). The first three reproduce frozen graph/audit/packed bytes; the last retries the saved wider v2 XML under the same 4 GiB/two-CPU cap and checks four origins against independent costs. Each case uses a fresh Docker container with networking disabled and read-only cached inputs. Recorded defaults under `data/import-pilot/stream-v1-<case>/` are complete and refuse overwrite; add `--run-name new-name` for a reproduction. `npm run routing:import:verify` checks the wider graph with the unchanged native kernel under the existing macOS network sandbox. See [exact commands, prerequisites, worker/cgroup measurements and crossing uncertainty](streaming-import-capacity.md). The optimized module preserves v2/v3 semantics; old workflows remain frozen references. All 60-minute/longer wide cases hit cuts, and the Otay route has source-marked access uncertainty. No provider calls, downloads or environment changes are needed.

## Qualify the wider v3 graph

The recorded wider v3 build can be rechecked with `npm run routing:wide:rebuild` and `npm run routing:wide:verify`. A full new run uses `npm run routing:wide -- --run-name new-name`; the default completed graph refuses overwrite. It reads the saved wider XML/v2 graph and downtown fixtures with Docker networking disabled, two CPUs and 4 GiB. Rebuild compares seven graph/audit/source artifacts; verification reuses the unchanged native kernel under the existing macOS network sandbox. Outputs are ignored under `data/barrier-pilot/san-diego-tijuana-wide-v3/`. See [exact commands, source audit, resources and route/cut GeoJSON](wide-v3-routing.md). Twelve selected city directions connect in the static model, while three Otay source uncertainties remain explicit; real eligibility, border waits and complete long-range coverage remain unverified. No provider/key/environment changes are involved.

## Preflight the broader cached buffer

`npm run routing:coverage -- --run-name fresh-name` prepares the pinned `[-117.4,32.3,-116.6,33.2]` San Diego/northern-Baja rectangle and counts road/state bounds with disk-backed SQLite. It requires the cached parent PBF, tools image and completed wider v3/rebuild/source artifacts; no provider key or network is used. Docker enforces two CPUs/4 GiB and read-only input mounts. Completed or failed identities under ignored `data/coverage-pilot/` refuse overwrite. The recorded `san-diego-tijuana-buffer-preflight-v1` and `san-diego-tijuana-buffer-preflight-r2` produce identical PBF/XML/SQLite bytes. Preparation reaches the cap with reclaim pressure but no OOM kills; the measured-count forecast exceeded the old importer’s cap for a full graph. The [compact follow-up](compact-routing-import.md) now builds and qualifies this same candidate; these records preserve the earlier preflight gate. See [measurements, exact prerequisites, source boundaries and evidence](coverage-buffer-preflight.md). No browser limits or environment values change.

## Run the compact importer and larger buffer

`npm run routing:compact -- --case downtown-v2|corridor-v2|corridor-v3|wide-v3|buffer-v3` selects one case; substitute a single name. The four small/frozen cases require exact graph/audit/packed parity before `buffer-v3` is admitted. Each uses fresh network-disabled Docker with two CPUs/4 GiB RAM and read-only inputs. Recorded outputs are ignored under `data/compact-pilot/compact-v1-<case>/`; existing attempts refuse overwrite. Parity reproductions accept `--run-name fresh-name`; the buffer gate binds the four recorded defaults and current worker fingerprints. The larger source is the prepared preflight XML, so no download/extraction/provider request is repeated.

`npm run routing:compact:reload` separately rechecks graph JSON/CSR under 1 GiB; add `--run-name fresh-name` to preserve an earlier reload. `npm run routing:compact:verify` uses compact JSON reload and the unchanged native kernel under the existing macOS network-denying sandbox/compiler prerequisites; it accepts `--run-name` for another completed buffer. See [exact commands, byte parity, resource/timing scopes and limits](compact-routing-import.md). RAM caps and Docker swap allowance are recorded separately. These experiments preserve v3 access and app/provider limits; source crossing uncertainty and complete long-range coverage remain unverified.

## Reimport compact OSM inputs with swap disabled

`npm run routing:inputs -- --case downtown-v2 --series fresh-name` uses compact node/way storage and a separate explicit no-swap Docker recipe. Run `corridor-v2`, `corridor-v3`, `wide-v3`, then `buffer-v3` with the same series; the final case requires four completed same-code parity proofs. All cases reimport cached XML and require exact frozen graph/audit/packed/source-excerpt bytes. Original oracle/native results are checksum-verified and reused on identical outputs. No extraction, download, provider key or request is needed.

The recorded `input-v1` series refuses overwrite; fresh series write ignored `data/input-pilot/<series>-<case>/`. Docker enforces two CPUs/4 GiB RAM with `--memory-swap 4g`, and the worker requires `memory.swap.max=0`. Historical wrappers retain their previous swap allowance. See [exact commands, resource measurements and remaining coverage limits](compact-osm-input.md). New geography still needs a resource preflight and new route/cut qualification.

## Inventory cuts and preflight the next cached increment

`npm run routing:cuts` inventories all audited cut states using the saved full oracle fields and attaches source boundary links. `npm run routing:coverage:next -- --case calibration` runs six native fixture comparisons, then requires byte-identical preparation of the current buffer. `--case candidate` prepares/counts the fixed larger California/northern-Baja profile after checking that proof; it does not build a new graph. All three use the unchanged two-CPU/4 GiB cap, container swap disabled, read-only inputs and 200 ms cgroup composition sampling. They need cached source/graph/proofs, without credentials or provider calls.

Recorded outputs are ignored under `data/coverage-pilot/buffer-cut-inventory-v1`, `staged-calibration-v2-r4` and `staged-candidate-v2`; use `--run-name fresh-name` to preserve old attempts. Candidate reproductions accept `--calibration-run fresh-calibration-name` and bind the recorded default cut inventory. Run `python3 -B docs/evidence/cut-buffer-2026-10-17/analyze.py` to recheck hashes/witness costs/resource evidence. See [exact commands, rejected shortcut, count bounds and held admission](coverage-increment-preflight.md). That original preparation reaches the cap with limit pressure despite zero OOM/swap. The resource follow-up below now passes a capped-import admission rule; this historical recipe remains frozen.

## Reproduce sparse preparation and complete-workload memory checks

`npm run routing:tools:sparse` verifies the cached base image and six locked wheels, downloading only missing tooling (2,354,828 bytes total), then builds the separate offline reader image without network. `npm run routing:resources` profiles an unchanged frozen-buffer parity import. `npm run routing:sparse -- --case calibration` qualifies six native fixtures and exact old-buffer XML; `--case candidate` requires that proof and exact candidate XML/census. `npm run routing:paged` repeats the frozen import/export with per-file checksum cache advice. `npm run routing:sparse:paged -- --case candidate` applies that advice to the same sparse preparation, reusing its verified calibration. No road downloads, credentials or provider calls are needed.

All experiment defaults are completed and refuse overwrite; pass `--run-name fresh-name`. Candidate commands accept `--calibration-run fresh-calibration-name`. They retain two CPUs/4 GiB, swap/network denial and read-only cached inputs, writing ignored `data/resource-pilot/` and `data/sparse-pilot/`. Run `python3 -B docs/evidence/sparse-resource-2026-10-17/analyze.py` to verify recorded code/source/graph/tooling hashes and admission. The combined recipe measures 2.94 GiB preparation / 2.09 GiB complete parity import and meets a 25% margin estimate of 3.67 GiB. It admits only a separate capped new build; coverage and 10–12-hour capability remain unproven. See [exact pins, measurements, Linux test limitation and next qualification](sparse-routing-resources.md).

## Reproduce the admitted coverage increment

`npm run routing:increment` builds the exact cached next-candidate XML under two CPUs/4 GiB RAM, with network and swap disabled. `npm run routing:increment:qualify` first calibrates the queue-based independent oracle on all five frozen fields, then compact-reloads the new graph and runs fresh full/bounded/partial/city checks. It adds a qualification identity/final manifest without changing the build manifest. `npm run routing:increment -- --stage rebuild` independently reimports and compares all seven output artifacts. `npm run routing:compact:verify -- --run-name increment-v3` uses the unchanged native verifier on macOS under network denial. `npm run routing:increment -- --stage cuts` inventories every audited endpoint/history state against the sealed qualification.

Recorded defaults are completed under ignored `data/compact-pilot/increment-v3`, `increment-v3-rebuild` and `increment-v3-cuts`. For reproduction, give the build a fresh `--run-name name`, use that same name for qualification/native verification, and pass fresh output names plus `--source-run name` to rebuild/cuts. Existing identities refuse overwrite. Read [exact source/code pins, resource scope, commands and remaining cuts](regional-coverage-increment.md) before running. This historical qualification takes about 28 minutes and peaks at 3.74 GiB; the follow-up below restores headroom without changing its functional results. Run `python3 -B docs/evidence/coverage-increment-2026-10-17/analyze.py` to recheck the recorded evidence. No credentials, provider calls or downloads are required.

## Reproduce lean qualification and the next one-hour preflight

```sh
npm run routing:qualify:lean
npm run routing:coverage:hour -- --case calibration
npm run routing:coverage:hour -- --case candidate
python3 -B docs/evidence/hour-preflight-2026-10-17/analyze.py
```

Requires the cached source/graphs/proofs and pinned tool images; no provider key or downloads are used. New jobs enforce two CPUs/4 GiB/no swap/no network/read-only inputs. Defaults are completed under `data/qualification-pilot/virtual-sink-v1`, `data/coverage-pilot/hour-calibration-v1` and `hour-candidate-v1` and refuse overwrite. Use fresh `--run-name` values; candidate accepts `--calibration-run fresh-calibration-name`. The recorded preflight pins `virtual-sink-v1` as its prerequisite. Changing that prerequisite requires a new versioned recipe, not an edit to a saved identity.

Qualification takes **14.98 minutes / 1.55 GiB complete cgroup peak**, with unchanged functional summary/field/CSR bytes and reused native evidence. Calibration/candidate preparation take **205.80/208.06 seconds**, peaking at **2.96/2.93 GiB**. The candidate's worst-phase estimate with 25% margin is **3.85 GiB**, admitting a separate capped attempt. These commands prepare/census the candidate; the follow-up below now builds and qualifies it. See [exact source/code/tool pins, resource scope and limitations](hour-coverage-preflight.md).

## Reproduce the east/south hour qualification

```sh
npm run routing:hour
npm run routing:hour -- --stage qualify
npm run routing:hour -- --stage rebuild
npm run routing:compact:verify -- --run-name hour-v3
npm run routing:hour -- --stage cuts
python3 -B docs/evidence/hour-qualification-2026-10-17/analyze.py
```

Defaults `data/compact-pilot/hour-v3`, `hour-v3-rebuild` and `hour-v3-cuts` are completed and refuse overwrite. Use a fresh build `--run-name`, that same name for qualification/native verification, and separate fresh output names plus `--source-run name` for rebuild/cuts. The recipe binds the exact admitted XML/profile/proofs and retains two CPUs/4 GiB/no swap/no network; the native verifier runs separately on the Mac under network denial. In the recorded run it overlaps the independent rebuild; timings retain that load. Read [pins, measurements, commands and limits](hour-coverage-qualification.md). All five selected origins now reach zero potential cuts within an hour, while full source/real-world/10–12-hour coverage and browser integration remain unfinished.

## Preflight two-hour coverage and paged-ID preparation

```sh
npm run routing:coverage:two-hour -- --case calibration
npm run routing:coverage:two-hour -- --case candidate
python3 -B docs/evidence/two-hour-preflight-2026-10-17/analyze.py
```

Requires cached current graph/source/native/rebuild/fixture/cut proofs and pinned reader image; no key/download/provider quota is used. Defaults `data/coverage-pilot/two-hour-calibration-v1` and `two-hour-candidate-v1` are completed and refuse overwrite; use fresh `--run-name` outputs and candidate `--calibration-run fresh-calibration-name`. Same scripts/profile/image calibration is mandatory. Two CPUs/4 GiB/no swap/no network/read-only inputs remain enforced.

Calibration reproduces exact current XML/census and six fixture graph/audit results. Worker peak is 0.52 GiB, but reference completion sets the 3.11 GiB container peak. Candidate census completes in about 4.2 minutes at 4 GiB with 3,750 limit events and zero OOM/swap; its forecast with margin is 20.64 GiB. **Admission is on hold; do not launch a larger graph.** See [source envelopes, exact commands, resource scopes and next memory task](two-hour-coverage-preflight.md). Current one-hour graph/app behavior remains unchanged.


## Reproduce lower-memory preparation and frozen import parity

```sh
npm run routing:lifetime -- --mode isolated --case calibration
npm run routing:lifetime -- --mode isolated --case candidate
npm run routing:lifetime -- --mode batched --case calibration
npm run routing:lifetime -- --mode batched --case candidate
npm run routing:keys -- --case downtown-v2
npm run routing:keys -- --case corridor-v3
npm run routing:keys -- --case wide-v3
npm run routing:keys -- --case hour-v3
python3 -B docs/evidence/routing-lifetimes-2026-10-18/analyze.py
```

All defaults are sealed. Use fresh preparation `--run-name` outputs and candidate `--calibration-run name` with the same mode. Use `--series fresh-series` on every parity case; the hour case requires those three same-code smaller proofs. The cached two-CPU/4 GiB/no-swap/no-network/read-only policy remains. No key, download or provider quota is used.

Four batches preserve exact current/candidate IDs/XML/census and six fixture graphs at **2.17 / 2.60 GiB** complete peaks; isolation alone still hits the cap on the larger input. Numeric road keys reproduce all four frozen graph cases; the current peak is **2.925 GiB**, with file cache still dominant. Existing route/native evidence is reused by identical graph bytes. **Larger graph admission remains on hold**; the wrappers cannot build it. See [commands, output names, measurements, source limits and next task](routing-preparation-lifetimes.md).


## Reproduce completed-input, export and checksum lifetimes

```sh
npm run routing:io -- --case downtown-v2
npm run routing:io -- --case corridor-v3
npm run routing:io -- --case wide-v3
npm run routing:io -- --case hour-v3
npm run routing:io:bounded -- --case downtown-v2
npm run routing:io:bounded -- --case corridor-v3
npm run routing:io:bounded -- --case wide-v3
npm run routing:io:bounded -- --case hour-v3
python3 -B docs/evidence/routing-io-2026-10-18/analyze.py
```

Defaults `data/io-pilot/io-v1-*` and `data/io-bounded-pilot/iob-v1-*` are sealed. Use a fresh `--series` consistently within each version; current cases require its three same-code smaller proofs. Equality references remain the canonical `keys-v1-*` and `io-v1-*` series, regardless of fresh output names. Both versions retain two CPUs/4 GiB/no swap/no network/read-only inputs and exact original qualification bindings. The current peak falls **2.925 → 2.030 → 1.798 GiB**, with exact artifacts and zero pressure; this is preprocessing, not a new route benchmark. **Larger graph admission stays on hold.** See [file policies, measurements, scope and next task](routing-io-lifetimes.md).


## Reproduce restriction-member road lookup storage

With the canonical `data/io-bounded-pilot/iob-v1-*` baselines and original qualified graph records present:

```sh
npm run routing:members -- --case downtown-v2
npm run routing:members -- --case corridor-v3
npm run routing:members -- --case wide-v3
npm run routing:members -- --case hour-v3
python3 -B docs/evidence/routing-member-lookup-2026-10-18/analyze.py
```

Defaults `data/member-pilot/members-v1-*` are sealed. For a repeat, use the same fresh `--series members-repeat-01` on all four commands; the current case requires its three same-code smaller proofs. Equality references remain canonical `iob-v1-*`, regardless of fresh output names. The wrapper retains two CPUs/4 GiB/no swap/no network/read-only inputs, global duplicate-geometry detection and original qualification bindings. It retains lookup entries only for restriction-member ways, with a global per-way duplicate scan and unchanged fallback priority. Seventeen fresh small fixtures run in each worker; regional full/bounded/partial/native qualification is reused on identical graph bytes. See [measurements, exact scope and remaining limits](routing-member-lookup.md). This does not admit a larger graph or raise the app's 60-minute cap.

## Reproduce targeted control-point source evidence

With the canonical `data/member-pilot/members-v1-*` baselines and original qualified graph records present:

```sh
npm run routing:evidence -- --case downtown-v2
npm run routing:evidence -- --case corridor-v3
npm run routing:evidence -- --case wide-v3
npm run routing:evidence -- --case hour-v3
python3 -B docs/evidence/routing-source-evidence-2026-10-18/analyze.py
```

Defaults `data/evidence-pilot/evidence-v1-*` are sealed. Repeat with the same fresh `--series evidence-repeat-01` on all four commands; the current case requires its three same-code smaller proofs. Equality references remain canonical `members-v1-*`. Two CPUs/4 GiB/no swap/no network/read-only inputs and original qualification bindings remain enforced. This version keeps incidence indexes only for five required source control points and profiles indexing, transition evidence and the unchanged XML passes separately. It runs 11 fresh source-evidence/failure fixtures plus the prior 17 importer fixtures in each worker. See [measurements, scope and remaining limits](routing-source-evidence.md). Larger graph admission and the app's 60-minute cap remain unchanged.

## Reproduce compact base-graph ID storage

With canonical `data/evidence-pilot/evidence-v1-*` baselines and original qualification records present:

```sh
npm run routing:base-ids -- --case corridor-v3 --id-mode strings --series base-strings-v1
npm run routing:base-ids -- --case downtown-v2
npm run routing:base-ids -- --case corridor-v3
npm run routing:base-ids -- --case wide-v3
npm run routing:base-ids -- --case hour-v3
python3 -B docs/evidence/routing-base-ids-2026-10-18/analyze.py
```

The corridor-only string profile and default `data/base-id-pilot/base-ids-v1-*` series are sealed. Repeat with fresh series names, using the same ordered series for all four cases; the current case requires its three same-code/same-mode smaller proofs. Equality references remain canonical `evidence-v1-*`. Both modes enforce two CPUs/4 GiB/no swap/no network/read-only inputs and original qualification bindings. Ordered compact roads retain one ID key, with original string-set validation for unordered/generic inputs; outgoing lists and routing rules stay unchanged. Separate shallow-object and cgroup phase measurements explain the remaining memory. See [commands, results, invariants and limits](routing-base-id-storage.md). This does not admit a larger graph or raise the app's 60-minute cap.

## Reproduce range-advised source-evidence XML reads

With canonical `data/base-id-pilot/base-ids-v1-*` baselines and original qualified records present:

```sh
npm run routing:xml -- --case downtown-v2
npm run routing:xml -- --case corridor-v3
npm run routing:xml -- --case wide-v3
npm run routing:xml -- --case hour-v3
python3 -B docs/evidence/routing-xml-streams-2026-10-18/analyze.py
```

Defaults `data/xml-pilot/xml-v1-*` are sealed. Repeat with the same fresh `--series xml-repeat-01` on all four commands, smaller cases first; equality references remain canonical `base-ids-v1-*`. Two CPUs/4 GiB/no swap/no network/read-only inputs and original qualification bindings remain enforced. This version advises completed ranges during source-evidence XML reads, closes handles explicitly, records full read/EOF/advice accounting and preserves XML processing bodies. Earlier import XML readers remain unchanged. See [measurements, fixtures and exact scope](routing-xml-streams.md). Larger admission and the app's 60-minute cap are unchanged.


## Reproduce compact outgoing-road storage

With canonical `data/xml-pilot/xml-v1-*` baselines and original qualified records present:

```sh
npm run routing:outgoing -- --case downtown-v2
npm run routing:outgoing -- --case corridor-v3
npm run routing:outgoing -- --case wide-v3
npm run routing:outgoing -- --case hour-v3
python3 -B docs/evidence/routing-outgoing-2026-10-18/analyze.py
```

Defaults `data/outgoing-pilot/outgoing-v1-*` are sealed. Repeat with the same fresh `--series outgoing-repeat-01` on all four commands, smaller cases first; equality references remain canonical `xml-v1-*`. Two CPUs/4 GiB/no swap/no network/read-only inputs and original qualification bindings stay enforced. This version uses one node map and numeric offset/reference arrays, preserving per-node order and validation with frozen list fallback. Construction checkpoints include temporary cursor overlap. See [measurements, fixtures and next qualification-memory task](routing-outgoing-storage.md). Larger admission and the app's 60-minute cap remain unchanged.
