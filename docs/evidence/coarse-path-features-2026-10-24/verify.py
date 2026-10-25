"""Read-only evidence/source/activation verification; no graph search or service access."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda path: json.loads(path.read_text())
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = load(folder / 'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name != 'sha256.json'}
for name, expected in manifest.items():
    assert digest(folder / name) == expected, name
checks = load(folder / 'checks.json')
for category in ['producerFiles', 'preservedFiles', 'referenceFiles']:
    for name, expected in checks[category].items():
        assert digest(repo / name) == expected, name
for name, record in checks['priorSealedEvidenceVerified'].items():
    base = repo / 'docs/evidence' / name
    assert digest(base / 'sha256.json') == record['manifestSha256'], name
    previous = load(base / 'sha256.json')
    assert len(previous) == record['files']
    for path, expected in previous.items():
        assert digest(base / path) == expected, (name, path)
finalized = load(repo / 'src/server/data/coarse-grid-v9.json')
candidate = load(repo / checks['candidate']['path'])
assert finalized.pop('version') == 'natural-earth-census-2026-grid-v9'
assert candidate.pop('version') == 'natural-earth-census-2026-connector-calibration-v1'
assert finalized == candidate
assert digest(repo / checks['candidate']['path']) == checks['candidate']['sha256']
assert digest(repo / checks['runtime']['path']) == checks['runtime']['sha256']
print(json.dumps({'recordFiles':len(manifest), 'sourceFiles':len(checks['producerFiles']),
    'priorSealedRuns':len(checks['priorSealedEvidenceVerified']), 'preservedV8AndUi':True,
    'versionOnlyActivation':True, 'allBindingsValid':True, 'providerRequests':0,
    'scope':'Saved files/hashes only; requires ignored qualified candidate and pinned source manifests. No env/key/DB access or producer/search.'},indent=2))
