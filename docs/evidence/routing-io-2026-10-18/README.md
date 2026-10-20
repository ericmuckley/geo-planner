# I/O lifetime evidence — October 18, 2026

Read [the findings and reproduction commands](../../archive/routing-io-lifetimes.md). This experiment manages completed file reads/writes against four frozen graphs under the unchanged cap. It uses no provider quota, downloads or new graph coverage.

```sh
python3 -B docs/evidence/routing-io-2026-10-18/analyze.py
```

`comparison.json` saves the analyzer output. `io-*` records are raw completed-input/bounded-output reports/manifests/identities. `bounded-*` records add bounded checksum reads against that predecessor. `old-*` records retain numeric-key baselines; `qualified-*` manifests and `frozen-*` independent/native reports bind the original graph/field evidence. Existing full/bounded/partial/native qualification is reused on identical graph bytes, not freshly run.

The analyzer checks run/source/code/profile identities, unchanged importer bodies, every output equality record, cache-policy scope and per-range accounting, no-swap/pressure policy, smaller proof bindings and reused independent/native counts/hashes. It does not load large graphs, rerun routes or produce new timings. `validation.json` lists exact check/workload commands, log/report hashes, tooling, preservation and scope. Large products and recipe snapshots remain in ignored `data/io-pilot/io-v1-*` and `data/io-bounded-pilot/iob-v1-*` directories.

Complete container peaks include final verification reads. Worker RSS and periodic composition samples are separate measurements, and maxima must not be summed. Host/cache/VM conditions are uncontrolled. No browser/HTTP/Vercel measurements, real border correctness or larger-graph admission are claimed.
