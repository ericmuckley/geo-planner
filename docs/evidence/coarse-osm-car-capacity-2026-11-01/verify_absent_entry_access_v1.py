"""Portable all79 new-ID absent-member endpoint-access proof; no replay."""
import json

from verify_absent_entry_runtime_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    report = stage('absent-entry-access')
    assert report['status'] == 'completed_all_endpoint_initial_access_profile'
    assert report['inputs'] == report['supported'] == report['newEndpointCollections'] == 79
    assert report['unsupported'] == report['reusedEndpointCollections'] == report['maskOmissionAllowanceInputs'] == 0
    assert report['originalSupportedInputsRetained'] == 78
    assert report['totalConnections'] == 10336 and report['maximumConnections'] == 1838
    assert len(report['rows']) == 79 and all(not row['offMask'] for row in report['rows'])
    total = result['newUniqueClosedAllocationBytes'] + load(HERE/'absent-entry-access-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 6785937408
    return {**result, 'absentMemberActualLoaderAll79NewConnectionsChecked': 10336,
            'uniqueClosedRoots': 221, 'newUniqueClosedAllocationBytes': total,
            'absentMemberActualLoaderOrAccuracyMeasured': True, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
