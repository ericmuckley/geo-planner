"""Verify the compiled mandatory-turn graph from sealed portable evidence only."""
import json
from verify_conditional_only_graph_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load, sha


def verify():
    result=previous();prefix='conditional-only-graph-run'
    report=stage(prefix,True)
    plan=load(HERE/(prefix+'-raw-v1/execution-plan.json'))
    assert sha(HERE/(prefix+'-plan-v1.json'))==sha(HERE/(prefix+'-raw-v1/execution-plan.json'))
    assert plan['previousClosedRoots']==result['registeredClosedRoots']==428
    assert plan['newClosedAllocationBytes']==result['newUniqueClosedAllocationBytes']
    assert report['status']=='conditional_only_national_graph_and_independent_complete_audit_passed'
    base=report['basePackedResult'];proof=report['independentAudit']
    assert base['vertices']==5731903 and base['postClosureArcs']==9853924 and base['preClosureArcs']==9882872
    assert base['sourceTurnRecords']==410509 and base['forbiddenTurnPairs']==237158
    assert proof['baseFields']['directedCostsAndPhysicalReversesChecked']==9853924
    assert proof['baseFields']['sourceTurnRecordsChecked']==410509
    assert proof['allPreArcMappingsChecked']==9882872 and proof['oldDirectedArcsRetained']==9665133
    assert proof['finalForbiddenPairsChecked']==260017
    assert proof['closureSubsetExact'] and proof['newEntryPairsIncomingArcOriginallyClosed'] and proof['oldAllowedTransitionsPreserved']
    assert report['augmentationCounts']==proof['augmentationCounts']==[25436,237158,25033,403,260017,9853924]
    assert report['originalNativeAugmentation']==[25398,237158,24998,400,259987,9853924]
    projection=report['mandatoryIncomingProjection']
    assert projection['allSourcePreArcsReplayed']==9882872 and projection['newIncomingOnlySourcePairs']==38
    assert projection['newActivePairs']==35 and projection['newDroppedPairs']==3
    assert projection['allOriginalNativeFinalPairsRetained'] and projection['allNewIncomingArcsOriginallyClosed'] and projection['noOldAllowedTransitionRemoved']
    assert report['comparisonParentPostArcs']==report['previousFinalPostArcs']==9853365
    assert report['finalPayloadBytes']==129466499
    assert report['sourcePbfReads']==report['sourceConstructorExecutions']==report['routingQueries']==report['providerRequests']==0
    assert not report['spatialOrPaidGeometryOrCodecBuilt'] and not report['appActivated']
    closed=load(HERE/(prefix+'-closed-v1.json'))
    for item in report['assets'].values():
        assert all(closed['roster'][item['path']][key]==item[key] for key in ['bytes','sha256'])
    total=result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']
    assert closed['usage']['conservativeAllocatedBytes']<268435456 and 64500000000+total+104857600<72*1024**3
    return {**result,'status':'mandatory_national_graph_all_source_fields_and_incoming_entry_bans_independently_qualified',
            'registeredClosedRoots':429,'newUniqueClosedAllocationBytes':total,
            'conditionalOnlyNationalGraphQualified':True,'conditionalOnlyGraphArcs':9853924,
            'conditionalOnlyNewRuntimeAssetsAndAccuracyPending':True,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
