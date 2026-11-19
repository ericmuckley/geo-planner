"""Portable complete national conditional source-fact overlay, no replay."""
import json
from verify_conditional_country_overlay_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load,sha


def verify():
    result=previous();report=stage('conditional-overlay-country-run',True)
    assert report['status']=='complete_conditional_source_fact_overlay_passed' and report['operation']=='run'
    assert report['sourceCounts']=={'ids':42993567,'xy':85987134,'anchors':5731903,'flags':5731903,'geometry':48163649,'ways':4227238,'arcs':9837326}
    assert report['resultPreClosureArcs']==9878318 and report['resultWays']==4227238 and report['resultFlags']==5731903
    assert report['overlayCounts']=={'records':16288,'changedSourceNodes':2,'changedNodesOutsideSelectedGraph':2,'changedGraphWays':16286,'newPreClosureArcs':40992}
    assert report['allOldSourceRowsAndArcCostsExact'] and report['newNativePricedArcsIndependentlyRebuilt']==40992
    assert report['unsupportedRelationsRead']==70376 and report['relationClosedNodesRetained']==1833
    assert report['overlayBytes']==457109695 and report['insertions']['groups']==16286
    assert report['newPreClosureCostOverflows']==0 and not report['selectedNodeFlagChanges']
    assert report['nationalFactOverlayBuilt'] and not report['runtimeGraphBuilt'] and not report['etaOrAppAccepted']
    review=load(HERE/'conditional-overlay-country-scope-review-v1.json');assert sha(HERE/review['source'])==review['sourceSha256']
    assert load(HERE/review['source'])[review['inheritedField']]==review['inheritedValue']
    assert review['countrySourceFactsRead'] and not review['finishedRuntimeGraphReadOrBuilt'] and not review['producerOrEvidenceChanged']
    record=load(HERE/'conditional-overlay-country-run-closed-v1.json')
    for name,pin in report['factRoster'].items():assert record['roster'][name]['bytes']==pin['bytes'] and record['roster'][name]['sha256']==pin['sha256']
    allocation=result['newUniqueClosedAllocationBytes']+record['usage']['conservativeAllocatedBytes'];assert allocation==5894873088
    return {**result,'conditionalCountryActualOverlayBuilt':True,'conditionalCountryOldPreClosureArcsExact':9837326,
            'conditionalCountryNewPreClosureArcsIndependentlyPriced':40992,'conditionalCountryResultPreClosureArcs':9878318,
            'conditionalCountryRuntimeGraphOrEtaAccepted':False,'uniqueClosedRoots':183,'newUniqueClosedAllocationBytes':allocation,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
