"""Read-only compatibility proof; no Docker, acquisition or producer replay."""
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
for name in ['execution-plan.json', 'decision.json', 'next-match-plan.json']:
    for path, sha in load(folder / name)['inputs'].items():
        if local or not path.startswith('data/'):
            assert digest(repo / path) == sha, (name, path)
assert digest(folder / 'execution-plan.json') == '6361ce288088706c74722d39112acd7a9da31e364446f08fa84458145c41c3df'
state, audit = load(folder / 'state.json'), load(folder / 'audit.json')
assert state['status'] == 'diagnostic_complete_source_incomplete'
assert state['memoryGuard'] == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0}
assert state['networkRequests'] == state['routingQueries'] == 0 and not state['originalFeasibilityQualified']
container = load(folder / 'container-result.json')
assert container['Limits']['NetworkMode'] == 'none' and container['Limits']['Memory'] == container['Limits']['MemorySwap'] == 1073741824
assert container['State']['ExitCode'] == 0 and not container['State']['OOMKilled'] and load(folder / 'cleanup.json')['removed']
assert audit['independentIdentitySampleMembershipWeightPartitionAndScopeAccounting']
assert audit['retainedRows'] == 55120 and audit['sourceArcWindowRecords'] == 2469 and audit['samplesChecked'] == 85629
assert audit['plannedWindows'] == 21 and audit['completedSourceWindows'] == 0 and not audit['originalFeasibilityQualified']
report, decision = load(folder / 'report.json'), load(folder / 'decision.json')
assert len(report['windows']) == 21 and sum(w['cachedRows'] > 0 for w in report['windows']) == 5
assert all(w['sourceStatus'] == 'incomplete_after_capture_stop' for w in report['windows'])
assert report['completedSourceWindows'] == report['networkRequests'] == report['routingQueries'] == 0 and not report['originalFeasibilityQualified']
assert report['scopeCounts']['speed']['presentRows'] == 6230 and report['scopeCounts']['speed']['missingRows'] == 48890
assert report['scopeCounts']['access']['presentRows'] == 15022 and report['scopeCounts']['access']['missingRows'] == 40098
assert report['frozenLimitStatusCounts']['unsupported_road_role'] == 19795 and report['frozenLimitStatusCounts']['usable'] == 3608
for name in ['allWindows', 'windowsWithCache']:
    group = report[name]
    assert sum(group['statusCounts'].values()) == group['arcCount']
    assert math.isclose(sum(group['statusSourceKm'].values()), group['sourceKm'], abs_tol=1e-8)
    assert math.isclose(sum(group['statusUnionAlignedKm'].values()), group['unionAlignedKm'], abs_tol=1e-8)
    assert math.isclose(group['provisionalEligibleMatchedKm'], 2.8270705809269594, abs_tol=1e-9)
assert report['windowsWithCache']['statusCounts']['union_aligned_without_single_candidate'] == 163
assert math.isclose(report['windowsWithCache']['unionAlignedKm'], 332.47729631451165, abs_tol=1e-9)
metrics = decision['metrics']
assert metrics['absentArcsWithAtLeast80PercentUnion'] == 163 and metrics['samples'] == 85629
assert math.isclose(metrics['unionAlignedPercentInWindowsWithCache'], 100 * report['windowsWithCache']['unionAlignedKm'] / report['windowsWithCache']['sourceKm'], abs_tol=1e-9)
assert not decision['originalFeasibilityQualified'] and not decision['productionModelChanged'] and decision['newNetworkRequests'] == 0
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
    'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True, 'localAssetsChecked': local,
    'retainedRows': 55120, 'sourceArcWindowRecords': 2469, 'samplesChecked': 85629,
    'unionSupportedAbsentArcs': 163, 'completedSourceWindows': 0, 'newNetworkRequests': 0,
    'originalFeasibilityQualified': False, 'v9Unchanged': True}, indent=2))
