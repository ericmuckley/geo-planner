# Sparse preparation/resource evidence

October 17, 2026. Read [the findings and exact reproduction commands](../../archive/sparse-routing-resources.md). This evidence admits a separate capped candidate import; **no new graph or coverage is qualified**.

`*-report.json` and `*-identity.json` copy the five completed jobs: unchanged import profile, advised parity import, sparse calibration, sparse candidate and advised sparse candidate. Matching logs preserve output. `tools-image.json` binds the separate image/base and locked wheel/Dockerfile hashes. Full generated files and script snapshots remain ignored under `data/resource-pilot/`, `data/sparse-pilot/` and `data/tools/`.

Run from the repository root:

```sh
python3 -B docs/evidence/sparse-resource-2026-10-17/analyze.py
```

The analyzer verifies copied/live reports, canonical run identities, current/snapshotted code, parent/source/census bytes, all six native fixture results, the four frozen semantic proofs, all seven rebuilt graph/audit/packed/source artifacts and wheel/image pins. It checks explicit 4 GiB/no-swap policy, zero OOM/kill/limit counters and evaluates the margin rule. It writes `comparison.json` and `admission.json`; raw reports remain unchanged. It requires the local cached artifacts and does not download or call providers.

`admission.json` records a **3,939,952,640-byte (3.67 GiB)** estimate including 25% margin. It explicitly sets `newGraphQualified=false` and `coverageVerified=false`. Scaling measured complete-container import/export is heuristic, not a peak-memory bound. Sparse selection without advice remains a hold in `comparison.json`.

`validation.json` records commands/results and hashes of copied check logs. Host routing tests pass 99/103 with four platform/tool skips; the scoped Linux suite passes 12/12, including those skipped cases. Full Linux discovery records one setup error because the reader image has no C++ compiler. The Mac native compiler/kernel cases pass. These results are preserved separately; full Linux discovery is not claimed to pass.

Resource maxima have different scopes: child RSS, container cumulative `memory.peak`, and sampled anonymous/file maxima are not interchangeable or additive. Timings are individual preprocessing observations with uncontrolled host cache/concurrency, not isolated search or HTTP benchmarks. Final small report writes follow the last resource checkpoint. Original source/graph/cost model and application environment are preserved; new offline tooling totals 2,354,828 bytes, with no new road download or provider request.
