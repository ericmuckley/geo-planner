# Restriction-member lookup evidence — October 18, 2026

Read [the findings and reproduction commands](../../archive/routing-member-lookup.md). This experiment retains only restriction-member lookup entries and scans all road geometry for duplicates under the unchanged resource cap. It uses cached files and no provider quota or downloads.

```sh
python3 -B docs/evidence/routing-member-lookup-2026-10-18/analyze.py
```

`comparison.json` saves the analyzer output. `members-*` records are the raw reports/manifests/identities and fresh small-fixture parity results. `bounded-*` records retain the prior complete-workflow baseline. `qualified-*` manifests and `frozen-*` independent/native reports bind the original graph evidence. `new-recipe-sha256.json` freezes the new files before any real-data run. Old producers remain unchanged.

The analyzer verifies source/profile/image/code/run identities, resolver/barrier body constraints, output equality records, full-graph duplicate/fallback fixture outcomes, smaller proof bindings, no-swap/pressure policy and reused regional independent/native counts/hashes. It does not load large graphs or rerun regional searches. Each parity worker verifies actual frozen source, artifacts, recipes and original qualification files before saving its report. Large outputs and recipe snapshots remain in ignored `data/member-pilot/members-v1-*`.

`validation.json` lists commands, log/report hashes, tooling, preservation and scope. Four logs retain the worker's phase measurements. Linux tests use the cached Pyosmium reader image because some existing fixture tests need it; the baseline parity workers need no new dependencies.

Regional route qualification is reused on identical bytes; fresh synthetic fixture full/bounded checks are separate. Complete container peaks include final verification reads. Worker RSS and sampled composition are separate scopes; host/cache/VM conditions are uncontrolled. No browser/HTTP/Vercel timings, real border eligibility or larger-graph admission are claimed.
