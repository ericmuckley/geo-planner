"""Portable complete source-geometry proof, without producer replay."""
import json

from verify_multiway_spatial_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous()
    report=stage('multiway-derived-geometry',True)
    assert report['status']=='multiway_geometry_and_complete_independent_audit_passed'
    proof=report['independentAudit']
    assert (proof['physicalSpansChecked'],proof['directedSourceCostsChecked'],proof['interiorPositionsChecked'],proof['longSpansChecked'])==(6582434,9822101,695689,533395)
    assert proof['curvedSpansChecked']==299233 and proof['runtimeBytes']==11559831
    assert proof['maximumDiscardedSourcePointErrorMeters']<=100 and proof['maximumDiscardedSourceTimeErrorMs']<=10000
    assert proof['sourcePbfReads']==proof['nativeProducerExecutions']==0
    total=result['newUniqueClosedAllocationBytes']+load(HERE/'multiway-derived-geometry-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total==7250468864
    return {**result,'multiViaNationalAll6582434PhysicalSpansSourceAudited':True,
            'multiViaPaidGeometryRuntimeBytes':11559831,
            'uniqueClosedRoots':246,'newUniqueClosedAllocationBytes':total,
            'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
