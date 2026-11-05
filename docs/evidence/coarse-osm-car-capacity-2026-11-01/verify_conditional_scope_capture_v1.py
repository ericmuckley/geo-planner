"""Portable captured conditional-key prototype; no source/graph/PBF replay."""
import hashlib
import json
from verify_water_diagnosis_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous();controls=load(HERE/'conditional-scope-controls-v1.json')
    assert controls['tests']==8 and controls['successful'] and controls['failures']==0
    assert sha(HERE/controls['log'])==controls['logSha256']
    for name,pin in controls['bindings'].items():assert sha(REPO/name)==pin,name
    report=stage('conditional-scope-capture')
    assert report['status']=='captured_source_conditional_scope_census_complete'
    c=report['counts'];assert c['nodeMetadataClassified']==143560 and c['wayMetadataClassified']==28995
    assert c['capturedNodeRowsVisited']==1123919 and c['capturedWayRows']==239253
    assert c['nodeNewPositive']==0 and c['wayNewPositive']==1
    assert c['nodeOldPositiveRetained']==143479 and c['wayOldPositiveRetained']==28610
    assert c['selectedNodeBlockedBefore']==c['selectedNodeBlockedAfter']==81
    assert report['records']==1 and report['sourceStatBefore']==report['sourceStatAfter']
    assert report['sourceSha256']=='00788f4b0176fe4cea3708160e41740af5ec3b71411e683f0df21897b296a922'
    assert report['nodeCoordinatesProjected']==report['nationalSourcePbfReads']==report['routingQueries']==report['applicationDbReads']==report['providerRequests']==report['graphConstructors']==0
    assert not report['engineOrProductionChanged'] and not report['nativePrototypeParityQualified'] and not report['nationalImpactMeasured']
    assert report['conditionalKeyCounts']['way/maxspeed:conditional']==108
    portable=load(HERE/'conditional-scope-capture-records-v1.json')
    assert sha(HERE/portable['sourceClosed'])==portable['sourceClosedSha256']
    encoded=''.join(json.dumps(row,sort_keys=True,allow_nan=False)+'\n' for row in portable['records']).encode()
    assert len(encoded)==portable['rawBytes'] and hashlib.sha256(encoded).hexdigest()==portable['rawSha256']==report['recordsSha256']
    closed=load(HERE/'conditional-scope-capture-closed-v1.json')
    total=result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']
    assert total==5382766592
    return {**result,'conditionalScopeCapturedControls':8,'conditionalScopeCapturedNewEligibleWays':1,
            'conditionalScopeCapturedNewUnblockedNodes':0,'conditionalScopeCapturedSpeedTaggedWays':108,
            'conditionalScopeNationalOrNativeAccepted':False,'newUniqueClosedAllocationBytes':total,
            'uniqueClosedRoots':167,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
