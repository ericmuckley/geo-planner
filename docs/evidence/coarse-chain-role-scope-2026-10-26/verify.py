"""Read-only additive-report proof; no Docker, network or producer replay."""
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
for name in ['execution-plan.json', 'decision.json', 'next-fragment-plan.json']:
    for path, sha in load(folder / name)['inputs'].items():
        if local or not path.startswith('data/'):
            assert digest(repo / path) == sha, (name, path)
assert digest(folder / 'execution-plan.json') == '755e53b44276429638969645629ab85a0c475a6a1a59a22e07b055f95a3724b2'
state, audit = load(folder / 'state.json'), load(folder / 'audit.json')
assert state['status'] == 'diagnostic_complete_source_incomplete'
assert state['memoryGuard'] == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0}
assert state['networkRequests'] == state['routingQueries'] == 0 and not state['originalFeasibilityQualified']
container = load(folder / 'container-result.json')
assert container['Limits']['NetworkMode'] == 'none' and container['Limits']['Memory'] == container['Limits']['MemorySwap'] == 1073741824
assert container['State']['ExitCode'] == 0 and not container['State']['OOMKilled'] and load(folder / 'cleanup.json')['removed']
assert audit['independentAdditiveRolePartitionOriginalFieldWeightAndOutcomeAudit']
assert audit['retainedRows'] == 55120 and audit['arcWindowRecords'] == 2469 and audit['samples'] == 85629
assert audit['plannedWindows'] == 21 and audit['completedSourceWindows'] == audit['matcherEnumerationsPerformed'] == 0
assert audit['newlyExhaustiveCandidateRecords'] == 0 and not audit['reportingHypothesisSupported']
report, decision = load(folder / 'report.json'), load(folder / 'decision.json')
assert len(report['windows']) == 21 and sum(w['cachedRows'] > 0 for w in report['windows']) == 5
assert all(w['sourceStatus'] == 'incomplete_after_capture_stop' for w in report['windows'])
assert report['completedSourceWindows'] == report['matcherEnumerationsPerformed'] == report['networkRequests'] == report['routingQueries'] == 0
assert not report['originalFeasibilityQualified'] and not report['reportingHypothesisSupported']
assert report['retainedLevelCategories'] == {'missing': 54045, 'partial': 722, 'uniform_nonzero': 353}
assert report['scopeRowCounts'] == {'speedRows': 6230, 'accessRows': 15022}
assert report['frozenLimitStatusCounts']['usable'] == 3608 and report['frozenLimitStatusCounts']['unsupported_road_role'] == 19795
all_records, candidates = report['cohorts']['all'], report['cohorts']['candidate_bearing']
assert all_records['arcCount'] == 2469 and all_records['samples'] == 85629 and all_records['originalCandidateChains'] == 82
assert all_records['originalPositiveRecords'] == 14 and all_records['originalCappedRecords'] == 0
assert all_records['declaredOutOfRoleIncidences'] == 766 and all_records['unresolvedInRoleIncidences'] == 2568
assert all_records['uniqueOutOfRolePublisherIds'] == 286 and all_records['uniqueUnresolvedInRolePublisherIds'] == 709
assert all_records['originalExhaustiveRecords'] == all_records['roleScopedExhaustiveRecords'] == 192
assert math.isclose(all_records['baselineProvisionalEligibleKm'], 2.8270705809269594, abs_tol=1e-9)
assert candidates['arcCount'] == 32 and candidates['originalCandidateChains'] == 82
assert candidates['originalStatusCounts'] == {'unresolved_with_candidates': 32}
assert candidates['roleScopedStatusCounts'] == {'unresolved_in_role_with_candidates': 32}
assert candidates['declaredOutOfRoleIncidences'] == 171 and candidates['unresolvedInRoleIncidences'] == 99
assert candidates['uniqueOutOfRolePublisherIds'] == 72 and candidates['uniqueUnresolvedInRolePublisherIds'] == 48
assert candidates['unresolvedInRoleReasonIncidences'] == {'endpoint_not_near_own_samples': 71, 'unsupported_level_rules': 6, 'nonprogressing_or_tied_endpoints': 16, 'outside_window_endpoint': 6}
assert candidates['outOfRoleReasonIncidences'] == {'unsupported_road_role': 171, 'unsupported_level_rules': 13}
assert candidates['roleScopedExhaustiveRecords'] == candidates['newlyExhaustiveCandidateRecords'] == 0
assert report['cohorts']['empty_cache']['arcCount'] == 1924
assert decision['metrics']['newlyExhaustiveCandidateRecords'] == 0 and not decision['reportingHypothesisSupported']
assert not decision['productionModelChanged'] and not decision['originalFeasibilityQualified']
assert decision['newNetworkRequests'] == decision['matcherEnumerationsPerformed'] == 0
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
    old_path = repo / 'data/coarse-quality/overture-timing-chains-v1/chains.jsonl'
    new_path = repo / 'data/coarse-quality/overture-timing-chain-role-scope-v1/role-scope.jsonl'
    with old_path.open() as stream: old = [json.loads(line) for line in stream]
    with new_path.open() as stream: new = [json.loads(line) for line in stream]
    assert len(old) == len(new) == 2469
    for original, current in zip(old, new, strict=True):
        assert set(current) - set(original) == {'declaredRoleScope', 'reportingProvenance'}
        assert all(current[k] == v for k, v in original.items())
        scope = current['declaredRoleScope']
        assert scope['declaredOutOfRoleRows'] == [r for r in original['excludedRows'] if 'unsupported_road_role' in r['reasons']]
        assert scope['unresolvedInRoleRows'] == [r for r in original['excludedRows'] if 'unsupported_road_role' not in r['reasons']]
        assert not scope['physicalIdentityVerified'] and not scope['carAccessVerified'] and not scope['sourceComplete']
    assert sum(len(r['candidates']) for r in new) == 82
    assert sum(r['declaredRoleScope']['newlyExhaustiveCandidateRecord'] for r in new) == 0
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
    'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True, 'localAssetsChecked': local,
    'retainedRows': 55120, 'arcWindowRecords': 2469, 'samples': 85629,
    'originalCandidateBearingArcsStillUnresolved': 32, 'newlyExhaustiveCandidateRecords': 0,
    'reportingHypothesisSupported': False, 'completedSourceWindows': 0,
    'newMatcherEnumerations': 0, 'newNetworkRequests': 0, 'v9Unchanged': True}, indent=2))
