"""Portable complete conditional CSR/entry controls; no graph replay."""
import json
from verify_conditional_entry_resolution_v3 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load


def verify():
    result=previous();report=stage('conditional-graph-controls',True)
    assert report['controls']=={'tests':38,'successful':True,'failures':0,'errors':0,'skips':0}
    assert report['sourcePbfReads']==0
    total=result['newUniqueClosedAllocationBytes']+load(HERE/'conditional-graph-controls-closed-v1.json')['usage']['conservativeAllocatedBytes'];assert total==5902999552
    return {**result,'conditionalPackedGraphNativeControls':38,'conditionalPackedGraphBuilt':False,
            'uniqueClosedRoots':188,'newUniqueClosedAllocationBytes':total,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
