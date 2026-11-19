"""Portable complete conditional paid-geometry/source-cost audit."""
import json
from verify_conditional_spatial_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    report = stage('conditional-derived-geometry', True)
    proof = report['independentAudit']
    assert report['status'] == 'conditional_geometry_and_complete_independent_audit_passed'
    assert proof['physicalSpansChecked'] == 6507003
    assert proof['directedSourceCostsChecked'] == 9744462
    assert proof['curvedSpansChecked'] == 298425 and proof['interiorPositionsChecked'] == 694656
    assert proof['longSpansChecked'] == 531577 and proof['lengthOverflowsChecked'] == 0
    assert proof['runtimeBytes'] == 11534916
    assert proof['maximumDiscardedSourcePointErrorMeters'] <= 100
    assert proof['maximumDiscardedSourceTimeErrorMs'] <= 10000
    assert report['routingQueries'] == report['sourcePbfReads'] == report['providerRequests'] == 0
    assert not report['accuracyQualified'] and not report['appActivated']
    total = result['newUniqueClosedAllocationBytes'] + load(HERE/'conditional-derived-geometry-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 6257414144
    return {**result, 'conditionalGeometryPhysicalSpansSourceChecked': 6507003,
            'conditionalGeometryRuntimeBytes': 11534916, 'uniqueClosedRoots': 192,
            'newUniqueClosedAllocationBytes': total, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
