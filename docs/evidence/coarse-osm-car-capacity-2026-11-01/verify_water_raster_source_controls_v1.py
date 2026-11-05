"""Portable complete tiny compact-water pipeline and preserved pin refusal."""
import json
from verify_water_raster_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load,sha


def verify():
    result=previous();report=stage('water-raster-source-controls',True)
    assert report['controls']=={'tests':21,'successful':True,'failures':0,'errors':0,'skips':0}
    assert not report['nationalDataMounted'] and not report['sourcePbfReads'] and not report['maskOrModelChanged']
    refusal=load(HERE/'water-raster-source-preinput-pin-stop-v1.json')
    assert refusal['recipeSha256']==sha(HERE/refusal['recipe'])
    assert not refusal['rootCreatedByRefusedCommand'] and not refusal['workerCreatedByRefusedCommand'] and not refusal['countryDataReadByRefusedCommand']
    return {**result,'waterCompleteTinyRasterPipelineLinuxControls':21,'waterCountryCompactRasterCompleted':False,
            'newUniqueClosedAllocationBytes':5301825536,'uniqueClosedRoots':150,
            'waterMaskOrModelChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
