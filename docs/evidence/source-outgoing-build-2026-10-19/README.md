# First source-node outgoing calibration build — October 19, 2026

This is a **partial handoff**, not acceptance of the complete memory follow-up. Read [the current report](../../six-hour-preflight.md#memory-follow-up) and [resume guide](../../agent-handoff.md). The first build completed; its exact repeat has not started, no calibration batch is running and the final result verifier/collector have not run end to end.

The bounded owner profile matches the accepted base identity. Its peak is diagnostic and excludes several whole-build phases; shallow reference sizes can double-count shared objects. The focused change replaces a temporary outgoing-node dictionary with offsets over existing sorted source IDs, preserving road order and the frozen generic fallback.

The complete first build peaks at **2.415 GiB** (3.018 GiB with 25% margin), down from 2.668 GiB. Complete worker wall time is **1,494.59 s**; pressure/OOM/kill/swap are zero. All eight qualified payloads match, and their current hashes were rechecked on the host for this handoff. Host hashing is not a new capped resource measurement. Seventeen fresh scoped fixtures record 416 full / 1,248 bounded / 320 partial independent comparisons. Supplemental `storage-fixtures.json` is included separately from the eight payloads.

`status.json` records the checkpoint, checks and ordered resume commands. `build/` and `owner-profile/` preserve measured reports/identities; `validation/` retains tests, health and the collector. The build manifest binds 149 scripts. `recipe-sha256.json` combines completed build/profile dependencies; `baseline-bindings.json` verifies the earlier two-hour and six-hour evidence/producers. `pending/` and `pending-sha256.json` preserve the prepared helpers at this checkpoint, not completed proof. Review and record any later helper revision transparently. The final collector's future directory is separate from this bundle.

The serving app remains on `two-hour-region-v2`, ready with zero provider calls. No revised optimized forecast, larger-region admission, new coverage, deployment, regional search rerun or browser claim is made. The original 9.40 GiB partial-source screen and missing-source hold remain. Large source/graph/CSR/native files and environment values remain local-only; this evidence is not a portable dataset bundle. Preserve frozen outputs/producers and failed attempts.

Safe verification from the repository root, without rebuilding:

```sh
python3 -B - <<'PYTHON'
import hashlib, json
from pathlib import Path
folder = Path('docs/evidence/source-outgoing-build-2026-10-19')
for filename, base in [('evidence-sha256.json', folder), ('recipe-sha256.json', Path('.'))]:
    records = json.loads((folder / filename).read_text())
    for name, expected in records.items():
        with (base / name).open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected, name
    print(filename, len(records), 'files match')
PYTHON
```

Pending helper hashes are checkpoint provenance; legitimate later edits must be explained, not confused with a completed result. The saved first-build collector refuses overwrite. Do not run it as a health check.
