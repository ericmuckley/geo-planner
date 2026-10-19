# Two-hour preflight evidence

Read [candidate planning, source/tool pins, reproduction commands and limitations](../../two-hour-coverage-preflight.md).

**Admission: HOLD.** Exact current XML/census and all six fixtures pass; candidate bounds are **9.73–10.12 million road states**. Preparation reaches **4 GiB / 3,750 limit events**, with zero OOM/swap. The **20.64 GiB** forecast includes 25% margin and is not measured graph/query memory. South/east envelope clipping is explicit. No larger graph is built.

```sh
python3 -B docs/evidence/two-hour-preflight-2026-10-17/analyze.py
```

The analyzer requires ignored local products under `data/`. It checks canonical identities, current/snapshotted code/profile/tool hashes, six fixture parity, exact current XML/census, original graph/fields/native binary identity, all source-linked frontier artifacts, parent source checksum, the full continuation-envelope calculation and the resource rule. Preparation and fixture function bodies remain identical to the frozen recipe. It emits `comparison.json` and `admission.json`; raw report/identity copies and validation logs retain provenance and measurement scope.

No new graph or native run is claimed. The current one-hour evidence is reused by exact identity. Source-envelope clipping is separate from RAM admission. Numeric budgets and successful extraction do not establish complete two-hour/source/real-world coverage.
