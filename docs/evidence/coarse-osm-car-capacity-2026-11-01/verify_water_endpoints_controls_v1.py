"""Portable endpoint/chain controls and preserved preinput mount refusal."""
import json
from verify_water_coordinates_source_v2_run_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load,sha


def verify():
    result=previous();stopped=load(HERE/'water-endpoints-preinput-stop-v1.json')
    assert stopped['recipeSha256']==sha(HERE/stopped['recipe'])
    assert not stopped['workerCreated'] and not stopped['outputCreated'] and not stopped['sourcePbfRead'] and not stopped['coordinatesRead']
    assert len(stopped['removedUnusedArtifactMounts'])==4
    controls=stage('water-endpoints-controls',True)
    assert controls['controls']=={'tests':26,'successful':True,'failures':0,'errors':0,'skips':0}
    assert not controls['nationalDataMounted'] and not controls['coordinatesExamined']
    return {**result,'waterEndpointAndNativeChainLinuxControls':26,'waterNationalEndpointDiagnosisCompleted':False,
            'newUniqueClosedAllocationBytes':4284268544,'uniqueClosedRoots':135,
            'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
