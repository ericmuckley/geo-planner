"""Portable blocker identity/contributor receipts, retaining every unknown/failure."""
import json

from verify_source_gap_corridors_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    probe = stage('blocked-node-obstruction')
    assert len(probe['rows']) == probe['originalCases'] == 83 and probe['searches'] == 166
    assert probe['blockedVerticesInGraph'] == 13776 and probe['improvedRoadLegs'] == 14
    assert probe['allStaticTurnBansRetained'] == 237741 and probe['singleViaHistoryStatesRetained'] == 34179
    assert probe['nodeMethodRestored'] and not probe['nodeAccessPermissionsVerified'] and not probe['candidateAdmitted']
    assert probe['afterLoad']['arrayBuffers'] == probe['afterQueries']['arrayBuffers'] == 144114287
    assert stage('blocked-node-ids-controls', True)['controls'] == dict(tests=10,successful=True,failures=0,errors=0,skips=0)
    captured = stage('blocked-node-ids-capture', True)
    country = stage('blocked-node-ids-run', True)
    assert captured['blockedVertices'] == captured['allNativeIdTuplesIndependentlyReplayed'] == 97
    assert captured['allGraphToSourceFlagsCompared'] == 46881
    assert country['blockedVertices'] == country['allNativeIdTuplesIndependentlyReplayed'] == 13776
    assert country['allVertexPermutationEntriesChecked'] == country['allGraphToSourceFlagsCompared'] == 5731903
    assert country['nativeIdsRemainUint64'] and country['sourcePbfReads'] == country['routingQueries'] == 0
    plan = load(HERE/'blocked-node-causes-plan-v2.json')
    cache = load(REPO/'docs/evidence/coarse-osm-extraction-2026-10-30/disk-capture-closed-run-v1.json')
    mapping = load(HERE/'blocked-node-ids-run-closed-v1.json')
    for name, pin in plan['bindings'].items():
        if name == plan['cacheDatabase']:
            assert pin == cache['roster']['extract/audit-selected.sqlite']['sha256'] == plan['cacheSha256']
        elif name == plan['relationMetadata']:
            assert pin == plan['relationSha256'] == '2929a9c5febd79bec88da4b2f8bbe4b6fc9bab1bc9229047e60ed4a7fabda332'
        elif name.startswith('data/'):
            assert name == mapping['root']+'/blocked-nodes.json.gz'
            assert pin == mapping['roster']['blocked-nodes.json.gz']['sha256']
        else:
            assert sha(REPO/name) == pin,name
    report = load(HERE/'blocked-node-causes-v2.json')
    assert report['recipeSha256'] == sha(HERE/'blocked-node-causes-plan-v2.json')
    assert report['blockedGraphNodes'] == 13776 and report['rawNodesKnown'] == 97
    assert len(report['unknownRawNodeIds']) == 13679 and not report['sourceReconciliationMismatchNodeIds']
    assert report['knownRawCauseCounts'] == {'restriction-only':16,'base-node':81}
    assert report['allRawUnsupportedRelationsRead'] == 70376
    assert report['allUnsupportedMemberNodeIds'] == 11084 and report['actualNodeOnlyClosureIds'] == 1833
    assert report['blockedGraphNodesWithRestrictionContributors'] == 1501
    assert len(report['all83TrialAttachmentsRetained']) == 83
    assert report['uniqueTrialBlockedNativeNodes'] == 32
    assert report['trialBlockedNodesRawKnown'] == 0 and report['trialBlockedNodesWithRestrictionContributors'] == 14
    assert report['sourcePbfReads'] == report['routingQueries'] == report['providerRequests'] == report['applicationDbReads'] == 0
    assert not report['sourcePermissionsOrPricesChanged'] and not report['appActivated']
    stop = load(HERE/'blocked-node-causes-v1-stop-review.json')
    assert not stop['analysisOutputCreated'] and not stop['cachedSourceSqliteOpened']
    assert stop['review']['allMentionedMemberNodeIds'] == 11084 and stop['review']['actualNodeOnlyClosureIds'] == 1833
    preflight = load(HERE/'blocked-node-causes-preinput-stop-v1.json')
    assert not preflight['planOrDatasetsRead'] and not preflight['analysisOutputCreated']
    total = result['newUniqueClosedAllocationBytes']
    for name in ('blocked-node-obstruction','blocked-node-ids-controls','blocked-node-ids-capture','blocked-node-ids-run'):
        total += load(HERE/(name+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total == plan['newClosedAllocationBytes'] == 9382998016 and plan['previousClosedRoots'] == 331
    return {**result,'status':'all_graph_blocker_ids_and_available_source_causes_audited_unknowns_preserved',
            'blockedGraphNativeIdsMapped':13776,'trialRawNodeMetadataStillUnknown':32,
            'rawNodeAndIndependentRelationContributionsKeptSeparate':True,
            'registeredClosedRoots':331,'newUniqueClosedAllocationBytes':total,
            'accuracyOrAppAccepted':False}


if __name__ == '__main__':
    print(json.dumps(verify()))
