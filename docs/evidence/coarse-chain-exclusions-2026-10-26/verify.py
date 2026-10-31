"""Read-only exclusion-audit proof; no Docker, acquisition or producer replay."""
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
for name in ['execution-plan.json', 'decision.json', 'next-role-scope-plan.json']:
    for path, sha in load(folder / name)['inputs'].items():
        if local or not path.startswith('data/'):
            assert digest(repo / path) == sha, (name, path)
assert digest(folder / 'execution-plan.json') == 'e11b33da9461de3aaf3a7874fe749896f2050b86722b3de2cc051d0b2546c0f1'
state, audit = load(folder / 'state.json'), load(folder / 'audit.json')
assert state['status'] == 'diagnostic_complete_source_incomplete'
assert state['memoryGuard'] == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0}
assert state['networkRequests'] == state['routingQueries'] == 0 and not state['originalFeasibilityQualified']
container = load(folder / 'container-result.json')
assert container['Limits']['NetworkMode'] == 'none' and container['Limits']['Memory'] == container['Limits']['MemorySwap'] == 1073741824
assert container['State']['ExitCode'] == 0 and not container['State']['OOMKilled'] and load(folder / 'cleanup.json')['removed']
assert audit['independentRawLevelMeasurementOverlapCohortAndDenominatorAudit']
assert audit['retainedRows'] == 55120 and audit['arcWindowRecords'] == 2469 and audit['samples'] == 85629
assert audit['excludedIncidences'] == 3334 and audit['plannedWindows'] == 21 and audit['completedSourceWindows'] == audit['matcherEnumerationsPerformed'] == 0
rejected = load(folder / 'preflight-rejection.json')
assert rejected['outputDirectoryAbsent'] and not rejected['sourceAnalysisPerformed'] and not rejected['dockerAccessPerformed'] and not rejected['frozenRecipeChanged']
assert rejected['verifiedPlanSha256'] == digest(folder / 'execution-plan.json')
report, decision = load(folder / 'report.json'), load(folder / 'decision.json')
assert len(report['windows']) == 21 and sum(w['cachedRows'] > 0 for w in report['windows']) == 5
assert all(w['sourceStatus'] == 'incomplete_after_capture_stop' for w in report['windows'])
assert report['completedSourceWindows'] == report['matcherEnumerationsPerformed'] == report['networkRequests'] == report['routingQueries'] == 0 and not report['originalFeasibilityQualified']
assert report['retainedLevelCategories'] == {'missing': 54045, 'partial': 722, 'uniform_nonzero': 353}
assert report['retainedLevelValueCategories'] == {'missing': 54045, 'uniform_nonzero': 1049, 'mixed': 26}
assert report['scopeRowCounts'] == {'speedRows': 6230, 'accessRows': 15022}
assert report['frozenLimitStatusCounts']['usable'] == 3608 and report['frozenLimitStatusCounts']['unsupported_road_role'] == 19795
all_records, candidates = report['cohorts']['all'], report['cohorts']['candidate_bearing']
assert all_records['arcCount'] == 2469 and all_records['samples'] == 85629 and all_records['candidateChains'] == 82
assert all_records['formerlyAbsentPositiveRecords'] == 14 and all_records['cappedRecords'] == 0
assert all_records['excludedIncidences'] == 3334 and all_records['uniqueExcludedPublisherIds'] == 995
assert math.isclose(all_records['baselineProvisionalEligibleKm'], 2.8270705809269594, abs_tol=1e-9)
assert candidates['arcCount'] == 32 and candidates['excludedIncidences'] == 270 and candidates['uniqueExcludedPublisherIds'] == 120
assert candidates['originalStatusCounts'] == {'unresolved_with_candidates': 32}
assert candidates['candidateOverlapIncidences'] == {'sample_and_endpoint': 36, 'sample_only': 208, 'neither': 26}
assert candidates['reasonIncidences']['unsupported_road_role'] == 171 and candidates['reasonIncidences']['unsupported_level_rules'] == 19
assert report['cohorts']['empty_cache']['arcCount'] == 1924 and report['cohorts']['empty_cache']['excludedIncidences'] == 0
assert decision['metrics']['explicitUniformZeroRows'] == 0 and not decision['productionModelChanged'] and not decision['originalFeasibilityQualified']
assert decision['newNetworkRequests'] == decision['matcherEnumerationsPerformed'] == 0
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
    path = repo / 'data/coarse-quality/overture-timing-chain-exclusions-v1/exclusions.jsonl'
    with path.open() as stream: records = [json.loads(line) for line in stream]
    assert len(records) == 2469 and sum(len(r['excluded']) for r in records) == 3334
    assert len({i['ordinal'] for r in records for i in r['excluded']}) == 995
    assert sum(r['sampleCount'] for r in records) == 85629 and sum(r['candidateCount'] for r in records) == 82
    assert all(r['sourceStatus'] == 'incomplete_after_capture_stop' for r in records)
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
    'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True, 'localAssetsChecked': local,
    'retainedRows': 55120, 'arcWindowRecords': 2469, 'samples': 85629,
    'excludedIncidences': 3334, 'uniqueExcludedPublisherIds': 995, 'candidateExcludedIncidences': 270,
    'uniformZeroLevelRows': 0, 'originalCandidateBearingArcsStillUnresolved': 32,
    'completedSourceWindows': 0, 'newMatcherEnumerations': 0, 'newNetworkRequests': 0, 'v9Unchanged': True}, indent=2))
