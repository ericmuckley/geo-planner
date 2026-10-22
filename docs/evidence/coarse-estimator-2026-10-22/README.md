# Coarse estimator milestone — October 22, 2026

This is the new coarse product model, separate from the preserved detailed OSM routing recipes. See [model and limitations](../../coarse-estimator.md).

| File | Evidence |
| --- | --- |
| [model.json](model.json) | Grid counts, pinned source URLs/hashes and compact artifact identity; deterministic rebuild matched |
| [national-smoke.json](national-smoke.json) | 42 in-process requests: fourteen origins at 6/10/12h, schema/count/payload checks and observations |
| [vercel-handler.json](vercel-handler.json) | Generated Vercel handler works locally with network fetches rejected; 5,246,694-byte function, coarse enabled, detailed experiment disabled |
| [server-tests.log](server-tests.log) | 26 passing tests, including synthetic model and invalid-query cases |
| [check.log](check.log), [typecheck.log](typecheck.log) | Checks pass; existing database non-null-assertion warning remains |
| [build.log](build.log), [build-vercel.log](build-vercel.log) | Ordinary and Vercel-target builds pass |
| [browser-check.json](browser-check.json), [screenshot](san-diego-six-hours.jpg) | Local browser flows and final six-hour filled contour |

These records do not establish driving-time accuracy, every-origin correctness, production latency, cloud concurrency or peak memory. The national cases are sequential direct server calls; local generated-handler invocation is not a cloud deployment. Runtime memory is only a process snapshot. Nantucket returns a single isolated cell because ferries are excluded. The browser basemap uses the network independently of the estimator.

Commands: `node --import tsx --test src/server/*.test.ts`, `npm run check`, `npm run typecheck`, `npm run routing:verify:coarse`, `npm run build`, `npm run build:vercel`, then `npm run check:coarse:vercel`. Local Vercel-handler measurements include handler execution, serialization and response reading; grid-search and contour timings have separate scopes. No hosted routing computations were used.

Verify this snapshot without rebuilding or network access:

```sh
python3 -B - <<'PYTHON'
import hashlib, json
from pathlib import Path
root = Path('docs/evidence/coarse-estimator-2026-10-22')
for name, expected in json.loads((root / 'sha256.json').read_text()).items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
model = json.loads((root / 'model.json').read_text())['artifact']
assert hashlib.sha256(Path(model['path']).read_bytes()).hexdigest() == model['sha256']
print('Coarse evidence and artifact match')
PYTHON
```
