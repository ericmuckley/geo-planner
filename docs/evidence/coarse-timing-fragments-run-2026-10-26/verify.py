"""Read-only measured-result proof; no Docker, geometry or producer replay."""
import hashlib
import json
import math
from pathlib import Path
import sys

from metrics import derive

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
plan_path = repo / 'docs/evidence/coarse-timing-fragments-2026-10-26/execution-plan.json'
assert digest(plan_path) == '509e98e071d67659698a550e6672766bad5e820a4f8d82c20688199669913fdd'
for record in [load(plan_path), load(folder / 'decision.json'), load(folder / 'next-input-design-plan.json')]:
    for path, sha in record['inputs'].items():
        if local or not path.startswith('data/'):
            assert digest(repo / path) == sha, path
state, audit = load(folder / 'state.json'), load(folder / 'audit.json')
assert state['status'] == 'diagnostic_complete_source_incomplete'
assert state['memoryGuard'] == {'memoryMaxBytes': 1073741824, 'swapMaxBytes': 0}
assert state['networkRequests'] == state['routingQueries'] == 0 and not state['originalFeasibilityQualified']
container = load(folder / 'container-result.json')
assert container['Limits']['NetworkMode'] == 'none' and container['Limits']['ReadonlyRootfs']
assert container['Limits']['Memory'] == container['Limits']['MemorySwap'] == 1073741824
assert container['State']['ExitCode'] == 0 and not container['State']['OOMKilled'] and load(folder / 'cleanup.json')['removed']
assert audit['independentProjectionIntervalConnectorUnionEnumerationAndOriginalControlAudit']
assert (audit['retainedRows'], audit['arcWindowRecords'], audit['samples']) == (55120, 2469, 85629)
assert audit['newUncappedClippedRecords'] == 96 and audit['hypothesisSupported'] and audit['completedSourceWindows'] == 0
report, decision, metrics = (load(folder / n) for n in ['report.json', 'decision.json', 'metrics.json'])
totals = report['allWindows']
assert totals['arcCount'] == 2469 and totals['samples'] == 85629
assert totals['statusCounts'] == {'unmeasured_empty_cache': 1924, 'cached_geometry_candidates': 128, 'no_candidate_under_fragment_rules': 417}
assert totals['recordsWithCandidates'] == 128 and totals['fragmentCandidates'] == 294 and totals['cappedRecords'] == 0
assert totals['originalCandidates'] == 82 and totals['originalCandidateBearingRecords'] == 32
assert totals['newUncappedClippedRecords'] == 96 and math.isclose(totals['newUncappedClippedSourceKm'], 61.774001360121694, abs_tol=1e-9)
assert math.isclose(totals['baselineProvisionalEligibleKm'], 2.8270705809269594, abs_tol=1e-9)
assert len(report['windows']) == 21 and sum(w['cachedRows'] > 0 for w in report['windows']) == 5
assert all(w['sourceStatus'] == 'incomplete_after_capture_stop' for w in report['windows'])
assert report['hypothesisSupported'] and report['completedSourceWindows'] == report['networkRequests'] == report['routingQueries'] == 0
assert not report['originalFeasibilityQualified'] and decision['hypothesisSupported'] and not decision['productionModelChanged']
new, all_records = metrics['cohorts']['new_clipped_positive'], metrics['cohorts']['all']
assert new['arcRecords'] == 96 and new['candidateVariants'] == 185 and new['originalStatusCounts'] == {'unresolved_without_candidates': 96}
assert new['recordsWithAnyAllParserUsableCandidate'] == 5 and new['allParserUsableCandidateVariants'] == 7
assert math.isclose(new['parserUsableCandidateSampleUnionKm'], 1.0333405652876946, abs_tol=1e-9)
assert all_records['recordsWithAnyAllParserUsableCandidate'] == 18 and all_records['allParserUsableCandidateVariants'] == 36
assert math.isclose(all_records['parserUsableCandidateSampleUnionKm'], 8.64864381270001, abs_tol=1e-9)
assert all_records['originalStatusCounts'] == {'unmeasured_empty_cache': 1924, 'unresolved_with_candidates': 32, 'unresolved_without_candidates': 321, 'no_cached_chain': 192}
if local:
    verify_files(checks['assetFiles'], repo)
    verify_files(checks['toolFiles'], repo)
    for path, names in checks['completedOutputs'].items():
        assert set(names) == {str(p.relative_to(repo / path)) for p in (repo / path).rglob('*') if p.is_file()}, path
    root = repo / 'data/coarse-quality/overture-timing-fragments-v1'
    for name in ['report.json', 'audit.json', 'state.json', 'container-result.json', 'cleanup.json']:
        assert digest(root / name) == digest(folder / name)
    assert digest(root / 'execution-plan.json') == digest(plan_path)
    assert derive(root, repo / 'data/coarse-quality/overture-timing-compatibility-v1/support.jsonl',
        repo / 'docs/evidence/coarse-chain-role-scope-2026-10-26/report.json') == metrics
    with (repo / 'data/coarse-quality/overture-timing-chains-v1/chains.jsonl').open('rb') as stream:
        original = {}
        for raw in stream:
            r = json.loads(raw); original[r['windowId'], r['arc']] = (r, hashlib.sha256(raw).hexdigest())
    with (root / 'fragments.jsonl').open() as stream:
        for r in map(json.loads, stream):
            old, sha = original.pop((r['windowId'], r['arc']))
            assert r['original'] == old and r['originalLineSha256'] == sha
            full = {n['ordinal']: n for n in old['nodes']}
            for node in r['nodes']:
                if node['mode'] == 'full': assert all(node[k] == v for k, v in full[node['ordinal']].items())
    assert not original
print(json.dumps({'recordFiles': len(manifest), 'producerFiles': len(checks['producerFiles']),
    'priorSealedRuns': len(checks['priorSealedEvidence']), 'allBindingsValid': True, 'localAssetsChecked': local,
    'retainedRows': 55120, 'arcWindowRecords': 2469, 'samples': 85629,
    'newUncappedClippedRecords': 96, 'hypothesisSupported': True, 'candidateBearingRecords': 128,
    'newRecordsWithParserUsableCandidate': 5, 'qualifiedNewSpeedCoverageAdmitted': False,
    'completedSourceWindows': 0, 'newNetworkRequests': 0, 'v9Unchanged': True}, indent=2))
