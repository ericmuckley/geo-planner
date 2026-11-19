"""Verify isolated native mandatory-fact controls without replaying a worker."""
import json
from verify_conditional_only_facts_stop_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load, sha


def verify():
    result = previous()
    prefix = 'conditional-only-facts-v2-controls'
    report = stage(prefix, True)
    plan = load(HERE / (prefix + '-raw-v1/execution-plan.json'))
    assert report['status'] == 'conditional_only_fact_compiler_controls_passed'
    assert report['controls'] == dict(tests=122, successful=True, failures=0, errors=0, skips=0)
    assert report['sourcePbfReads'] == report['routingQueries'] == 0
    assert not any(dest.startswith('/facts/') for dest in plan['mounts'].values())
    assert plan['previousClosedRoots'] == result['registeredClosedRoots'] == 424
    assert plan['newClosedAllocationBytes'] == result['newUniqueClosedAllocationBytes']
    assert sha(HERE / (prefix + '-plan-v1.json')) == sha(HERE / (prefix + '-raw-v1/execution-plan.json'))
    closed = load(HERE / (prefix + '-closed-v1.json'))
    assert closed['usage']['conservativeAllocatedBytes'] < 268435456
    total = result['newUniqueClosedAllocationBytes'] + closed['usage']['conservativeAllocatedBytes']
    assert 64500000000 + total + 104857600 + 2 * 268435456 < 72 * 1024**3
    return {**result, 'status': 'mandatory_facts_actual_linux_native_compiler_controls_qualified_data_pending',
            'registeredClosedRoots': 425, 'newUniqueClosedAllocationBytes': total,
            'conditionalOnlyActualLinuxNativeFactControls': 122, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
