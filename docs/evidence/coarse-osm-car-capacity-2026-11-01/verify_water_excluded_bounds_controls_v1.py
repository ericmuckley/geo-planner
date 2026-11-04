"""Portable excluded-source coverage controls, no geographic admission."""
import json
from verify_water_points_run_v1 import verify as previous
from verify_entry_runtime_v1 import stage


def verify():
    result=previous();report=stage('water-excluded-bounds-controls',True)
    assert report['controls']=={'tests':45,'successful':True,'failures':0,'errors':0,'skips':0}
    assert not report['nationalDataMounted'] and not report['sourcePbfReads'] and not report['maskOrModelChanged']
    return {**result,'waterExcludedSourceBoundsLinuxControls':45,'waterExcludedSourceBoundsRunCompleted':False,
            'newUniqueClosedAllocationBytes':5294886912,'uniqueClosedRoots':146,
            'waterMaskOrModelChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
