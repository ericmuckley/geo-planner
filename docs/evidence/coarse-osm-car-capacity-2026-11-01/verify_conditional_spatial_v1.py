"""Portable complete conditional spatial permutation audit."""
import json
from verify_conditional_derived_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load


def verify():
    result=previous();report=stage('conditional-derived-spatial',True);proof=report['independentAudit']
    assert report['status']=='conditional_spatial_and_complete_independent_audit_passed'
    assert proof['verticesChecked']==5731903 and proof['directedArcsCostsPhysicalReversesChecked']==9744462
    assert proof['forbiddenTurnPairsChecked']==250228 and proof['spatialCellsChecked']==56970 and proof['spatialIndexBytes']==341823
    assert report['nativeResult']['totalBytesIncludingOfflinePermutations']==190998276
    assert report['routingQueries']==report['sourcePbfReads']==report['sourceConstructorExecutions']==0 and not report['accuracyQualified']
    total=result['newUniqueClosedAllocationBytes']+load(HERE/'conditional-derived-spatial-closed-v1.json')['usage']['conservativeAllocatedBytes'];assert total==6228377600
    return {**result,'conditionalSpatialPermutationAllArcsExact':9744462,'conditionalSpatialIndexBytes':341823,
            'uniqueClosedRoots':191,'newUniqueClosedAllocationBytes':total,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
