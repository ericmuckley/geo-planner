"""Portable mask-link CPU evidence; no graph or producer replay."""
import json
from verify_water_mask_index_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load


def verify():
    result=previous(); report=stage('water-mask-cpu-profile')
    assert report['status']=='water_mask_links_cpu_profile_complete'
    assert report['samples']==19520 and report['profile']['bytes']==175704
    assert report['baselineArrayBuffers']==report['releasedArrayBuffers']==72590
    assert report['roadQueries']==report['sourcePbfReads']==report['providerRequests']==0
    original=load(HERE/'water-mask-index-profile-raw-v1/report.json')['rows'][0]['before']
    assert report['fingerprints']==original['fingerprints']
    ring_samples=sum(row['exclusiveSamples'] for row in report['topSelf'] if row['function']=='containsIndexedRing')
    assert ring_samples==9897
    closed=load(HERE/'water-mask-cpu-profile-closed-v1.json')
    total=result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']
    assert total==5338836992
    return {**result,'waterMaskLinkCpuSamples':19520,'waterMaskTopRingMembershipSamples':9897,
            'newUniqueClosedAllocationBytes':total,'uniqueClosedRoots':161,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
