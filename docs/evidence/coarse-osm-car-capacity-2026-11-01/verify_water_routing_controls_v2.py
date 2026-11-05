"""Portable guarded-lookup controls and preserved partial run; no producer replay."""
import json
from verify_water_routing_controls_v1 import verify as previous
from verify_preparation_v1 import HERE,REPO,load,sha


def verify():
    result=previous()
    controls=load(HERE/'water-routing-controls-v4.json')
    assert controls['tests']==19 and controls['failures']==0 and controls['strictTypesPassed']
    assert controls['exactCellComparisons']==49409 and controls['explicitFastAndExactBranchControls']==2
    assert sha(HERE/controls['log'])==controls['logSha256']
    for name,pin in controls['bindings'].items(): assert sha(REPO/name)==pin,name
    closed=load(HERE/'water-latitude-evaluation-closed-v1.json')
    root=HERE/'water-latitude-evaluation-raw-v1'
    assert closed['terminalRecord']=='failure.json'
    for name,pin in closed['roster'].items():
        if not pin['ignoredLargeAsset']: assert (root/name).stat().st_size==pin['bytes'] and sha(root/name)==pin['sha256']
    plan=load(root/'execution-plan.json')
    for name,pin in plan['bindings'].items():
        if name.startswith(('scripts/','routing/','docs/')): assert sha(REPO/name)==pin,name
    failure=load(root/'failure.json')
    assert failure['error']=='controlled_stop_decimal_lookup_overhead' and failure['ownerExitCode']==143
    assert failure['completedOriginGroups']==2 and failure['completedOriginPointTimings']==12
    assert failure['savedDisplayFiles']==10 and failure['completedDiagnosticDisplays']==3
    assert failure['providerRequests']==0 and not failure['fullAccuracyMeasured'] and not failure['modelOrProductionChanged']
    origins=[load(root/f'origin-{i:02}.json') for i in (1,2)]
    old=load(HERE/'entry-evaluation-raw-v1/report.json')
    timings={key:row for phase in old['phases'] if 'diagnostic' in phase for key,row in phase['diagnostic']['timings'].items()}
    for origin in origins:
        for key,row in origin['diagnostic']['timings'].items(): assert row['ticks']==timings[key]['ticks']
    total=result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']
    assert total==5336391680
    return {**result,'waterRoutingIndexControls':19,'waterExactCellFlagComparisons':49409,
            'waterRoutingPerformanceStopsPreserved':3,'waterPartialOriginGroups':2,
            'waterPartialUnchangedPointTimings':12,'waterPartialSavedDisplays':10,
            'newUniqueClosedAllocationBytes':total,'uniqueClosedRoots':159,
            'waterRoutingQueriesMeasured':True,'waterFullAccuracyMeasured':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
