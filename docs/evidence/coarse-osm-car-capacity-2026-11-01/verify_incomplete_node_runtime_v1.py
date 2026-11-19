"""Saved node-correction qualification and runtime proof; no ignored data or queries."""
import json

from verify_conditional_node_candidate_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    assert stage('incomplete-node-controls', True)['controls'] == dict(
        tests=75, successful=True, failures=0, errors=0, skips=0)
    captured = stage('incomplete-node-capture', True)
    assert captured['dimensions'] == [143560, 46881, 28995, 79148, 78363, 4178]
    assert captured['openedVertices'] == 16 and captured['flagAudit']['allVertexFlagsIndependentlyCompared'] == 46881
    assert captured['independentCompleteSourceCsrAudit']['directedCostsAndPhysicalReversesChecked'] == 78363
    assert captured['independentCompleteSourceCsrAudit']['sourceTurnRecordsChecked'] == 4178
    assert captured['independentCompleteSourceCsrAudit']['forbiddenTurnPairsChecked'] == 2598
    assert captured['allOtherSourceFactsByteExact'] and len(captured['unchangedOtherRoutingFields']) == 10
    flags = stage('incomplete-node-flags')
    assert flags['originalGraphVertices'] == flags['allVertexFlagsIndependentlyCompared'] == 5731903
    assert flags['allOriginalBlockersAndRawTagsReplayed'] == 13776
    assert flags['sourceIncompleteRelations'] == 2525 and flags['openedVertices'] == 1488
    assert flags['remainingBlockedVertices'] == 6574 and flags['signalsAndReversalBitsExact']
    assert flags['everyOldUnblockedVertexExact'] and flags['everyIndependentUnconvertedRestrictionContributorRetained']
    assert not flags['routingOrAccuracyAccepted'] and not flags['appActivated']
    failed = load(HERE / 'incomplete-node-wire-audit-closed-v1.json')
    assert failed['terminalRecord'] == 'failure.json'
    root = HERE / 'incomplete-node-wire-audit-raw-v1'
    for name, pin in failed['roster'].items():
        if not pin['ignoredLargeAsset']:
            assert sha(root / name) == pin['sha256']
    plan = load(root / 'execution-plan.json')
    for name, pin in plan['bindings'].items():
        if name.startswith(('scripts/', 'routing/', 'docs/')):
            assert sha(REPO / name) == pin
    wire = stage('incomplete-node-wire')
    decoded = stage('incomplete-node-wire-audit-v2')
    assert wire['copiedCoreFieldsByteIdentical'] == decoded['copiedCoreFieldsByteIdentical'] == 12
    assert wire['copiedContextFieldsByteIdentical'] == decoded['copiedContextFieldsByteIdentical'] == 6
    assert wire['replacedNodeFlagBytes'] == decoded['replacementNodeFlagBytesIndependentlyDecoded'] == 5731903
    assert decoded['contextRawBytesIndependentlyAuthenticated'] == 1788678
    assert wire['combinedCoreAndContextCompressedBytes'] == decoded['combinedCoreAndContextCompressedBytes'] == 46824533
    assert wire['allPhysicalIdsCostsGeometryAndTurnsUnchanged'] and decoded['coreAndContextBindingsExact']
    assert wire['coreManifestSha256'] == 'fac644b553e17146d4a787c6155e837a7adee6023fe4d001d4385be6a0be5a74'
    assert wire['contextManifestSha256'] == '4f8fc332704de60d990cb6a7efa9ef0e781c148fb2999f3383d374a5f764f7fb'
    access = stage('incomplete-node-access')
    assert access['inputs'] == access['supported'] == access['newEndpointCollections'] == 79
    assert access['unsupported'] == access['reusedEndpointCollections'] == access['maskOmissionAllowanceInputs'] == 0
    assert access['totalConnections'] == 10403 and access['maximumConnections'] == 1840
    assert access['originalSupportedInputsRetained'] == 78
    prior = load(HERE / 'conditional-node-access-raw-v1/report.json')
    assert all(a['coordinate'] == b['coordinate'] and a['output'] == b['output']
               for a, b in zip(access['rows'], prior['rows']))
    total = result['newUniqueClosedAllocationBytes']
    for key in ('controls', 'capture', 'flags', 'wire', 'wire-audit', 'wire-audit-v2', 'access'):
        total += load(HERE / ('incomplete-node-' + key + '-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total == 10092052480
    return {**result, 'status': 'incomplete_node_source_flags_runtime_and_all_endpoints_qualified',
            'registeredClosedRoots': 372, 'newUniqueClosedAllocationBytes': total,
            'newNodeCorrectionImplemented': True, 'sourceQualifiedAdditionalNodeOpenings': 1488,
            'all79EndpointArtifactsFreshAndIdentical': True, 'nextFullCandidateScorePending': True,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
