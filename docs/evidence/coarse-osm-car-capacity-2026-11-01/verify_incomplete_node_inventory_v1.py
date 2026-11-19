"""Saved incomplete-maneuver metadata only; no source/graph load or model query."""
import json

from verify_conditional_node_runtime_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    report = stage('incomplete-node-inventory')
    assert report['allRawUnsupportedRelations'] == sum(report['classificationCounts'].values()) == 70376
    assert report['originalNodeOnlyRelations'] == 2551 and report['originalNodeOnlyClosureIds'] == 1833
    assert report['selectedIncompleteRelations'] == sum(report['selectedKinds'].values()) == 2525
    assert report['allOriginalBlockedNodeTagsReplayed'] == 13776
    assert report['originalRestrictionBlockedGraphNodes'] == 1501
    assert report['currentPassablePolicyBlockedNodes'] == 8062
    assert report['proposedPolicyBlockedNodes'] == 6574 and report['potentialNewOpenGraphNodes'] == 1488
    assert report['nodesRetainingIndependentContributors'] == 13
    assert report['everyDirectNodeGuardRetained'] and report['everyOtherContributorRetained']
    assert not report['actualNodeFlagsChanged'] and not report['nativeOrRuntimeQualified'] and not report['appActivated']
    assert all(report[k] == 0 for k in ('sourcePbfReads', 'routingQueries', 'providerRequests', 'applicationDbReads'))
    review = load(HERE / 'incomplete-node-restrictions-source-review-v1.json')
    assert review['policyId'] == report['policy']['id'] and review['controls']['hostTests'] == 6
    assert not review['controls']['actualLinuxQualified']
    for name, pin in review['codeBindings'].items():
        assert sha(REPO / name) == pin
    stopped = load(HERE / 'incomplete-node-inventory-preinput-stop-v1.json')
    assert not stopped['outputRootExisted'] and not stopped['sourceOrGraphInputsRead']
    record = load(HERE / 'incomplete-node-inventory-closed-v1.json')
    assert all(record['roster']['incomplete-node-metadata.json.gz'][k] == report['artifact'][k]
               for k in ('bytes', 'sha256'))
    plan = load(HERE / 'incomplete-node-inventory-raw-v1/execution-plan.json')
    assert plan['activeCandidateOwnedReserveBytes'] == 268435456
    total = result['newUniqueClosedAllocationBytes'] + record['usage']['conservativeAllocatedBytes']
    assert total == 9998737408
    return {**result, 'status': 'conditional_node_runtime_complete_incomplete_maneuver_metadata_only',
            'registeredClosedRoots': 364, 'newUniqueClosedAllocationBytes': total,
            'incompleteStaticSingletonViaRelations': 2525,
            'potentialAdditionalNodeOpeningsBeforeNativeQualification': 1488,
            'newNodeCorrectionImplemented': False, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
