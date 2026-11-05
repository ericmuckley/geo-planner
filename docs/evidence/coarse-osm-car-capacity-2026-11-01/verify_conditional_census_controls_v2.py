"""Versioned access-time correction and retained pre-audit source checkpoint."""
import json
from verify_conditional_source_stop_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load,sha


def verify():
    result=previous();review=load(HERE/'conditional-source-audit-correction-v2.json')
    assert sha(HERE/review['failureClosed'])==review['failureClosedSha256']
    report=stage('conditional-source-controls-v2',True)
    assert report['checks']=={'positivePipeline':True,'wrongSourceRejected':True,'nationalSourceMounted':False,'independentChangedTagAudit':True,'auditUnitTests':7}
    root=HERE/'conditional-source-controls-v2-raw-v1'
    assert load(root/'audit-controls.json')=={'tests':7,'successful':True,'failures':0,'errors':0,'skips':0}
    checkpoint=load(root/'source-census.json');tiny=report['tiny']
    assert checkpoint['receipt']==tiny['receipt'] and checkpoint['conditional']==tiny['conditional']
    assert tiny['receipt']['nativeEof'] and tiny['conditional']['changedRecords']==2 and tiny['conditional']['complete']==1
    allocation=result['newUniqueClosedAllocationBytes']+load(HERE/'conditional-source-controls-v2-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert allocation==5414400000
    return {**result,'conditionalCensusAuditControls':7,'conditionalCensusAccessTimeAndReceiptCorrectionQualified':True,
            'conditionalNationalMetadataMeasured':False,'uniqueClosedRoots':178,'newUniqueClosedAllocationBytes':allocation,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
