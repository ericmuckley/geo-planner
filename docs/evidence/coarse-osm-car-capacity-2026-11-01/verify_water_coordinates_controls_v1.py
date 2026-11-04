"""Portable native coordinate/source-shadow/tiny-pipeline qualification."""
import json
from verify_water_references_source_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import closed,load


def verify():
    result=previous();root,_=closed('water-coordinates','build','v1',0)
    artifact=load(root/'result.json')
    assert artifact['artifactBytes']==2008032 and artifact['artifactSha256']=='460f16df0e612990e4c27daf7046634b01717a518d129e616d908cb0f8d2c438'
    root,plan=closed('water-coordinates','controls','v1',0)
    assert load(root/'controls.json')=={'tests':55,'successful':True,'failures':0,'errors':0,'skips':0}
    assert plan['artifact']['sha256']==artifact['artifactSha256']
    pipeline=stage('water-coordinates-source-controls',True)
    assert pipeline['checks']=={'positivePipeline':True,'wrongSourceRejected':True,'nationalSourceMounted':False,'nationalIndexMounted':False,
                               'sourceCoordinateShadowExact':True,'completeRequestedIdPartition':True,'producerBuffersReleasedBeforeAudit':True}
    capture=pipeline['tiny']['coordinates']['capture'];audit=pipeline['independentAudit']
    assert capture['requested']==audit['requestedIdsIndependentlyPartitioned']==5
    assert capture['present']==audit['presentCoordinatesIndependentlyDecoded']==4
    assert capture['missing']==audit['missingIdsIndependentlyCompared']==1
    assert capture['canonicalBytes']==audit['allCanonicalSourceIdXYBytesCompared']==64
    assert pipeline['tiny']['receipt']['pythonProjectionFrames']==0
    return {**result,'waterCoordinateNativeLinuxControls':55,'waterCoordinateTinyControllerAndSourceShadowAuditPassed':True,
            'newUniqueClosedAllocationBytes':3349250048,'uniqueClosedRoots':131,
            'waterNationalCoordinateCaptureCompleted':False,'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
