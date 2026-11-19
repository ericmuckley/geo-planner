"""Saved complete-port certificates; no ignored typed facts, native worker or queries."""
import json
from collections import Counter

from verify_conditional_only_port_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def check_port_stage(prefix, counts, geometry):
    report = stage(prefix, True)
    assert report['status'] == 'complete_typed_conditional_only_source_ports_independently_audited'
    assert report['sourceCounts'] == dict(zip(['ids', 'anchors', 'ways', 'arcs'], counts))
    assert [report[k] for k in ['allSourceNodeIdsChecked', 'allSourceAnchorsChecked',
                              'allSourceWayRowsChecked', 'allSourcePreArcsChecked']] == counts
    assert report['sourceGeometryReferenceCount'] == geometry
    assert report['metadataCandidates'] == sum(report['statusCounts'].values()) == 158
    assert report['sourceSupportedRules'] + report['retainedFallbackRules'] == 158
    assert report['statusCounts'].get('source-ports-supported', 0) == report['sourceSupportedRules']
    record = load(HERE / (prefix + '-closed-v1.json'))
    assert all(record['roster'][report['artifact']['file']][k] == report['artifact'][k] for k in ['bytes', 'sha256'])
    assert not record['roster'][report['artifact']['file']]['ignoredLargeAsset']
    descriptors = load(HERE / (prefix + '-raw-v1') / report['artifact']['file'])
    source = load(HERE / 'conditional-only-inventory-v1-raw-v1/candidate-metadata.json')['candidates']
    rows = descriptors['rows']
    assert len(rows) == len(source) == 158
    assert dict(Counter(row['status'] for row in rows)) == report['statusCounts']
    for row, meta in zip(rows, source):
        original = meta['derived']
        for key, name in [('sourceRelationId', 'identity'), ('fromWayId', 'from_way'),
                          ('viaNodeId', 'via_node'), ('toWayId', 'to_way'), ('kind', 'kind')]:
            assert row[key] == original[name]
        incoming, outgoing, target = (row[k] for k in ['incomingPreArcIds', 'allOutgoingPreArcIds', 'toOutgoingPreArcIds'])
        for values in [incoming, outgoing, target]:
            assert values == sorted(set(values)) and all(type(i) is int and 0 <= i < counts[3] for i in values)
        assert set(target) <= set(outgoing)
        if row['status'] == 'source-ports-supported':
            assert incoming and max(len(incoming), len(outgoing), len(target)) <= 64
            assert row['forbiddenPreArcPairs'] == [[a, b] for a in incoming for b in outgoing if b not in target]
        else:
            assert row['forbiddenPreArcPairs'] == []
    audit = report['independentAudit']
    assert audit['allCandidateSourceDescriptorsIndependentlyReplayed'] == 158
    assert audit['secondSourcePreArcsChecked'] == counts[3]
    assert audit['independentSelectedSourcePortRows'] == report['selectedSourcePortRows']
    assert audit['supportedRules'] == report['sourceSupportedRules']
    assert audit['supportedRulesWithoutToPorts'] == sum(r['status'] == 'source-ports-supported' and not r['toOutgoingPreArcIds'] for r in rows)
    assert audit['forbiddenPreArcPairsIncludingOverlaps'] == sum(len(r['forbiddenPreArcPairs']) for r in rows)
    assert not audit['sourceOrGraphChanged']
    for key in ['sourcePbfReads', 'sourceConstructorExecutions', 'routingQueries', 'providerRequests', 'applicationDbReads']:
        assert report[key] == 0
    assert not report['sourcePermissionsOrPricesChanged'] and not report['appActivated']
    assert report['workerSecondsIncludingBindingsAllSourceScansAuditsAndPreservation'] < 900
    return report, record


def verify():
    result = previous()
    prefix = 'conditional-only-ports-capture'
    report, closed = check_port_stage(prefix, [143560, 46881, 28995, 79148], 177956)
    plan = load(HERE / (prefix + '-raw-v1/execution-plan.json'))
    assert plan['previousClosedRoots'] == result['registeredClosedRoots'] == 417
    assert plan['newClosedAllocationBytes'] == result['newUniqueClosedAllocationBytes']
    total = result['newUniqueClosedAllocationBytes'] + closed['usage']['conservativeAllocatedBytes']
    assert 64500000000 + total + 104857600 < 72 * 1024**3
    assert report['sourceSupportedRules'] == 1 and report['retainedFallbackRules'] == 157
    assert report['independentAudit']['forbiddenPreArcPairsIncludingOverlaps'] == 0
    return {**result, 'status': 'conditional_only_complete_captured_ports_qualified_national_pending',
            'registeredClosedRoots': 418, 'newUniqueClosedAllocationBytes': total,
            'conditionalOnlyCapturedPhysicalPortsValidated': True,
            'conditionalOnlyCapturedSupportedRules': 1, 'conditionalOnlyPhysicalSourcePortsValidated': False,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
