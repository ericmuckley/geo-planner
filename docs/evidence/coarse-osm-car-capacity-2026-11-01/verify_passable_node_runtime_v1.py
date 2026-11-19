"""Saved full source-tag and qualified node-runtime receipts; no ignored asset reads."""
import json

from verify_selected_node_tags_capture_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous()
    collected=stage('selected-node-tags-source-run-v1',True)
    assert collected['selectedTags']['selectedRecords']==collected['selectedTags']['requestedNodes']==13776
    assert collected['causeCounts']=={'restriction-only':1501,'base-node':12275}
    assert collected['allCached97OriginalTagsExact'] and not collected['unknownRawNodeIds']
    assert collected['sourcePbfScans']==1 and collected['routingQueries']==collected['providerRequests']==collected['applicationDbReads']==0
    assert not collected['sourcePermissionsOrPricesChanged'] and not collected['appActivated']
    root=HERE/'selected-node-tags-source-run-v1-raw-v1'
    receipt=load(root/'receipt.json')
    assert receipt['nativeEof'] and receipt['pythonProjectionFrames']==0
    assert receipt['counts']==dict(node=1606229364,way=162688797,relation=1624265)
    assert receipt['semanticSha256']=='209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16'
    closed=load(HERE/'selected-node-tags-source-run-v1-closed-v1.json')
    for name,pin in collected['artifacts'].items():
        assert all(closed['roster'][name][key]==pin[key] for key in ('bytes','sha256'))
    inventory_plan=load(HERE/'blocked-node-tags-inventory-plan-v1.json')
    for name,pin in inventory_plan['bindings'].items():
        if name.startswith('data/'):
            assert name==closed['root']+'/node-evidence.json.gz'
            assert pin==closed['roster']['node-evidence.json.gz']['sha256']
        else:assert sha(REPO/name)==pin,name
    inventory=load(HERE/'blocked-node-tags-inventory-v1.json')
    assert inventory['recipeSha256']==sha(HERE/'blocked-node-tags-inventory-plan-v1.json')
    assert inventory['blockedGraphNodes']==13776 and inventory['unknownRawNodes']==0
    assert len(inventory['all83TrialCases'])==83 and inventory['uniqueTrialBlockedNodes']==32
    assert inventory['trialNodeExposureCounts']=={'None':14,'toll_booth':11,'cattle_grid':6,'gate':1}
    overlay=stage('passable-node-overlay')
    assert overlay['allOriginalBlockersAndRawTagsReplayed']==13776 and overlay['allVertexFlagsIndependentlyCompared']==5731903
    assert overlay['openedVertices']==5714 and overlay['remainingBlockedVertices']==8062
    assert overlay['openedBarrierCounts']=={'cattle_grid':4760,'toll_booth':938,'entrance':16}
    assert overlay['signalsAndReversalBitsExact'] and overlay['everyOldUnblockedVertexExact'] and overlay['everyIndependentRestrictionContributorRetained']
    assert overlay['sourcePbfReads']==overlay['routingQueries']==0 and not overlay['routingOrAccuracyAccepted']
    review=load(HERE/'passable-barriers-source-review-v1.json')
    assert review['policy']==overlay['policy'] and review['syntheticControls']['tests']==7
    for name,pin in review['codeBindings'].items():assert sha(REPO/name)==pin
    routes=stage('passable-node-routes')
    assert routes['originalCases']==83 and len(routes['rows'])==83 and routes['searches']==166
    assert routes['improvedRoadLegs']==9 and routes['sourceQualifiedOpenings']==5714
    assert routes['allBaselineRoadLegTimesReproduced'] and routes['nodeMethodRestored']
    assert routes['allStaticTurnBansRetained']==237741 and routes['singleViaHistoryStatesRetained']==34179
    assert routes['afterLoad']['arrayBuffers']==routes['afterQueries']['arrayBuffers']==144114287
    assert not routes['candidateAdmitted'] and routes['newMaps']==0
    wire=stage('passable-node-wire');audit=stage('passable-node-wire-audit')
    assert wire['copiedCoreFieldsByteIdentical']==audit['copiedCoreFieldsByteIdentical']==12
    assert wire['copiedContextFieldsByteIdentical']==audit['copiedContextFieldsByteIdentical']==6
    assert wire['replacedNodeFlagBytes']==audit['replacementNodeFlagBytesIndependentlyDecoded']==5731903
    assert audit['contextRawBytesIndependentlyAuthenticated']==1786511
    assert wire['combinedCoreAndContextCompressedBytes']==audit['combinedCoreAndContextCompressedBytes']==46805260
    assert audit['coreAndContextBindingsExact']
    core=load(HERE/'passable-node-wire-raw-v1/core/manifest.json')
    context=load(HERE/'passable-node-wire-raw-v1/context/manifest.json')
    assert core['requiresTurnContextSearch'] and context['graphCoreManifestSha256']==wire['coreManifestSha256']
    assert core['fields']['routing/node-flags.u8']['rawSha256']==overlay['artifacts']['proposed-node-flags.u8']['sha256']
    access=stage('passable-node-access')
    prior=load(HERE/'tagged-timing-access-raw-v1/report.json')
    assert access['inputs']==access['supported']==79 and access['unsupported']==0
    assert access['originalSupportedInputsRetained']==78 and access['totalConnections']==10338
    assert access['maximumConnections']==1840 and access['maskOmissionAllowanceInputs']==0
    assert all(a['coordinate']==b['coordinate'] and a['output']==b['output'] for a,b in zip(access['rows'],prior['rows']))
    preinput=load(HERE/'passable-node-access-preinput-stop-v1.json')
    assert not preinput['datasetReads'] and not preinput['outputRootCreated'] and not preinput['codeOrRecipeChanged']
    total=result['newUniqueClosedAllocationBytes']
    for prefix in ('selected-node-tags-source-run-v1','passable-node-overlay','passable-node-routes','passable-node-wire','passable-node-wire-audit','passable-node-access'):
        total+=load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total==9456082944
    return {**result,'status':'complete_original_node_tags_and_generic_passable_runtime_qualified',
            'allGraphBlockerOriginalTagsKnown':13776,'trialRawNodeMetadataStillUnknown':0,
            'nationalOriginalTagsMeasured':True,
            'inheritedTimingMetricsScope':'Previous full timing candidate; corrected full-map result is separate.',
            'sourceQualifiedOpenedVertices':5714,'sourceQualifiedImprovedFixedRoadLegs':9,
            'freshEndpointCollections':79,'newSourcePolicyFullMapAccuracyMeasured':False,
            'registeredClosedRoots':340,'newUniqueClosedAllocationBytes':total,
            'ignoredAssetsReadOrProducerExecutions':0,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
