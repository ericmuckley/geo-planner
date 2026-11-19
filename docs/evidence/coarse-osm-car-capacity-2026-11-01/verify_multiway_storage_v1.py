"""Portable complete source and lossless-storage proof, no producer replay."""
import json

from verify_multiway_geometry_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous();total=result['newUniqueClosedAllocationBytes']
    for kind,fields,raw,compressed in [('core',13,129604610,46264539),('geometry',7,11559831,7955821)]:
        packed=stage('multiway-codec-'+kind,False)
        audited=stage('multiway-codec-audit-'+kind,False)
        assert packed['fields']==audited['fields']==fields
        assert packed['rawBytes']==audited['bytesIndependentlyDecodedAndCompared']==raw
        assert packed['compressedBytes']==audited['compressedBytes']==compressed
        assert audited['sourcePbfReads']==audited['nativeProducerExecutions']==audited['routingQueries']==0
        for name in ('multiway-codec-'+kind,'multiway-codec-audit-'+kind):
            total+=load(HERE/f'{name}-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total==7309275136
    return {**result,'multiViaStorageAll141164441RawBytesIndependentlyCompared':True,
            'multiViaCoreAndGeometryCompressedBytes':54220360,
            'uniqueClosedRoots':250,'newUniqueClosedAllocationBytes':total,
            'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
