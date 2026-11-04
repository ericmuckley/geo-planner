"""Portable typed saved-data catalog qualification, no country geometry claim."""
import json
from verify_water_area_controls_v1 import verify as previous
from verify_preparation_v1 import closed,load


def verify():
    result=previous();root,_=closed('water-catalog','build','v1',0);artifact=load(root/'result.json')
    assert artifact['artifactBytes']==1997192 and artifact['artifactSha256']=='f9674798c5e2135ffb4945d82a45bf970092c8a0f456e12eefbe266fe4cf070e'
    root,plan=closed('water-catalog','controls','v1',0)
    assert load(root/'controls.json')=={'tests':30,'successful':True,'failures':0,'errors':0,'skips':0}
    assert plan['artifact']['sha256']==artifact['artifactSha256']
    assert not plan['policy']['maskOrRoutingChanged']
    return {**result,'waterTypedCatalogLinuxControls':30,
            'waterCountryPolygonProducerQualified':False,
            'newUniqueClosedAllocationBytes':4303839232,'uniqueClosedRoots':140,
            'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
