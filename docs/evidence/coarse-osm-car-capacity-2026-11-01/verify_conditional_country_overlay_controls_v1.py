"""Portable exact country-overlay worker qualification on complete capture."""
import json
from verify_conditional_overlay_capture_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load


def verify():
    result=previous();report=stage('conditional-overlay-country-controls',True)
    assert report['status']=='complete_conditional_source_fact_overlay_passed' and report['operation']=='controls'
    assert report['sourceCounts']=={'ids':143560,'xy':287120,'anchors':46881,'flags':46881,'geometry':177956,'ways':28995,'arcs':78811}
    assert report['resultPreClosureArcs']==79118 and report['newNativePricedArcsIndependentlyRebuilt']==307
    assert report['allOldSourceRowsAndArcCostsExact'] and report['unsupportedRelationsRead']==819 and report['relationClosedNodesRetained']==19
    assert report['overlayBytes']==3506497 and report['insertions']['groups']==108
    assert not report['nationalFactOverlayBuilt'] and not report['runtimeGraphBuilt'] and not report['etaOrAppAccepted']
    allocation=result['newUniqueClosedAllocationBytes']+load(HERE/'conditional-overlay-country-controls-closed-v1.json')['usage']['conservativeAllocatedBytes'];assert allocation==5435531264
    return {**result,'conditionalCountryOverlayWholeCapturedPipelineQualified':True,'conditionalCountryActualOverlayBuilt':False,
            'uniqueClosedRoots':182,'newUniqueClosedAllocationBytes':allocation,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
