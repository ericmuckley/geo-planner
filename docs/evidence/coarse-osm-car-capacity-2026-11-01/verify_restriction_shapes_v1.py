"""Portable metadata-shape inventory proof, with the point-only probe retained."""
import json

from verify_context_points_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    report = stage('restriction-shapes', False)
    assert report['status'] == 'saved_restriction_shapes_inventory_complete'
    national, captured = report['sources']
    assert national['rows'] == sum(national['shapes'].values()) == 70376
    assert national['shapes'] == {'conditional-fallback': 9467, 'static-single-via-way-no': 46533, 'other-static-fallback': 13573, 'static-single-via-way-only': 803}
    assert captured['rows'] == sum(captured['shapes'].values()) == 4900
    assert captured['shapes']['static-single-via-way-only'] == 4
    assert report['sourcePbfReads'] == report['countryGraphReads'] == report['queries'] == 0
    assert not report['policyActivated']
    total = result['newUniqueClosedAllocationBytes'] + load(HERE/'restriction-shapes-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 6886903808
    return {**result, 'savedAll70376UnsupportedRelationShapesChecked': True,
            'staticSingleViaWayOnlyNationalShapes': 803,
            'uniqueClosedRoots': 237, 'newUniqueClosedAllocationBytes': total,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
