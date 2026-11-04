"""Portable strict area-helper qualification; no country polygon admission."""
import json
from verify_water_endpoints_run_v1 import verify as previous
from verify_preparation_v1 import closed,load


def verify():
    result=previous();root,_=closed('water-area','build','v1',0)
    artifact=load(root/'result.json')
    assert artifact['artifactBytes']==1902656
    assert artifact['artifactSha256']=='ef478ffb909fee3720ccafda461623c64dce7bc8425ec8e176db4db8aff2d942'
    root,plan=closed('water-area','controls','v1',0)
    assert plan['artifact']['sha256']==artifact['artifactSha256']
    assert load(root/'controls.json')=={'tests':20,'successful':True,'failures':0,'errors':0,'skips':0}
    assert plan['caps']['overallRetainedBytes']==77309411328
    assert not plan['policy']['maskOrRoutingChanged']
    assert all(not name.endswith(('.pbf','/001.bin','.sqlite','.jsonl')) for name in plan['inputs'])
    return {**result,'waterStrictAreaHelperLinuxControls':20,
            'waterCountryPolygonProducerQualified':False,
            'newUniqueClosedAllocationBytes':4298035200,'uniqueClosedRoots':138,
            'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
