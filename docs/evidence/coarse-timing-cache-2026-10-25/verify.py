"""Read-only cache-analysis proof; no Docker, source producer or network."""
import hashlib
import json
import math
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
local = '--local-assets' in sys.argv
for name in ['execution-plan.json', 'execution-plan-v2.json', 'decision.json', 'next-diagnostic-plan.json']:
    for path, sha in load(folder / name)['inputs'].items():
        if local or not path.startswith('data/'):
            assert digest(repo / path) == sha, (name, path)
assert digest(folder / 'execution-plan.json') == 'b2f53de08632e136f3163fbfeb79bbdf391c7e54fc90c80c799b2e2ccf1c98eb'
assert digest(folder / 'execution-plan-v2.json') == 'd50ebaa3d9efbee3bd3c88c61a6135d3577c49c98551c85d5d94be022bbd4cf2'
state, audit = load(folder / 'state.json'), load(folder / 'audit.json')
assert state['status'] == 'offline_analysis_complete_source_incomplete'
assert state['memoryGuard'] == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0}
assert state['networkRequests'] == state['routingQueries'] == 0 and not state['originalFeasibilityQualified']
container = load(folder / 'container-result.json')
assert container['Limits']['NetworkMode'] == 'none' and container['Limits']['Memory'] == container['Limits']['MemorySwap'] == 1073741824
assert container['State']['ExitCode'] == 0 and not container['State']['OOMKilled']
assert load(folder / 'cleanup.json')['removed']
assert audit['independentRawIdentityFieldGeometryAndSourceWeightAudit']
assert audit['retainedRows'] == 55120 and audit['censusArcWindowRecords'] == 2469
assert audit['windows'] == 21 and audit['completedSourceWindows'] == 0 and not audit['originalFeasibilityQualified']
report, decision = load(folder / 'report.json'), load(folder / 'decision.json')
metrics = decision['metrics']
assert len(report['windows']) == 21 and report['completedSourceWindows'] == 0
assert report['fieldNonemptyCounts']['speed_limits'] == metrics['rowsWithSpeedLimits'] == 6230
assert report['limitStatusCounts']['usable'] == metrics['eligibleWholeSpanBidirectionalStaticLimitRows'] == 3608
assert sum(report['limitStatusCounts'].values()) == report['retainedUniqueRows'] == metrics['retainedRows'] == 55120
assert all(w['sourceStatus'] == 'incomplete_after_capture_stop' for w in report['windows'])
assert sum(w['publisherTotals']['bboxCandidateRows'] > 0 for w in report['windows']) == metrics['windowsWithCachedRows'] == 5
source_km = math.fsum(g['sourceKm'] for w in report['windows'] for g in w['sourceClassesKph'].values())
cache_km = math.fsum(g['sourceKm'] for w in report['windows'] if w['publisherTotals']['bboxCandidateRows'] for g in w['sourceClassesKph'].values())
matched_km = math.fsum(g['provisionalStaticLimitMatchedKm'] for w in report['windows'] for g in w['sourceClassesKph'].values())
for name, actual in [('censusSourceKmAllWindows', source_km), ('censusSourceKmWindowsWithCache', cache_km), ('provisionalStaticLimitMatchedCensusKm', matched_km)]:
    assert math.isclose(metrics[name], actual, abs_tol=1e-9), name
assert math.isclose(matched_km, 2.8270705809269594, abs_tol=1e-9)
assert not decision['originalFeasibilityQualified'] and not decision['productionModelChanged'] and decision['newNetworkRequests'] == 0
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    verify_files(load(folder / 'failed-attempt.json')['files'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
    'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True, 'localAssetsChecked': local,
    'retainedRows': 55120, 'censusArcWindowRecords': 2469, 'completedSourceWindows': 0,
    'newNetworkRequests': 0, 'failedPreflightPreserved': True, 'originalFeasibilityQualified': False, 'v9Unchanged': True}, indent=2))
