"""Portable exact mask-component comparison, no graph, source or producer replay."""
import json
from verify_water_routing_controls_v2 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous()
    controls=load(HERE/'water-routing-controls-v5.json')
    assert controls['tests']==20 and controls['failures']==0 and controls['strictTypesPassed']
    assert sha(HERE/controls['log'])==controls['logSha256']
    for name,pin in controls['bindings'].items():assert sha(REPO/name)==pin,name
    report=stage('water-mask-index-profile')
    assert report['status']=='national_frame_mask_ring_index_equal' and len(report['rows'])==2
    assert report['baselineArrayBuffers']==report['releasedArrayBuffers']==72232
    assert report['retainedArrayBuffers']==report['afterQueriesArrayBuffers']==15837780
    assert report['packetBackingBytes']==15340000
    assert report['roadQueries']==report['sourcePbfReads']==report['providerRequests']==0 and not report['modelOrProductionChanged']
    for row in report['rows']:
        assert row['before']['fingerprints']==row['after']['fingerprints']
        assert row['before']['backingBytes']==row['after']['backingBytes']<2097152
    closed=load(HERE/'water-mask-index-profile-closed-v1.json')
    total=result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']
    assert total==5337518080
    return {**result,'waterRingIndexPrototypeControls':20,'waterRingIndexNationalMaskComparisons':2,
            'waterRingIndexEqualLandBoundaryLinks':True,'waterRingIndexAdoptedInCandidate':False,
            'newUniqueClosedAllocationBytes':total,'uniqueClosedRoots':160,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
