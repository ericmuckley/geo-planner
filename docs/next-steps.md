# Next steps for coding agents

Updated October 30, 2026. Read [AGENTS.md](../AGENTS.md), [handoff](agent-handoff.md), [status](implementation-status.md) and [local development](local-development.md).

**V9 is committed at `648c731` (commit message `v8`), user-reported deployed and verified.** The agent's 15 production API checks also pass for `coarse-road-grid-v9`, min 30/max 720 and the saved 6/10/12 h counts. No provider call or history write was needed. Public model metadata does not expose deployed Git SHA; hosted browser verification is user-reported. [Hosted result and latest preflight](evidence/coarse-backbone-preflight-2026-10-25/README.md).

**Current work:** national bank capacity passes with identical 938 MB banks. Road capture stopped at the old 250,000 selected-element limit; all failure evidence is closed and preserved. Next is bounded disk-backed selection under the same 4 GiB memory, four-hour and 64 GiB storage limits. [Evidence and recovery](evidence/coarse-osm-extraction-2026-10-30/README.md). Deployed v9 is unchanged.


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

## 1. Qualify bounded disk-backed selected records

National capacity passes two complete source traversals and identical938MBbanks. The subsequent capture is USED/stopped/closed at its250kselected-element guard:11,201,886ways recognized, no first EOF/second pass/output. Worker absent; no OOM or measured wall/IO cap. Safe`python3 -B docs/evidence/coarse-osm-extraction-2026-10-30/verify_filtered_capture_stop_v1.py`. All used code/recipes/source/failed files remain immutable. [Evidence](evidence/coarse-osm-extraction-2026-10-30/README.md).

1. Implement separate versioned disk-backed primary/audit selected records, ordered geometry/field/membership hashes and streaming output/audit. Preserve raw fields, unresolved restriction members, independent predicates/materialization and missing-reference failure. No source/window/class/ID exceptions or resampling.
2. Expand the new native selected-ID boundary to2M under a new ABI/bridge, preserving all source metadata/semantic/EOF/framing/coordinate/callback/row guards. Qualify actual Linux beyond250kselection/projection, cap+1/ABI/sentinel/error cases, disk limits/transactions/corruption/ownership and exact tiny frozen four-pass output/input preservation/independent tamper detection. No national run before controls/proof/lifecycle/freeze.
3. Same4GiB RAM/zero swap/twoCPU/four-hour/64GiB retained total and original21windows. New internal selected allowance2Munique/4Moccurrences,512MiBraw/state,1GiBnormalized output/8MiBselected row; source-copy/canonical4MiB/frame8MiB unchanged. Proposed two SQLite spools<=1.25GiB/cache8MiB each, OS file cap2GiB, cell writes bound to exact qualified938,364,831byte bank. After actual retained58,226,331,751 +64MiBmetadata +256MiBtmp, owned<=10,157,600,665bytes. Prove worst-case writable allocation and preserve every failed byte; never change a used cap/result in place.
4. Only after qualification freeze a new bounded complete capture. Require two full source EOF/count/semantic traversals, every highway reference/geometry, independent full raw/window output audit, readonly fine validation and complete resource/owned cleanup proof. Then source/publisher adequacy, separately frozen native speed/access applicability/inventory, >=50%usable-limit/independent matching and physical checks; later one frozen timing candidate and all83ORS/35Valhalla/package/API/model gates.

The attribute-facts draft passes9host checks but remains unfrozen/unqualified on real data; all timing permissions stay unreviewed. No provider/paid/DB/push/deploy/model switch. All48/6/29 reference budgets stay consumed; v9remains deployed. User authorized autonomous local work until a real resource/architecture/product decision needs guidance.

## 2. Produce a new timing candidate only after data feasibility and a policy freeze

<a id="2-propose-a-new-correction-only-after-the-controlled-diagnosis"></a>

The 1.10 allowance and unbuffered backbone remain rejected under their original decisions. Any later generic policy needs a separately specified evidence-backed hypothesis and exact artifact/implementation/evaluation freeze before search, without parameter sweeps or post-result retuning.

Retain every [original gate](evidence/coarse-backbone-preflight-2026-10-25/next-design.json): >=10% overall/frontier MAE improvement vs v9 on all 83 ORS, original/regional/horizon means/tails/frontier median and 35 Valhalla means no worse; losses<=20 min frontier/5 min older; definite frontier errors<=12, missed<=2 overall/1 at 12h; all 83 finite/166 sums/35 older shaded. Only after all accuracy gates pass, require independent physical/source/shore/transfer/path checks, full first local packaged estimate<=5 s, retained decoded<=162,238,546 bytes, function<=70 MB, software/API and shared-camera review. Diagnostic 900-minute timings are separate. No active switch before every necessary gate passes.

Saved 83/35 are observed development data, not a fresh holdout/national/area/traffic truth. Primary observed ORS recommended-fallback semantics and 35 Valhalla sensitivity remain explicit. All 48/6/29 budgets are consumed; fresh references need a separately approved bounded plan. Unchanged persistence needs no cloud history writes/full DB suite.

## Deferred scope

The runtime stays v9. Further display-resolution increases, traffic/turns/terrain/access, precise borders/coasts, caching, accounts/sharing/import, PostGIS and advanced regional research remain deferred. Detailed six-hour expansion stays held at 9.290 GiB versus 4 GiB. [Six-hour report](six-hour-preflight.md), [two-hour baseline](two-hour-region.md).
