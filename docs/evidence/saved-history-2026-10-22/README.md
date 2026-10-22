# Saved history — October 22, 2026

The browser-private PostgreSQL history follow-up to [the coarse estimator](../../coarse-estimator.md). [Current behavior and API](../../local-development.md#saved-history-api) explain ownership, local fallback and limitations.

| Record | Result |
| --- | --- |
| [Migration](migration.json) | Reviewed additive initial migration applied to the empty cloud database; creates saved history and the existing starter table |
| [Source API with PostgreSQL](database-source.json) | Persistence, owner isolation, concurrent merges and twenty-entry retention pass |
| [Generated Vercel handler with PostgreSQL](database-vercel.json) | Same live DB checks pass through the locally generated Vercel handler |
| [Server tests](server-tests.log) | All thirty pass, including four new history tests |
| [Check](check.log), [typecheck](typecheck.log) | Pass; previous database non-null assertion removed |
| [Production build](build.log), [Vercel build](build-vercel.log) | Both pass |
| [Generated-handler packaging](vercel-handler.json) | 5,581,861-byte function; coarse estimates and missing-DB fallback pass; detailed experiment disabled; no embedded configured secrets or grid in client JavaScript |
| [Browser check](browser-check.json), [cloud-save screenshot](cloud-saved.jpg) | New save, reload, model-aware Load/Replay and Cloud saved status; older local entries remain local |

Database checks generate an isolated owner and synthetic queries, then delete only that generated test row. Existing user histories are preserved. The browser check saves/replays the public San Diego default, while deliberately leaving pre-existing local entries unuploaded. The screenshot includes only the test entry and history controls, excluding unrelated prior locations. No connection strings, raw browser cookie tokens or private prior query values are recorded.

Commands: `npm run db:generate -- --name=saved_history` (already generated; do not repeat for health), review `drizzle/0000_saved_history.sql`, `npm run db:migrate` (applied), `npm run db:verify`, normal checks/builds, `npm run check:coarse:vercel`, and `npm run db:verify -- --vercel` after the Vercel build. The integration commands write temporary test data; they are not read-only health checks. Do not rerun live DB checks solely to validate documentation.

The web app has not been verified on an actual Vercel deployment. A local generated-handler invocation, even against real cloud PostgreSQL, does not measure cloud HTTP latency, cold starts, concurrency or peak memory. Travel-time accuracy remains uncalibrated. History is private to a browser cookie, with no sign-in/cross-device access, inactive-owner cleanup, global owner-count cap or write rate limiting.

`sha256.json` binds these records; `source-sha256.json` records the implementation/migration at this milestone. Verify without network access:

```sh
python3 -B - <<'PYTHON'
import hashlib, json
from pathlib import Path
root = Path('docs/evidence/saved-history-2026-10-22')
for index, base in [('sha256.json', root), ('source-sha256.json', Path('.'))]:
    for name, expected in json.loads((root / index).read_text()).items():
        assert hashlib.sha256((base / name).read_bytes()).hexdigest() == expected, name
print('Saved-history evidence and source snapshot match')
PYTHON
```
