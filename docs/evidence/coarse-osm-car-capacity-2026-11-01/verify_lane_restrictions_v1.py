"""Portable fresh-epoch national restriction proof; no producer or large reads."""
import json

from verify_entry_runtime_v1 import stage
from verify_explicit_lane_overlay_v2 import verify as previous
from verify_preparation_v1 import HERE, load


def verify():
    result=previous();total=result['newUniqueClosedAllocationBytes']
    control=stage('lane-restrictions-controls',True)
    assert control['controls']==dict(tests=36,successful=True,failures=0,errors=0,skips=0)
    capture=stage('lane-restrictions-capture',True)
    assert capture['dimensions']==[28995,46881,79148,461,615]
    assert capture['capturedClosureAndPairsMatchQualifiedObjectPrototype'] and capture['capturedReferencePostArcs']==77459
    assert capture['multiVia']['newClosureIds']==506 and capture['multiVia']['combinedEntryPairs']==308
    country=stage('lane-restrictions-run',True)
    assert country['status']=='fresh_source_epoch_single_and_multi_restrictions_independently_audited'
    assert country['dimensions']==[4227238,5731903,9882872,46533,39869]
    assert country['relationInputAudit']==dict(unsupportedRelations=70376,singleViaRules=46533,constantFallbackWayIds=39869,originalClosureIds=149699,rawRelationRuleFallbackAndOriginalUnionExact=True)
    assert country['originalConservativePostArcs']==9665133
    assert country['freshNativeCounts']==[46533,23199,23196,138,149699,99093,23025,9882872,9748979]
    single=country['singleVia'];multi=country['multiVia']
    assert single['baselineAudit']['preArcsChecked']==9882872 and single['baselineAudit']['decisionsChecked']==46533
    assert single['newFinalArcs']==9811860 and single['newClosureIds']==40259
    assert multi['preArcsCheckedTwice']==9882872 and multi['sourceUnsupportedRelationsChecked']==70376
    assert (multi['multiViaRules'],multi['resolvedMultiViaRules'],multi['inactiveMissingMemberMultiRules'],multi['noJoinMultiFallbackRules'])==(3569,2638,917,14)
    assert (multi['newMultiEntryPairs'],multi['combinedEntryPairs'],multi['newClosureIds'],multi['proposedPostArcs'])==(2614,25398,29657,9826630)
    assert multi['independentSourceJoinDecisionCounts']=={'0':2638,'3':917,'2':14}
    for report in (capture,country):
        assert not report['oldNumericArcIdsReused'] and not report['previousLaneGraphMonotonicityAssumed']
        assert not report['sourceCostsFlagsOrPreArcsChanged'] and not report['runtimeGraphBuilt'] and not report['appActivated']
        assert report['sourcePbfReads']==report['coordinatesRead']==report['routingQueries']==0
    for prefix in ('lane-restrictions-controls','lane-restrictions-capture','lane-restrictions-run'):
        total+=load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total==7892664320 and 64500000000+total+104857600+268435456*2<72*1024**3
    return {**result,'status':'fresh_lane_epoch_national_restriction_audits_passed',
            'freshRestrictionLinuxControls':36,'capturedClosureAndEntryOracleExact':True,
            'nationalFreshPreArcsAudited':9882872,'nationalFreshFinalArcs':9826630,
            'oldNumericArcIdsReused':False,'previousGraphMonotonicityAssumed':False,
            'uniqueClosedRoots':280,'newUniqueClosedAllocationBytes':total,
            'laneNationalGraphBuilt':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
