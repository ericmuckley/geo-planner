"""Reconcile national mandatory facts, source guards and native-order current flags."""
import json
from verify_conditional_only_facts_capture_v2 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load, sha


def verify():
    result = previous()
    prefix = 'conditional-only-facts-v2-run'
    report = stage(prefix, True)
    plan = load(HERE / (prefix + '-raw-v1/execution-plan.json'))
    assert sha(HERE / (prefix + '-plan-v1.json')) == sha(HERE / (prefix + '-raw-v1/execution-plan.json'))
    assert plan['previousClosedRoots'] == result['registeredClosedRoots'] == 426
    assert plan['newClosedAllocationBytes'] == result['newUniqueClosedAllocationBytes']
    assert report['status'] == 'conditional_only_national_facts_and_retention_independently_audited'
    assert report['allOriginalUnsupportedRelations'] == 70376 and report['previousConvertedRelations'] == 7480
    assert report['mandatoryMetadata'] == report['localMandatoryMetadata'] == report['convertedOnlyRelations'] == 158
    assert report['representedOnlyRelations'] == 30 and report['inactiveFromOnlyRelations'] == 128 and report['localFallbackRelations'] == 0
    assert report['outsideLocalMetadata'] == []
    assert report['currentClosedWays'] == 16968 and report['newClosedWays'] == 16680 and len(report['newUnclosedWayIds']) == 288
    assert report['currentPostArcs'] == 9853365 and report['newFinalPostArcs'] == 9853924
    assert report['combinedEntryPairs'] == 25436 and report['newMandatoryPairs'] == report['newEntryPairs'] == 38
    ports = report['mandatorySourcePortAudit']
    assert ports['allCandidateSourceDescriptorsIndependentlyReplayed'] == 158 and ports['secondSourcePreArcsChecked'] == 9882872
    assert ports['supportedRulesWithoutToPorts'] == 4 and ports['representedRules'] == 30 and ports['inactiveFromRules'] == 128
    assert report['previousSourcePortAudit']['allCandidateSourceDescriptorsIndependentlyReplayed'] == 7480
    assert report['allPreArcRetentionMappingsCounted'] == 9882872
    for key in ['allIndependentContributorsRetained','allOldAllowedTransitionsPreserved','everyCurrentTypedTurnByteExact','everyCurrentFlagRetainedInNativeOrder','sourcePreArcIdsRetained']:
        assert report[key]
    flags = report['currentFlagOrderAudit']
    assert flags['spatialAndNativeRowsIndependentlyCompared'] == 5731903
    assert flags['sourceQualifiedOpenedNodeIdsPreserved'] == report['priorIncompleteNodeOpeningsPreserved'] == 1488
    assert flags['everyOriginalFlagReproducedThroughBijection'] and flags['everyFinalFlagRoundTripsExactly'] and flags['signalsReversalAndIndependentBlockersPreserved']
    assert report['certifiedViaNativeNodeFlagCountsPerRule'] == {'4':19,'6':11}
    assert report['turnAudit'] == dict(oldSourceTurnsByteExact=409178,newAllStateJunctionBans=1331,allSourceTurnsIndependentlyCompared=410509)
    artifacts = load(HERE / (prefix + '-raw-v1/artifacts.json'))
    assert artifacts['cost-facts/flags-0000.bin'] == dict(bytes=5731903,sha256='fbc418484601cc6deadd631b88adfc1aa47ed098de21f126f771e013afc6a579')
    projected = load(HERE / 'conditional-only-inactive-overlay-v1-raw-v1/report.json')
    assert artifacts['cost-facts/closures-0000.bin']['sha256'] == projected['artifacts'][0]['sha256']
    assert artifacts['entry-pairs-pre.u32']['sha256'] == projected['artifacts'][1]['sha256']
    assert artifacts['cost-facts/turns-0000.bin']['sha256'] == '3179550fdd4a05386e0793f5f22d754b1f03b12ab1b28155d1f261dc17be2781'
    closed = load(HERE / (prefix + '-closed-v1.json'))
    for name, item in artifacts.items():
        assert all(closed['roster'][name][key] == item[key] for key in ['bytes','sha256'])
    assert report['sourcePbfReads'] == report['sourceConstructorExecutions'] == report['routingQueries'] == report['providerRequests'] == report['applicationDbReads'] == 0
    assert report['compiler'] is None and not report['newTimingOrAccuracyQualified'] and not report['appActivated'] and not report['postArcIdsReusable']
    total = result['newUniqueClosedAllocationBytes'] + closed['usage']['conservativeAllocatedBytes']
    assert closed['usage']['conservativeAllocatedBytes'] < 268435456 and 64500000000 + total + 104857600 < 72*1024**3
    return {**result,'status':'mandatory_national_facts_and_exact_current_native_flag_order_source_qualified',
            'registeredClosedRoots':427,'newUniqueClosedAllocationBytes':total,
            'conditionalOnlyNewGraphArcsBeforeConstruction':9853924,'conditionalOnlyNationalFactsQualified':True,
            'conditionalOnlyNationalGraphQualified':False,'accuracyOrAppAccepted':False}


if __name__ == '__main__':
    print(json.dumps(verify()))
