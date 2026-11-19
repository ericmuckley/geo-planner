"""Portable full captured streaming/native overlay equality; no graph replay."""
import json
from verify_conditional_source_v2 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load


def verify():
    result=previous();report=stage('conditional-overlay-capture',True)
    assert report['status']=='complete_captured_conditional_overlay_native_merge_audit_passed'
    assert (report['originalWaysChecked'],report['originalFlagsChecked'],report['originalArcsChecked'])==(28995,46881,78811)
    assert report['changedWayRows']==108 and report['addedNativePricedArcs']==307 and report['changedNodeFlags']==0
    assert report['allOldSourceRowsAndArcCostsExact'] and report['allNewNativePricedArcsChecked']
    assert report['unsupportedSourceRelationsRead']==819 and report['relationClosedNodesRetained']==19
    assert sum(x['bytes'] for x in report['previousConditionalPackedFieldsByteIdentical'])==1038945
    assert report['previousConditionalPaidFixturesExact']==82 and report['previousConditionalFinite']==77 and report['previousConditionalUnavailable']==5
    assert report['queriesExecutedHere']==report['sourcePbfReads']==report['sourceConstructorExecutions']==report['providerRequests']==report['applicationDbReads']==0
    assert not report['nationalGraphMerged'] and not report['appActivated']
    allocation=result['newUniqueClosedAllocationBytes']+load(HERE/'conditional-overlay-capture-closed-v1.json')['usage']['conservativeAllocatedBytes'];assert allocation==5430337536
    return {**result,'conditionalCapturedOverlayAllOldArcsExact':78811,'conditionalCapturedOverlayNewNativeArcs':307,
            'conditionalCapturedOverlayPreviousRoutingBytesExact':1038945,'conditionalCapturedOverlayPaidFixturesExact':82,
            'uniqueClosedRoots':181,'newUniqueClosedAllocationBytes':allocation,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
