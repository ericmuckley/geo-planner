"""Reconcile isolated synthetic port controls; no source/runtime worker execution."""
import json

from verify_conditional_only_inventory_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    prefix = 'conditional-only-ports-controls'
    report = stage(prefix, True)
    assert report['status'] == 'conditional_only_source_ports_controls_passed'
    assert report['controls'] == dict(tests=45, successful=True, failures=0, errors=0, skips=0)
    assert report['sourcePbfReads'] == report['routingQueries'] == 0
    plan = load(HERE / (prefix + '-raw-v1/execution-plan.json'))
    assert plan['previousClosedRoots'] == result['registeredClosedRoots'] == 416
    assert plan['newClosedAllocationBytes'] == result['newUniqueClosedAllocationBytes']
    assert not any(destination.startswith('/facts/') for destination in plan['mounts'].values())
    closed = load(HERE / (prefix + '-closed-v1.json'))
    total = result['newUniqueClosedAllocationBytes'] + closed['usage']['conservativeAllocatedBytes']
    assert closed['usage']['conservativeAllocatedBytes'] < 67108864
    assert 64500000000 + total + 104857600 < 72 * 1024**3
    return {**result, 'status': 'conditional_only_actual_linux_port_controls_qualified_source_reads_pending',
            'registeredClosedRoots': 417, 'newUniqueClosedAllocationBytes': total,
            'conditionalOnlyActualLinuxControls': 45,
            'conditionalOnlyPhysicalSourcePortsValidated': False, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
