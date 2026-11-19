"""Portable complete conditional entry resolution and old-transition proof."""
import json
from verify_conditional_entry_controls_v3 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load


def verify():
    result=previous();report=stage('conditional-entry-resolution-v3-run',True)
    assert report['status']=='conditional_national_entry_resolution_and_independent_audit_passed'
    assert report['nativeCounts']==[46533,23138,23257,138,149699,99208,22964,9878318,9744462]
    proof=report['independentAudit'];assert proof['preArcsChecked']==9878318 and proof['candidateRulesChecked']==46533 and proof['entryPairsChecked']==22964
    assert proof['originalPostArcs']==9660787 and proof['candidatePostArcs']==9744462 and proof['fallbackUnionExact']
    assert report['originalClosureBaselineDelta']=={'originalPostArcs':9620680,'addedPreClosureArcs':40992,'addedArcsOutsideOriginalClosures':40107,'addedArcsInsideOriginalClosures':885,'newPostUnderOriginalClosures':9660787,'insertionGroups':16286}
    keep=report['previousEntryPreservation'];assert keep['allNewClosuresAreOldClosures'] and keep['allOldAllowedSourceTransitionsRetained']
    assert keep['oldEntryPairsRetained']==22835 and keep['newEntryPairs']==22964 and keep['newClosureIds']==99208 and keep['oldClosureIds']==99508
    assert not report['runtimeGraphBuilt'] and not report['appActivated'] and report['sourcePbfReads']==report['sourceConstructorExecutions']==report['routingQueries']==report['providerRequests']==0
    total=result['newUniqueClosedAllocationBytes']+load(HERE/'conditional-entry-resolution-v3-run-closed-v1.json')['usage']['conservativeAllocatedBytes'];assert total==5901737984
    return {**result,'conditionalEntryResolutionComplete':True,'conditionalEntryOldAllowedTransitionsRetained':True,
            'conditionalResolvedCandidateArcs':9744462,'conditionalResolvedAdditionalArcsVsPriorEntry':40612,
            'uniqueClosedRoots':187,'newUniqueClosedAllocationBytes':total,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
