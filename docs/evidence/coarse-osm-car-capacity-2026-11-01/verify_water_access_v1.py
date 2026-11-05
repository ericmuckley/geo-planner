"""Portable routing-adapter/access proof; no source, graph, model or provider replay."""
import json
from verify_water_geography_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result=previous()
    controls=load(HERE/'water-routing-controls-v1.json')
    assert controls['status']=='nine_generic_water_routing_controls_passed'
    assert controls['tests']==9 and controls['failures']==0 and controls['strictTypesPassed']
    assert controls['npmCheckPassed'] and controls['npmBuildPassed']
    assert sha(HERE/controls['log'])==controls['logSha256']
    for name,pin in controls['bindings'].items(): assert sha(REPO/name)==pin,name
    report=stage('water-access')
    assert report['status']=='completed_all_endpoint_initial_access_profile'
    assert report['inputs']==report['supported']==report['newEndpointCollections']==79
    assert report['reusedEndpointCollections']==report['unsupported']==0
    assert report['originalSupportedInputsRetained']==78
    assert report['totalConnections']==10256 and report['maximumConnections']==1835
    assert report['maskOmissionAllowanceInputs']==0
    assert report['waterPacketBackingBytes']==15340000 and report['waterCompressedBytes']==1781499
    assert report['sourceIncompleteFeatures']==1
    assert len(report['rows'])==79 and all(r['supported'] for r in report['rows'])
    assert all(r['originalSupportedInputRetained'] is not False for r in report['rows'])
    assert all(0<r['connections']<=4096 and not r['offMask'] for r in report['rows'])
    closed=load(HERE/'water-access-closed-v1.json')
    total=result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']
    assert total==5329178624
    return {**result,'waterRoutingAdapterControls':9,'waterAccessSupportedInputs':79,
            'waterAccessPriorPositiveInputsRetained':78,'waterAccessOffMaskAllowances':0,
            'waterAccessChoices':10256,'waterAccessMaximumChoices':1835,
            'newUniqueClosedAllocationBytes':total,'uniqueClosedRoots':156,
            'waterRoutingQueriesMeasured':False,'accuracyOrAppAccepted':False}


if __name__=='__main__': print(json.dumps(verify()))
