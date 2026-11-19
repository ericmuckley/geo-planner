"""Portable complete compact context metadata and independent source proof."""
import json

from verify_context_footprint_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    assert stage('context-records-controls', True)['controls'] == dict(tests=16, successful=True, failures=0, errors=0, skips=0)
    report = stage('context-records-run', True)
    assert report['status'] == 'complete_context_records_and_independent_source_audit_passed'
    assert (report['completePreArcsMapped'], report['retainedArcsMapped'], report['contextPrefixGroups'], report['contextStates']) == (9878318, 9807359, 22946, 31692)
    assert report['prohibitedExitArcRecords'] == 20156 and report['activeTriggerPairs'] == 20185
    assert report['supportedTurnPairsRetained'] == 234013 and report['oldFinalForbiddenUnionPairsChecked'] == 252230
    assert report['oldAllowedPathsRemainOrdinary']
    assert report['contextRuntimeBackingBytes'] == 1746705 and report['sourceOnlyForbiddenBytes'] == 1404078
    assert report['selectedRetainedWayArcRecords'] == 55752 and report['additionalQueryLabelBytes'] == 126768
    proof = report['independentAudit']
    assert proof['status'] == 'independent_complete_context_state_exit_trigger_source_audit_passed'
    assert (proof['allContextStatesSourceMapped'], proof['allProhibitedExitArcRecordsChecked'], proof['allActiveEntryTriggerPairsChecked']) == (31692, 20156, 20185)
    assert proof['selectedSourceArcAttributesChecked'] == 59803
    assert proof['oldFinalTurnUnionExact'] and proof['allOldAllowedPathsRemainOrdinary']
    assert report['componentLayoutProjection']['proposedTypedHeldBytes'] == 159505534
    assert not report['componentLayoutProjection']['actualLoaderSearchOrFullAppQualified']
    assert report['requiresTurnContextSearch'] and not report['runtimeQueryImplemented']
    assert report['sourcePbfReads'] == report['sourceConstructorExecutions'] == report['coordinatesRead'] == report['routingQueries'] == 0
    assert not report['sourceCostsFlagsClosureUnionOrPhysicalArcIdsChanged'] and not report['accuracyOrAppQualified'] and not report['appActivated']
    total = result['newUniqueClosedAllocationBytes']
    for name in ('controls', 'run'):
        total += load(HERE/f'context-records-{name}-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 6835003392
    return {**result, 'contextNationalAll31692StatesSourceAudited': True,
            'contextNationalAll20156ExitsSourceAudited': True,
            'contextNationalAll20185TriggersSourceAudited': True,
            'contextNationalRuntimeRecordBackingBytes': 1746705,
            'uniqueClosedRoots': 233, 'newUniqueClosedAllocationBytes': total,
            'contextActualRuntimeOrAccuracyQualified': False, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
