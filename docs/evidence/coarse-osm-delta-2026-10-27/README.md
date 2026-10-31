# Native delta V1: cache drift control stopped the frozen run

The first separately frozen offline run builds the C ABI codec successfully but stops at one of44 actual Linux controls.43 pass/no skips; `test_whole_shard_truncation_symlink_cache_and_catalog_drift_refused` accepts a tampered cached shard. File metadata can remain equal after a rapid overwrite on Linux; nanosecond timestamp fields are not an integrity guarantee. The unchanged-stamp cache assumption in the frozen format/lookup recipe is therefore insufficient.

Host42 controls pass/two native skips. Compiler succeeds:201,016-byte artifact SHA256 `efe338cabf78035b93b936afb623741162e376df8451e5fede8590bbf724dc23`; all codec/format/output/independent-audit tests except the cache case pass. This is a **preserved stop, not qualified native indexing**. Build/controls workers exit0/2/not OOM, both owned removals/independent absence recorded. Host9.784250s includes input/qualified-rootfs hashes/build/controls/cleanup. No network/source/saved sample/national/model/app change.

[Result](raw/run-summary.json), [actual test log](raw/controls/worker.log), [freeze](freeze.json), [format contract](format-spec.json), [closed output](closed-output.json). Recipe SHA `2ccffe1256c99183e2df4bab97205a18c5105e7e1c9e081fc02b30965d2ba9db`; all source/code/records stay unchanged. The used command is historical; do not replay it. The compiled artifact stays ignored; all other raw records are mirrored unchanged.

Next implement a separate V2 lookup correction, reusing the same compiled codec: authenticate a bounded shard snapshot by its full SHA256 for every queried shard in each lookup batch, then decode or serve cached rows only from that authenticated snapshot. Keep encoding/layout/payload codec/validators/audit/caps unchanged and add a deterministic unchanged-metadata regression. New code/output/recipe before one offline control run; no recompile, downloads, real sample or speed/import claim. Native metadata validation and index IO remain Python.

Safe proof, no Docker/network/compile/native/archive or producer replay:

```sh
python3 -B docs/evidence/coarse-osm-delta-2026-10-27/verify.py
python3 -B docs/evidence/coarse-osm-delta-2026-10-27/verify.py --local-assets
```
