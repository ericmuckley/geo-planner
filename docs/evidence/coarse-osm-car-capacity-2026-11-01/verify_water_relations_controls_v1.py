"""Portable water relation controls; national extraction is a separate result."""
import json
from verify_water_source_v1 import verify as previous
from verify_entry_runtime_v1 import stage


def verify():
    result=previous()
    controls=stage('water-relations-controls',True)
    assert controls['controls']=={'tests':26,'successful':True,'failures':0,'errors':0,'skips':0}
    assert not controls['nationalSourceMounted']
    return {**result,'waterRelationLinuxControls':26,'waterRelationsPreserved':False,
            'newUniqueClosedAllocationBytes':2861023232,'uniqueClosedRoots':116,
            'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
