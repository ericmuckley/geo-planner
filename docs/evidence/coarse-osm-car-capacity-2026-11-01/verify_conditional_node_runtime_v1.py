"""Verify the new graph/runtime receipts; no ignored assets or model queries."""
import json

from verify_conditional_node_facts_v2 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    graph = stage('conditional-node-graph-run', True)
    assert graph['basePackedResult']['postClosureArcs'] == 9837848
    assert graph['basePackedResult']['sourceTurnRecords'] == 410509
    assert graph['independentAudit']['allPreArcMappingsChecked'] == 9882872
    assert graph['independentAudit']['baseFields']['directedCostsAndPhysicalReversesChecked'] == 9837848
    assert graph['independentAudit']['finalForbiddenPairsChecked'] == 259656
    assert graph['previousFinalPostArcs'] == 9826630 and graph['conditionalJunctionBansAdded'] == 1331
    assert graph['finalPayloadBytes'] == 129367877 and not graph['appActivated']
    spatial = stage('conditional-node-derived-spatial', True)
    assert spatial['independentAudit']['directedArcsCostsPhysicalReversesChecked'] == 9837848
    assert spatial['independentAudit']['forbiddenTurnPairsChecked'] == 259656
    assert spatial['independentAudit']['verticesChecked'] == 5731903
    geometry = stage('conditional-node-derived-geometry', True)['independentAudit']
    assert geometry['physicalSpansChecked'] == 6593121
    assert geometry['directedSourceCostsChecked'] == 9837848
    assert geometry['interiorPositionsChecked'] == 695863
    assert geometry['runtimeBytes'] == 11561993
    assert geometry['maximumDiscardedSourcePointErrorMeters'] <= 100
    assert geometry['maximumDiscardedSourceTimeErrorMs'] <= 10000
    history = stage('conditional-node-context-run', True)
    assert history['contextStates'] == 34253 and history['contextRuntimeBackingBytes'] == 1788678
    assert history['supportedSourceTurnPairs'] == 236831 and history['retainedStaticForbiddenPairs'] == 239315
    assert history['finalForbiddenUnionPairsChecked'] == 259656
    assert history['independentAudit']['allContextStatesSourceMapped'] == 34253
    assert history['independentAudit']['allActiveEntryTriggerPairsChecked'] == 22673
    assert history['independentAudit']['allProhibitedExitArcRecordsChecked'] == 22689
    assert history['requiresTurnContextSearch'] and not history['accuracyOrAppQualified']
    for kind, raw, compressed, fields in (
        ('core', 129709700, 46368293, 13), ('geometry', 11561993, 7957604, 7),
    ):
        encoded = stage('conditional-node-codec-' + kind)
        audited = stage('conditional-node-codec-audit-' + kind)
        assert encoded['rawBytes'] == audited['bytesIndependentlyDecodedAndCompared'] == raw
        assert encoded['compressedBytes'] == audited['compressedBytes'] == compressed
        assert encoded['fields'] == audited['fields'] == fields
    wire = stage('conditional-node-context-wire')
    decoded = stage('conditional-node-context-wire-audit')
    assert wire['copiedCoreFieldsByteIdentical'] == decoded['copiedCoreFieldsByteIdentical'] == 12
    assert decoded['replacementCoreBytesIndependentlyDecoded'] == 1435890
    assert decoded['contextBytesIndependentlyCompared'] == 1788678
    assert decoded['contextFieldsIndependentlyDecoded'] == 6
    assert wire['combinedCoreAndContextCompressedBytes'] == decoded['combinedCoreAndContextCompressedBytes'] == 46826892
    assert wire['coreManifestSha256'] == '5426229ad6bd91eb7a56e6a2ec18e76bf27bdeb1b610c41898c8404813f9bf18'
    assert wire['contextManifestSha256'] == '0f60213843a07dc121c5221732e36775b91bbd404dd240457d7ca902862d7e9c'
    access = stage('conditional-node-access')
    assert access['inputs'] == access['newEndpointCollections'] == 79
    assert access['reusedEndpointCollections'] == access['unsupported'] == 0
    assert access['supported'] == 79 and access['originalSupportedInputsRetained'] == 78
    assert access['maximumConnections'] <= 4096 and access['maskOmissionAllowanceInputs'] == 0
    assert all(row['reusedPriorEndpoint'] is None for row in access['rows'])
    stopped = load(HERE / 'conditional-node-codec-core-preinput-stop-v1.json')
    assert not stopped['outputRootExisted'] and not stopped['sourceOrGraphInputsRead']
    keys = ['graph-run', 'derived-spatial', 'derived-geometry', 'context-run',
            'codec-core', 'codec-geometry', 'codec-audit-core', 'codec-audit-geometry',
            'context-wire', 'context-wire-audit', 'access']
    total = result['newUniqueClosedAllocationBytes']
    for key in keys:
        total += load(HERE / ('conditional-node-' + key + '-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert 64500000000 + total + 104857600 < 72 * 1024**3
    return {**result, 'status': 'conditional_node_runtime_and_all_fresh_endpoints_qualified',
            'registeredClosedRoots': 363, 'newUniqueClosedAllocationBytes': total,
            'freshNationalGraphPending': False, 'freshNationalGraphArcs': 9837848,
            'matchingContextStates': 34253, 'all79EndpointCollectionsFresh': True,
            'newFullCandidateScorePending': True, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
