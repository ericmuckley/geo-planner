"""Portable exact compact raster qualification, no country or mask admission."""
import json
from verify_water_excluded_bounds_run_v1 import verify as previous
from verify_preparation_v1 import closed,load


def verify():
    result=previous();root,_=closed('water-raster','build','v1',0);artifact=load(root/'result.json')
    assert artifact['artifactBytes']==424520 and artifact['artifactSha256']=='75e2f039359dcfd85b21d003b365c697f4ca12567b554e23131c3c76e1b22a3c'
    root,plan=closed('water-raster','controls','v1',0)
    assert plan['artifact']['sha256']==artifact['artifactSha256']
    assert load(root/'controls.json')=={'tests':19,'successful':True,'failures':0,'errors':0,'skips':0}
    return {**result,'waterExactRasterLinuxControls':19,'waterCountryCompactRasterCompleted':False,
            'newUniqueClosedAllocationBytes':5300371456,'uniqueClosedRoots':149,
            'waterMaskOrModelChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
