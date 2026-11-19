"""Portable spatial/geometry/readonly-view native qualification."""
import json
from verify_conditional_graph_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load


def verify():
    result=previous();report=stage('conditional-derived-controls',True)
    assert report['controls']=={'tests':37,'successful':True,'failures':0,'errors':0,'skips':0}
    total=result['newUniqueClosedAllocationBytes']+load(HERE/'conditional-derived-controls-closed-v1.json')['usage']['conservativeAllocatedBytes'];assert total==6035943424
    return {**result,'conditionalSpatialGeometryNativeControls':37,'uniqueClosedRoots':190,'newUniqueClosedAllocationBytes':total,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
