"""Saved generic conditional metadata proof; no source port, graph or ignored data reads."""
import json
from verify_passable_node_candidate_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous();report=stage('conditional-node-turns-inventory')
    assert report['allRawUnsupportedRelations']==70376 and sum(report['classificationCounts'].values())==70376
    assert report['metadataCandidates']==7480 and sum(report['candidateKinds'].values())==7480
    assert report['allOriginalWayClosuresIndependentlyReconstructed']==29657
    assert report['potentialUnclosedWaysBeforeSourcePortValidation']==12689
    assert report['potentialBaseEligibleMajorWaysBeforeSourcePortValidation']==6411
    assert report['potentialBaseIneligibleMajorWaysBeforeSourcePortValidation']==203
    assert report['potentialOutsideMajorTableBeforeSourcePortValidation']==6075
    assert report['everyIndependentUnconvertedContributorRetained'] and not report['physicalSourcePortsValidated']
    assert report['sourcePbfReads']==report['sourceConstructorExecutions']==report['routingQueries']==report['providerRequests']==report['applicationDbReads']==0
    assert not report['sourcePermissionsOrPricesChanged'] and not report['appActivated']
    review=load(HERE/'conditional-node-turns-source-review-v2.json')
    assert review['policy']==report['policy'] and review['controls']['tests']==13
    assert review['policy']['relationTypes']==['restriction','restriction:motorcar','restriction:motor_vehicle','restriction:vehicle']
    for name,pin in review['codeBindings'].items():assert sha(REPO/name)==pin,name
    record=load(HERE/'conditional-node-turns-inventory-closed-v1.json')
    assert all(record['roster']['candidate-metadata.json.gz'][key]==report['artifact'][key] for key in ('bytes','sha256'))
    total=result['newUniqueClosedAllocationBytes']+record['usage']['conservativeAllocatedBytes'];assert total==9485426688
    return {**result,'status':'corrected_candidate_closed_conditional_turn_metadata_feasible_ports_pending',
            'registeredClosedRoots':345,'newUniqueClosedAllocationBytes':total,
            'conditionalMetadataCandidates':7480,'potentialMajorWaysBeforePortValidation':6411,
            'physicalSourcePortsValidated':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
