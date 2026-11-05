"""Portable compiled conditional-policy parity; no source/native replay."""
import json
from verify_conditional_speed_capture_v1 import verify as previous
from verify_preparation_v1 import HERE,REPO,closed,load,sha


def verify():
    result=previous();allocation=result['newUniqueClosedAllocationBytes']
    stop=load(HERE/'car-closed-build-v3.json');raw=HERE/'car-raw/build-v3'
    for name,pin in stop['roster'].items():
        assert not pin['ignoredLargeAsset'] and (raw/name).stat().st_size==pin['bytes'] and sha(raw/name)==pin['sha256']
    assert load(raw/'container-result.json')['workerNeverCreated']
    assert load(raw/'run-summary.json')['exitCode']==2 and load(raw/'cleanup.json')['independentInspectAbsent']
    assert load(HERE/'car-cleanup-build-v3.json')['independentlyAbsent']
    allocation+=stop['usage']['conservativeAllocatedBytes']
    for stage in ('build','controls','equivalence'):
        root,plan=closed('car',stage,'v4',0)
        assert plan['caps']['overallRetainedBytes']==72*1024**3 and plan['tests']==25
        if stage=='build':
            artifact=load(root/'result.json')
            assert artifact['artifactSha256']=='e26548e67da721e35de0a6f1d7f329b8a7237d04c490aeadc13793b99c9ca231' and artifact['artifactBytes']==1731272
        elif stage=='controls':assert load(root/'controls.json')=={'tests':25,'successful':True,'failures':0,'errors':0,'skips':0}
        else:
            matched=load(root/'result.json')
            assert [matched[k] for k in ('selectedNodes','majorWays','relations','sourceWaysExamined','sourceNodeIdsVisited')]==[143560,28995,4900,239253,1123919]
            assert matched['sourceStatBefore']==matched['sourceStatAfter']
            assert matched['sourceSha256']=='00788f4b0176fe4cea3708160e41740af5ec3b71411e683f0df21897b296a922'
            assert matched['invalidSourceRecordsRetainedAndCompared']==2
            assert matched['nodeCoordinatesProjected']==matched['sourcePbfReads']==matched['networkRequests']==matched['applicationDbReads']==0
            assert not matched['policyV3QualifiedOnCountry'] and not matched['etaQualified'] and not matched['modelChanged']
        allocation+=load(HERE/f'car-closed-{stage}-v4.json')['usage']['conservativeAllocatedBytes']
    assert allocation==5392412672
    return {**result,'conditionalNativeLinuxControls':25,'conditionalNativeCapturedMetadataRowsMatched':177455,
            'conditionalNativePreservedSandboxStop':True,'conditionalNativeNationalOrEtaAccepted':False,
            'uniqueClosedRoots':172,'newUniqueClosedAllocationBytes':allocation,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
