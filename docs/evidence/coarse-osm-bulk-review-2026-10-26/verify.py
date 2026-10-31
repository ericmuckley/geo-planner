"""Read-only bulk-design no-go proof; no downloads, tools or producer replay."""
import hashlib
import json
from pathlib import Path
import sys

folder = Path(__file__).resolve().parent
repo = folder.parents[2]
load = lambda p: json.loads(p.read_text())


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_files(files, root):
    for name, sha in files.items():
        assert digest(root / name) == sha, name


manifest = load(folder / 'sha256.json')
assert set(manifest) == {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name != 'sha256.json'}
verify_files(manifest, folder)
checks = load(folder / 'checks.json')
verify_files(checks['producerFiles'], repo)
verify_files(checks['preservedFiles'], repo)
for name, record in checks['priorSealedEvidence'].items():
    base = repo / 'docs/evidence' / name
    assert digest(base / 'sha256.json') == record['manifestSha256']
    previous = load(base / 'sha256.json')
    assert len(previous) == record['files']
    verify_files(previous, base)
decision = load(folder / 'decision.json')
assert decision['status'] == 'no_go_under_unchanged_envelope' and decision['selectedAcquisitionDesigns'] == 0
assert decision['reviewedApproaches'] == len(decision['approaches']) == 2 and not decision['acquisitionCommands']
verify_files(decision['inputs'], repo)
verify_files(load(folder / 'next-scope-plan.json')['inputs'], repo)
original = load(repo / 'docs/evidence/coarse-timing-design-2026-10-25/data-input-proposal.json')
assert decision['windows'] == [{'id': w['id'], 'bbox': w['bbox']} for w in original['selection']['windows']]
assert len(decision['windows']) == 21 and decision['snapshotUtc'] == '2026-10-21T00:00:00Z'
caps = decision['unchangedHardCaps']
assert caps == {'totalHttpBodyBytes': 536870912, 'toolBodyBytesWithinTotal': 134217728, 'httpAttempts': 10000,
    'retries': 0, 'paidSpend': 0, 'routingProviderRequests': 0, 'clientMemoryBytes': 1073741824, 'swapBytes': 0,
    'workingBytes': 2147483648, 'normalizedExtractBytes': 134217728, 'uniqueTypedElements': 250000,
    'elementOccurrences': 500000, 'wallSeconds': 3600, 'tmpBytes': 67108864}
sizes = decision['sourceSizeArithmetic']
assert [r['listedBytes'] for r in sizes] == [671829508, 12219271434]
for row in sizes:
    assert row['listedBytes'] > caps['totalHttpBodyBytes']
    assert row['exceedsTotalBodyCeilingByBytes'] == row['listedBytes'] - caps['totalHttpBodyBytes']
    assert row['bodyCeilingRatio'] == row['listedBytes'] / caps['totalHttpBodyBytes']
closure = load(folder / 'closure-review.json')
left, bottom, right, top = closure['bbox']
(x1, y1), (x2, y2) = closure['wayNodes']
assert y1 == y2 and bottom < y1 < top and x1 < left < right < x2
inside = any(left <= x <= right and bottom <= y <= top for x, y in closure['wayNodes'])
assert not inside and not closure['anyNodeInsideBox'] and closure['segmentIntersectsBox']
assert not closure['documentedCompleteWaysSeedSelectsThisWay'] and not closure['routingRulesChanged']
sources = load(folder / 'sources.json')
assert sources['primaryDocumentationBrowsingPerformed'] and not sources['browsingHttpBytesAttemptsMeteredOrClaimed']
assert len(sources['sources']) == 10 and len({s['id'] for s in sources['sources']}) == 10
assert all(s['url'].startswith('https://') and s['observedDate'] == '2026-10-26' for s in sources['sources'])
assert all(decision[k] == 0 for k in ['newRoadStatusInterpreterReplicationRequests', 'newToolDownloads', 'newRoutingProviderRequests', 'newMatcherRuns', 'databaseReadsWrites'])
assert not decision['sourceAdapterImplemented'] and not decision['originalFeasibilityQualified']
assert not decision['implementationChanged'] and not decision['runtimeChanged']
local = '--local-assets' in sys.argv
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
    'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True, 'localAssetsChecked': local,
    'reviewedApproaches': 2, 'selectedAcquisitionDesigns': 0, 'unchangedWindows': 21,
    'resourceArithmeticAndSyntheticClosureCheck': True, 'newRoadOrToolRequests': 0,
    'sourceFeasibilityQualified': False, 'v9Unchanged': True}, indent=2))
