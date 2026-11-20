# Next steps for coding agents

Updated November 19, 2026. Read [AGENTS.md](../AGENTS.md), [handoff](agent-handoff.md), [status](implementation-status.md) and [local development](local-development.md).

**V9 is committed at `648c731` (commit message `v8`), user-reported deployed and verified.** The agent's 15 production API checks also pass for `coarse-road-grid-v9`, min 30/max 720 and the saved 6/10/12 h counts. No provider call or history write was needed. Public model metadata does not expose deployed Git SHA; hosted browser verification is user-reported. [Hosted result and latest preflight](evidence/coarse-backbone-preflight-2026-10-25/README.md).

**Production.** Release `b765050` adds **Browse trailheads** and **Browse campgrounds** to the v9 app. The live six-hour Flagstaff check verified both lists, their pins and the elevation filter. The replacement engine remains held after seven failed release checks. [Hosted release checks](evidence/usgs-area-layers-2026-11-18/browse-lists-release-v1.json).

**Local preview.** The map estimates a two-hour Flagstaff example on open and recomputes after origin and time changes. On phones, **Trip controls** starts as a collapsed bottom bar. Share the URL to restore the starting point, time, layers and elevation range. [Local review](local-development.md#try-the-simplified-map).

Start with the [simplified map release and trip-planning check](#1-review-and-release-the-simplified-map). The [routing stop rule](#2-decide-when-routing-is-good-enough) records when to revisit the engine.

<a id="1-publish-and-verify-latest-v8"></a>
<a id="1-publish-and-verify-the-time-slider"></a>
<a id="1-authorize-and-acquire-the-frozen-reference-set"></a>
<a id="1-prototype-generic-road-class-timing-calibration"></a>
<a id="2-preserve-reproducible-offline-reference-access"></a>
<a id="1-implement-and-test-the-matched-reference-control"></a>
<a id="2-obtain-the-separate-six-request-budget-then-acquire"></a>
<a id="1-obtain-the-separate-six-request-budget-then-acquire"></a>
<a id="2-interpret-the-matched-results-and-select-a-generic-correction"></a>
<a id="1-prepare-the-remaining-same-provider-benchmark-offline"></a>
<a id="1-obtain-the-separate-29-request-budget-then-acquire"></a>
<a id="2-interpret-the-consistent-provider-development-benchmark"></a>
<a id="1-specify-one-generic-timing-cost-revision-offline"></a>
<a id="2-produce-and-evaluate-the-one-planned-revision-then-qualify-only-if-it-passes"></a>
<a id="current-ui-follow-up-ready-for-review"></a>
<a id="completed-v8-hosted-slider-and-first-frontier-references"></a>
<a id="completed-class-timing-candidate-rejected"></a>
<a id="completed-matched-reference-runner-tested"></a>
<a id="completed-six-matched-route-references-acquired"></a>
<a id="completed-remaining-29-planrunner-tested-offline"></a>
<a id="completed-all-83-same-provider-references-paired"></a>
<a id="completed-damped-10082-experiment-rejected"></a>
<a id="1-diagnose-generic-features-beyond-class-and-expressway"></a>
<a id="2-evaluate-only-the-next-evidence-backed-planned-revision"></a>
<a id="1-review-commit-and-deploy-the-qualified-local-changes"></a>
<a id="2-verify-the-hosted-v9-deployment"></a>
<a id="3-select-the-next-structural-accuracy-improvement"></a>
<a id="1-implement-the-protected-25-m-geometry-size-preflight"></a>
<a id="2-build-a-routing-candidate-only-after-geometry-and-footprint-pass"></a>

<a id="1-implement-the-isolated-binary-packagingload-probe"></a>
<a id="2-freeze-and-build-a-routing-candidate-only-after-packaging-passes"></a>

<a id="1-freeze-and-implement-one-routing-candidate"></a>
<a id="2-evaluate-and-qualify-that-single-frozen-candidate"></a>

<a id="1-audit-saved-candidate-paths-and-provider-differences-offline"></a>
<a id="2-propose-another-generic-model-change-only-after-that-diagnosis"></a>

<a id="1-specify-and-freeze-one-generic-cost-only-hypothesis"></a>
<a id="2-evaluate-only-that-separately-frozen-policy"></a>

<a id="1-reprice-captured-old-graph-state-paths-at-the-fixed-110-policy"></a>

<a id="1-join-saved-timing-residuals-with-generic-path-exposures"></a>

<a id="1-audit-saved-travel-distance-budgets-and-unresolved-portions"></a>

<a id="1-design-one-generic-timing-hypothesis-from-available-features"></a>

<a id="1-implement-the-capped-road-attribute-pilot-reader-and-controls"></a>
<a id="2-freeze-and-run-one-21-window-data-feasibility-pilot"></a>

<a id="1-analyze-the-preserved-partial-cache-offline-and-make-one-input-decision"></a>

<a id="1-diagnose-cached-geometry-and-scope-compatibility-offline"></a>

<a id="1-test-one-generic-endpoint-connected-segment-matcher-offline"></a>

<a id="1-audit-unresolved-chain-exclusions-and-make-one-geometry-input-decision"></a>

<a id="1-test-declared-role-uncertainty-reporting-without-changing-matches"></a>

<a id="1-implement-and-synthetically-test-terminal-fragment-geometry"></a>

<a id="1-run-the-frozen-cached-terminal-fragment-experiment-once"></a>

<a id="1-design-one-bounded-complete-road-attribute-input-pilot"></a>

<a id="1-implement-and-synthetically-verify-bounded-osm-capture-controls"></a>

<a id="1-run-the-frozen-native-osm-snapshot-capture-once"></a>

<a id="1-design-one-bounded-deterministic-bulknative-osm-input"></a>

<a id="1-propose-one-versioned-offline-us-input-resource-and-snapshot-revision"></a>

<a id="1-implement-and-synthetically-verify-the-proposed-offline-us-input-controls"></a>

<a id="1-run-the-frozen-metadata-only-dependency-lock-setup-once"></a>

<a id="1-run-the-frozen-v3-four-catalogue-metadata-correction-once"></a>

<a id="1-implement-freeze-and-run-one-bounded-locked-tool-native-smoke-stage"></a>

<a id="1-prepare-a-versioned-expat-runtime-correction-reusing-saved-wheels"></a>

<a id="1-implement-freeze-and-run-the-exact-one-package-runtime-correction"></a>

<a id="1-implement-and-freeze-an-exact-national-input-recipe"></a>

<a id="1-run-the-exact-frozen-national-input-experiment-once"></a>

<a id="1-run-the-separately-frozen-v3-national-input-correction-once"></a>

<a id="1-profile-and-redesign-the-offline-importer-using-the-saved-source"></a>

<a id="1-freeze-and-run-a-read-only-national-count-and-mixed-object-feasibility-screen"></a>

<a id="1-prototype-the-compact-two-pass-importer-before-another-full-extraction"></a>

<a id="1-specify-the-bulknative-fast-path-and-smaller-lossless-index"></a>

<a id="1-implement-freeze-and-run-one-metadata-only-native-build-dependency-lock"></a>

<a id="1-implement-and-freeze-the-v2-config-only-cdn-metadata-correction"></a>

<a id="1-prepare-bounded-pinned-artifact-acquisition-and-minimal-compilerabi-qualification"></a>

<a id="1-implement-the-native-validationindex-helper-with-synthetic-equivalence-controls"></a>

<a id="1-implement-the-native-metadata-validatorprojector-and-bounded-block-handoff"></a>

<a id="1-freeze-fixed-saved-sample-equivalence-and-performance-checks"></a>

<a id="1-run-the-exact-frozen-fixed-sample-test-once"></a>

<a id="1-specify-one-bounded-countrywide-feasibility-screen"></a>

<a id="1-implement-and-synthetically-qualify-the-countrywide-screen-helper"></a>

<a id="1-close-and-qualify-the-whole-source-execution-wrapper-then-freeze-its-run"></a>

<a id="1-implement-and-qualify-the-complete-road-extraction-prototype"></a>

<a id="1-finish-and-independently-close-the-running-national-road-capture"></a>

<a id="1-qualify-generic-conservative-road-rejection-before-another-national-stage"></a>

<a id="1-qualify-read-only-fine-revalidation-then-measure-national-cell-bank-capacity"></a>

<a id="1-qualify-lossless-id-gap-run-storage-under-the-unchanged-bank-limit"></a>

<a id="1-complete-the-new-national-bank-census-under-unchanged-limits"></a>

<a id="1-complete-and-audit-the-running-filtered-road-capture"></a>

<a id="1-measure-captured-road-metadata-before-timing-model-use"></a>

<a id="1-choose-the-next-road-data-architecture"></a>

<a id="1-build-the-approved-direct-osm-prototype"></a>

<a id="1-prepare-a-bounded-national-footprint-census"></a>

<a id="1-qualify-and-complete-the-exact-routing-only-topology-census"></a>

<a id="1-qualify-static-car-costs-and-compact-encoding-on-the-captured-native-graph"></a>

<a id="1-diagnose-the-new-primary-road-paths-before-another-model-change"></a>

<a id="1-qualify-a-national-explicit-lane-metadata-census"></a>

<a id="1-finish-the-national-lane-census-then-qualify-source-cost-overlays"></a>

<a id="1-recompute-restrictions-and-rebuild-the-lane-corrected-graph"></a>

<a id="1-finish-exact-timing-cost-routing-qualification"></a>

<a id="1-finish-the-timing-runtime-and-evaluate-fresh-grids"></a>

<a id="1-prepare-the-compiled-mandatory-turn-graph-for-a-fresh-accuracy-benchmark"></a>

<a id="1-finish-the-road-engine-benchmark-and-decide-what-ships"></a>

<a id="1-add-the-first-useful-places-layer"></a>

<a id="1-review-and-release-the-destination-and-fuel-features"></a>

<a id="1-review-and-release-the-outdoor-places-layers"></a>

<a id="1-review-the-public-lands-and-elevation-layers"></a>

<a id="1-use-the-released-planning-layers"></a>

<a id="1-review-and-release-place-search"></a>

<a id="1-use-place-search-in-trip-planning"></a>

<a id="1-review-and-release-outdoor-place-filters"></a>

<a id="1-review-and-release-the-browse-lists"></a>

<a id="1-review-and-release-directions-links"></a>

## 1. Review and release the simplified map

**Released.** Browse lists are live in `b765050`. The production browser check opened both lists and their map details, expanded campgrounds from 20 to 40 entries, and cleared the results and popup by raising the elevation filter. [Hosted results](evidence/usgs-area-layers-2026-11-18/browse-lists-release-v1.json).

1. **Review the local map on a phone with the live basemap.** Check that **Trip controls** starts collapsed in portrait and landscape, leaves half the screen for the map when open, and folds away when you pick a place from the list. Confirm the zoom buttons, attribution and popup close button stay reachable. Move the pin, change the time, adjust both elevation handles and open the copied URL in a fresh tab to verify that it restores the area and filters. On desktop, check the opening panel, cluster hover counts, **Details** sources and project link, and **View in Google Maps**. [Local review](local-development.md#try-the-simplified-map), [mobile checks](local-development.md#floating-map-controls), [sharing check](local-development.md#share-a-map-view).
2. **Publish after approval.** Run the checks, server tests and both builds on the exact release commit. Verify the static assets and confirm the matching Vercel deployment is live. [Release commands](local-development.md#verify-the-simplified-map-build).
3. **Finish the trip-planning check.** On the deployed app, try a short trip and a six-hour trip across desktop and phone layouts. Move the starting pin, let the area update, filter the outdoor places and open the URL on the other device. Select a place and open it in Google Maps. Pass when the URL reproduces the area and filters, the list and pin agree, and Maps opens the location shown on the Geo Planner map. Fix blockers in that flow. Additional place metadata, business availability and in-app driving directions are deferred.

**Engine decision:** Seven release checks still fail in the completed comparison. None of the 83 saved estimates changed from the preceding prototype. Keep the replacement held. [Full result](evidence/coarse-osm-car-capacity-2026-11-01/conditional-only-evaluation-v2-raw-v1/report.json). There are 439 closed roots with 11,444,031,488 bytes of newer allocation and no active producer.

## 2. Decide when routing is good enough

<a id="2-propose-a-new-correction-only-after-the-controlled-diagnosis"></a>
<a id="2-produce-a-new-timing-candidate-only-after-data-feasibility-and-a-policy-freeze"></a>

**Pause routing experiments.** The saved comparison shows a substantial improvement from the road prototype, with a new shoreline omission and several large timing regressions that still block release. Previous speed and display experiments have no qualified fix for both problems. Keep v9 for rough trip planning. [Product accuracy review](implementation-status.md#routing-accuracy-for-trip-planning).

1. **Prioritize errors that change the trip decision.** For six- to twelve-hour estimates, start with a place shown on the wrong side of the limit when its reference is more than 30 minutes from it. Use 30 minutes to rank investigation priorities and keep the original release checks. The saved maps cover six, ten and twelve hours. Include the 30-minute and default two-hour views in the next product spot-check.
2. **Test one correction only when there is a clear cause and a credible general fix.** Reuse saved cases to demonstrate the failure and include a control that should stay correct. For the shoreline case, a new approach would need to retain the proven land access without painting the surrounding water. Stop after the focused check if the fix adds a serious error or the evidence gives no clear next correction.
3. **Stop tuning when a candidate passes the existing release checks and the app spot-check.** Ship that candidate and return to app work. Keep a record of smaller discrepancies for future reports.

The 1.10 allowance and unbuffered backbone remain rejected under their original decisions. Any later generic policy needs a separately specified evidence-backed hypothesis and exact artifact/implementation/evaluation freeze before search, without parameter sweeps or post-result retuning.

Retain every [original gate](evidence/coarse-backbone-preflight-2026-10-25/next-design.json): >=10% overall/frontier MAE improvement vs v9 on all 83 ORS, original/regional/horizon means/tails/frontier median and 35 Valhalla means no worse; losses<=20 min frontier/5 min older; definite frontier errors<=12, missed<=2 overall/1 at 12h; all 83 finite/166 sums/35 older shaded. Only after all accuracy gates pass, require independent physical/source/shore/transfer/path checks, full first local packaged estimate<=5 s, retained decoded<=162,238,546 bytes, function<=70 MB, software/API and shared-camera review. Diagnostic 900-minute timings are separate. No active switch before every necessary gate passes.

Saved 83/35 are observed development data, not a fresh holdout/national/area/traffic truth. Primary observed ORS recommended-fallback semantics and 35 Valhalla sensitivity remain explicit. All 48/6/29 budgets are consumed; fresh references need a separately approved bounded plan. Unchanged persistence needs no cloud history writes/full DB suite.

## Deferred scope

The runtime stays v9. Finer-grid app activation, traffic/turns/terrain/access, precise borders/coasts, caching, accounts and query import, PostGIS and advanced regional research remain deferred. Detailed six-hour expansion stays held at 9.290 GiB versus 4 GiB. [Six-hour report](six-hour-preflight.md), [two-hour baseline](two-hour-region.md).
