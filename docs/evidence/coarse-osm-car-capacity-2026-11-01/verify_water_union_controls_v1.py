"""Portable qualified union counter/pipeline, preserving failed V1 controls."""
import json
from verify_water_closure_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, closed, load


def verify():
    result=previous()
    root,_=closed('water-union','build','v1',0)
    artifact=load(root/'result.json')
    assert artifact['artifactSha256']=='bd1673758a3e6eed23d304dd6765bc29adba87d4e05c09fea250d5db00380b1a'
    assert artifact['artifactBytes']==2007728
    root,_=closed('water-union','controls','v1',2)
    assert load(root/'controls.json')=={'tests':42,'successful':False,'failures':0,'errors':24,'skips':0}
    root,plan=closed('water-union','controls','v2',0)
    assert load(root/'controls.json')=={'tests':42,'successful':True,'failures':0,'errors':0,'skips':0}
    assert plan['artifact']['sha256']==artifact['artifactSha256']
    assert plan['mounts']['docs/evidence/coarse-osm-offline-plan-2026-10-26/proposal.json']=='/docs/evidence/coarse-osm-offline-plan-2026-10-26/proposal.json'
    pipeline=stage('water-union-source-controls',True)
    assert pipeline['checks']=={'positivePipeline':True,'wrongSourceRejected':True,'nationalSourceMounted':False,'memberWayUnionExact':True}
    assert pipeline['tiny']['water']['union']['requestedMemberWays']==3
    assert pipeline['tiny']['water']['union']['memberWaysFound']==2
    assert pipeline['tiny']['water']['missingMemberWayIds']==[5]
    return {**result,'waterUnionLinuxControls':42,'waterUnionNativeArtifactUnchangedAfterFixtureCorrection':True,
            'waterUnionTinyControllerPipelineAndWrongSourcePassed':True,'waterUnionNationalCensusCompleted':False,
            'newUniqueClosedAllocationBytes':2885619712,'uniqueClosedRoots':123,
            'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
