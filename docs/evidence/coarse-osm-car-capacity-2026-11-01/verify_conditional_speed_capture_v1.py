"""Portable complete conditional-speed capture proof, no producer replay."""
import hashlib
import json
from verify_conditional_scope_capture_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous();controls=load(HERE/'conditional-speed-controls-v1.json')
    assert controls['tests']==17 and controls['successful'] and controls['failures']==0
    assert sha(HERE/controls['log'])==controls['logSha256']
    for name,pin in controls['bindings'].items():assert sha(REPO/name)==pin,name
    report=stage('conditional-speed-capture');c=report['counts']
    assert report['status']=='captured_source_conditional_speed_census_complete'
    assert c['nodeMetadataClassified']==143560 and c['wayMetadataClassified']==28995
    assert c['capturedNodeRowsVisited']==1123919 and c['capturedWayRows']==239253
    assert c['nodeNewPositive']==0 and c['wayNewPositive']==108 and c['wayStaticSpeedPriced']==107
    assert c['waySpeedUnsupported']==1 and c['wayWithConditionalCandidates']==109
    assert c['nodeOldPositiveRetained']==143479 and c['wayOldPositiveRetained']==28610
    assert c['selectedNodeBlockedBefore']==c['selectedNodeBlockedAfter']==81
    assert report['records']==109 and report['sourceStatBefore']==report['sourceStatAfter']
    assert report['sourceSha256']=='00788f4b0176fe4cea3708160e41740af5ec3b71411e683f0df21897b296a922'
    for key in ('nodeCoordinatesProjected','nationalSourcePbfReads','routingQueries','applicationDbReads','providerRequests','graphConstructors'):assert report[key]==0
    assert not report['engineOrProductionChanged'] and not report['nativePrototypeParityQualified'] and not report['nationalImpactMeasured']
    portable=load(HERE/'conditional-speed-capture-records-v1.json')
    assert sha(HERE/portable['sourceClosed'])==portable['sourceClosedSha256']
    encoded=''.join(json.dumps(row,sort_keys=True,allow_nan=False)+'\n' for row in portable['records']).encode()
    assert len(encoded)==portable['rawBytes'] and hashlib.sha256(encoded).hexdigest()==portable['rawSha256']==report['recordsSha256']
    records=portable['records'];assert len(records)==109
    speed=[r for r in records if r['conditionalSpeedStatus']=='static-minimum']
    assert len(speed)==107 and all(r['eligibilityGained'] for r in speed)
    assert sum(r['eligibilityGained'] for r in records)==108
    assert sum(r['conditionalSpeedStatus']=='unsupported' for r in records)==1
    for row in speed:
        for direction in ('forward','backward'):
            value=row['after'][direction]
            if value is not None:assert value>0 and value<=160
    closed=load(HERE/'conditional-speed-capture-closed-v1.json')
    total=result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']
    assert total==5383995392
    return {**result,'conditionalSpeedCapturedControls':17,'conditionalSpeedCapturedStaticPricedWays':107,
            'conditionalSpeedCapturedCombinedNewEligibleWays':108,'conditionalSpeedNativeOrNationalAccepted':False,
            'uniqueClosedRoots':168,'newUniqueClosedAllocationBytes':total,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
