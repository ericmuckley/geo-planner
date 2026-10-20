"""Preserve the completed first build; exact repeat/final result remain pending."""
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[3]
validation = Path(__file__).parent
folder = root / 'docs/evidence/source-outgoing-build-2026-10-19'
assert not folder.exists(), 'Preserve completed handoff evidence'
build = root / 'data/compact-pilot/source-outgoing-v1'
profile = root / 'data/resource-pilot/two-hour-base-owners-v1'
assert not (build.with_name(build.name + '-rebuild')).exists(), 'Reassess checkpoint: repeat exists'
assert not (validation / 'result.json').exists(), 'Reassess checkpoint: final result exists'

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def load(path): return json.loads(path.read_text())
def write(path, value): path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
def copy(source, name):
    target = folder / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)

manifest = load(build / 'build-manifest.json')
report = load(build / 'build-report.json')
reference = load(root / 'data/compact-pilot/two-hour-region-v2/manifest.json')
payloads = report['identicalQualifiedArtifacts']
assert len(payloads) == 8
for name in payloads:
    expected = reference['artifacts'][name]
    path = build / name
    assert manifest['artifacts'][name] == expected
    assert path.stat().st_size == expected['bytes'] and sha(path) == expected['sha256'], name
assert sha(build / 'build-report.json') == manifest['artifacts']['build-report.json']['sha256']
assert report['resources'] == {'peakBytes': 2592776192, 'pressureEvents': 0, 'swapBytes': 0, 'with25PercentMarginBytes': 3240970240}
recipes = dict(manifest['scripts'])
for name, expected in recipes.items():
    assert sha(root / 'routing' / name) == expected == sha(build / 'recipe' / name), name
for name, expected in load(profile / 'report.json')['scripts'].items():
    assert sha(root / 'routing' / name) == expected, name
    if name in recipes: assert recipes[name] == expected
    recipes[name] = expected
bindings = {}
for name, recipe_name in [('two-hour-region-2026-10-19', 'final-recipe-sha256.json'), ('six-hour-preflight-2026-10-19', 'recipe-sha256.json')]:
    previous = root / 'docs/evidence' / name
    for filename, base in [('evidence-sha256.json', previous), (recipe_name, root)]:
        records = load(previous / filename)
        for key, expected in records.items(): assert sha(base / key) == expected, key
        bindings[name + '/' + filename] = {'files': len(records), 'allMatch': True}
for name in ('worker-health-handoff.json', 'app-config-handoff.json'):
    health = load(validation / name)
    assert health['ready'] and health['graphIdentity'] == reference['graphIdentity']
    assert health['publicApiCalls'] == 0 and health['maxMinutes'] == 720
running = (validation / 'docker-running-handoff.txt').read_text()
assert len(running.splitlines()) == 1 and 'valhalla' in running, running
checkpoint = load(validation / 'active-work.json')
checkpoint.update({'updatedAt': datetime.now(timezone.utc).isoformat(), 'stage': 'first-build-complete-rebuild-pending', 'calibrationJobRunning': False, 'firstBuildResources': report['resources'], 'firstBuildWorkerWallMs': report['workerWallMs'], 'identicalQualifiedArtifacts': payloads, 'repeatStarted': False, 'finalResultVerifierExecuted': False, 'finalEvidenceCollectorExecuted': False, 'resume': 'Run read-only recovery/owner checks, then the exact repeat; do not rerun the completed owner profile or first build. Larger coverage remains held.'})
write(validation / 'active-work.json', checkpoint)
folder.mkdir(parents=True, exist_ok=False)
for name in ('report.json', 'identity.json', 'owners.json'): copy(profile / name, Path('owner-profile') / name)
for name in ('build-manifest.json', 'build-report.json', 'run-identity.json', 'storage-fixtures.json', 'scoped-fixtures.json'):
    copy(build / name, Path('build') / name)
for name in ('npm-test.log', 'routing-test.log', 'check.log', 'typecheck.log', 'build.log', 'worker-health-handoff.json', 'app-config-handoff.json', 'docker-running-handoff.txt', 'active-work.json', 'check-docs.py', 'collect-build-handoff.py'):
    copy(validation / name, Path('validation') / name)
pending = {'routing/source_outgoing_result.py': sha(root / 'routing/source_outgoing_result.py'), 'data/resource-pilot/source-outgoing-validation-v1/collect-evidence.py': sha(validation / 'collect-evidence.py')}
copy(root / 'routing/source_outgoing_result.py', Path('pending') / 'source_outgoing_result.py')
copy(validation / 'collect-evidence.py', Path('pending') / 'collect-evidence.py')
write(folder / 'recipe-sha256.json', {'routing/' + name: expected for name, expected in recipes.items()})
write(folder / 'pending-sha256.json', pending)
write(folder / 'baseline-bindings.json', bindings)
write(folder / 'status.json', {**checkpoint, 'scope': 'Completed first build only. Repeat, final proof binding, revised admission and final collector are pending. No larger graph admitted or released.', 'originalPartialForecastWithMarginGiB': 9.40, 'optimizedForecastRecomputed': False, 'buildRecipeFiles': len(manifest['scripts']), 'allCurrentFirstBuildPayloadHashesVerified': True, 'hostHashingScope': 'Read-only host checks after the complete capped build; not new Linux resource measurements.', 'validationCommands': ['npm test', 'npm run test:routing', 'npm run check', 'npm run typecheck', 'npm run build'], 'nextCommandsInOrder': ['node routing/source-outgoing-region.mjs --stage rebuild', 'python3 -B routing/source_outgoing_result.py', 'python3 -B data/resource-pilot/source-outgoing-validation-v1/collect-evidence.py']})
(folder / 'README.md').write_text('''# First source-node outgoing calibration build — October 19, 2026

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
''')
for command, name in [(['python3', '-B', str(validation / 'check-docs.py')], 'doc-links-handoff.json'), (['git', 'diff', '--check'], 'diff-check-handoff.log')]:
    result = subprocess.run(command, cwd=root, text=True, capture_output=True)
    (folder / 'validation' / name).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, (name, result.stdout, result.stderr)
write(folder / 'evidence-sha256.json', {str(path.relative_to(folder)): sha(path) for path in sorted(folder.rglob('*')) if path.is_file()})
print(json.dumps({'evidenceFiles': len(load(folder / 'evidence-sha256.json')), 'recipeFiles': len(recipes), 'payloadsMatch': len(payloads), 'baselineBindings': bindings, 'docLinks': load(folder / 'validation/doc-links-handoff.json')}, indent=2))
