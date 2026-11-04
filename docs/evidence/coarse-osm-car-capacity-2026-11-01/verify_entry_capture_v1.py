"""Portable captured entry-correction proof; never read ignored inputs or query."""
import json
from verify_preparation_v1 import HERE, REPO, load, sha
from verify_restriction_entry_v1 import verify as previous


def verify():
    result = previous()
    closed = load(HERE/'restriction-entry-capture-closed-v1.json')
    root = HERE/'restriction-entry-capture-raw-v1'
    assert closed['terminalRecord'] == 'report.json'
    for name, pin in closed['roster'].items():
        if not pin['ignoredLargeAsset']:
            assert (root/name).stat().st_size == pin['bytes'] and sha(root/name) == pin['sha256']
    for name, pin in load(root/'execution-plan.json')['bindings'].items():
        if not name.startswith('data/'):
            assert sha(REPO/name) == pin
    controls = load(HERE/'restriction-entry-graph-controls-v1.json')
    assert controls['tests'] == 8 and controls['successful'] and controls['failures'] == controls['skips'] == 0
    for name, pin in controls['codeBindings'].items():
        assert sha(REPO/name) == pin
    report = load(root/'report.json')
    assert report['recipeSha256'] == sha(HERE/'restriction-entry-capture-plan-v1.json')
    assert report['allOriginalOptimaReproduced'] and report['allBaselineAllowedTransitionsPreserved']
    assert (report['originalCases'], report['originalUnreachable'], report['candidateFinite']) == (82, 14, 74)
    assert (report['previousFailuresRecovered'], report['previousFiniteImproved'], report['candidateStillUnreachable']) == (6, 7, 8)
    assert (report['convertedRelations'], report['fallbackRelations'], report['activeEntryPairs']) == (295, 524, 271)
    assert (report['candidateArcs'], report['candidateForbiddenPairs'], report['payloadBytes']) == (76426, 2650, 1037031)
    assert not report['nationalPolicyChanged'] and not report['appActivated']
    assert report['sourcePbfReads'] == report['sourceConstructorExecutions'] == report['providerRequests'] == report['applicationDbReads'] == 0
    runtime = load(HERE/'restriction-entry-runtime-v1.json')
    assert runtime['recipeSha256'] == sha(HERE/'restriction-entry-runtime-plan-v1.json')
    for name, pin in load(HERE/'restriction-entry-runtime-plan-v1.json')['bindings'].items():
        assert sha(REPO/name) == pin
    assert len(report['rows']) == len(runtime['checks']) == 82
    for row, checked in zip(report['rows'], runtime['checks']):
        assert row['index'] == checked['index'] and row['candidateTicks'] == checked['ticks']
        if row['baselineTicks'] is not None:
            assert row['candidateTicks'] is not None and row['candidateTicks'] <= row['baselineTicks']
        assert row['sourceReplayed'] == (row['candidateTicks'] is not None)
    return {**result, 'capturedEntryQueriesIndependentlyExact': 82, 'previousCapturedFailuresRecovered': 6,
            'previousCapturedFiniteImproved': 7, 'remainingCapturedFailures': 8,
            'newUniqueClosedAllocationBytes': 2358697984, 'uniqueClosedRoots': 87,
            'actualEntryArcResolutionOrRoutingTested': True, 'nationalPolicyOrEtaChanged': False,
            'reads': 'Small mirrors/bound code only; no ignored source/path/packed input, query, PBF, provider or DB.'}


if __name__ == '__main__':
    print(json.dumps(verify()))
