"""Portable lane consumer/tiny-PBF qualification; no national producer replay."""
import json

from verify_entry_runtime_v1 import stage
from verify_explicit_lanes_native_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result=previous();total=result['newUniqueClosedAllocationBytes']
    for operation in ('build','controls'):
        closed=load(HERE/f'explicit-lane-census-closed-{operation}-v1.json')
        root=HERE/'explicit-lane-census-raw'/f'{operation}-v1'
        for name,pin in closed['roster'].items():
            if not pin['ignoredLargeAsset']:
                assert (root/name).stat().st_size==pin['bytes'] and sha(root/name)==pin['sha256']
        plan=load(root/'execution-plan.json')
        assert plan['stage']==operation and plan['phase']=='explicit_lane_census_qualification_v1' and plan['tests']==43
        for name,pin in plan['inputs'].items():
            if name.startswith(('scripts/','routing/','docs/')):assert sha(REPO/name)==pin,name
        assert load(root/'run-summary.json')['exitCode']==0
        final=load(root/'container-result.json')
        assert final['State']['ExitCode']==final['clientExitCode']==0 and not final['State']['OOMKilled']
        assert load(root/'cleanup.json')['independentInspectAbsent']
        assert load(HERE/f'explicit-lane-census-cleanup-{operation}-v1.json')['independentlyAbsent']
        host=load(root/'container-initial.json')['HostConfig']
        assert host['NetworkMode']=='none' and host['Memory']==host['MemorySwap']==4294967296
        assert host['ReadonlyRootfs'] and host['NanoCpus']==2000000000 and host['PidsLimit']==64
        metrics=load(root/'metrics.json')
        assert int(metrics['memory.peak'])<=4294967296 and metrics['memory.swap.max']=='0'
        assert 'oom 0\n' in metrics['memory.events'] and 'oom_kill 0\n' in metrics['memory.events']
        report=load(root/'result.json')
        if operation=='build':
            assert report['artifactBytes']==2011336
            assert report['artifactSha256']=='b0efa1cc0f0f34a599f37d10e9585d57cc71d71bc830bd75010b83da9132a01a'
        else:
            assert {key:report[key] for key in ('tests','successful','failures','errors','skips')}=={'tests':43,'successful':True,'failures':0,'errors':0,'skips':0}
        total+=closed['usage']['conservativeAllocatedBytes']
    pipeline=stage('explicit-lane-source-controls-v1',True)
    assert pipeline['status']=='explicit_lane_source_controller_pipeline_passed'
    assert pipeline['checks']=={'positivePipeline':True,'wrongSourceRejected':True,'nationalSourceMounted':False,'independentChangedTagAudit':True,'auditUnitTests':6}
    tiny=pipeline['tiny'];receipt=tiny['receipt'];c=tiny['explicitLanes']
    assert receipt['nativeEof'] and receipt['counts']=={'node':4,'way':3,'relation':2} and receipt['pythonProjectionFrames']==0
    assert c['newlyEligibleWays']==tiny['independentChangedTagAudit']['counts']['ways']==1
    assert c['changedNodeFlags']==0 and c['allNodeFlagsExact']==4
    total+=load(HERE/'explicit-lane-source-controls-v1-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total==7399342080
    assert 64500000000+total+104857600+67108864+268435456<72*1024**3
    return {**result,'laneCensusActualLinuxControls':43,'laneTinyPbfAndWrongSourcePipelinePassed':True,
            'laneNationalMetadataCompleted':False,'uniqueClosedRoots':268,
            'newUniqueClosedAllocationBytes':total,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
