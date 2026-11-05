"""Portable country-certificate controls/profile/stops; no producer or graph replay."""
import json
from verify_water_mask_cpu_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous();controls=load(HERE/'water-routing-controls-v6.json')
    assert controls['tests']==20 and controls['failures']==0 and controls['strictTypesPassed']
    assert controls['extraQueryBitplaneBytesAtMaximum']==312500 and controls['queryCapBytes']==67108864
    assert sha(HERE/controls['log'])==controls['logSha256']
    for name,pin in controls['bindings'].items():assert sha(REPO/name)==pin,name
    profile=stage('water-mask-country-profile')
    assert profile['status']=='national_frame_mask_country_certificate_equal' and len(profile['rows'])==2
    assert profile['retainedArrayBuffers']==profile['afterQueriesArrayBuffers']==15855121
    assert profile['baselineArrayBuffers']==profile['releasedArrayBuffers']==73757
    assert profile['roadQueries']==profile['sourcePbfReads']==profile['providerRequests']==0 and not profile['modelOrProductionChanged']
    original=load(HERE/'water-mask-index-profile-raw-v1/report.json')['rows']
    for row,old in zip(profile['rows'],original):
        assert row['before']['fingerprints']==row['after']['fingerprints']==old['before']['fingerprints']
        cells=row['frame']['width']*row['frame']['height']
        assert row['after']['backingBytes']==row['before']['backingBytes']+(cells+7)//8
    stopped=load(HERE/'water-fast-evaluation-closed-v1.json');root=HERE/'water-fast-evaluation-raw-v1'
    assert stopped['terminalRecord']=='failure.json'
    for name,pin in stopped['roster'].items():
        if not pin['ignoredLargeAsset']:assert (root/name).stat().st_size==pin['bytes'] and sha(root/name)==pin['sha256']
    for name,pin in load(root/'execution-plan.json')['bindings'].items():
        if name.startswith(('scripts/','routing/','docs/')):assert sha(REPO/name)==pin,name
    failure=load(root/'failure.json')
    assert failure['error']=='controlled_stop_redundant_country_checks' and failure['ownerExitCode']==143
    assert failure['completedOriginGroups']==failure['completedDiagnosticDisplays']==6
    assert failure['completedOriginPointTimings']==36 and failure['savedDisplayFiles']==24
    assert not failure['fullAccuracyMeasured'] and not failure['modelOrProductionChanged'] and failure['providerRequests']==0
    for i in range(1,7):
        phase=load(root/f'origin-{i:02}.json')
        assert len(phase['diagnostic']['timings'])==6 and all(row['ticks'] is not None for row in phase['diagnostic']['timings'].values())
    closed=load(HERE/'water-mask-country-profile-closed-v1.json')
    total=result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']+stopped['usage']['conservativeAllocatedBytes']
    assert total==5351587840
    return {**result,'waterCountryCertificateControls':20,'waterCountryCertificateNationalMasksEqual':2,
            'waterQueryAdditionalBitplaneBytesMaximum':312500,'waterRoutingPerformanceStopsPreserved':4,
            'waterPartialV4OriginGroups':6,'waterPartialV4FinitePointTimings':36,
            'newUniqueClosedAllocationBytes':total,'uniqueClosedRoots':163,
            'waterFullAccuracyMeasured':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
