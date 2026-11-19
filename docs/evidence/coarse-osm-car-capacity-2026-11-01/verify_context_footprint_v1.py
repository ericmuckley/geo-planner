"""Portable complete national context metadata/state footprint; no replay."""
import json

from verify_context_turns_capture_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    assert stage('context-footprint-controls', True)['controls'] == dict(tests=8, successful=True, failures=0, errors=0, skips=0)
    report = stage('context-footprint-run', True)
    assert report['status'] == 'complete_typed_static_turn_context_footprint_inventory'
    assert (report['waysChecked'], report['completePreArcsChecked'], report['retainedArcsCounted'], report['rulesChecked']) == (4227238, 9878318, 9807359, 46533)
    assert (report['closureIdsRetained'], report['resolvedRulesRetained'], report['inactiveMissingMemberRulesRetained'], report['noJoinFallbackRulesRetained']) == (40259, 23138, 23257, 138)
    assert (report['allResolvedPrefixGroups'], report['activeEntryPrefixGroups'], report['sourcePreEntryPairsChecked'], report['activeEntryPairs']) == (22946, 20167, 22964, 20185)
    assert report['entryPairsBlockedByOtherClosures'] == 2779
    assert report['additionalContextStateUpperBound'] == 31692
    assert report['possibleStatesIncludingOrdinaryArcs'] == 9839051
    assert report['possibleExitArcRecordsUpperBound'] == 32060
    assert report['rawContextRuntimeFieldsUpperBoundBytes'] == 556497
    assert report['triggerIncomingBitsetBytes'] == 1225920 and report['additionalQueryLabelBytes'] == 126768
    assert report['boundedSelectedPreArcRecords'] == 42277 and report['artifact']['bytes'] == 734272
    projected = report['componentLayoutProjection']
    assert projected['proposedHeldTypedBackingUpperBytes'] == 159541246 <= 162238546
    assert projected['proposedQueryBackingOnSameParentWorkspaceBytes'] == 59798211 < 67108864
    assert projected['retainedProjectionFits'] and projected['queryProjectionFits']
    assert not projected['isRuntimeOrFullAppAdmission']
    assert report['sourcePbfReads'] == report['sourceConstructorExecutions'] == report['routingQueries'] == report['coordinatesRead'] == 0
    assert not report['nationalNodeDictionaryBuilt'] and not report['sourceCostsOrFlagsOrClosureUnionChanged']
    assert not report['runtimeArtifactBuilt'] and not report['accuracyOrAppQualified'] and not report['appActivated']
    total = result['newUniqueClosedAllocationBytes']
    for name in ('controls', 'run'):
        total += load(HERE/f'context-footprint-{name}-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 6828486656
    return {**result, 'contextNationalCompleteStateFootprintMeasured': True,
            'contextNationalAdditionalStates': 31692,
            'contextNationalExtraQueryLabelBytes': 126768,
            'contextRuntimeOrAppMemoryQualified': False,
            'uniqueClosedRoots': 231, 'newUniqueClosedAllocationBytes': total,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
