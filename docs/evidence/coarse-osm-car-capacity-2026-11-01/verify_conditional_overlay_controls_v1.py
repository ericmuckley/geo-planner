"""Portable synthetic overlay/streaming admission; no actual graph replay."""
import json
from verify_conditional_census_controls_v2 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load


def verify():
    result=previous();report=stage('conditional-overlay-controls',True)
    assert report['status']=='conditional_overlay_synthetic_native_controls_passed'
    assert report['controls']=={'tests':18,'successful':True,'failures':0,'errors':0,'skips':0}
    assert report['sourcePbfReads']==report['countryGraphReads']==report['providerRequests']==report['applicationDbReads']==0
    assert not report['graphOrModelChanged']
    allocation=result['newUniqueClosedAllocationBytes']+load(HERE/'conditional-overlay-controls-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert allocation==5416026112
    return {**result,'conditionalOverlayNativeControls':18,'conditionalOverlayActualGraphMerged':False,
            'uniqueClosedRoots':179,'newUniqueClosedAllocationBytes':allocation,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
