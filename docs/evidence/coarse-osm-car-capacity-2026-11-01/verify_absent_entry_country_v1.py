"""Portable national absent-member metadata and full graph proof; no replay."""
import json

from verify_absent_entry_capture_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    controls = stage('absent-entry-country-controls', True)
    assert controls['controls'] == dict(tests=28, successful=True, failures=0, errors=0, skips=0)
    resolution = stage('absent-entry-country-run', True)
    baseline = resolution['baselineAudit']
    assert (baseline['waysChecked'], baseline['preArcsChecked'], baseline['candidateRulesChecked']) == (4227238, 9878318, 46533)
    assert baseline['fallbackUnionExact'] and baseline['allPairsUseActualSourceNodeIdentity']
    assert (resolution['retainedEntryRules'], resolution['inactiveMissingMemberRules'], resolution['remainingNoJoinFallbackRules']) == (23138, 23257, 138)
    assert (resolution['constantFallbackWayIdsRetained'], resolution['previousClosureIds'], resolution['newClosureIds']) == (39869, 99208, 40259)
    assert (resolution['previousFinalArcs'], resolution['newFinalArcs']) == (9744462, 9807359)
    assert resolution['closureSubset'] and resolution['entryPairsByteIdentical']
    assert resolution['allOldAllowedTransitionsRetainedWithUnchangedSourceFacts']
    assert resolution['sourcePbfReads'] == resolution['sourceConstructorExecutions'] == resolution['nativeKernelExecutions'] == resolution['routingQueries'] == 0
    assert not resolution['sourceCostsOrNodeFlagsChanged'] and not resolution['appActivated']
    controls = stage('absent-entry-graph-controls', True)
    assert controls['controls'] == dict(tests=38, successful=True, failures=0, errors=0, skips=0)
    graph = stage('absent-entry-graph-run', True)
    assert graph['status'] == 'absent_entry_national_graph_and_independent_complete_audit_passed'
    base = graph['basePackedResult']
    assert (base['vertices'], base['preClosureArcs'], base['postClosureArcs']) == (5731903, 9878318, 9807359)
    assert base['costOverflowEntries'] == 2 and base['reverseOverflowEntries'] == 0
    assert graph['augmentationCounts'] == [22964, 234013, 20185, 2779, 252230, 9807359]
    proof = graph['independentAudit']
    assert proof['allPreArcMappingsChecked'] == 9878318 and proof['finalForbiddenPairsChecked'] == 252230
    assert proof['closureSubsetExact'] and proof['oldAllowedTransitionsPreserved']
    assert proof['newEntryPairsOnlyTouchOriginallyClosedArcs']
    assert proof['baseFields']['directedCostsAndPhysicalReversesChecked'] == 9807359
    assert graph['finalPayloadBytes'] == 129140387
    assert graph['routingQueries'] == graph['sourcePbfReads'] == graph['sourceConstructorExecutions'] == 0
    assert not graph['spatialOrPaidGeometryOrCodecBuilt'] and not graph['appActivated']
    total = result['newUniqueClosedAllocationBytes']
    for name in ('country-controls', 'country-run', 'graph-controls', 'graph-run'):
        total += load(HERE/f'absent-entry-{name}-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 6501289984
    return {**result, 'absentMemberNationalMetadataAudited': True,
            'absentMemberNationalDirectedArcsAudited': 9807359,
            'absentMemberArcsRestoredOverConditionalCandidate': 62897,
            'absentMemberNationalForbiddenPairsAudited': 252230,
            'uniqueClosedRoots': 213, 'newUniqueClosedAllocationBytes': total,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
