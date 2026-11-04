"""Portable exact-reference helper and tiny-controller qualification only."""
import json
from verify_water_union_source_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import closed, load


def verify():
    result=previous()
    root,_=closed('water-references','build','v1',0)
    artifact=load(root/'result.json')
    assert artifact['artifactBytes']==2010336
    assert artifact['artifactSha256']=='a5608d9bdc25a3b431ee72a1f0181c63fe6919206f1a33cfb0000e22b3e11dfb'
    root,plan=closed('water-references','controls','v1',0)
    assert load(root/'controls.json')=={'tests':62,'successful':True,'failures':0,'errors':0,'skips':0}
    assert plan['artifact']['sha256']==artifact['artifactSha256']
    pipeline=stage('water-references-source-controls',True)
    assert pipeline['checks']=={'positivePipeline':True,'wrongSourceRejected':True,'nationalSourceMounted':False,
                               'memberWayUnionExact':True,'referenceBytesAndUniqueIdsExact':True,'producerBuffersReleasedBeforeAudit':True}
    tiny=pipeline['tiny']['water'];audit=pipeline['independentAudit']
    assert tiny['referenceCapture']['ways']==audit['allWayRecordsAndFieldsDecoded']==2
    assert tiny['referenceCapture']['references']==audit['allReferenceOccurrencesChecked']==4
    assert tiny['referenceCapture']['uniqueNodes']==audit['allUniqueNodeIdsIndependentlyCompared']==4
    assert not tiny['referenceStore']['coordinatesRetained'] and not audit['coordinatesOrRingsConstructed']
    return {**result,'waterReferenceLinuxControls':62,'waterReferenceTinyControllerAndIndependentAuditPassed':True,
            'waterNationalExactReferenceCaptureCompleted':False,'newUniqueClosedAllocationBytes':2894491648,'uniqueClosedRoots':127,
            'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
