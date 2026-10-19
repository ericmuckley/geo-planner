# Larger regional routing experiment

Updated October 18, 2026. Work in progress: build and independently verify the prepared Southern California/northern Baja increment, then release it to the local experiment. The existing qualified graph stays available until all checks pass. No provider requests, road downloads, environment-file changes or cloud deployment are involved.

## Target and acceptance criteria

The candidate bounds are **[-118.0,31.6,-115.5,34.0]**, expanding the current **[-117.65,31.9,-116.0,33.6]** on every side. Its prepared OSM XML is 823,266,297 bytes, SHA-256 `fba7c77ac4b46c7ac714c843c03311731556f5bfad3797dee5fc4b11539a608f`. This is an intermediate coverage increment; it does not guarantee complete two-hour coverage or US-wide routing.

Release requires:

- A fresh graph identity and all seven build artifacts reproduced byte for byte.
- Five origins checked against independent full fields and eight bounded budgets, twelve finite city directions, both partial destinations, unchanged source-backed access/turn decisions and explicit border uncertainty.
- Fresh native-kernel agreement and an inventory of every audited boundary/history state with source links.
- Actual complete-container measurements under two CPUs, 4 GiB RAM, no swap and no network. Admission forecasts retain a 25% margin; measured peaks and forecasts are reported separately.
- Real 90/120-minute browser queries, correct snapping, clear coverage warnings and separate search/display/HTTP timings.
- Relevant tests, `npm run check`, `npm run typecheck`, `npm run build` and the Vercel target build.

The coverage goal is zero reached potential data edges within 120 minutes for the selected origins. An intermediate graph may be released with clear warnings if routing checks pass but geographic gaps remain. Zero detected edges still does not certify source completeness or real driving eligibility.

## Reproduction so far

The prepared source is already sealed under `data/coverage-pilot/experiment-increment-v1`. Preserve it and the original producers. New versioned workers use the existing qualified outgoing-road importer, static v3 model, independent algorithms and native kernel.

```sh
node routing/region-verify.mjs --stage calibrate
node routing/region-increment.mjs --stage build
node routing/region-increment.mjs --stage rebuild
node routing/region-verify.mjs --stage qualify
sandbox-exec -f routing/native-network.sb python3 -B routing/compact_native.py --run-name experiment-region-v1
node routing/region-increment.mjs --stage cuts
```

Run names are sealed; repeat completed/failed stages with fresh names and use `--source-run` where applicable. Qualification writes into its build directory; rerunning a failed qualification requires a fresh preserved build directory. Do not overwrite identity files or old attempts.

The old whole-workflow forecast was **5.277 GiB including margin**, driven by verification. A separately capped build is eligible at **3,727,746,227 bytes including margin**. Build-only admission cannot authorize an app switch. A new verifier limits its road-ID map to actual fixture targets, streams oracle bytes and releases completed label arrays. It retains Dijkstra, independent queue relaxation, full/bounded/partial comparisons and exact old-output parity. Its actual calibration must pass before admitting candidate qualification. The first attempt (`experiment-lean-v1`) was intentionally stopped after graph reload alone peaked at **1,409,110,016 bytes**, enough to fail that forecast. Its files and partial evidence are preserved. The replacement (`experiment-ranged-v1`) runs the unchanged compact JSON parser through a read-only UTF-8 stream that advises completed file ranges. It checks every old functional result and all five oracle files exactly before its peak can be used for admission. Unicode boundaries, parser equivalence and failure cleanup have focused tests.

Raw logs and initial file fingerprints are being recorded in `data/experiment-pilot/larger-region-v1/`. Final measurements and browser evidence will be linked here after verification.
