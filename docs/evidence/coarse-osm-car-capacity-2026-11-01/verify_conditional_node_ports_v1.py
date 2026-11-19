"""Verify saved source-port receipts; no ignored facts, native worker or query reads."""
import json

from verify_conditional_node_inventory_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    controls = stage('conditional-node-ports-controls')['controls']
    assert controls == dict(tests=26, successful=True, failures=0, errors=0, skips=0)
    total = result['newUniqueClosedAllocationBytes']
    for operation, counts, supported, geometry, ports in (
        ('capture', [143560, 46881, 28995, 79148], 100, 177956, 186),
        ('run', [42993567, 5731903, 4227238, 9882872], 1331, 48163649, 2583),
    ):
        key = 'conditional-node-ports-' + operation
        report = stage(key)
        assert list(report['sourceCounts'].values()) == counts
        assert [report[k] for k in ('allSourceNodeIdsChecked', 'allSourceAnchorsChecked',
                                   'allSourceWayRowsChecked', 'allSourcePreArcsChecked')] == counts
        assert report['sourceGeometryReferenceCount'] == geometry
        assert report['sourceSupportedRules'] == supported
        assert report['retainedFallbackRules'] == 7480 - supported
        assert sum(report['statusCounts'].values()) == report['metadataCandidates'] == 7480
        assert report['statusCounts']['source-ports-supported'] == supported
        assert report['selectedSourcePortRows'] == ports
        proof = report['independentAudit']
        assert proof['allCandidateSourceDescriptorsIndependentlyReplayed'] == 7480
        assert proof['secondSourcePreArcsChecked'] == counts[3]
        assert proof['independentSelectedSourcePortRows'] == ports
        assert proof['supportedRules'] == supported and not proof['sourceOrGraphChanged']
        for k in ('sourcePbfReads', 'sourceConstructorExecutions', 'routingQueries',
                  'providerRequests', 'applicationDbReads'):
            assert report[k] == 0
        assert not report['sourcePermissionsOrPricesChanged'] and not report['appActivated']
        record = load(HERE / (key + '-closed-v1.json'))
        assert all(record['roster']['source-port-descriptors.json.gz'][k] == report['artifact'][k]
                   for k in ('bytes', 'sha256'))
    for operation in ('controls', 'capture', 'run'):
        total += load(HERE / ('conditional-node-ports-' + operation + '-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total == 9489760256
    return {**result, 'status': 'conditional_node_source_ports_qualified_compiler_pending',
            'registeredClosedRoots': 348, 'newUniqueClosedAllocationBytes': total,
            'physicalSourcePortsValidated': True, 'capturedSupportedRules': 100,
            'nationalSupportedRules': 1331, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
