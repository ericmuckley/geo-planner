"""Portable qualification of unchanged selected-path source annotation."""
import json
from verify_conditional_access_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    report = stage('conditional-attributes-controls', True)
    assert report['controls'] == {'tests': 7, 'successful': True, 'failures': 0, 'errors': 0, 'skips': 0}
    total = result['newUniqueClosedAllocationBytes'] + load(HERE/'conditional-attributes-controls-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 6319751168
    return {**result, 'conditionalSelectedPathSourceAttributeControls': 7,
            'uniqueClosedRoots': 198, 'newUniqueClosedAllocationBytes': total,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
