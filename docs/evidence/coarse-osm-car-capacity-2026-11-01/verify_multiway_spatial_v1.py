"""Portable spatial/source audit; no national producer replay."""
import json

from verify_multiway_graph_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous()
    assert stage('multiway-derived-controls',True)['controls']==dict(tests=37,successful=True,failures=0,errors=0,skips=0)
    report=stage('multiway-derived-spatial',True)
    assert report['status']=='multiway_spatial_and_complete_independent_audit_passed'
    proof=report['independentAudit']
    assert (proof['verticesChecked'],proof['directedArcsCostsPhysicalReversesChecked'],proof['forbiddenTurnPairsChecked'])==(5731903,9822101,257888)
    assert proof['spatialCellsChecked']==56970 and proof['spatialIndexBytes']==341823
    total=result['newUniqueClosedAllocationBytes']
    for name in ('controls','spatial'):
        total+=load(HERE/f'multiway-derived-{name}-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total==7221358592
    return {**result,'multiViaNationalNewSpatialPermutationAllSourceFieldsExact':True,
            'uniqueClosedRoots':245,'newUniqueClosedAllocationBytes':total,
            'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
