# Same-provider benchmark completed: 83 finite pairs

October 24, 2026. **The user-approved 29-request run succeeds on all 29 cases**, with no retries, replacement, auth/status probe, fallback or paid upgrade. Reusing the saved six controls and 48 frontier results yields **83/83 finite ORS comparisons**. All engine/build/graph/OSM metadata matches; no snap exceeds100m. [Authorization](authorization.json), [frozen plan](../coarse-benchmark-plan-2026-10-24/plan.json), [complete comparison](comparison.json), [raw 29 capture](reference/sha256.json).

This is measured acquisition/reporting only. Base remains `37ff14b`; the report, previous calibration/reference tooling and floating-map UI remain local/uncommitted. No app routing/grid/source-data/DB/env/schema/dependency change, commit or deployment. The active graph stays v8, SHA `2beb2fb6d9af6e07f37c5ba53acdeca2da1334c31a5fadd1371efd5453134910`.

## Model comparisons against one reference provider

All 83 routes use ORS 9.10.0, build `2026-08-13T11:53:14Z`, graph `2026-09-21T10:31:27Z`, OSM `2026-09-13T23:59:59Z`. These are observed development cases, not a fresh holdout, national/area accuracy, traffic truth or a demonstration that this engine is correct. The selected road-class policy is the already-saved 105→95 /80→85km/h prototype; no new model/search/parameters were fitted during acquisition.

| Development set | Cases | Current v8 MAE min | Saved prototype MAE min | Improve / regress |
| --- | ---: | ---: | ---: | ---: |
| Original regional | 11 | 11.213 | 6.093 | 8 / 3 |
| Broader regional | 24 | 10.016 | 8.517 | 14 / 10 |
| Long-horizon frontier | 48 | 52.273 | 35.097 | 32 / 16 |
| All development cases | 83 | 34.612 | 23.567 | 54 / 29 |

Across 83 cases the prototype's mean absolute difference improves **31.91%**; median changes 21.295→13.628min and nearest-rank p90 93.697→56.730min. The frontier-only p90 changes 116.332→70.165min. At 6/10/12h, frontier means change 33.985/44.060/78.775→27.694/34.298/43.299min. All individual gains/regressions, set/horizon/origin metrics, signed/absolute/percentage differences, route distances and snaps remain in the full ledger. No combined mean replaces the per-set results.

The improvement is encouraging but uneven. **29 cases regress**, including a worst **+71.547min** absolute-error increase (`frontier/hays-ks-720-inside`); the ten largest regressions are retained in [independent analysis](analysis.json), with the complete ledger in the comparison. Frontier classifications change 23→31 correct,17→8 false reachable,5→6 missed reachable; three remain ambiguous. At12h missed reachable increases 2→4 even though the aggregate12h error improves. The policy therefore has unresolved individual-route/classification regressions, not merely a publication checkbox.

## Reference difference and historical decision

Every one of the 35 old OD pairs has a longer ORS estimate than saved Valhalla: mean signed/absolute **15.491min**, median **14.458min**, mean absolute percentage **16.484%**. The six-route control's observed discrepancy extends to this complete selected older set. Engine/profile/data/date and chosen route remain confounded; do not apply a universal offset, scale, city/region exception or assume which engine is truth.

The historical105→95 /80→85 candidate **remains rejected under its original frozen Valhalla gates**. Those reports, thresholds, producer bytes, failures and all original 35 reference outcomes stay unchanged. The newer ORS comparison is separate descriptive evidence and cannot retroactively turn that failed experiment into an accepted one. The benchmark plan explicitly selected a common-provider comparison before the 29 outcomes, with no new model acceptance threshold or activation permission. Runtime remains v8.

**Next work is offline:** use all 83 saved source/path components and both reference comparisons to investigate the generic road-class/geometry features behind the regressions. Define one prospective timing-cost revision and its reference policy/per-set/tail/classification/physical/runtime/Vercel gates before producing it. Keep old gates/results as historical evidence and report Valhalla sensitivity explicitly; do not silently relax criteria to ship the saved failed artifact. No exact new parameter values or thresholds are selected by this acquisition report. No further provider acquisition is needed for that diagnostic and candidate specification, and **no further call is authorized**. [Ordered next task](../../next-steps.md).

## Acquisition and reproducibility

Exactly29 fixed POSTs ran `2026-10-24T20:24:10.359Z`–`20:27:13.486Z`. Every HTTP status is 200; minimum start interval **6500ms**, returned quota remaining **1999→1971**, maximum retained response **65,474B**, HTTP-plus-body elapsed **443–3138ms** per request. These are this run's returned counters, not a dashboard/current-quota reading; earlier captures retain their earlier counter values. HTTP-plus-body time excludes persistence and is not provider engine-search time. No known key echo required redaction and only whitelisted nonsecret headers are retained. All 29 attempted ledger entries and all 83 joined cases remain; no failure or large-snap exclusion was used. New29 max snap 37.634m; all 83 max79.634m, so primary and <=100m sensitivity retain all 83.

The untouched [tested runner](../../../scripts/compare-coarse-benchmark.ts) pins plan SHA `77d357142dfe266274c3dc6693732963b296e027888b036725f70b27d5401a93`. The [capture manifest](reference/sha256.json), [source/check bindings](checks.json) and top-level report manifest preserve exact producer/source/request/response/result identities. Raw responses retain `© openrouteservice by HeiGIT | Data from OpenStreetMap`, CC-BY-SA 4.0, separately from the NE/Census runtime model. Saved54 references are reused byte for byte. The original failed experiment, six-route result and 29-tool readiness reports remain sealed and unchanged.

Two actual CLI replays match byte for byte; a fresh restoration of the preserved capture also reproduces the report. An [independent Python audit](analyze.py) reads all 83 raw responses and frozen model records, verifies hashes/ODs/durations/distances/snaps/signed/absolute/percentage arithmetic and pooled per-set/tail/gain metrics, plus29-request timing/header/quota records. Its output repeats identically. Previous15 synthetic tests/check 164/typechecks/build remain their [dated readiness proof](../coarse-benchmark-plan-2026-10-24/README.md); no app implementation or sealed tool changed, so graph/source/DB/server/Vercel/build suites were not rerun for this capture/report. [Safe replay/restoration commands](../../local-development.md#same-provider-benchmark).

The following command **already ran once**; its exact 29-call approval is consumed. Do not rerun/retry, including into a different directory:

```sh
node --import tsx scripts/compare-coarse-benchmark.ts --capture data/coarse-quality/benchmark-reference-v1 --confirm-29-requests
```

Read-only independent audit from the repo root, without an env file, key or network:

```sh
python3 -B docs/evidence/coarse-benchmark-reference-2026-10-24/analyze.py > /tmp/coarse-benchmark-independent-analysis.json
```

Before capture, the [official endpoint announcement](https://ask.openrouteservice.org/t/deprecating-api-openrouteservice-org-in-favour-of-api-heigit-org/7912) and [official quota/snap FAQ](https://giscience.github.io/openrouteservice/frequently-asked-questions#when-and-how-does-my-quota-reset) were refreshed. [Review record](provider-review.json) distinguishes published defaults from actual returned headers. No new account/plan/terms acceptance, extra auth/status/quota probe or paid upgrade occurred. Future raw references remain distinct from any runtime artifact.
