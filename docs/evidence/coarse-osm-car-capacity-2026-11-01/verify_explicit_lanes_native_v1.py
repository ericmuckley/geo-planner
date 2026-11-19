"""Small-record native lane qualification proof; never executes producers."""
import json

from verify_multiway_diagnosis_and_lanes_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result=previous();total=result['newUniqueClosedAllocationBytes']
    reports={}
    for stage in ('build','controls','equivalence'):
        closed=load(HERE/f'explicit-lanes-native-closed-{stage}-v1.json')
        root=HERE/'explicit-lanes-native-raw'/f'{stage}-v1'
        for name,pin in closed['roster'].items():
            if not pin['ignoredLargeAsset']:
                assert (root/name).stat().st_size==pin['bytes'] and sha(root/name)==pin['sha256']
        plan=load(root/'execution-plan.json')
        assert plan['stage']==stage and plan['phase']=='native_car_explicit_lanes_v1'
        assert plan['policy']['id']=='static-car-explicit-ordinary-lane-prototype-v1' and plan['tests']==28
        for name,pin in plan['inputs'].items():
            if name.startswith(('scripts/','routing/','docs/')):assert sha(REPO/name)==pin,name
        assert load(root/'run-summary.json')['exitCode']==0
        assert load(root/'cleanup.json')['removed'] and load(root/'cleanup.json')['independentInspectAbsent']
        assert load(HERE/f'explicit-lanes-native-cleanup-{stage}-v1.json')['independentlyAbsent']
        final=load(root/'container-result.json')
        assert final['State']['ExitCode']==final['clientExitCode']==0 and not final['State']['OOMKilled']
        host=load(root/'container-initial.json')['HostConfig']
        assert host['NetworkMode']=='none' and host['Memory']==host['MemorySwap']==4294967296
        assert host['ReadonlyRootfs'] and host['NanoCpus']==2000000000 and host['PidsLimit']==64
        metrics=load(root/'metrics.json')
        assert int(metrics['memory.peak'])<=4294967296 and metrics['memory.swap.max']=='0'
        assert 'oom 0\n' in metrics['memory.events'] and 'oom_kill 0\n' in metrics['memory.events']
        reports[stage]=load(root/'result.json');total+=closed['usage']['conservativeAllocatedBytes']
    build=reports['build']
    assert build['artifactSha256']=='01d1b8fab64d16d7993f907a743410f845d71885d75c18674121343edc3c6979'
    assert build['artifactBytes']==1731736
    tested=reports['controls']
    assert {key:tested[key] for key in ('tests','successful','failures','errors','skips')}=={'tests':28,'successful':True,'failures':0,'errors':0,'skips':0}
    parity=reports['equivalence']
    assert parity['status']=='passed_complete_captured_metadata_native_policy_equivalence'
    assert (parity['selectedNodes'],parity['majorWays'],parity['relations'])==(143560,28995,4900)
    assert (parity['sourceWaysExamined'],parity['sourceNodeIdsVisited'])==(239253,1123919)
    assert parity['sourceStatBefore']==parity['sourceStatAfter']
    assert parity['sourceSha256']=='00788f4b0176fe4cea3708160e41740af5ec3b71411e683f0df21897b296a922'
    assert parity['nodeCoordinatesProjected']==parity['sourcePbfReads']==parity['networkRequests']==parity['applicationDbReads']==0
    assert not parity['nationalArtifactBuilt'] and not parity['etaQualified'] and not parity['vercelQualified'] and not parity['modelChanged']
    # These copied labels describe comparison to the new frozen Python reference,
    # not unchanged eligibility versus the old policy. The separate captured
    # comparison records exactly 28 intentional lane-eligibility changes.
    assert parity['existingCapturedDecisionsUnchanged'] and not parity['policyV3QualifiedOnCountry']
    assert load(HERE/'explicit-lanes-capture-raw-v1/report.json')['counts']['newEligible']==28
    assert total==7391420416
    assert 64500000000+total+104857600+3*67108864+268435456<72*1024**3
    return {**result,'nativeLaneActualLinuxControls':28,'nativeLaneCompleteCapturedPolicyParity':True,
            'nativeLaneNationalQualified':False,'uniqueClosedRoots':265,
            'newUniqueClosedAllocationBytes':total,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
