"""Portable all79 new-ID conditional-source endpoint-access proof."""
import json
from verify_conditional_runtime_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    report = stage('conditional-access')
    assert report['status'] == 'completed_all_endpoint_initial_access_profile'
    assert report['inputs'] == report['supported'] == report['newEndpointCollections'] == 79
    assert report['unsupported'] == report['reusedEndpointCollections'] == report['maskOmissionAllowanceInputs'] == 0
    assert report['originalSupportedInputsRetained'] == 78
    assert report['totalConnections'] == 10273 and report['maximumConnections'] == 1835
    assert len(report['rows']) == 79 and all(not row['offMask'] for row in report['rows'])
    total = result['newUniqueClosedAllocationBytes'] + load(HERE/'conditional-access-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 6318518272
    return {**result, 'conditionalActualLoaderAll79NewConnectionsChecked': 10273,
            'uniqueClosedRoots': 197, 'newUniqueClosedAllocationBytes': total,
            'conditionalActualLoaderOrAccuracyMeasured': True, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
