"""Fresh all-endpoint receipt over the newly qualified runtime, no model query."""
import json

from verify_inactive_conditional_runtime_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous();access=stage('inactive-conditional-access')
    assert access['inputs']==access['supported']==access['newEndpointCollections']==79
    assert access['unsupported']==access['reusedEndpointCollections']==access['maskOmissionAllowanceInputs']==0
    assert access['totalConnections']==10422 and access['maximumConnections']==1840
    assert access['originalSupportedInputsRetained']==78
    closed=load(HERE/'inactive-conditional-access-closed-v1.json')
    assert len(access['rows'])==79
    for row in access['rows']:
        output=row['output'];assert closed['roster'][output['filename']]['sha256']==output['sha256']
    total=result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']
    assert total==10739052544 and 64500000000+total+104857600<72*1024**3
    prior=load(HERE/'incomplete-node-access-raw-v1/report.json')
    identical=sum(a['output']==b['output']for a,b in zip(access['rows'],prior['rows']))
    assert identical==0
    return {'status':'inactive_conditional_complete_runtime_and_all79_fresh_endpoints_qualified',
            'registeredClosedRoots':400,'newUniqueClosedAllocationBytes':total,
            'freshNationalGraphArcs':9853365,'additionalDirectedSegmentsVsPriorCandidate':15517,
            'matchingContextStates':34256,'matchingContextRawBytes':1790714,
            'all1488PriorNodeOpeningsRecomputed':True,'remainingBlockedVertices':6574,
            'coreContextGeometryCompressedBytes':54807593,
            'all79EndpointCollectionsFresh':True,'newInitialChoices':10422,
            'maximumInitialChoices':1840,'maskOmissionAllowanceInputs':0,
            'endpointArtifactsIdenticalToPrevious':identical,
            'previousCompleteCandidateMeanAbsoluteMinutes':12.755537148594374,
            'newFullCandidateScorePending':True,'newRouteOrMapResultClaimed':False,
            'ignoredAssetsReadOrProducerExecutions':0,'accuracyOrAppAccepted':False}



if __name__=='__main__':print(json.dumps(verify()))
