# Six matched-route references: material provider difference

October 24, 2026. **Six approved requests, six successful pairs, no retries or paid upgrade.** The user approved this exact separate budget with “Yes go ahead”; [authorization](authorization.json) binds the frozen plan and tested producer. Base commit remains `37ff14b`. This capture/report, the six-route tools, rejected calibration and separate floating-map UI are local/uncommitted. No model/grid/app/schema/env/dependency change, commit or deployment occurred in this acquisition follow-up.

## Measured result

The unchanged [control plan](../coarse-class-calibration-2026-10-23/control-plan.json) selects ranks 0/6/13/20/27/34 among all 35 older routes by saved reference distance, holding exact public OD coordinates fixed. Every ORS estimate is longer than its saved Valhalla estimate. Mean signed/absolute difference **15.970min**, median **15.524min**, range **4.275–32.285min**; percentages range **6.37–29.72%**. Four of six differences are at least five minutes and the median signed difference exceeds five minutes: the plan's exploratory material-positive-discrepancy flag passes. All six pairs remain; maximum endpoint snap **14.92m**, none >100m, so the snap-quality sensitivity retains all six.

| Public validation route | Valhalla min | ORS min | ORS − Valhalla min | Difference |
| --- | ---: | ---: | ---: | ---: |
| Joshua Tree → Twentynine Palms | 15.19 | 19.71 | +4.52 | +29.7% |
| Idyllwild → Palm Springs | 51.99 | 61.44 | +9.46 | +18.2% |
| San Diego → Julian | 67.14 | 71.42 | +4.27 | +6.4% |
| San Diego → Idyllwild | 109.86 | 131.45 | +21.59 | +19.7% |
| San Diego → Big Bear Lake | 150.41 | 174.11 | +23.69 | +15.8% |
| Santa Barbara → Brawley | 272.24 | 304.52 | +32.28 | +11.9% |

[Complete comparison](comparison.json) retains percentages, distances, endpoint snaps and engine/data metadata for every case. ORS returns **9.10.0**, graph `2026-09-21T10:31:27Z`, OSM `2026-09-13T23:59:59Z`; all six engine/build/graph/OSM metadata records match those in the prior 48-route run. The old Valhalla status is **3.9.1-7fd2228e5**, tileset-last-modified `1792170595`. This controls OD differences, but does not separate engine/profile/data/date or different chosen routes, prove either reference correct, establish traffic truth or justify national accuracy. Named routes enter validation only.

## What this changes

The earlier regional and frontier comparisons use materially different reference timings on these matched routes. Treating their error summaries as directly interchangeable would confound that difference with model performance. Do not subtract a fixed 16-minute offset, scale times from these six routes, introduce regional exceptions or infer that this explains every frontier error. The gaps vary in both minutes and percentages.

An explicitly **post hoc sensitivity**, reusing the already-saved candidate timings without new searches, also scores the rejected speed candidate against these six ORS results. Current-v8 mean absolute difference is **8.087min**; candidate **8.272min**, two improve/four regress. Against the same six Valhalla results those means are **9.738 / 15.003min**. This is not a predeclared new gate and does not rescue the candidate. Its original 83-case rejection and all gates remain unchanged; v8 stays active. [Independent arithmetic/protocol audit](analysis.json), [offline analyzer](analyze.py), [original failed decision](../coarse-class-calibration-2026-10-23/decision.json).

**Next:** prepare a separately versioned, bounded plan/tool for the **29 remaining** older OD pairs so all 35 can also be compared with ORS. Reuse the six results here and all 48 frontier results; keep the old Valhalla evidence as a distinct sensitivity. The 35 old OD pairs are distinct, so 29 are unmatched. Freeze the remaining list, interpretation and future candidate criteria before acquisition/tuning; retain all failures and graph/profile/date caveats. Build/test the concrete runner before requesting a new exact budget. **No further provider calls are authorized.** This proposal is not an implemented benchmark, a candidate selection or a change to any failed gate. All observed references remain development data.

## Capture and verification

The recorded run uses the [tested six-route CLI](../../../scripts/compare-coarse-control.ts) and [core](../../../scripts/coarse-control.ts) without edits. All six HTTP statuses are 200; returned quota remaining is **1951→1946**, immediately following the old run's last 1952. Minimum request-start interval is **6501ms**. Capture runs `2026-10-24T19:37:06.672Z`–`19:37:41.600Z`; individual HTTP-plus-body elapsed is **737–2422ms**, excluding persistence and not measuring engine search time. Maximum retained response is **75,327 bytes**. No retry, redirect, fallback, auth/status probe, body-limit/timeout failure, paid upgrade or replacement call occurred. No key values are printed; only allowed nonsecret response headers are retained. Zero known key echoes required redaction.

Complete requests/responses/results and all six ledger entries are preserved under [reference/](reference/sha256.json), separate from the NE/Census runtime artifact. Raw provider provenance remains `© openrouteservice by HeiGIT | Data from OpenStreetMap`, CC-BY-SA 4.0. [Source/check bindings](checks.json) and the report manifest bind capture, producer and analysis bytes. The original plan, tool-readiness report, failed candidate, 48-route capture and active v8 SHA remain unchanged. Separate floating-map UI bytes are preserved.

Two actual CLI offline replays match byte for byte; the independent analyzer checks durations, signed/absolute/percentage differences, original timings, source/capture hashes, quota counters, spacing and post hoc arithmetic. A fresh-directory restoration from the preserved capture also replays identically. Previous 13 synthetic tests and check/typechecks/build remain [dated tool-readiness proof](../coarse-control-tool-2026-10-24/README.md); no app implementation changed and no redundant graph/DB/server/Vercel/build suite was rerun for reference acquisition and reporting. See [replay/restoration commands](../../local-development.md#matched-reference-control).

The following command **already ran once** and must not be rerun/retried, even into another directory. Its six-call approval is now consumed:

```sh
node --import tsx scripts/compare-coarse-control.ts --capture data/coarse-quality/matched-control-reference-v1 --confirm-6-requests
```

The read-only audit can be repeated from the repo root, without an env file or key:

```sh
python3 -B docs/evidence/coarse-control-reference-2026-10-24/analyze.py > /tmp/coarse-control-independent-analysis.json
```

Before capture, public primary documentation was refreshed: [official HeiGIT migration announcement](https://ask.openrouteservice.org/t/deprecating-api-openrouteservice-org-in-favour-of-api-heigit-org/7912) supports the fixed endpoint/existing key; [official FAQ](https://giscience.github.io/openrouteservice/frequently-asked-questions#when-and-how-does-my-quota-reset) documents default limits/headers and the public snap radius. No account/plan/terms change or extra quota probe occurred. [Review record](provider-review.json) distinguishes published defaults from the actual counters returned by these six approved requests.
