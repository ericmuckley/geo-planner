"""Check closed fact/compiler receipts without reading ignored source or graph files."""
import json

from verify_conditional_node_ports_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    failed = load(HERE / 'conditional-node-facts-controls-closed-v1.json')
    assert failed['terminalRecord'] == 'failure.json'
    root = HERE / 'conditional-node-facts-controls-raw-v1'
    for name, pin in failed['roster'].items():
        if not pin['ignoredLargeAsset']:
            assert sha(root / name) == pin['sha256']
    plan = load(root / 'execution-plan.json')
    for name, pin in plan['inputs'].items():
        if name.startswith(('scripts/', 'routing/', 'docs/')):
            assert sha(REPO / name) == pin
    assert load(root / 'cleanup.json')['independentInspectAbsent']
    assert load(root / 'run-summary.json')['exitCode'] != 0
    assert load(root / 'failure.json')['status'] == 'conditional_node_fact_controls_preinput_dependency_stop'
    stopped = load(HERE / 'conditional-node-facts-v2-preinput-stop-v1.json')
    assert not stopped['outputRootExisted'] and not stopped['workerCreated']
    assert stopped['sourcePbfReads'] == 0
    assert stage('conditional-node-facts-v2-controls', True)['controls'] == dict(
        tests=63, successful=True, failures=0, errors=0, skips=0)
    for operation, count, old, new, turns, flags, arcs, shared in (
        ('capture', 100, 506, 341, 4078, 0, 78363, 9),
        ('run', 1331, 29657, 27421, 409178, 5714, 9837848, 155),
    ):
        key = 'conditional-node-facts-v2-' + operation
        report = stage(key, True)
        assert report['convertedRelations'] == count
        assert report['sourceSupportedOutsideLocalMetadata'] == 0
        assert report['originalFinalClosedWays'] == old and report['newFinalClosedWays'] == new
        assert len(report['reopenedWayIds']) == old - new
        assert report['sharedClosedWaysRetained'] == shared
        assert report['everyIndependentUnconvertedContributorRetained']
        assert report['turnAudit'] == dict(oldSourceTurnsByteExact=turns,
                                          newAllStateJunctionBans=count,
                                          allSourceTurnsIndependentlyCompared=turns + count)
        audit = report['nativeFlagAudit']
        assert audit['changedVertices'] == flags
        assert audit['allVertexFlagsIndependentlyCompared'] == report['sourceCounts']['anchors']
        assert audit['signalsAndReversalBitsExact'] and audit['everyIndependentRestrictionContributorRetained']
        assert audit['everyOldUnblockedVertexExact'] and report['allOtherPhysicalSourceFactsUnchanged']
        assert report['newFinalPostArcs'] == arcs and report['sourcePreArcIdsRetained']
        assert not report['postArcIdsReusable'] and not report['newTimingOrAccuracyQualified']
        assert not report['appActivated']
        for name in ('sourcePbfReads', 'sourceConstructorExecutions', 'routingQueries',
                     'providerRequests', 'applicationDbReads'):
            assert report[name] == 0
        record = load(HERE / (key + '-closed-v1.json'))
        for name, pin in report['assets'].items():
            assert all(record['roster'][name][k] == pin[k] for k in ('bytes', 'sha256'))
        if operation == 'capture':
            compiler = report['compiler']
            assert compiler['dimensions'] == [143560, 46881, 28995, 79148, 78363, 4178]
            proof = compiler['independentCompleteSourceAndEntryAudit']
            assert proof['allPreArcMappingsChecked'] == 79148
            assert proof['baseFields']['directedCostsAndPhysicalReversesChecked'] == 78363
            assert proof['baseFields']['sourceTurnRecordsChecked'] == 4178
            assert proof['finalForbiddenPairsChecked'] == 2858
            assert compiler['physicalFieldsCopiedExactly'] and proof['closureSubsetExact']
        else:
            assert report['compiler'] is None
    total = result['newUniqueClosedAllocationBytes'] + failed['usage']['conservativeAllocatedBytes']
    for operation in ('controls', 'capture', 'run'):
        total += load(HERE / ('conditional-node-facts-v2-' + operation + '-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total == 9525207040
    return {**result, 'status': 'conditional_node_facts_and_captured_compiler_qualified',
            'registeredClosedRoots': 352, 'newUniqueClosedAllocationBytes': total,
            'nationalWholeWayFallbacksReplaced': 1331, 'nationalRoadWaysRecovered': 2236,
            'nationalDirectedSegmentsRecovered': 11218, 'freshNationalGraphPending': True,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
