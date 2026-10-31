"""Read-only endpoint-chain proof; no Docker, acquisition or producer replay."""
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
for name in ['execution-plan.json', 'decision.json', 'next-exclusion-plan.json']:
    for path, sha in load(folder / name)['inputs'].items():
        if local or not path.startswith('data/'):
            assert digest(repo / path) == sha, (name, path)
assert digest(folder / 'execution-plan.json') == '84aa2a9446495d7b00be88b1bc8cb271490e77d3092e9c7586dfe411578fd6f5'
state, audit = load(folder / 'state.json'), load(folder / 'audit.json')
assert state['status'] == 'diagnostic_complete_source_incomplete'
assert state['memoryGuard'] == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0}
assert state['networkRequests'] == state['routingQueries'] == 0 and not state['originalFeasibilityQualified']
container = load(folder / 'container-result.json')
assert container['Limits']['NetworkMode'] == 'none' and container['Limits']['Memory'] == container['Limits']['MemorySwap'] == 1073741824
assert container['State']['ExitCode'] == 0 and not container['State']['OOMKilled'] and load(folder / 'cleanup.json')['removed']
assert audit['independentBoundedEnumerationJoinsProgressWeightsAmbiguityCapsAndScopeAccounting']
assert audit['retainedRows'] == 55120 and audit['sourceArcWindowRecords'] == 2469 and audit['samples'] == 85629
assert audit['plannedWindows'] == 21 and audit['completedSourceWindows'] == 0 and audit['hypothesisSupported']
report, decision = load(folder / 'report.json'), load(folder / 'decision.json')
assert len(report['windows']) == 21 and sum(w['cachedRows'] > 0 for w in report['windows']) == 5
assert all(w['sourceStatus'] == 'incomplete_after_capture_stop' for w in report['windows'])
assert report['completedSourceWindows'] == report['networkRequests'] == report['routingQueries'] == 0 and not report['originalFeasibilityQualified']
assert report['scopeRowCounts'] == {'speedRows': 6230, 'accessRows': 15022}
assert report['frozenLimitStatusCounts']['usable'] == 3608 and report['frozenLimitStatusCounts']['unsupported_road_role'] == 19795
assert report['hypothesisSupported'] and decision['hypothesisSupported']
for name in ['allWindows', 'windowsWithCache']:
    group = report[name]
    assert sum(group['statusCounts'].values()) == group['arcCount']
    assert math.isclose(sum(group['statusSourceKm'].values()), group['sourceKm'], abs_tol=1e-8)
    assert group['recordsWithCandidates'] == 32 and group['candidateChains'] == 82 and group['cappedRecords'] == 0
    assert group['formerlyAbsentUncappedWithChain'] == 14
    assert math.isclose(group['formerlyAbsentUncappedSourceKm'], 21.25481114779464, abs_tol=1e-9)
    assert math.isclose(group['baselineProvisionalEligibleKm'], 2.8270705809269594, abs_tol=1e-9)
assert report['allWindows']['statusCounts']['unmeasured_empty_cache'] == 1924
assert report['windowsWithCache']['statusCounts'] == {'unresolved_with_candidates': 32, 'unresolved_without_candidates': 321, 'no_cached_chain': 192}
assert len(decision['positiveArcRecords']) == 14 and all(r['status'] == 'unresolved_with_candidates' for r in decision['positiveArcRecords'])
assert not decision['originalFeasibilityQualified'] and not decision['productionModelChanged'] and decision['newNetworkRequests'] == 0
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
    chains = repo / 'data/coarse-quality/overture-timing-chains-v1/chains.jsonl'
    with chains.open() as stream:
        records = [json.loads(line) for line in stream]
    assert len(records) == 2469 and sum(r['supportsHypothesis'] for r in records) == 14
    assert sum(len(r['candidates']) for r in records) == 82
    assert sum(c['allMembersParserUsable'] for r in records for c in r['candidates']) == 13
    for r in records:
        assert r['expandedStates'] <= 4096 and not r['searchCapped']
        if r['excludedRows']: assert not r['searchExhaustiveForDeclaredRows']
        for c in r['candidates']:
            assert len(c['rowOrdinals']) <= 64 and len(c['rowOrdinals']) == len(set(c['rowOrdinals']))
            assert c['fraction'] >= .8 - 1e-12
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
    'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True, 'localAssetsChecked': local,
    'retainedRows': 55120, 'sourceArcWindowRecords': 2469, 'samples': 85629,
    'formerlyAbsentUncappedWithChain': 14, 'candidateChains': 82, 'candidateArcsStillUnresolved': 32,
    'completedSourceWindows': 0, 'newNetworkRequests': 0, 'originalFeasibilityQualified': False, 'v9Unchanged': True}, indent=2))
