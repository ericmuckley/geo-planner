"""Portable exact water-point scan controls, no point/land/routing admission."""
import json
from verify_water_polygons_run_v2 import verify as previous
from verify_entry_runtime_v1 import stage


def verify():
    result=previous();report=stage('water-points-controls',True)
    assert report['controls']=={'tests':13,'successful':True,'failures':0,'errors':0,'skips':0}
    assert not report['nationalDataMounted'] and not report['sourcePbfReads'] and not report['maskOrModelChanged']
    return {**result,'waterExactPointScanLinuxControls':13,'waterSavedEndpointWaterScanCompleted':False,
            'newUniqueClosedAllocationBytes':5291761664,'uniqueClosedRoots':144,
            'waterMaskOrModelChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
