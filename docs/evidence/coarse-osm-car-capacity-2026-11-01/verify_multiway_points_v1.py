"""Portable all83 point-only result and fresh-ID access proof; no map admission."""
import json

from verify_multiway_context_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous();access=stage('multiway-access',False)
    assert access['inputs']==access['newEndpointCollections']==access['supported']==79
    assert access['reusedEndpointCollections']==access['unsupported']==access['maskOmissionAllowanceInputs']==0
    assert access['totalConnections']==10338 and access['maximumConnections']==1840
    assert access['originalSupportedInputsRetained']==78
    report=stage('multiway-points',False)
    assert report['status']=='all83_multiway_primary_finish_context_feasibility_complete'
    assert report['originalCases']==83 and report['valhallaCases']==35
    assert len(report['phases'])==21 and len(report['comparisons'])==len(report['rows'])==83
    assert report['roadArrivalRegressions']==0 and report['roadFinishesImproved']==17 and report['changedPointTimes']==16
    assert report['contextStates']==34101 and report['contextDataBackingBytes']==1784491
    assert report['maximumQueryBackingBytes']==51006374 < 67108864
    assert report['heldCoreGeometryContextsBackingBytes']==144055087
    assert report['afterLoad']['arrayBuffers']==report['afterQueries']['arrayBuffers']==144138687
    old=load(HERE/'absent-entry-evaluation-raw-v1/report.json')
    old_rows={r['id']:r for r in old['rows']}
    timings={key:value for p in old['phases'] for key,value in p['diagnostic']['timings'].items()}
    new_rows={r['id']:r for r in report['rows']}
    assert old_rows.keys()==new_rows.keys()==timings.keys()
    for row in report['comparisons']:
        key=row['id'];saved=timings[key]
        assert row['previousRoadTicks']==saved['roadTicks'] and row['previousPointTicks']==saved['ticks']
        assert row['frozenLocalGridTicks']==saved['localGridTicks']
        point=min(v for v in (row['bestRoadTicks'],saved['localGridTicks']) if v is not None)
        assert row['pointTicks']==point and new_rows[key]['candidate']['pointMinutes']==point/480
        assert new_rows[key]['baseline']==old_rows[key]['baseline']
        assert new_rows[key]['candidate']['predictedReachable']==old_rows[key]['candidate']['predictedReachable']==row['frozenPublicShaded']
        for name in ('origin','destination','referenceMinutes','valhallaMinutes','budgetMinutes','set'):
            assert new_rows[key][name]==old_rows[key][name]
    assert report['overall']['candidate']['pairedFinite']==83
    assert report['overall']['candidate']['meanAbsoluteMinutes']==36.51196787148596
    assert not report['candidateAdmitted'] and not report['numericalGatesPassed'] and report['providerRequests']==0
    total=result['newUniqueClosedAllocationBytes']
    for name in ('multiway-access','multiway-points'):
        total+=load(HERE/f'{name}-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total==7370608640
    return {**result,'multiViaAll79NewIdAccessCollectionsChecked':True,
            'multiViaAll83PointOnlyComparisonsComplete':True,
            'multiViaPointOnlyProxyMaeMinutes':36.51196787148596,
            'multiViaMapsRerendered':False,
            'uniqueClosedRoots':256,'newUniqueClosedAllocationBytes':total,
            'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
