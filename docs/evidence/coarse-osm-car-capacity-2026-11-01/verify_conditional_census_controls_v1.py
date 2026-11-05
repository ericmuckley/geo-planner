"""Portable metadata helper and tiny controller admission; no source replay."""
import json
from verify_conditional_graph_capture_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,closed,load


def verify():
    result=previous();allocation=result['newUniqueClosedAllocationBytes']
    for operation in ('build','controls'):
        root,plan=closed('conditional-census',operation,'v1',0)
        assert plan['tests']==38 and plan['caps']['overallRetainedBytes']==72*1024**3
        if operation=='build':
            a=load(root/'result.json');assert a['artifactBytes']==2010960 and a['artifactSha256']=='9fe3d294c6ecf2efce8c2ad9688a775753cb2da1947827bb198328c4f84823fa'
        else:assert load(root/'controls.json')=={'tests':38,'successful':True,'failures':0,'errors':0,'skips':0}
        allocation+=load(HERE/f'conditional-census-closed-{operation}-v1.json')['usage']['conservativeAllocatedBytes']
    report=stage('conditional-source-controls',True)
    assert report['status']=='conditional_source_controller_pipeline_passed'
    assert report['checks']=={'positivePipeline':True,'wrongSourceRejected':True,'nationalSourceMounted':False,'independentChangedTagAudit':True,'auditUnitTests':4}
    assert load(HERE/'conditional-source-controls-raw-v1/audit-controls.json')=={'tests':4,'successful':True,'failures':0,'errors':0,'skips':0}
    tiny=report['tiny'];c=tiny['conditional'];assert c['newlyEligibleWays']==c['changedNodeFlags']==1 and c['changedRecords']==2
    assert tiny['receipt']['nativeEof'] and tiny['receipt']['pythonProjectionFrames']==0
    assert tiny['receipt']['counts']=={'node':4,'way':3,'relation':2}
    assert tiny['independentChangedTagAudit']['counts']['nodes']==tiny['independentChangedTagAudit']['counts']['ways']==1
    allocation+=load(HERE/'conditional-source-controls-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert allocation==5403676672
    return {**result,'conditionalCensusLinuxControls':38,'conditionalCensusAuditControls':4,
            'conditionalCensusTinyPipelineQualified':True,'conditionalNationalMetadataMeasured':False,
            'uniqueClosedRoots':176,'newUniqueClosedAllocationBytes':allocation,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
