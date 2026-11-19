"""Reconcile complete national mandatory-port receipts without large typed facts or routing."""
import json

from verify_conditional_only_ports_capture_v1 import check_port_stage, verify as previous
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    prefix = 'conditional-only-ports-run'
    report, closed = check_port_stage(prefix, [42993567, 5731903, 4227238, 9882872], 48163649)
    plan = load(HERE / (prefix + '-raw-v1/execution-plan.json'))
    assert plan['previousClosedRoots'] == result['registeredClosedRoots'] == 418
    assert plan['newClosedAllocationBytes'] == result['newUniqueClosedAllocationBytes']
    total = result['newUniqueClosedAllocationBytes'] + closed['usage']['conservativeAllocatedBytes']
    assert closed['usage']['conservativeAllocatedBytes'] < 67108864
    assert 64500000000 + total + 104857600 < 72 * 1024**3
    assert 0 < report['sourceSupportedRules'] <= 158
    return {**result, 'status': 'conditional_only_complete_national_ports_qualified_fact_overlay_pending',
            'registeredClosedRoots': 419, 'newUniqueClosedAllocationBytes': total,
            'conditionalOnlyPhysicalSourcePortsValidated': True,
            'conditionalOnlyNationalSupportedRules': report['sourceSupportedRules'],
            'conditionalOnlyNationalFallbackRules': report['retainedFallbackRules'],
            'conditionalOnlyNationalSupportedWithoutToPorts': report['independentAudit']['supportedRulesWithoutToPorts'],
            'conditionalOnlyNationalForbiddenPairsIncludingOverlaps': report['independentAudit']['forbiddenPreArcPairsIncludingOverlaps'],
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
