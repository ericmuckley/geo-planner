"""Fresh paid geometry/history/node flags/storage receipts; no ignored data or queries."""
import json

from verify_inactive_conditional_graph_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous();geometry=stage('inactive-conditional-derived-geometry',True)
    assert geometry['independentAudit']['directedSourceCostsChecked']==9853365
    assert not geometry['accuracyQualified'] and not geometry['appActivated']
    history=stage('inactive-conditional-context-run',True)
    assert history['contextStates']==34256 and history['contextRuntimeBackingBytes']==1790714
    assert history['retainedStaticForbiddenPairs']==239622 and history['finalForbiddenUnionPairsChecked']==259967
    flags=stage('inactive-conditional-incomplete-flags')
    assert flags['allVertexFlagsIndependentlyCompared']==5731903 and flags['allOriginalBlockersAndRawTagsReplayed']==13776
    assert flags['openedVertices']==1488 and flags['remainingBlockedVertices']==6574
    assert flags['signalsAndReversalBitsExact'] and flags['everyOldUnblockedVertexExact'] and flags['everyIndependentUnconvertedRestrictionContributorRetained']
    assert not flags['routingOrAccuracyAccepted'] and not flags['appActivated']
    for kind,raw,compressed in [('core',129804668,46392946),('geometry',11563162,7958320)]:
        packed=stage('inactive-conditional-codec-'+kind);audit=stage('inactive-conditional-codec-audit-'+kind)
        assert packed['rawBytes']==audit['bytesIndependentlyDecodedAndCompared']==raw
        assert packed['compressedBytes']==audit['compressedBytes']==compressed
        assert audit['sourcePbfReads']==audit['nativeProducerExecutions']==audit['routingQueries']==0
    packed=stage('inactive-conditional-context-wire');audit=stage('inactive-conditional-context-wire-audit')
    assert packed['copiedCoreFieldsByteIdentical']==audit['copiedCoreFieldsByteIdentical']==12
    assert packed['contextRawBytes']==audit['contextBytesIndependentlyCompared']==1790714
    assert packed['combinedCoreAndContextCompressedBytes']==audit['combinedCoreAndContextCompressedBytes']==46851632
    final=stage('inactive-conditional-wire');decoded=stage('inactive-conditional-wire-audit')
    assert final['copiedCoreFieldsByteIdentical']==decoded['copiedCoreFieldsByteIdentical']==12
    assert final['copiedContextFieldsByteIdentical']==decoded['copiedContextFieldsByteIdentical']==6
    assert final['replacedNodeFlagBytes']==decoded['replacementNodeFlagBytesIndependentlyDecoded']==5731903
    assert decoded['contextRawBytesIndependentlyAuthenticated']==1790714 and decoded['coreAndContextBindingsExact']
    assert final['combinedCoreAndContextCompressedBytes']==decoded['combinedCoreAndContextCompressedBytes']==46849273
    assert final['coreManifestSha256']=='3dee327e0ba1204a4b4c003db6d3c51eae1d459a9c8d2724f052d7424060e0a1'
    assert final['contextManifestSha256']=='cb77087b7299b804240421d2cd51463f64fc3c2b1821fb63cdeeefe47ab8253f'
    total=result['newUniqueClosedAllocationBytes']
    prefixes=['derived-geometry','context-run','incomplete-flags','codec-core','codec-geometry','codec-audit-core','codec-audit-geometry','context-wire','context-wire-audit','wire','wire-audit']
    for prefix in prefixes:total+=load(HERE/('inactive-conditional-'+prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total==10736594944 and 64500000000+total+104857600<72*1024**3
    return {**result,'status':'inactive_conditional_fresh_geometry_context_flags_and_all_storage_bytes_audited',
            'registeredClosedRoots':399,'newUniqueClosedAllocationBytes':total,
            'matchingContextStates':34256,'matchingContextRawBytes':1790714,'all1488PriorNodeOpeningsRecomputed':True,
            'coreContextGeometryCompressedBytes':54807593,'freshGeometryContextStorageAndQueriesPending':False,
            'freshEndpointAndFullCandidateScorePending':True,'retainedBackingBytes':None,
            'meanAbsoluteMinutesScope':'Preceding incomplete-node V2 complete candidate only; new inactive-turn score pending.',
            'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
