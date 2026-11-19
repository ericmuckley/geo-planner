"""Verify captured mandatory facts and complete native oracle without source replay."""
import json
from verify_conditional_only_fact_controls_v2 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load, sha


def verify():
    result = previous()
    prefix = 'conditional-only-facts-v2-capture'
    report = stage(prefix, True)
    plan = load(HERE / (prefix + '-raw-v1/execution-plan.json'))
    assert sha(HERE / (prefix + '-plan-v1.json')) == sha(HERE / (prefix + '-raw-v1/execution-plan.json'))
    assert plan['previousClosedRoots'] == result['registeredClosedRoots'] == 425
    assert plan['newClosedAllocationBytes'] == result['newUniqueClosedAllocationBytes']
    assert report['status'] == 'conditional_only_captured_facts_and_native_compiler_audited'
    assert report['allOriginalUnsupportedRelations'] == 819 and report['previousConvertedRelations'] == 209
    assert report['mandatoryMetadata'] == 158 and report['localMandatoryMetadata'] == report['convertedOnlyRelations'] == 4
    assert report['representedOnlyRelations'] == 1 and report['inactiveFromOnlyRelations'] == 3 and report['localFallbackRelations'] == 0
    assert len(report['outsideLocalMetadata']) == 154 and all(row['portStatus'] == 'from-way-outside-major-facts' for row in report['outsideLocalMetadata'])
    assert report['currentClosedWays'] == 154 and report['newClosedWays'] == 146 and len(report['newUnclosedWayIds']) == 8
    assert report['currentPostArcs'] == 78757 and report['newFinalPostArcs'] == 78771
    assert report['combinedEntryPairs'] == 308 and report['newMandatoryPairs'] == report['newEntryPairs'] == 0
    assert report['mandatorySourcePortAudit']['allCandidateSourceDescriptorsIndependentlyReplayed'] == 158
    assert report['mandatorySourcePortAudit']['secondSourcePreArcsChecked'] == 79148
    assert report['mandatorySourcePortAudit']['inactiveFromRules'] == 157
    for key in ['allIndependentContributorsRetained','allOldAllowedTransitionsPreserved','everyCurrentTypedTurnByteExact','everyCurrentFlagRetainedInNativeOrder','sourcePreArcIdsRetained']:
        assert report[key]
    compiler = report['compiler']
    assert compiler['dimensions'] == [143560,46881,28995,79148,78771,4178]
    proof = compiler['independentCompleteSourceAndEntryAudit']
    assert compiler['physicalFieldsCopiedExactly'] and proof['allPreArcMappingsChecked'] == 79148
    assert proof['baseFields']['directedCostsAndPhysicalReversesChecked'] == 78771
    assert proof['baseFields']['sourceTurnRecordsChecked'] == 4178 and proof['finalForbiddenPairsChecked'] == 2867
    assert proof['closureSubsetExact'] and proof['newEntryPairsOnlyTouchOriginallyClosedArcs'] and proof['oldAllowedTransitionsPreserved']
    assert report['sourcePbfReads'] == report['sourceConstructorExecutions'] == report['routingQueries'] == report['providerRequests'] == report['applicationDbReads'] == 0
    assert not report['newTimingOrAccuracyQualified'] and not report['appActivated'] and not report['postArcIdsReusable']
    assert report['currentFlagOrderAudit'] is None
    assert report['certifiedViaNativeNodeFlagCountsPerRule'] == {'4': 1}
    old_assets = load(HERE / 'conditional-only-facts-capture-raw-v1/artifacts.json')
    assert load(HERE / (prefix + '-raw-v1/artifacts.json')) == old_assets
    closed = load(HERE / (prefix + '-closed-v1.json'))
    total = result['newUniqueClosedAllocationBytes'] + closed['usage']['conservativeAllocatedBytes']
    assert closed['usage']['conservativeAllocatedBytes'] < 268435456
    assert 64500000000 + total + 104857600 + 2*268435456 < 72*1024**3
    return {**result, 'status':'mandatory_facts_captured_native_compiler_and_all_source_oracle_qualified',
            'registeredClosedRoots':426,'newUniqueClosedAllocationBytes':total,
            'conditionalOnlyCapturedPostArcs':78771,'conditionalOnlyNationalFactsQualified':False,'accuracyOrAppAccepted':False}


if __name__ == '__main__':
    print(json.dumps(verify()))
