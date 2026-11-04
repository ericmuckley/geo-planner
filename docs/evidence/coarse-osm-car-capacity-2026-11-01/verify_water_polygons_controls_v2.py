"""Portable complete tiny polygon pipeline, with startup failures preserved."""
import json
from verify_water_catalog_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous()
    preinput=load(HERE/'water-polygons-preinput-stop-v1.json')
    assert preinput['recipeSha256']==sha(HERE/preinput['recipe'])
    assert not preinput['outputCreated'] and not preinput['workerCreated'] and not preinput['countryCoordinateOrWayRead']
    closed=load(HERE/'water-polygons-controls-closed-v1.json');root=HERE/'water-polygons-controls-raw-v1'
    for name,pin in closed['roster'].items():
        if not pin['ignoredLargeAsset']:assert (root/name).stat().st_size==pin['bytes'] and sha(root/name)==pin['sha256']
    for name,pin in load(root/'execution-plan.json')['inputs'].items():
        if name.startswith(('scripts/','routing/','docs/')):assert sha(REPO/name)==pin
    assert closed['terminalRecord']=='failure.json'
    assert 'ModuleNotFoundError' in load(root/'failure.json')['error']
    assert load(root/'container-result.json')['State']['ExitCode']==2
    assert load(root/'cleanup.json')['independentInspectAbsent']
    controls=stage('water-polygons-v2-controls',True)
    assert controls['controls']=={'tests':43,'successful':True,'failures':0,'errors':0,'skips':0}
    assert not controls['nationalDataMounted'] and not controls['sourcePbfReads'] and not controls['maskOrModelChanged']
    short=load(HERE/'water-polygons-v2-short-pin-preinput-stop-v1.json')
    assert short['recipeSha256']==sha(HERE/short['attemptedRecipe'])
    assert not short['outputCreatedByRejectedCommand'] and not short['workerCreatedByRejectedCommand'] and not short['countryDataReadByRejectedCommand']
    return {**result,'waterCompleteTinyPolygonPipelineLinuxControls':43,
            'waterCountryPolygonProducerQualified':True,'waterCountryPolygonRunCompleted':False,
            'newUniqueClosedAllocationBytes':4306751488,'uniqueClosedRoots':142,
            'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
