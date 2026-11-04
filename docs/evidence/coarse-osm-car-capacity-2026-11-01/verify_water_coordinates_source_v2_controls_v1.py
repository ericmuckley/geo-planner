"""Portable disk-only V2 correction; original failed run remains failed."""
import json
from verify_water_coordinates_stop_v2 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous();revision=load(HERE/'water-coordinate-storage-revision-v2.json')
    clarification=load(HERE/'water-coordinate-storage-revision-v2-clarification-v1.json')
    assert clarification['originalRecordSha256']==sha(HERE/'water-coordinate-storage-revision-v2.json')
    assert clarification['actualWorkerAndClientExit']==1 and clarification['actualHostDriverExit']==2
    assert revision['oldRetainedBytes']==64*1024**3 and revision['newRetainedBytes']==72*1024**3
    assert revision['capacityObservation']['freeBytes']>=revision['newRun']['initialHostFreeMinimumBytes']==88*1024**3
    assert revision['unchanged']['workerMemoryBytes']==4294967296 and revision['unchanged']['swapBytes']==0 and revision['unchanged']['cpus']==2
    assert revision['unchanged']['nativeEncoderAndIndependentDecoderArtifactSha256']=='460f16df0e612990e4c27daf7046634b01717a518d129e616d908cb0f8d2c438'
    assert revision['newRun']['ownedBytes']==2415919104 and revision['newRun']['encodedCompressedSoftBytes']==2147483648
    assert revision['newRun']['jointRawOutputUpperBytes']==1933022118
    pipeline=stage('water-coordinates-source-v2-controls',True)
    assert all(pipeline['checks'][k] for k in ('positivePipeline','wrongSourceRejected','sourceCoordinateShadowExact','completeRequestedIdPartition','producerBuffersReleasedBeforeAudit'))
    assert not pipeline['checks']['nationalSourceMounted'] and not pipeline['checks']['nationalIndexMounted']
    assert pipeline['independentAudit']['allCanonicalSourceIdXYBytesCompared']==64
    return {**result,'waterCoordinateV2DiskOnlyControllerQualified':True,'currentOfflineRetainedEnvelopeBytes':72*1024**3,
            'newUniqueClosedAllocationBytes':3778031616,'uniqueClosedRoots':133,
            'waterNationalCoordinateCaptureCompleted':False,'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
