"""Portable routing controls and preserved stops; never execute a model or producer."""
import json
from verify_water_access_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def stopped(prefix,error):
    closed=load(HERE/f'{prefix}-closed-v1.json')
    assert closed['terminalRecord']=='failure.json'
    root=HERE/f'{prefix}-raw-v1'
    for name,pin in closed['roster'].items():
        assert not pin['ignoredLargeAsset']
        assert (root/name).stat().st_size==pin['bytes'] and sha(root/name)==pin['sha256']
    plan=load(root/'execution-plan.json')
    for name,pin in plan['bindings'].items():
        if name.startswith(('scripts/','routing/','docs/')): assert sha(REPO/name)==pin,name
    failure=load(root/'failure.json')
    assert failure['error']==error and failure['ownerExitCode']==143
    assert not failure['accuracyMeasured'] and not failure['modelOrProductionChanged']
    assert failure['completeDiagnosticDisplays']==failure['providerRequests']==0
    return closed['usage']['conservativeAllocatedBytes']


def verify():
    result=previous()
    total=result['newUniqueClosedAllocationBytes']
    for version,count in [(2,10),(3,18)]:
        controls=load(HERE/f'water-routing-controls-v{version}.json')
        assert controls['tests']==count and controls['failures']==0 and controls['strictTypesPassed']
        assert sha(HERE/controls['log'])==controls['logSha256']
        for name,pin in controls['bindings'].items(): assert sha(REPO/name)==pin,name
    total+=stopped('water-evaluation','controlled_stop_unindexed_display_fallback')
    total+=stopped('water-indexed-evaluation','controlled_stop_exhaustive_coarse_crossing_scan')
    assert total==5331419136
    return {**result,'waterRoutingIndexControls':18,'waterRoutingPerformanceStopsPreserved':2,
            'newUniqueClosedAllocationBytes':total,'uniqueClosedRoots':158,
            'waterRoutingQueriesMeasured':False,'accuracyOrAppAccepted':False}


if __name__=='__main__': print(json.dumps(verify()))
